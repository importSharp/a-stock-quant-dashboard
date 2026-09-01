from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.intraday_skill_analysis import tencent_quotes


def _batch_quotes(codes: list[str], batch_size: int = 80) -> dict[str, dict[str, Any]]:
    quotes: dict[str, dict[str, Any]] = {}
    for start in range(0, len(codes), batch_size):
        quotes.update(tencent_quotes(codes[start : start + batch_size]))
    return quotes


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _round(value: float) -> float:
    return round(value, 2)


def main() -> int:
    dashboard_path = ROOT / "web" / "public" / "data" / "dashboard.json"
    dashboard = json.loads(dashboard_path.read_text(encoding="utf-8"))
    stock_pool = dashboard.get("stockPool") or []
    meta = {
        row["code"]: {
            "industry": row.get("industry") or "其他",
            "historyScore": float(row.get("score") or 0),
        }
        for row in stock_pool
        if row.get("code")
    }
    quotes = _batch_quotes(list(meta))

    sector_rows: dict[str, list[float]] = defaultdict(list)
    for code, quote in quotes.items():
        if code not in meta:
            continue
        pct = float(quote.get("change_pct") or 0)
        if -11 < pct < 11:
            sector_rows[meta[code]["industry"]].append(pct)

    sector_stats: dict[str, dict[str, float]] = {}
    for industry, changes in sector_rows.items():
        if not changes:
            continue
        sector_stats[industry] = {
            "change": sum(changes) / len(changes),
            "breadth": sum(value > 0 for value in changes) / len(changes) * 100,
            "count": float(len(changes)),
        }

    first_attack: list[dict[str, Any]] = []
    reseal: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for code, quote in quotes.items():
        name = str(quote.get("name") or "")
        price = float(quote.get("price") or 0)
        previous = float(quote.get("last_close") or 0)
        open_price = float(quote.get("open") or 0)
        high = float(quote.get("high") or 0)
        limit_up = float(quote.get("limit_up") or 0)
        pct = float(quote.get("change_pct") or 0)
        amount_yi = float(quote.get("amount_wan") or 0) / 10000
        turnover = float(quote.get("turnover_pct") or 0)
        volume_ratio = float(quote.get("vol_ratio") or 0)
        market_cap = float(quote.get("mcap_yi") or 0)
        if (
            not price
            or price > 35
            or not previous
            or not open_price
            or "ST" in name.upper()
            or "退" in name
            or not code.startswith(("000", "001", "002", "003", "600", "601", "603", "605"))
        ):
            continue

        industry = meta.get(code, {}).get("industry", "其他")
        sector = sector_stats.get(industry, {"change": 0.0, "breadth": 0.0, "count": 0.0})
        gap = (open_price / previous - 1) * 100
        hold = (price / open_price - 1) * 100
        distance = (limit_up / price - 1) * 100 if limit_up else 99
        touched = bool(limit_up and high >= limit_up - 0.001)
        sector_score = _clamp(sector["change"] * 7, 0, 18) + _clamp((sector["breadth"] - 45) / 3, 0, 12)
        base = {
            "code": code,
            "name": name,
            "industry": industry,
            "price": _round(price),
            "pct": _round(pct),
            "auctionGap": _round(gap),
            "vsOpen": _round(hold),
            "distanceToLimit": _round(distance),
            "amountYi": _round(amount_yi),
            "turnover": _round(turnover),
            "volumeRatio": _round(volume_ratio),
            "limitPrice": _round(limit_up),
            "sectorChange": _round(sector["change"]),
            "sectorBreadth": _round(sector["breadth"]),
        }

        if (
            not touched
            and 1.5 <= pct < 9.75
            and 0.8 <= gap <= 8.8
            and hold >= -1.5
            and distance <= 8
            and amount_yi >= 0.25
            and volume_ratio >= 1.2
        ):
            score = (
                22
                + sector_score
                + _clamp((pct - 1.5) * 2.8, 0, 20)
                + _clamp((8 - distance) * 1.6, 0, 12)
                + _clamp((hold + 1.5) * 2.2, 0, 11)
                + _clamp(math.log10(amount_yi + 1) * 7, 0, 7)
                + _clamp(volume_ratio / 4, 0, 5)
                + (5 if 15 <= market_cap <= 80 else 2 if market_cap <= 150 else 0)
            )
            first_attack.append(
                {
                    **base,
                    "score": round(score, 1),
                    "trigger": f"放量突破{high:.2f}并维持开盘价{open_price:.2f}上方",
                    "invalidate": f"跌破{open_price:.2f}且板块宽度回落",
                }
            )
        elif touched and price < limit_up and pct >= 4 and distance <= 5 and hold >= -4:
            score = 45 + sector_score + _clamp((5 - distance) * 5, 0, 25) + _clamp(volume_ratio / 3, 0, 8)
            reseal.append(
                {
                    **base,
                    "score": round(score, 1),
                    "trigger": f"重新站上{max(price, limit_up * 0.99):.2f}并出现回封买单",
                    "invalidate": f"距涨停扩大至5%以上或跌破开盘价{open_price:.2f}",
                }
            )
        elif touched or (gap >= 4 and hold <= -2.5):
            rejected.append(
                {
                    **base,
                    "score": 0,
                    "trigger": "不参与，等待重新转强",
                    "invalidate": "高开低走或炸板回落",
                }
            )

    first_attack.sort(key=lambda row: row["score"], reverse=True)
    reseal.sort(key=lambda row: row["score"], reverse=True)
    rejected.sort(key=lambda row: (row["pct"], row["amountYi"]), reverse=True)
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    payload = {
        "asOf": now,
        "market": "沪深主板 · 非ST · 35元以下",
        "mode": "竞价后动态扫描",
        "refreshSeconds": 15,
        "firstAttack": first_attack[:10],
        "reseal": reseal[:10],
        "rejected": rejected[:10],
        "sectorLeaders": sorted(
            (
                {"name": name, **{key: _round(value) for key, value in values.items()}}
                for name, values in sector_stats.items()
                if values["count"] >= 3
            ),
            key=lambda row: (row["change"], row["breadth"]),
            reverse=True,
        )[:8],
        "rules": {
            "firstAttack": "尚未触板；竞价高开0.8%-8.8%；守住开盘价；距涨停不超过8%；量比和成交额达标",
            "reseal": "已经触板后打开；距涨停不超过5%；分时未明显破位",
            "warning": "模型分是排序分，不是经过样本外校准的涨停概率",
        },
    }
    output = ROOT / "web" / "public" / "data" / "auction-mobile.json"
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output)
    print(f"首次冲板 {len(first_attack)} · 回封 {len(reseal)} · 淘汰 {len(rejected)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
