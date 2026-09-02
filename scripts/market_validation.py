"""Explainable, fail-closed validation for the live a-stock-data snapshot."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any


def _number(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
        return result if result == result else default
    except (TypeError, ValueError):
        return default


def _check(key: str, label: str, status: str, detail: str, meaning: str, *, blocking: bool = False) -> dict[str, Any]:
    return {"key": key, "label": label, "status": status, "detail": detail, "meaning": meaning, "blocking": blocking}


def _endpoint(snapshot: dict[str, Any], key: str) -> dict[str, Any]:
    return next((row for row in snapshot.get("endpointStatus") or [] if row.get("key") == key), {})


def _parse_time(value: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _limit_price(previous_close: float) -> float:
    return float((Decimal(str(previous_close)) * Decimal("1.10")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def validate_market(snapshot: dict[str, Any], now: datetime) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    stamp = _parse_time((snapshot.get("meta") or {}).get("asOf"))
    if not stamp:
        checks.append(_check("freshness", "数据新鲜度", "fail", "快照没有有效时间", "无法确认行情属于当前时点", blocking=True))
    else:
        if stamp.tzinfo and not now.tzinfo:
            now = now.replace(tzinfo=stamp.tzinfo)
        elif now.tzinfo and not stamp.tzinfo:
            stamp = stamp.replace(tzinfo=now.tzinfo)
        age = max(0, int((now - stamp).total_seconds()))
        status = "pass" if age <= 90 else "warn" if age <= 180 else "fail"
        checks.append(_check("freshness", "数据新鲜度", status, f"快照延迟 {age} 秒", "过期行情不能用于计算买卖区间", blocking=status == "fail"))

    required = ["pools", "hotQuotes"]
    missing = [key for key in required if _endpoint(snapshot, key).get("status") != "ok"]
    sector_ok = any(_endpoint(snapshot, key).get("status") == "ok" for key in ("industryStrength", "industryFallback"))
    if not sector_ok:
        missing.append("industryStrength")
    checks.append(_check(
        "sources", "关键数据链路", "pass" if not missing else "fail",
        "涨停池、实时行情和板块数据均可用" if not missing else "不可用：" + "、".join(missing),
        "缺少任一关键来源就停止生成候选", blocking=bool(missing),
    ))

    groups = list(snapshot.get("boardCandidates") or []) + list(snapshot.get("themeCandidates") or [])
    rows: dict[str, dict[str, Any]] = {}
    for row in snapshot.get("hot") or []:
        if row.get("code"):
            rows[str(row["code"])] = row
    for group in groups:
        for row in group.get("rows") or []:
            if row.get("code"):
                rows[str(row["code"])] = row
    valid = [row for row in rows.values() if _number(row.get("price")) > 0 and _number(row.get("high")) >= _number(row.get("low")) > 0]
    quote_ratio = len(valid) / len(rows) if rows else 0.0
    quote_status = "pass" if len(valid) >= 3 and quote_ratio >= .8 else "warn" if valid else "fail"
    checks.append(_check(
        "quotes", "实时行情完整性", quote_status,
        f"{len(valid)}/{len(rows)} 只股票价格与高低价有效",
        "避免用缺字段或异常价格计算候选", blocking=quote_status == "fail",
    ))

    audited = 0
    mismatches = 0
    for row in valid:
        previous = _number(row.get("last_close"))
        reported = _number(row.get("limit_up"))
        if previous <= 0 or reported <= 0:
            continue
        audited += 1
        if abs(_limit_price(previous) - reported) > .011:
            mismatches += 1
    limit_status = "pass" if audited and not mismatches else "fail" if mismatches else "warn"
    checks.append(_check(
        "limitMath", "涨停价核验", limit_status,
        f"核验 {audited} 只，异常 {mismatches} 只" if audited else "缺少昨收价，无法数学复核",
        "防止错误涨停价影响距离和追高上限", blocking=bool(mismatches),
    ))

    indices = list((snapshot.get("indices") or {}).values())
    index_changes = [_number(row.get("change_pct")) for row in indices if _number(row.get("price")) > 0]
    average_index = sum(index_changes) / len(index_changes) if index_changes else 0.0
    index_status = "pass" if index_changes and average_index >= -.5 else "warn" if index_changes and average_index >= -1.2 else "fail"
    checks.append(_check(
        "indices", "大盘环境", index_status,
        f"主要指数平均 {average_index:+.2f}%" if index_changes else "主要指数行情不可用",
        "弱市中降低追涨信号可信度", blocking=index_status == "fail",
    ))

    sectors = snapshot.get("industryStrength") or []
    leaders = [row for row in sectors[:5] if _number(row.get("change_pct")) > 0]
    breadth_status = "pass" if len(leaders) >= 3 else "warn" if leaders else "fail"
    checks.append(_check(
        "breadth", "板块联动", breadth_status, f"前五板块中 {len(leaders)} 个上涨",
        "多板块共振比单只股票异动更可靠", blocking=False,
    ))

    break_rate = _number((snapshot.get("sentiment") or {}).get("breakRate"))
    break_status = "pass" if break_rate <= 25 else "warn" if break_rate <= 40 else "fail"
    checks.append(_check(
        "breakRate", "炸板风险", break_status, f"当前炸板率 {break_rate:.1f}%",
        "炸板率过高说明追涨承接较弱", blocking=break_status == "fail",
    ))

    blocking_failures = [row for row in checks if row["blocking"] and row["status"] == "fail"]
    degraded = [row for row in checks if row["status"] != "pass"]
    status = "red" if blocking_failures else "yellow" if degraded else "green"
    label = {"green": "数据与市场验证通过", "yellow": "谨慎：部分验证降级", "red": "停止：验证未通过"}[status]
    return {
        "status": status, "label": label, "allowRecommendations": not blocking_failures,
        "checkedAt": now.isoformat(timespec="seconds"), "checks": checks,
        "summary": "；".join(row["detail"] for row in degraded[:3]) if degraded else "关键数据、价格和市场环境均通过检查",
        "method": "a-stock-data端点数据 + 本地确定性校验规则",
    }
