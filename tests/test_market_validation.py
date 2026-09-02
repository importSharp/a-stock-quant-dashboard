from __future__ import annotations

from datetime import datetime, timedelta, timezone

from scripts.market_validation import validate_market


NOW = datetime(2026, 9, 2, 9, 35, tzinfo=timezone(timedelta(hours=8)))


def snapshot() -> dict:
    quotes = [
        {"code": f"60000{i}", "price": 10.3, "high": 10.4, "low": 10.0, "last_close": 10, "limit_up": 11}
        for i in range(1, 5)
    ]
    return {
        "meta": {"asOf": NOW.isoformat()},
        "endpointStatus": [
            {"key": "pools", "status": "ok"}, {"key": "hotQuotes", "status": "ok"},
            {"key": "industryStrength", "status": "ok"},
        ],
        "hot": quotes,
        "indices": {"sh": {"price": 3300, "change_pct": .3}, "sz": {"price": 11000, "change_pct": .2}},
        "industryStrength": [{"change_pct": value} for value in (2, 1.8, 1.3, .8, .5)],
        "sentiment": {"breakRate": 18},
    }


def test_green_when_data_and_market_checks_pass():
    result = validate_market(snapshot(), NOW)
    assert result["status"] == "green"
    assert result["allowRecommendations"] is True


def test_stale_or_missing_critical_source_blocks_recommendations():
    stale = snapshot()
    stale["meta"]["asOf"] = (NOW - timedelta(minutes=4)).isoformat()
    assert validate_market(stale, NOW)["status"] == "red"
    missing = snapshot()
    missing["endpointStatus"][0]["status"] = "error"
    assert validate_market(missing, NOW)["allowRecommendations"] is False


def test_limit_price_mismatch_blocks_recommendations():
    value = snapshot()
    value["hot"][0]["limit_up"] = 12
    result = validate_market(value, NOW)
    assert result["status"] == "red"
    assert next(row for row in result["checks"] if row["key"] == "limitMath")["status"] == "fail"


def test_moderate_market_risk_is_yellow_but_not_blocking():
    value = snapshot()
    value["sentiment"]["breakRate"] = 32
    result = validate_market(value, NOW)
    assert result["status"] == "yellow"
    assert result["allowRecommendations"] is True
