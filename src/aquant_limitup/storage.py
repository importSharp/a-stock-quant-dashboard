from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import sqlite3
from typing import Iterator

import pandas as pd


SCHEMA = """
CREATE TABLE IF NOT EXISTS stocks (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    exchange TEXT NOT NULL,
    industry TEXT NOT NULL,
    list_date TEXT,
    is_st INTEGER NOT NULL DEFAULT 0,
    price REAL,
    pct_change REAL,
    volume REAL,
    amount REAL,
    turnover REAL,
    pe_ttm REAL,
    volume_ratio REAL,
    market_cap REAL,
    float_market_cap REAL,
    return_60_snapshot REAL,
    return_ytd REAL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS daily_bars (
    code TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    open REAL NOT NULL,
    close REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    volume REAL NOT NULL,
    amount REAL NOT NULL,
    amplitude REAL,
    pct_change REAL,
    change REAL,
    turnover REAL,
    PRIMARY KEY (code, trade_date)
);

CREATE INDEX IF NOT EXISTS idx_bars_date ON daily_bars(trade_date);
CREATE INDEX IF NOT EXISTS idx_bars_code_date ON daily_bars(code, trade_date);

CREATE TABLE IF NOT EXISTS scan_runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    as_of TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    universe_size INTEGER NOT NULL,
    note TEXT
);

CREATE TABLE IF NOT EXISTS candidates (
    run_id INTEGER NOT NULL,
    rank_no INTEGER NOT NULL,
    code TEXT NOT NULL,
    strategy_type TEXT NOT NULL,
    model_score REAL NOT NULL,
    sector_score REAL,
    reason TEXT,
    PRIMARY KEY (run_id, rank_no),
    FOREIGN KEY (run_id) REFERENCES scan_runs(run_id)
);
"""


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript(SCHEMA)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def upsert_stocks(self, frame: pd.DataFrame) -> None:
        if frame.empty:
            return
        columns = list(frame.columns)
        placeholders = ",".join("?" for _ in columns)
        updates = ",".join(f"{c}=excluded.{c}" for c in columns if c != "code")
        sql = (
            f"INSERT INTO stocks ({','.join(columns)}) VALUES ({placeholders}) "
            f"ON CONFLICT(code) DO UPDATE SET {updates}"
        )
        rows = [tuple(_sql_value(value) for value in row) for row in frame.itertuples(index=False, name=None)]
        with self.connect() as connection:
            connection.executemany(sql, rows)

    def upsert_bars(self, frame: pd.DataFrame) -> None:
        if frame.empty:
            return
        columns = [
            "code", "trade_date", "open", "close", "high", "low", "volume",
            "amount", "amplitude", "pct_change", "change", "turnover",
        ]
        frame = frame[columns]
        placeholders = ",".join("?" for _ in columns)
        updates = ",".join(
            f"{column}=excluded.{column}" for column in columns if column not in {"code", "trade_date"}
        )
        sql = (
            f"INSERT INTO daily_bars ({','.join(columns)}) VALUES ({placeholders}) "
            f"ON CONFLICT(code, trade_date) DO UPDATE SET {updates}"
        )
        rows = [tuple(_sql_value(value) for value in row) for row in frame.itertuples(index=False, name=None)]
        with self.connect() as connection:
            connection.executemany(sql, rows)

    def stocks(self) -> pd.DataFrame:
        with self.connect() as connection:
            return pd.read_sql_query("SELECT * FROM stocks ORDER BY code", connection)

    def bars(self, start: str | None = None, end: str | None = None) -> pd.DataFrame:
        where = []
        params: list[str] = []
        if start:
            where.append("trade_date >= ?")
            params.append(start)
        if end:
            where.append("trade_date <= ?")
            params.append(end)
        clause = f"WHERE {' AND '.join(where)}" if where else ""
        with self.connect() as connection:
            return pd.read_sql_query(
                f"SELECT * FROM daily_bars {clause} ORDER BY code, trade_date",
                connection,
                params=params,
            )

    def latest_bar_date(self) -> str | None:
        with self.connect() as connection:
            row = connection.execute("SELECT MAX(trade_date) FROM daily_bars").fetchone()
        return row[0] if row else None

    def codes_with_bars(self) -> set[str]:
        with self.connect() as connection:
            rows = connection.execute("SELECT DISTINCT code FROM daily_bars").fetchall()
        return {str(row[0]) for row in rows}

    def save_scan(self, as_of: str, candidates: pd.DataFrame, universe_size: int) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO scan_runs(as_of, universe_size) VALUES (?, ?)",
                (as_of, universe_size),
            )
            run_id = int(cursor.lastrowid)
            rows = []
            for rank_no, row in enumerate(candidates.itertuples(index=False), start=1):
                rows.append(
                    (
                        run_id,
                        rank_no,
                        row.code,
                        row.strategy_type,
                        float(row.model_score),
                        float(row.sector_score),
                        row.reason,
                    )
                )
            connection.executemany(
                """
                INSERT INTO candidates(
                    run_id, rank_no, code, strategy_type, model_score, sector_score, reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
        return run_id


def _sql_value(value):
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value
