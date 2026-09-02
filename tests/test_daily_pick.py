from __future__ import annotations

from datetime import datetime
import json

from scripts.daily_pick import (
    build_daily_pick,
    calculate_price_levels,
    market_phase,
    refresh_frozen_pick,
    resolve_daily_pick,
)


TZ = datetime.now().astimezone().tzinfo


def at(hour: int, minute: int, weekday_day: int = 2) -> datetime:
    return datetime(2026, 9, weekday_day, hour, minute, tzinfo=TZ)


def row(code: str, sector: str, score: float = 82, *, minute: bool = True) -> dict:
    return {
        "code": code,
        "name": f"测试{code}",
        "sector": sector,
        "price": 10.30,
        "pct": 3.2,
        "open": 10.10,
        "high": 10.40,
        "low": 10.02,
        "limit_up": 11.00,
        "turnover": 2.4,
        "vol_ratio": 2.1,
        "amount_yi": 1.8,
        "base_score": score,
        "minute": minute,
    }


def bars() -> list[dict]:
    return [
        {"open": 10.10, "high": 10.20, "low": 10.02, "close": 10.15, "volume": 100},
        {"open": 10.15, "high": 10.30, "low": 10.12, "close": 10.25, "volume": 180},
        {"open": 10.25, "high": 10.36, "low": 10.22, "close": 10.32, "volume": 260},
        {"open": 10.32, "high": 10.40, "low": 10.28, "close": 10.35, "volume": 220},
        {"open": 10.35, "high": 10.38, "low": 10.29, "close": 10.30, "volume": 160},
    ]


def healthy_snapshot(candidates: list[dict]) -> dict:
    return {
        "meta": {"asOf": at(9, 35).isoformat()},
        "endpointStatus": [
            {"key": "hotQuotes", "status": "ok"},
            {"key": "pools", "status": "ok"},
            {"key": "industryStrength", "status": "ok"},
        ],
        "rankedCandidates": candidates,
        "pools": {"broken": [], "limit_up": []},
        "sentiment": {"breakRate": 18},
    }


def test_market_phase_respects_confirmation_window_and_weekend():
    assert market_phase(at(9, 34)) == "waiting"
    assert market_phase(at(9, 35)) == "generation"
    assert market_phase(at(9, 40)) == "missed"
    assert market_phase(at(10, 0)) == "missed"
    assert market_phase(at(9, 35, weekday_day=5)) == "market_closed"


def test_price_levels_use_opening_volume_weighted_typical_price():
    levels = calculate_price_levels(row("600001", "通信"), bars())
    assert levels["priceSource"] == "开盘5分钟量价中枢"
    assert levels["zoneLow"] < levels["zoneHigh"] < levels["chaseCap"]
    assert levels["invalidation"] < levels["zoneLow"]
    assert levels["breakout"] >= 10.40
    assert levels["chaseCap"] < 11.00


def test_builds_three_core_and_two_watch_with_sector_cap():
    candidates = [
        row("600001", "通信", 95), row("600002", "通信", 93), row("600003", "通信", 92),
        row("000001", "电力", 91), row("000002", "电力", 88), row("002001", "消费", 85),
    ]
    minute = {item["code"]: bars() for item in candidates[:4]}
    result = build_daily_pick(healthy_snapshot(candidates), at(9, 35), minute)
    assert result["status"] == "selected"
    assert len(result["core"]) == 3
    assert len(result["watch"]) == 2
    all_rows = result["core"] + result["watch"]
    assert max(sum(pick["sector"] == sector for pick in all_rows) for sector in {p["sector"] for p in all_rows}) <= 2
    assert len({pick["sector"] for pick in result["core"]}) >= 2
    assert all(pick["priceLevels"] for pick in result["core"])


def test_unhealthy_sources_never_create_a_pick():
    snapshot = healthy_snapshot([row("600001", "通信")])
    snapshot["endpointStatus"][0]["status"] = "error"
    result = build_daily_pick(snapshot, at(9, 35), {"600001": bars()})
    assert result["status"] == "source_error"
    assert result["core"] == []
    assert "热点股实时行情" in result["message"]


def test_hard_filters_do_not_force_five_candidates():
    good = row("600001", "通信")
    too_expensive = row("600002", "通信") | {"price": 36}
    st = row("000001", "电力") | {"name": "ST测试"}
    overextended = row("002001", "消费") | {"pct": 8.8}
    result = build_daily_pick(
        healthy_snapshot([good, too_expensive, st, overextended]),
        at(9, 35),
        {"600001": bars()},
    )
    assert [item["code"] for item in result["core"]] == ["600001"]
    assert result["watch"] == []


def test_same_day_state_is_reused_and_only_live_price_changes(tmp_path):
    snapshot = healthy_snapshot([row("600001", "通信", 95), row("000001", "电力", 90)])
    first = resolve_daily_pick(snapshot, at(9, 35), tmp_path, {"600001": bars(), "000001": bars()})
    assert first["status"] == "selected"
    original_codes = [item["code"] for item in first["core"] + first["watch"]]
    changed = healthy_snapshot([row("002001", "消费", 100)])
    second = resolve_daily_pick(changed, at(9, 38), tmp_path, {"002001": bars()}, {"600001": 10.55, "000001": 9.95})
    assert [item["code"] for item in second["core"] + second["watch"]] == original_codes
    assert second["core"][0]["currentPrice"] == 10.55
    state = json.loads(next(tmp_path.glob("daily-pick-*.json")).read_text(encoding="utf-8"))
    assert state["frozen"] is True


def test_previous_day_state_is_not_reused(tmp_path):
    old = {"date": "2026-09-01", "status": "selected", "core": [{"code": "600999"}], "watch": []}
    (tmp_path / "daily-pick-20260901.json").write_text(json.dumps(old), encoding="utf-8")
    result = resolve_daily_pick(healthy_snapshot([]), at(9, 34), tmp_path, {})
    assert result["status"] == "waiting"
    assert result["core"] == []


def test_live_state_boundaries():
    frozen = {
        "core": [{"code": "600001", "currentPrice": 10.3, "priceLevels": {"zoneLow": 10.1, "zoneHigh": 10.3, "breakout": 10.4, "chaseCap": 10.6, "invalidation": 9.9}}],
        "watch": [],
    }
    assert refresh_frozen_pick(frozen, {"600001": 10.2})["core"][0]["liveState"] == "进入参考区间"
    assert refresh_frozen_pick(frozen, {"600001": 10.5})["core"][0]["liveState"] == "突破确认"
    assert refresh_frozen_pick(frozen, {"600001": 10.7})["core"][0]["liveState"] == "超过追高上限"
    assert refresh_frozen_pick(frozen, {"600001": 9.8})["core"][0]["liveState"] == "跌破失效价"
