"""Pure, explainable 09:35 daily-pick selection and persistence."""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import datetime, time
import json
from pathlib import Path
import re
from typing import Any


MAIN_BOARD = re.compile(r"(?:000|001|002|003|600|601|603|605)\d{3}$")
REQUIRED_LABELS = {
    "hotQuotes": "热点股实时行情",
    "pools": "涨停/炸板池",
}


def _number(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
        return result if result == result else default
    except (TypeError, ValueError):
        return default


def market_phase(now: datetime) -> str:
    if now.weekday() >= 5:
        return "market_closed"
    clock = now.timetz().replace(tzinfo=None)
    if clock < time(9, 35):
        return "waiting"
    if clock < time(9, 40):
        return "generation"
    return "missed"


def _status(snapshot: dict[str, Any], key: str) -> str:
    for item in snapshot.get("endpointStatus") or []:
        if item.get("key") == key:
            return str(item.get("status") or "error")
    return "missing"


def source_errors(snapshot: dict[str, Any]) -> list[str]:
    errors = [label for key, label in REQUIRED_LABELS.items() if _status(snapshot, key) != "ok"]
    sector_ok = any(_status(snapshot, key) == "ok" for key in ("industryStrength", "industryFallback"))
    has_themes = bool(snapshot.get("themeCandidates"))
    if not sector_ok and not has_themes:
        errors.append("板块或题材归因")
    return errors


def is_untouched_limit_candidate(row: dict[str, Any], blocked: set[str] | None = None) -> bool:
    """Return true only when the stock is still tradable and has never touched limit-up today."""
    code = str(row.get("code") or "")
    price = _number(row.get("price"))
    high = _number(row.get("high"))
    limit_up = _number(row.get("limit_up"))
    if code in (blocked or set()) or price <= 0 or high <= 0 or limit_up <= 0:
        return False
    distance = (limit_up / price - 1.0) * 100
    return price < limit_up - 0.001 and high < limit_up - 0.001 and 0 < distance <= 8.0


def _eligible(row: dict[str, Any], blocked: set[str]) -> bool:
    code = str(row.get("code") or "")
    name = str(row.get("name") or "")
    price = _number(row.get("price"))
    pct = _number(row.get("pct", row.get("change_pct")))
    open_price = _number(row.get("open"), price)
    return bool(
        MAIN_BOARD.fullmatch(code)
        and "ST" not in name.upper()
        and "退" not in name
        and is_untouched_limit_candidate(row, blocked)
        and 0 < price <= 35
        and 1.0 <= pct <= 7.5
        and _number(row.get("vol_ratio")) >= 1.2
        and 0.15 <= _number(row.get("turnover", row.get("turnover_pct"))) <= 15
        and _number(row.get("amount_yi", _number(row.get("amount_wan")) / 10000)) >= 0.2
        and open_price > 0
        and price >= open_price * 0.985
    )


def _score(row: dict[str, Any], sector_rank: int, resonance: int, break_rate: float) -> tuple[float, dict[str, float]]:
    if "base_score" in row:
        total = _number(row["base_score"])
        return total, {"板块": round(total * .30, 1), "开盘": round(total * .25, 1), "量能": round(total * .20, 1), "共振": round(total * .15, 1), "风控": round(total * .10, 1)}
    pct = _number(row.get("pct", row.get("change_pct")))
    price = _number(row.get("price"))
    open_price = _number(row.get("open"), price)
    vol_ratio = _number(row.get("vol_ratio"))
    turnover = _number(row.get("turnover", row.get("turnover_pct")))
    amount = _number(row.get("amount_yi", _number(row.get("amount_wan")) / 10000))
    main_pct = max(0.0, _number(row.get("main_pct")))
    sector = max(8.0, 30.0 - sector_rank * 3.0) + min(main_pct / 15.0, 1.0) * 3.0
    sweet_spot = max(0.0, 1.0 - abs(pct - 4.0) / 4.0)
    retention = max(0.0, min((price / open_price - 0.985) / 0.035, 1.0))
    opening = sweet_spot * 15.0 + retention * 10.0
    volume = min(max(vol_ratio - 1.0, 0) / 2.5, 1.0) * 8.0 + max(0.0, 1.0 - abs(turnover - 4.0) / 8.0) * 6.0 + min(amount / 5.0, 1.0) * 6.0
    theme = min(resonance / 3.0, 1.0) * 15.0
    risk = max(0.0, 10.0 - max(pct - 6.0, 0) * 3.0 - max(break_rate - 35.0, 0) * .12)
    breakdown = {"板块": round(min(sector, 30), 1), "开盘": round(opening, 1), "量能": round(volume, 1), "共振": round(theme, 1), "风控": round(risk, 1)}
    return round(sum(breakdown.values()), 1), breakdown


def rank_candidates(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    if snapshot.get("rankedCandidates") is not None:
        rows = [dict(item) for item in snapshot.get("rankedCandidates") or []]
    else:
        merged: dict[str, dict[str, Any]] = {}
        quotes = {str(row.get("code")): row for row in snapshot.get("hot") or [] if row.get("code")}
        groups = list(snapshot.get("boardCandidates") or []) + list(snapshot.get("themeCandidates") or [])
        for group_rank, group in enumerate(groups):
            sector = str(group.get("name") or "热点题材")
            for item in group.get("rows") or []:
                code = str(item.get("code") or "")
                if not code:
                    continue
                current = merged.setdefault(code, {"code": code, "sectors": [], "sectorRank": group_rank})
                current.update(item)
                current.update(quotes.get(code) or {})
                current["sectorRank"] = min(int(current.get("sectorRank", group_rank)), group_rank)
                if sector not in current["sectors"]:
                    current["sectors"].append(sector)
        rows = list(merged.values())
    pools = snapshot.get("pools") or {}
    blocked = {
        str(item.get("code"))
        for item in (pools.get("limit_up") or []) + (pools.get("broken") or [])
    }
    sector_counts = Counter(str(row.get("sector") or (row.get("sectors") or ["热点题材"])[0]) for row in rows)
    break_rate = _number((snapshot.get("sentiment") or {}).get("breakRate"))
    ranked = []
    for index, row in enumerate(rows):
        row = dict(row)
        sector = str(row.get("sector") or (row.get("sectors") or ["热点题材"])[0])
        row["sector"] = sector
        if not _eligible(row, blocked):
            continue
        score, breakdown = _score(row, int(row.get("sectorRank", index)), sector_counts[sector], break_rate)
        if score < 60:
            continue
        row["score"] = score
        row["scoreBreakdown"] = breakdown
        ranked.append(row)
    return sorted(ranked, key=lambda item: (-_number(item.get("score")), str(item.get("code"))))


def calculate_price_levels(row: dict[str, Any], bars: list[dict[str, Any]] | None) -> dict[str, Any]:
    valid = [bar for bar in (bars or [])[:5] if _number(bar.get("close")) > 0]
    if valid:
        weights = [max(_number(bar.get("volume")), 1.0) for bar in valid]
        typical = [(_number(bar.get("high")) + _number(bar.get("low")) + _number(bar.get("close"))) / 3 for bar in valid]
        center = sum(value * weight for value, weight in zip(typical, weights)) / sum(weights)
        opening_high = max(_number(bar.get("high")) for bar in valid)
        opening_low = min(_number(bar.get("low")) for bar in valid)
        source = "开盘5分钟量价中枢"
        degraded = False
    else:
        center = sum((_number(row.get("open")), _number(row.get("low")), _number(row.get("price")))) / 3
        opening_high = _number(row.get("high"), _number(row.get("price")))
        opening_low = _number(row.get("low"), center)
        source = "日内开高低降级"
        degraded = True
    zone_low = max(opening_low, center * .995)
    zone_high = max(zone_low + .01, center * 1.005)
    breakout = max(zone_high, opening_high * 1.002)
    limit_up = _number(row.get("limit_up"), _number(row.get("price")) * 1.1)
    chase_cap = max(zone_high + .01, min(_number(row.get("price")) * 1.03, opening_high * 1.02, limit_up * .97))
    invalidation = min(opening_low * .995, _number(row.get("open"), opening_low) * .98)
    return {
        "zoneLow": round(zone_low, 2), "zoneHigh": round(zone_high, 2),
        "breakout": round(breakout, 2), "chaseCap": round(chase_cap, 2),
        "invalidation": round(invalidation, 2), "priceSource": source, "degraded": degraded,
    }


def _live_state(price: float, levels: dict[str, Any]) -> str:
    if price <= _number(levels.get("invalidation")):
        return "跌破失效价"
    if price > _number(levels.get("chaseCap")):
        return "超过追高上限"
    if price >= _number(levels.get("breakout")):
        return "突破确认"
    if _number(levels.get("zoneLow")) <= price <= _number(levels.get("zoneHigh")):
        return "进入参考区间"
    return "等待进入区间"


def _present(row: dict[str, Any], rank: int, tier: str, levels: dict[str, Any]) -> dict[str, Any]:
    price = _number(row.get("price"))
    limit_up = _number(row.get("limit_up"))
    distance_to_limit = (limit_up / price - 1.0) * 100 if price > 0 and limit_up > 0 else 0.0
    breakdown = row.get("scoreBreakdown") or {}
    reasons = [
        f"{row.get('sector', '热点题材')}联动，板块研究得分 {breakdown.get('板块', 0)}",
        f"当日尚未触板 · 距涨停 {distance_to_limit:.2f}% · 9:35 涨幅 {_number(row.get('pct', row.get('change_pct'))):.2f}%",
        f"换手 {_number(row.get('turnover', row.get('turnover_pct'))):.2f}% · 成交 {_number(row.get('amount_yi', _number(row.get('amount_wan')) / 10000)):.2f}亿",
    ]
    return {
        "rank": rank, "tier": tier, "code": str(row.get("code")), "name": str(row.get("name")),
        "sector": str(row.get("sector")), "score": round(_number(row.get("score")), 1),
        "scoreBreakdown": breakdown, "confirmedPrice": price, "currentPrice": price,
        "changePct": _number(row.get("pct", row.get("change_pct"))),
        "limitPrice": round(limit_up, 2), "distanceToLimit": round(distance_to_limit, 2),
        "untouchedAtSelection": True, "priceLevels": levels,
        "liveState": _live_state(price, levels), "reasons": reasons,
    }


def _empty(now: datetime, status: str, message: str) -> dict[str, Any]:
    return {"date": now.date().isoformat(), "generatedAt": None, "status": status, "message": message, "frozen": False, "core": [], "watch": [], "disclosure": "可解释规则研究排序，不是上涨概率或个性化买入建议。"}


def build_daily_pick(snapshot: dict[str, Any], now: datetime, minute_bars: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    phase = market_phase(now)
    if phase == "market_closed":
        return _empty(now, phase, "非交易日，不生成候选。")
    if phase == "waiting":
        return _empty(now, phase, "等待 9:35 开盘确认。")
    if phase == "missed":
        return _empty(now, "no_pick", "已错过 9:35～9:40 生成窗口，不使用午后数据补算。")
    errors = source_errors(snapshot)
    if errors:
        return _empty(now, "source_error", "关键数据不可用：" + "、".join(errors))
    ranked = rank_candidates(snapshot)
    selected: list[dict[str, Any]] = []
    per_sector: Counter[str] = Counter()
    for row in ranked:
        sector = str(row.get("sector") or "热点题材")
        if per_sector[sector] >= 2:
            continue
        selected.append(row)
        per_sector[sector] += 1
        if len(selected) == 5:
            break
    core_rows = [row for row in selected if minute_bars.get(str(row.get("code")))][:3]
    if len(core_rows) >= 3 and len({row["sector"] for row in core_rows}) < 2:
        replacement = next((row for row in selected[3:] if minute_bars.get(str(row.get("code"))) and row["sector"] != core_rows[0]["sector"]), None)
        if replacement:
            core_rows[2] = replacement
    core_codes = {str(row.get("code")) for row in core_rows}
    watch_rows = [row for row in selected if str(row.get("code")) not in core_codes][:2]
    core = [_present(row, index + 1, "核心", calculate_price_levels(row, minute_bars.get(str(row.get("code"))))) for index, row in enumerate(core_rows)]
    watch = [_present(row, len(core) + index + 1, "观察", calculate_price_levels(row, minute_bars.get(str(row.get("code"))))) for index, row in enumerate(watch_rows)]
    if not core and not watch:
        return _empty(now, "no_pick", "当前没有达到研究门槛的候选。")
    return {
        "date": now.date().isoformat(), "generatedAt": now.isoformat(timespec="seconds"),
        "status": "selected", "message": f"已固定 {len(core)} 只核心、{len(watch)} 只观察候选。",
        "frozen": True, "core": core, "watch": watch,
        "disclosure": "仅筛选生成时尚未触板且距涨停不超过8%的股票；研究分不是涨停概率或个性化买入建议。",
    }


def refresh_frozen_pick(pick: dict[str, Any], live_prices: dict[str, float]) -> dict[str, Any]:
    result = deepcopy(pick)
    for item in result.get("core", []) + result.get("watch", []):
        price = _number(live_prices.get(str(item.get("code"))), _number(item.get("currentPrice")))
        item["currentPrice"] = price
        item["liveState"] = _live_state(price, item.get("priceLevels") or {})
    return result


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def resolve_daily_pick(
    snapshot: dict[str, Any], now: datetime, state_dir: Path,
    minute_bars: dict[str, list[dict[str, Any]]], live_prices: dict[str, float] | None = None,
) -> dict[str, Any]:
    path = state_dir / f"daily-pick-{now:%Y%m%d}.json"
    if path.exists():
        frozen = json.loads(path.read_text(encoding="utf-8"))
        return refresh_frozen_pick(frozen, live_prices or {})
    result = build_daily_pick(snapshot, now, minute_bars)
    if result.get("frozen") or market_phase(now) == "missed":
        result["frozen"] = True
        _atomic_json(path, result)
    return result
