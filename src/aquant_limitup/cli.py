from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import date, timedelta
import json
from pathlib import Path
import sys

import pandas as pd

from .backtest import walk_forward_backtest
from .config import load_config
from .features import build_feature_panel
from .provider import EastMoneyProvider
from .report import save_dashboard_data, save_kline_data, save_report
from .rules import is_main_board
from .scanner import scan
from .storage import Store


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="A股主板涨停研究工具")
    parser.add_argument("--config", default="config/default.toml")
    subparsers = parser.add_subparsers(dest="command", required=True)

    sync = subparsers.add_parser("sync", help="同步股票列表和日线")
    sync.add_argument("--max-stocks", type=int, default=None, help="首次试运行可限制股票数量")
    sync.add_argument("--start", default=None, help="历史开始日期 YYYY-MM-DD")
    sync.add_argument("--missing-only", action="store_true", help="只同步本地尚无日线的股票")
    sync.add_argument("--use-cached-snapshot", action="store_true", help="使用本地股票清单，跳过快照刷新")
    sync.add_argument(
        "--history-source",
        choices=["eastmoney", "yahoo"],
        default="eastmoney",
        help="历史日线来源",
    )

    scan_parser = subparsers.add_parser("scan", help="生成最新候选日报")
    scan_parser.add_argument("--date", default=None, help="扫描日期 YYYY-MM-DD")

    backtest = subparsers.add_parser("backtest", help="历史逐日Top-K验证")
    backtest.add_argument("--start", default=None)
    backtest.add_argument("--end", default=None)
    backtest.add_argument("--top-k", type=int, default=5)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = load_config(args.config)
    store = Store(config.data.database)
    try:
        if args.command == "sync":
            return _sync(args, config, store)
        if args.command == "scan":
            return _scan(args, config, store)
        if args.command == "backtest":
            return _backtest(args, config, store)
    except (RuntimeError, ValueError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 2
    return 0


def _sync(args, config, store: Store) -> int:
    provider = EastMoneyProvider(
        timeout=config.data.request_timeout_seconds,
        retries=config.data.request_retries,
    )
    if args.use_cached_snapshot:
        stocks = store.stocks()
        if stocks.empty:
            raise ValueError("本地股票清单为空，不能跳过快照刷新")
        print(f"使用本地股票清单：{len(stocks)}只")
    else:
        print("同步主板股票快照...")
        try:
            stocks = provider.stock_snapshot()
            stocks = stocks.loc[stocks["code"].map(is_main_board)].copy()
            if config.universe.exclude_st:
                stocks = stocks.loc[stocks["is_st"].eq(0)]
            store.upsert_stocks(stocks)
        except RuntimeError as exc:
            stocks = store.stocks()
            if stocks.empty:
                raise
            print(f"警告: 股票快照更新失败，使用本地缓存继续: {exc}")

    targets = stocks.sort_values("amount", ascending=False, na_position="last")
    if args.missing_only:
        existing_codes = store.codes_with_bars()
        targets = targets.loc[~targets["code"].isin(existing_codes)]
        print(f"缺失日线股票：{len(targets)}只")
    if args.max_stocks:
        targets = targets.head(args.max_stocks)
    latest = store.latest_bar_date()
    if args.start:
        start_text = args.start
    elif latest:
        start_text = (pd.Timestamp(latest) - pd.Timedelta(days=10)).strftime("%Y-%m-%d")
    else:
        start_text = config.data.history_start
    start = start_text.replace("-", "")
    print(f"同步 {len(targets)} 只股票日线，开始日期 {start}...")
    completed = 0
    failed = []
    history_loader = (
        provider.daily_bars_yahoo
        if args.history_source == "yahoo"
        else provider.daily_bars
    )
    with ThreadPoolExecutor(max_workers=config.data.sync_workers) as executor:
        futures = {
            executor.submit(
                history_loader,
                row.code,
                start=start,
                float_shares=(
                    float(row.float_market_cap) / float(row.price)
                    if pd.notna(row.float_market_cap)
                    and pd.notna(row.price)
                    and float(row.price) > 0
                    else None
                ),
            ): row.code
            for row in targets.itertuples(index=False)
        }
        for future in as_completed(futures):
            code = futures[future]
            try:
                store.upsert_bars(future.result())
                completed += 1
                if completed % 25 == 0 or completed == len(targets):
                    print(f"  已完成 {completed}/{len(targets)}")
            except Exception as exc:
                failed.append((code, str(exc)))
    print(f"同步完成：成功 {completed}，失败 {len(failed)}")
    if failed:
        print("失败代码：" + ", ".join(code for code, _ in failed[:20]))
    return 0 if completed else 2


def _load_panel(store: Store) -> pd.DataFrame:
    stocks = store.stocks()
    bars = store.bars()
    if stocks.empty or bars.empty:
        raise ValueError("数据库为空，请先运行 sync")
    return build_feature_panel(bars, stocks)


def _scan(args, config, store: Store) -> int:
    panel = _load_panel(store)
    result = scan(panel, config.universe, config.strategy, as_of=args.date)
    path = save_report(result, config.report_directory)
    validation = None
    try:
        validation_start = (
            panel["trade_date"].max() - pd.Timedelta(days=120)
        ).strftime("%Y-%m-%d")
        summary = walk_forward_backtest(
            panel,
            config.universe,
            config.strategy,
            start=validation_start,
            top_k=5,
        )
        validation = asdict(summary)
    except ValueError:
        pass
    if Path("web").is_dir():
        save_dashboard_data(
            result,
            Path("web/public/data/dashboard.json"),
            validation=validation,
        )
        kline_count = save_kline_data(
            panel,
            result.stock_pool["code"],
            Path("web/public/data/klines"),
        )
        print(f"网页K线：{kline_count}只")
    run_id = store.save_scan(result.as_of, result.candidates, result.universe_size)
    print(f"扫描完成，run_id={run_id}")
    print(f"报告：{path}")
    print(result.candidates[["code", "name", "industry", "strategy_type", "model_score"]].to_string(index=False))
    return 0


def _backtest(args, config, store: Store) -> int:
    panel = _load_panel(store)
    summary = walk_forward_backtest(
        panel,
        config.universe,
        config.strategy,
        start=args.start,
        end=args.end,
        top_k=args.top_k,
    )
    print(json.dumps(asdict(summary), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
