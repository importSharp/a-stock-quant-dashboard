from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path

import pandas as pd

from .scanner import ScanResult


def render_markdown(result: ScanResult) -> str:
    lines = [
        f"# A股主板涨停观察日报（{result.as_of}）",
        "",
        "> 模型分数是启发式排序，不是承诺概率；集合竞价前不得视为最终候选。",
        "",
        f"有效股票池：{result.universe_size} 只",
        "",
        "## 强势板块",
        "",
        "| 排名 | 板块 | 强度 | 5日收益 | 20日收益 | 20日线上占比 | 触板率 |",
        "|---:|---|---:|---:|---:|---:|---:|",
    ]
    for index, row in result.sectors.iterrows():
        lines.append(
            f"| {index + 1} | {row.industry} | {row.sector_score * 100:.1f} | "
            f"{row.sector_return_5 * 100:.1f}% | {row.sector_return_20 * 100:.1f}% | "
            f"{row.sector_breadth_20 * 100:.1f}% | {row.sector_touch_rate * 100:.1f}% |"
        )
    lines.extend(
        [
            "",
            "## 个股候选",
            "",
            "| 排名 | 代码 | 名称 | 板块 | 类型 | 分数 | 20日 | 量比 | 理由 |",
            "|---:|---|---|---|---|---:|---:|---:|---|",
        ]
    )
    for index, row in result.candidates.iterrows():
        lines.append(
            f"| {index + 1} | {row.code} | {row['name']} | {row.industry} | "
            f"{row.strategy_type} | {row.model_score:.1f} | {row.return_20 * 100:.1f}% | "
            f"{row.amount_ratio:.2f} | {row.reason} |"
        )
    lines.extend(["", "## 强势板块内候选（每板块最多10只）", ""])
    for sector in result.sectors.itertuples(index=False):
        group = result.sector_candidates.loc[
            result.sector_candidates["industry"] == sector.industry
        ]
        lines.extend(
            [
                f"### {sector.industry}（{len(group)}只）",
                "",
                "| 板块排名 | 代码 | 名称 | 类型 | 分数 | 20日 | 量比 | 理由 |",
                "|---:|---|---|---|---:|---:|---:|---|",
            ]
        )
        for row in group.itertuples(index=False):
            lines.append(
                f"| {row.sector_rank} | {row.code} | {row.name} | {row.strategy_type} | "
                f"{row.model_score:.1f} | {row.return_20 * 100:.1f}% | "
                f"{row.amount_ratio:.2f} | {row.reason} |"
            )
        lines.append("")
    lines.extend(
        [
            "",
            "## 使用规则",
            "",
            "- 9:25后必须用集合竞价重新确认；当前版本尚未接入实时竞价数据。",
            "- 一字涨停、停牌、板块转弱或高开过度时不追。",
            "- 本报告仅用于量化研究，不构成投资建议。",
            "",
        ]
    )
    return "\n".join(lines)


def save_report(result: ScanResult, directory: str | Path) -> Path:
    output_dir = Path(directory)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"limitup-{result.as_of}.md"
    path.write_text(render_markdown(result), encoding="utf-8")
    result.candidates.to_csv(
        output_dir / f"limitup-{result.as_of}.csv", index=False, encoding="utf-8-sig"
    )
    return path


def save_dashboard_data(
    result: ScanResult,
    destination: str | Path,
    validation: dict | None = None,
) -> Path:
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    candidates = []
    for rank_no, row in enumerate(result.candidates.itertuples(index=False), start=1):
        candidates.append(_candidate_record(row, rank_no))
    sectors = []
    for rank_no, row in enumerate(result.sectors.itertuples(index=False), start=1):
        sectors.append(
            {
                "rank": rank_no,
                "name": row.industry,
                "score": round(float(row.sector_score) * 100, 2),
                "return5": round(float(row.sector_return_5) * 100, 2),
                "return20": round(float(row.sector_return_20) * 100, 2),
                "breadth20": round(float(row.sector_breadth_20) * 100, 2),
                "amountRatio": round(float(row.sector_amount_ratio), 2),
                "touchRate": round(float(row.sector_touch_rate) * 100, 2),
                "closeRate": round(float(row.sector_close_rate) * 100, 2),
            }
        )
    sector_candidates = []
    for sector in result.sectors.itertuples(index=False):
        group = result.sector_candidates.loc[
            result.sector_candidates["industry"] == sector.industry
        ]
        sector_candidates.append(
            {
                "name": sector.industry,
                "score": round(float(sector.sector_score) * 100, 2),
                "available": len(group),
                "candidates": [
                    _candidate_record(row, int(row.sector_rank))
                    for row in group.itertuples(index=False)
                ],
            }
        )
    payload = {
        "asOf": result.as_of,
        "generatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "universeSize": result.universe_size,
        "modelStage": "收盘预选",
        "auctionStatus": "待9:25竞价确认",
        "validation": validation,
        "sectors": sectors,
        "candidates": candidates,
        "sectorCandidates": sector_candidates,
        "stockPool": [
            _candidate_record(row, rank_no)
            for rank_no, row in enumerate(result.stock_pool.itertuples(index=False), start=1)
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def save_kline_data(
    panel: pd.DataFrame,
    codes: list[str] | pd.Series,
    destination: str | Path,
    *,
    days: int = 120,
) -> int:
    output_dir = Path(destination)
    output_dir.mkdir(parents=True, exist_ok=True)
    wanted = {str(code).zfill(6) for code in codes}
    source = panel.loc[panel["code"].isin(wanted)].sort_values(["code", "trade_date"])
    written = 0
    for code, group in source.groupby("code", sort=False):
        recent = group.tail(days + 20).copy()
        recent["ma5"] = recent["close"].rolling(5).mean()
        recent["ma10"] = recent["close"].rolling(10).mean()
        recent["ma20"] = recent["close"].rolling(20).mean()
        recent = recent.tail(days)
        bars = []
        for row in recent.itertuples(index=False):
            bars.append(
                {
                    "date": pd.Timestamp(row.trade_date).strftime("%Y-%m-%d"),
                    "open": round(float(row.open), 3),
                    "close": round(float(row.close), 3),
                    "high": round(float(row.high), 3),
                    "low": round(float(row.low), 3),
                    "volume": round(float(row.volume), 2),
                    "ma5": _finite_round(row.ma5, 3),
                    "ma10": _finite_round(row.ma10, 3),
                    "ma20": _finite_round(row.ma20, 3),
                }
            )
        payload = {"code": str(code), "days": len(bars), "bars": bars}
        (output_dir / f"{code}.json").write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        written += 1
    return written


def _finite_round(value, digits: int):
    return None if pd.isna(value) else round(float(value), digits)


def _candidate_record(row, rank_no: int) -> dict:
    return {
        "rank": rank_no,
        "code": row.code,
        "name": row.name,
        "industry": row.industry,
        "close": round(float(row.close), 2),
        "change": round(float(row.pct_change), 2),
        "type": row.strategy_type,
        "score": round(float(row.model_score), 2),
        "sectorScore": round(float(row.sector_score) * 100, 2),
        "return20": round(float(row.return_20) * 100, 2),
        "return60": round(float(row.return_60) * 100, 2),
        "amountRatio": round(float(row.amount_ratio), 2),
        "turnover5": round(float(row.average_turnover_5), 2),
        "reason": row.reason,
        "eligible": bool(getattr(row, "eligible", True)),
        "eligibilityReason": getattr(row, "eligibility_reason", "符合当前股票池"),
    }
