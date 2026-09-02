"""Publish the web snapshot using only endpoints documented by a-stock-data.

No legacy local model, Yahoo data, dashboard.json, or historical fallback is read.
An unavailable endpoint is recorded as unavailable instead of being backfilled.
"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any, Callable

from daily_pick import (
    build_confirmed_strength_pool,
    is_untouched_limit_candidate,
    market_phase,
    rank_candidates,
    resolve_daily_pick,
)
from intraday_skill_analysis import (
    board_candidates,
    board_fund_flow,
    cls_telegraph,
    eastmoney_global_news,
    industry_comparison,
    limit_pools,
    opening_minutes,
    tencent_quotes,
    ths_hot,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "web" / "public" / "data" / "a-stock-data.json"


CAPABILITIES = [
    {"group": "行情", "items": "实时行情、日/分钟K线、复权因子", "mode": "实时/按需", "sources": "通达信 · 腾讯 · 百度 · 新浪"},
    {"group": "板块", "items": "行业涨幅、概念/行业资金、成分股", "mode": "实时", "sources": "东方财富"},
    {"group": "打板", "items": "涨停池、连板、炸板、跌停、昨涨停", "mode": "实时", "sources": "东方财富涨停专题"},
    {"group": "竞价", "items": "实时价量、量比、换手、主力净流入", "mode": "实时", "sources": "腾讯 · 东方财富"},
    {"group": "热度", "items": "同花顺热点、个股人气榜、互动易", "mode": "实时/按需", "sources": "同花顺 · 东方财富"},
    {"group": "资讯", "items": "电报、全球快讯、个股新闻", "mode": "实时/按需", "sources": "财联社 · 东方财富"},
    {"group": "公告", "items": "巨潮公告、业绩预告、风险提示", "mode": "按需", "sources": "巨潮资讯 · 东方财富"},
    {"group": "资金", "items": "融资融券、大宗交易、资金流、股东户数", "mode": "按需", "sources": "东方财富 · 深交所"},
    {"group": "基本面", "items": "三大报表、F10、分红、估值历史", "mode": "按需", "sources": "东方财富 · 新浪"},
    {"group": "研报", "items": "个股研报、盈利预测、i问财", "mode": "按需", "sources": "东方财富 · 同花顺"},
    {"group": "ETF期权", "items": "ETF行情、T型报价、希腊字母、IV", "mode": "按需", "sources": "腾讯 · 上交所"},
    {"group": "宏观", "items": "社融、PMI及宏观时间序列", "mode": "按需", "sources": "国家统计局 · 央行"},
]


def main() -> int:
    now = datetime.now().astimezone()
    result: dict[str, Any] = {
        "meta": {
            "skill": "a-stock-data",
            "version": "3.7.1",
            "asOf": now.isoformat(timespec="seconds"),
            "policy": "仅使用 a-stock-data 文档内端点；失败不使用旧缓存补位",
            "filters": "沪深主板 · 非ST/退市 · 候选价≤35元 · 已触板/未触板双池独立展示",
        },
        "endpointStatus": [],
        "capabilities": CAPABILITIES,
    }

    def collect(key: str, label: str, source: str, call: Callable[[], Any], empty: Any) -> Any:
        started = datetime.now().astimezone()
        try:
            value = call()
            size = len(value) if hasattr(value, "__len__") else 1
            result["endpointStatus"].append({
                "key": key, "label": label, "source": source, "status": "ok",
                "count": size, "updatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
            })
            return value
        except Exception as exc:  # endpoints are intentionally isolated
            result["endpointStatus"].append({
                "key": key, "label": label, "source": source, "status": "error", "count": 0,
                "updatedAt": started.isoformat(timespec="seconds"),
                "error": f"{type(exc).__name__}: {exc}",
            })
            return empty

    result["indices"] = collect(
        "indices", "指数行情", "腾讯行情", lambda: tencent_quotes(["sh000001", "sz399001", "sh000300"]), {},
    )
    result["industryStrength"] = collect(
        "industryStrength", "行业涨幅", "东方财富行业板块", lambda: industry_comparison(20), [],
    )
    result["industryFunds"] = collect(
        "industryFunds", "行业资金", "东方财富板块资金", lambda: board_fund_flow("industry", 20), [],
    )
    result["conceptFunds"] = collect(
        "conceptFunds", "概念资金", "东方财富板块资金", lambda: board_fund_flow("concept", 20), [],
    )
    result["pools"] = collect(
        "pools", "涨停/炸板池", "东方财富涨停专题", lambda: limit_pools(now.strftime("%Y%m%d")), {},
    )
    if not result["industryStrength"] and result["pools"]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in (result["pools"].get("limit_up") or []) + (result["pools"].get("broken") or []):
            industry = str(row.get("industry") or "").strip()
            if industry:
                grouped.setdefault(industry, []).append(row)
        result["industryStrength"] = [
            {
                "name": name,
                "code": "POOL-" + str(index + 1),
                "change_pct": round(sum(float(row.get("pct") or 0) for row in rows) / len(rows), 2),
                "up_count": len(rows),
                "down_count": 0,
                "leader": max(rows, key=lambda row: float(row.get("pct") or 0)).get("name", ""),
                "source": "东方财富涨停/炸板池聚合",
            }
            for index, (name, rows) in enumerate(sorted(grouped.items(), key=lambda item: len(item[1]), reverse=True)[:20])
        ]
        result["endpointStatus"].append({
            "key": "industryFallback", "label": "板块强度降级", "source": "东方财富涨停/炸板池聚合",
            "status": "ok", "count": len(result["industryStrength"]),
            "updatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        })
    result["hot"] = collect(
        "hot", "题材热点", "同花顺热点", lambda: ths_hot(now.strftime("%Y-%m-%d")), [],
    )
    if result["hot"]:
        live_hot = collect(
            "hotQuotes", "热点股实时行情", "腾讯行情",
            lambda: tencent_quotes([row["code"] for row in result["hot"]]), {},
        )
        for row in result["hot"]:
            quote = live_hot.get(row["code"]) or {}
            row.update({
                "price": quote.get("price", row.get("price", 0)),
                "pct": quote.get("change_pct", row.get("pct", 0)),
                "turnover": quote.get("turnover_pct", row.get("turnover", 0)),
                "vol_ratio": quote.get("vol_ratio", 0),
                "amount_yi": round(float(quote.get("amount_wan", 0)) / 10000, 2),
                "open": quote.get("open", 0), "high": quote.get("high", 0), "low": quote.get("low", 0),
                "limit_up": quote.get("limit_up", 0), "limit_down": quote.get("limit_down", 0),
            })
    result["news"] = {
        "cls": collect("clsNews", "财联社电报", "财联社", lambda: cls_telegraph(30), []),
        "eastmoney": collect("emNews", "全球快讯", "东方财富", lambda: eastmoney_global_news(30), []),
    }
    result["etfs"] = collect(
        "etfs", "ETF行情", "腾讯行情",
        lambda: tencent_quotes(["510300", "510500", "510050", "512480", "512760", "159995", "159915"]), {},
    )

    # Candidate universe comes only from the current top industry-board endpoints.
    # It never reads dashboard.json or the legacy local model.
    board_sets = []
    for board in result["industryStrength"][:6]:
        code = str(board.get("code") or "")
        if not code.startswith("BK"):
            continue
        rows = collect(
            f"board:{code}", f"{board.get('name', code)}成分候选", "东方财富板块成分",
            lambda code=code: board_candidates(code, 10), [],
        )
        board_sets.append({"name": board.get("name", ""), "code": code, "rows": rows})
    result["boardCandidates"] = board_sets

    # When the EastMoney board endpoint is unavailable, the visual board view can
    # still use a-stock-data's THS topic attribution + Tencent live quotes. The
    # provenance is explicit and this is not presented as an EastMoney industry.
    themes: dict[str, dict[str, Any]] = {}
    for row in result["hot"]:
        eligible = 0 < float(row.get("price") or 0) <= 35 and 1.5 <= float(row.get("pct") or 0) < 9.85
        for token in re.split(r"[+、；;/|]", str(row.get("reason") or "")):
            token = token.strip()
            if 2 <= len(token) <= 14:
                theme = themes.setdefault(token, {"strength": 0, "rows": []})
                theme["strength"] += 1
                if eligible:
                    theme["rows"].append(row)
    result["themeCandidates"] = [
        {"name": name, "code": "THS-THEME", "source": "同花顺题材归因 + 腾讯实时行情", "rows": sorted(theme["rows"], key=lambda x: (float(x.get("pct") or 0), float(x.get("vol_ratio") or 0)), reverse=True)[:10]}
        for name, theme in sorted(themes.items(), key=lambda item: item[1]["strength"], reverse=True)
        if theme["rows"]
    ][:6]
    if not result["themeCandidates"]:
        broken_by_industry: dict[str, list[dict[str, Any]]] = {}
        for row in result.get("pools", {}).get("broken") or []:
            if 0 < float(row.get("price") or 0) <= 35 and float(row.get("pct") or 0) < 9.85:
                broken_by_industry.setdefault(str(row.get("industry") or "炸板观察"), []).append(row)
        result["themeCandidates"] = [
            {"name": name, "code": "BROKEN-POOL", "source": "东方财富炸板池行业归类", "rows": sorted(rows, key=lambda row: float(row.get("pct") or 0), reverse=True)[:10]}
            for name, rows in sorted(broken_by_industry.items(), key=lambda item: len(item[1]), reverse=True)[:6]
        ]

    candidate_groups = result["boardCandidates"] or result["themeCandidates"]
    candidate_codes = sorted({str(row.get("code")) for group in candidate_groups for row in group.get("rows") or [] if row.get("code")})
    candidate_quotes = collect(
        "candidateQuotes", "候选实时行情", "腾讯行情",
        lambda: tencent_quotes(candidate_codes), {},
    ) if candidate_codes else {}
    for group in candidate_groups:
        for row in group.get("rows") or []:
            quote = candidate_quotes.get(str(row.get("code"))) or {}
            if not quote:
                continue
            row.update({
                "name": quote.get("name") or row.get("name"),
                "price": quote.get("price") or row.get("price"),
                "pct": quote.get("change_pct", row.get("pct", 0)),
                "open": quote.get("open", 0), "high": quote.get("high", 0), "low": quote.get("low", 0),
                "limit_up": quote.get("limit_up", 0), "limit_down": quote.get("limit_down", 0),
                "turnover": quote.get("turnover_pct") or row.get("turnover", 0),
                "vol_ratio": quote.get("vol_ratio") or row.get("vol_ratio", 0),
                "amount_yi": round(float(quote.get("amount_wan") or 0) / 10000, 2) or row.get("amount_yi", 0),
            })

    blocked_codes = {
        str(row.get("code"))
        for row in ((result.get("pools") or {}).get("limit_up") or []) + ((result.get("pools") or {}).get("broken") or [])
    }
    for group in candidate_groups:
        group["rows"] = [
            row for row in group.get("rows") or []
            if is_untouched_limit_candidate(row, blocked_codes)
        ]

    pools = result.get("pools") or {}
    up = pools.get("limit_up") or []
    broken = pools.get("broken") or []
    result["sentiment"] = {
        "limitUp": len(up),
        "broken": len(broken),
        "breakRate": round(len(broken) / (len(up) + len(broken)) * 100, 1) if up or broken else 0,
        "limitDown": len(pools.get("limit_down") or []),
        "maxHeight": max((int(row.get("limit_days") or 0) for row in up), default=0),
    }

    confirmed_codes = list(dict.fromkeys(
        str(row.get("code")) for row in (up[:8] + broken[:8]) if row.get("code")
    ))
    confirmed_quotes = collect(
        "confirmedQuotes", "已触板强势股行情", "腾讯行情",
        lambda: tencent_quotes(confirmed_codes), {},
    ) if confirmed_codes else {}
    result["confirmedPicks"] = build_confirmed_strength_pool(pools, confirmed_quotes)

    state_dir = ROOT / "data" / "runtime"
    state_path = state_dir / f"daily-pick-{now:%Y%m%d}.json"
    minute_bars: dict[str, list[dict[str, Any]]] = {}
    if market_phase(now) == "generation" and not state_path.exists():
        minute_errors = []
        for candidate in rank_candidates(result)[:12]:
            code = str(candidate.get("code") or "")
            try:
                bars = opening_minutes(code, now.strftime("%Y-%m-%d"))
                if bars:
                    minute_bars[code] = bars
                else:
                    minute_errors.append(f"{code}: 无开盘分钟数据")
            except Exception as exc:
                minute_errors.append(f"{code}: {type(exc).__name__}: {exc}")
        result["endpointStatus"].append({
            "key": "openingMinutes", "label": "开盘5分钟量价", "source": "新浪分钟K线",
            "status": "ok" if minute_bars else "error", "count": len(minute_bars),
            "updatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
            **({"error": "；".join(minute_errors[:3])} if minute_errors else {}),
        })

    live_prices: dict[str, float] = {}
    if state_path.exists():
        try:
            frozen = json.loads(state_path.read_text(encoding="utf-8"))
            frozen_codes = [str(row.get("code")) for row in (frozen.get("core") or []) + (frozen.get("watch") or []) if row.get("code")]
            frozen_quotes = tencent_quotes(frozen_codes) if frozen_codes else {}
            live_prices = {code: float(quote.get("price") or 0) for code, quote in frozen_quotes.items()}
        except Exception as exc:
            result["endpointStatus"].append({
                "key": "dailyPickQuotes", "label": "固定候选现价", "source": "腾讯行情", "status": "error", "count": 0,
                "updatedAt": datetime.now().astimezone().isoformat(timespec="seconds"), "error": f"{type(exc).__name__}: {exc}",
            })
    result["dailyPick"] = resolve_daily_pick(result, now, state_dir, minute_bars, live_prices)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT.with_suffix(OUTPUT.suffix + ".tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(OUTPUT)
    print(OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
