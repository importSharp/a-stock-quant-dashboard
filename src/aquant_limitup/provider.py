from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import base64
import json
import os
import shutil
import subprocess
import time
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

from .rules import eastmoney_secid, exchange_of, is_main_board


@dataclass
class EastMoneyProvider:
    timeout: int = 20
    retries: int = 3

    quote_url: str = "https://push2delay.eastmoney.com/api/qt/clist/get"
    history_url: str = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    yahoo_history_url: str = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"

    def _json(self, base_url: str, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{base_url}?{urlencode(params)}"
        last_error: Exception | None = None
        for attempt in range(self.retries):
            try:
                if os.name == "nt":
                    return self._json_via_powershell(url)
                request = Request(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 aquant-limitup/0.1",
                        "Accept": "application/json,text/plain,*/*",
                    },
                )
                with urlopen(request, timeout=self.timeout) as response:
                    return json.loads(response.read().decode("utf-8"))
            except Exception as exc:  # network boundary
                last_error = exc
                time.sleep(min(8.0, 1.0 * (2**attempt)))
        raise RuntimeError(f"行情请求失败: {url}") from last_error

    def _json_via_powershell(self, url: str) -> dict[str, Any]:
        executable = shutil.which("pwsh") or shutil.which("powershell")
        if not executable:
            raise RuntimeError("Windows环境未找到PowerShell网络客户端")
        script = (
            "$ProgressPreference='SilentlyContinue';"
            "$response=Invoke-WebRequest -Uri $env:AQUANT_REQUEST_URL -UseBasicParsing "
            "-TimeoutSec ([int]$env:AQUANT_REQUEST_TIMEOUT);"
            "$bytes=[Text.Encoding]::UTF8.GetBytes($response.Content);"
            "[Convert]::ToBase64String($bytes)"
        )
        request_environment = os.environ.copy()
        request_environment["AQUANT_REQUEST_URL"] = url
        request_environment["AQUANT_REQUEST_TIMEOUT"] = str(self.timeout)
        completed = subprocess.run(
            [
                executable,
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                script,
            ],
            env=request_environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=self.timeout + 15,
            check=False,
        )
        if completed.returncode != 0:
            message = completed.stderr.strip() or "PowerShell行情请求失败"
            raise RuntimeError(message)
        payload = base64.b64decode(completed.stdout.strip()).decode("utf-8")
        return json.loads(payload)

    def stock_snapshot(self) -> pd.DataFrame:
        fields = ",".join(
            [
                "f2", "f3", "f5", "f6", "f8", "f9", "f10", "f12", "f14",
                "f20", "f21", "f24", "f25", "f26", "f100",
            ]
        )
        rows: list[dict[str, Any]] = []
        page = 1
        # The upstream endpoint silently caps a response at 100 rows even when
        # a larger pz is requested, so paginate by the effective limit.
        page_size = 100
        total: int | None = None
        while True:
            payload = self._json(
                self.quote_url,
                {
                    "pn": page,
                    "pz": page_size,
                    "po": 1,
                    "np": 1,
                    "fltt": 2,
                    "invt": 2,
                    "fid": "f6",
                    "ut": "bd1d9ddb04089700cf9c27f6f7426281",
                    "fs": "m:0+t:6,m:1+t:2",
                    "fields": fields,
                },
            )
            diff = ((payload.get("data") or {}).get("diff") or [])
            if total is None:
                total = int((payload.get("data") or {}).get("total") or 0)
            if not diff:
                break
            rows.extend(diff)
            if len(rows) >= total or len(diff) < page_size:
                break
            page += 1
            # Avoid bursting a public quote endpoint during full-universe sync.
            time.sleep(2.50)

        renamed = []
        for row in rows:
            code = str(row.get("f12", "")).zfill(6)
            if not is_main_board(code):
                continue
            name = str(row.get("f14", ""))
            renamed.append(
                {
                    "code": code,
                    "name": name,
                    "exchange": exchange_of(code),
                    "industry": str(row.get("f100") or "未分类"),
                    "list_date": str(row.get("f26") or ""),
                    "is_st": int("ST" in name.upper()),
                    "price": _number(row.get("f2")),
                    "pct_change": _number(row.get("f3")),
                    "volume": _number(row.get("f5")),
                    "amount": _number(row.get("f6")),
                    "turnover": _number(row.get("f8")),
                    "pe_ttm": _number(row.get("f9")),
                    "volume_ratio": _number(row.get("f10")),
                    "market_cap": _number(row.get("f20")),
                    "float_market_cap": _number(row.get("f21")),
                    "return_60_snapshot": _number(row.get("f24")),
                    "return_ytd": _number(row.get("f25")),
                    "updated_at": pd.Timestamp.now().isoformat(),
                }
            )
        return pd.DataFrame(renamed)

    def daily_bars(
        self,
        code: str,
        *,
        start: str = "20230101",
        end: str | None = None,
        float_shares: float | None = None,
    ) -> pd.DataFrame:
        end = end or date.today().strftime("%Y%m%d")
        payload = self._json(
            self.history_url,
            {
                "secid": eastmoney_secid(code),
                "ut": "fa5fd1943c7b386f172d6893dbfba10b",
                "klt": 101,
                "fqt": 0,
                "beg": start.replace("-", ""),
                "end": end.replace("-", ""),
                "fields1": "f1,f2,f3,f4,f5,f6",
                "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
            },
        )
        data = payload.get("data") or {}
        output = []
        for item in data.get("klines") or []:
            parts = item.split(",")
            if len(parts) < 11:
                continue
            output.append(
                {
                    "code": str(code).zfill(6),
                    "trade_date": parts[0],
                    "open": float(parts[1]),
                    "close": float(parts[2]),
                    "high": float(parts[3]),
                    "low": float(parts[4]),
                    "volume": float(parts[5]),
                    "amount": float(parts[6]),
                    "amplitude": float(parts[7]),
                    "pct_change": float(parts[8]),
                    "change": float(parts[9]),
                    "turnover": float(parts[10]),
                }
            )
        return pd.DataFrame(output)

    def daily_bars_yahoo(
        self,
        code: str,
        *,
        start: str = "20230101",
        end: str | None = None,
        float_shares: float | None = None,
    ) -> pd.DataFrame:
        start_date = pd.Timestamp(start)
        end_date = pd.Timestamp(end or date.today().strftime("%Y%m%d"))
        suffix = "SS" if str(code).startswith("6") else "SZ"
        symbol = f"{str(code).zfill(6)}.{suffix}"
        payload = self._json(
            self.yahoo_history_url.format(symbol=symbol),
            {
                "period1": int(start_date.timestamp()),
                "period2": int((end_date + pd.Timedelta(days=1)).timestamp()),
                "interval": "1d",
                "events": "history",
            },
        )
        result = ((payload.get("chart") or {}).get("result") or [])
        if not result:
            return pd.DataFrame()
        chart = result[0]
        timestamps = chart.get("timestamp") or []
        quote = (((chart.get("indicators") or {}).get("quote") or [{}])[0])
        frame = pd.DataFrame(
            {
                "trade_date": pd.to_datetime(timestamps, unit="s", utc=True)
                .tz_convert("Asia/Shanghai")
                .strftime("%Y-%m-%d"),
                "open": quote.get("open") or [],
                "close": quote.get("close") or [],
                "high": quote.get("high") or [],
                "low": quote.get("low") or [],
                "volume": quote.get("volume") or [],
            }
        ).dropna(subset=["open", "close", "high", "low", "volume"])
        if frame.empty:
            return frame
        previous_close = frame["close"].shift(1)
        typical_price = frame[["open", "close", "high", "low"]].mean(axis=1)
        frame.insert(0, "code", str(code).zfill(6))
        frame["amount"] = frame["volume"] * typical_price
        frame["amplitude"] = 100 * (frame["high"] - frame["low"]) / previous_close
        frame["pct_change"] = 100 * (frame["close"] / previous_close - 1)
        frame["change"] = frame["close"] - previous_close
        frame["turnover"] = (
            100 * frame["volume"] / float_shares
            if float_shares and float_shares > 0
            else 0.0
        )
        return frame[
            [
                "code", "trade_date", "open", "close", "high", "low", "volume",
                "amount", "amplitude", "pct_change", "change", "turnover",
            ]
        ]


def _number(value: Any) -> float | None:
    if value in (None, "-", ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
