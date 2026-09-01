from __future__ import annotations

import csv
from datetime import datetime, timedelta
import hashlib
import json
import math
from pathlib import Path
import random
import re
import sys
import time
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126 Safari/537.36"
ZTB_UT = "7eea3edcaed734bea9cbfc24409ed989"
ROOT = Path(__file__).resolve().parents[1]
_last_em_call = 0.0


def _get_bytes(
    url: str,
    params: dict[str, Any] | None = None,
    *,
    referer: str = "",
    timeout: int = 20,
) -> bytes:
    global _last_em_call
    if params:
        url = f"{url}?{urlencode(params)}"
    headers = {"User-Agent": UA, "Accept": "application/json,text/plain,*/*"}
    if referer:
        headers["Referer"] = referer
    attempts = 2 if "eastmoney.com" in url else 1
    last_error: Exception | None = None
    for attempt in range(attempts):
        if "eastmoney.com" in url:
            wait = 1.35 - (time.time() - _last_em_call)
            if wait > 0:
                time.sleep(wait + random.uniform(0.10, 0.30))
        request = Request(url, headers=headers)
        try:
            with urlopen(request, timeout=timeout) as response:
                return response.read()
        except Exception as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(2.0 + random.uniform(0.2, 0.8))
        finally:
            if "eastmoney.com" in url:
                _last_em_call = time.time()
    assert last_error is not None
    raise last_error


def _get_json(
    url: str,
    params: dict[str, Any] | None = None,
    *,
    referer: str = "",
    encoding: str = "utf-8",
) -> Any:
    return json.loads(_get_bytes(url, params, referer=referer).decode(encoding))


def _main_board(code: str) -> bool:
    return bool(re.fullmatch(r"(?:000|001|002|003|600|601|603|605)\d{3}", code))


def _non_st(name: str) -> bool:
    return "ST" not in name.upper() and "退" not in name


def tencent_quotes(codes: list[str]) -> dict[str, dict[str, Any]]:
    sh_indices = {"000300", "000905", "000016", "000688", "000852", "000010"}
    prefixed: list[str] = []
    original: dict[str, str] = {}
    for code in codes:
        low = code.lower()
        if low.startswith(("sh", "sz", "bj")):
            key = low
        elif code in sh_indices or code.startswith(("5", "6", "9")):
            key = f"sh{code}"
        else:
            key = f"sz{code}"
        prefixed.append(key)
        original[key] = code
    raw = _get_bytes("https://qt.gtimg.cn/q=" + ",".join(prefixed)).decode("gbk")
    out: dict[str, dict[str, Any]] = {}
    for line in raw.split(";"):
        if "=" not in line or '"' not in line:
            continue
        key = line.split("=", 1)[0].split("_")[-1]
        values = line.split('"', 2)[1].split("~")
        if len(values) < 53:
            continue
        code = original.get(key, key)
        number = lambda i: float(values[i]) if values[i] else 0.0
        out[code] = {
            "name": values[1],
            "price": number(3),
            "last_close": number(4),
            "open": number(5),
            "change_pct": number(32),
            "high": number(33),
            "low": number(34),
            "amount_wan": number(37),
            "turnover_pct": number(38),
            "pe_ttm": number(39),
            "mcap_yi": number(45),
            "pb": number(46),
            "limit_up": number(47),
            "limit_down": number(48),
            "vol_ratio": number(49),
        }
    return out


def industry_comparison(top_n: int = 15) -> list[dict[str, Any]]:
    data = _get_json(
        "https://push2.eastmoney.com/api/qt/clist/get",
        {
            "pn": 1,
            "pz": 100,
            "po": 1,
            "np": 1,
            "fltt": 2,
            "invt": 2,
            "fid": "f3",
            "fs": "m:90+t:2",
            "fields": "f2,f3,f4,f12,f14,f104,f105,f136,f140",
        },
        referer="https://quote.eastmoney.com/",
    )
    items = (data.get("data") or {}).get("diff") or []
    return [
        {
            "name": item.get("f14", ""),
            "code": item.get("f12", ""),
            "change_pct": item.get("f3", 0),
            "up_count": item.get("f104", 0),
            "down_count": item.get("f105", 0),
            "leader": item.get("f140", ""),
            "leader_change": item.get("f136", 0),
        }
        for item in items[:top_n]
    ]


def board_fund_flow(board_type: str, top_n: int = 15) -> list[dict[str, Any]]:
    fs = {"industry": "m:90+t:2", "concept": "m:90+t:3"}[board_type]
    data = _get_json(
        "https://push2.eastmoney.com/api/qt/clist/get",
        {
            "pn": 1,
            "pz": 200,
            "po": 1,
            "np": 1,
            "fltt": 2,
            "invt": 2,
            "fid": "f62",
            "fs": fs,
            "fields": "f12,f14,f3,f62,f184,f66,f72,f78,f84,f204",
        },
        referer="https://quote.eastmoney.com/",
    )
    items = (data.get("data") or {}).get("diff") or []
    return [
        {
            "name": item.get("f14", ""),
            "code": item.get("f12", ""),
            "change_pct": item.get("f3", 0),
            "main_net": item.get("f62", 0),
            "main_pct": item.get("f184", 0),
            "super_large_net": item.get("f66", 0),
            "leader": item.get("f204", ""),
        }
        for item in items[:top_n]
    ]


def board_candidates(board_code: str, top_n: int = 10) -> list[dict[str, Any]]:
    """板块内仍可交易的主板候选：35元以下、未涨停、按盘中强度排序。"""
    data = _get_json(
        "https://push2.eastmoney.com/api/qt/clist/get",
        {
            "pn": 1,
            "pz": 200,
            "po": 1,
            "np": 1,
            "fltt": 2,
            "invt": 2,
            "fid": "f3",
            "fs": f"b:{board_code}",
            "fields": "f2,f3,f6,f8,f10,f12,f14,f20,f62,f184",
        },
        referer="https://quote.eastmoney.com/",
    )
    rows = []
    for item in (data.get("data") or {}).get("diff") or []:
        code, name = str(item.get("f12", "")), str(item.get("f14", ""))
        price = float(item.get("f2") or 0)
        pct = float(item.get("f3") or 0)
        turnover = float(item.get("f8") or 0)
        vol_ratio = float(item.get("f10") or 0)
        if (
            not _main_board(code)
            or not _non_st(name)
            or price <= 0
            or price > 35
            or pct < 1.5
            or pct >= 9.85
        ):
            continue
        score = (
            min(max(pct - 1.5, 0) / 8.35, 1) * 45
            + min(max(vol_ratio - 0.7, 0) / 2.3, 1) * 20
            + max(0, 1 - abs(turnover - 10) / 20) * 15
            + min(max(float(item.get("f184") or 0), 0) / 15, 1) * 20
        )
        rows.append(
            {
                "code": code,
                "name": name,
                "price": price,
                "pct": pct,
                "turnover": turnover,
                "vol_ratio": vol_ratio,
                "amount_yi": round(float(item.get("f6") or 0) / 1e8, 2),
                "main_net_yi": round(float(item.get("f62") or 0) / 1e8, 2),
                "main_pct": float(item.get("f184") or 0),
                "score": round(score, 1),
            }
        )
    return sorted(rows, key=lambda row: row["score"], reverse=True)[:top_n]


def _pool(endpoint: str, sort: str, date: str) -> list[dict[str, Any]]:
    data = _get_json(
        f"https://push2ex.eastmoney.com/{endpoint}",
        {
            "ut": ZTB_UT,
            "dpt": "wz.ztzt",
            "Pageindex": 0,
            "pagesize": 10000,
            "sort": sort,
            "date": date,
        },
        referer="https://quote.eastmoney.com/",
    )
    return (data.get("data") or {}).get("pool") or []


def limit_pools(date: str) -> dict[str, list[dict[str, Any]]]:
    raw = {
        "limit_up": _pool("getTopicZTPool", "fbt:asc", date),
        "broken": _pool("getTopicZBPool", "fbt:asc", date),
        "limit_down": _pool("getTopicDTPool", "fund:asc", date),
        "yesterday": _pool("getYesterdayZTPool", "zs:desc", date),
    }
    out: dict[str, list[dict[str, Any]]] = {}
    for kind, rows in raw.items():
        normalized = []
        for row in rows:
            code, name = str(row.get("c", "")), str(row.get("n", ""))
            if not _main_board(code) or not _non_st(name):
                continue
            normalized.append(
                {
                    "code": code,
                    "name": name,
                    "price": (row.get("p") or 0) / 1000,
                    "pct": row.get("zdp", 0),
                    "turnover": row.get("hs", 0),
                    "industry": row.get("hybk", ""),
                    "limit_days": row.get("lbc", row.get("ylbc", 0)),
                    "seal_fund": row.get("fund", 0),
                    "break_times": row.get("zbc", row.get("oc", 0)),
                    "first_seal": row.get("fbt", row.get("yfbt", "")),
                }
            )
        out[kind] = normalized
    return out


def ths_hot(date_iso: str) -> list[dict[str, Any]]:
    data = _get_json(
        f"http://zx.10jqka.com.cn/event/api/getharden/date/{date_iso}/orderby/date/orderway/desc/charset/GBK/",
    )
    rows = data.get("data") or []
    if isinstance(rows, dict):
        rows = rows.get("list") or rows.get("data") or []
    output = []
    for row in rows:
        code, name = str(row.get("code", "")), str(row.get("name", ""))
        if not _main_board(code) or not _non_st(name):
            continue
        def num(key: str) -> float:
            try:
                return float(row.get(key) or 0)
            except (TypeError, ValueError):
                return 0.0
        output.append(
            {
                "code": code,
                "name": name,
                "reason": str(row.get("reason") or ""),
                # 该接口在 2026-08 已缩减为题材归因字段，行情稍后由腾讯批量补齐。
                "price": num("close"),
                "pct": num("zhangfu"),
                "turnover": num("huanshou"),
                "amount": num("chengjiaoe"),
                "dde": num("ddejingliang"),
            }
        )
    return output


def cls_telegraph(page_size: int = 50) -> list[dict[str, Any]]:
    params = {
        "appName": "CailianpressWeb",
        "os": "web",
        "sv": "7.7.5",
        "last_time": "",
        "refresh_type": "1",
        "rn": str(page_size),
    }
    query = "&".join(f"{key}={params[key]}" for key in sorted(params))
    sign = hashlib.md5(hashlib.sha1(query.encode()).hexdigest().encode()).hexdigest()
    data = _get_json(
        f"https://www.cls.cn/v1/roll/get_roll_list?{query}&sign={sign}",
        referer="https://www.cls.cn/",
    )
    rows = []
    for item in (data.get("data") or {}).get("roll_data") or []:
        timestamp = item.get("ctime")
        rows.append(
            {
                "title": item.get("title") or item.get("brief") or "",
                "content": item.get("content") or item.get("brief") or "",
                "time": datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S") if timestamp else "",
            }
        )
    return rows


def eastmoney_global_news(page_size: int = 50) -> list[dict[str, Any]]:
    data = _get_json(
        "https://np-weblist.eastmoney.com/comm/web/getFastNewsList",
        {
            "client": "web",
            "biz": "web_724",
            "fastColumn": "102",
            "sortEnd": "",
            "pageSize": page_size,
            "req_trace": f"premarket-{int(time.time())}",
        },
        referer="https://kuaixun.eastmoney.com/",
    )
    return [
        {
            "title": item.get("title", ""),
            "summary": (item.get("summary") or "")[:240],
            "time": item.get("showTime", ""),
        }
        for item in (data.get("data") or {}).get("fastNewsList") or []
    ]


def previous_trade_day(day: datetime) -> datetime:
    candidate = day - timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate -= timedelta(days=1)
    return candidate


def _latest_local_candidates() -> dict[str, dict[str, Any]]:
    reports = sorted((ROOT / "reports").glob("limitup-*.csv"), reverse=True)
    if not reports:
        return {}
    with reports[0].open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return {str(row["code"]).zfill(6): row for row in rows}


def rank_watchlist(
    hot: list[dict[str, Any]],
    pools: dict[str, list[dict[str, Any]]],
    local: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    limit_codes = {row["code"] for row in pools["limit_up"]}
    broken_codes = {row["code"] for row in pools["broken"]}
    token_counts: dict[str, int] = {}
    for row in hot:
        if row.get("_origin") != "hot":
            continue
        for token in re.split(r"[+、；;/|]", row["reason"]):
            token = token.strip()
            if 2 <= len(token) <= 14:
                token_counts[token] = token_counts.get(token, 0) + 1

    ranked = []
    for row in hot:
        if row["code"] in limit_codes or row["price"] <= 0 or row["price"] > 35:
            continue
        pct = row["pct"]
        if pct < 2.0 or pct >= 9.85:
            continue
        turnover = row["turnover"]
        amount_yi = row["amount"] / 1e8 if row["amount"] else 0
        theme_heat = max(
            (token_counts.get(token.strip(), 0) for token in re.split(r"[+、；;/|]", row["reason"])),
            default=0,
        )
        local_row = local.get(row["code"])
        local_score = float(local_row["model_score"]) if local_row else 0.0
        score = (
            min(max(pct - 2, 0) / 7.5, 1) * 35
            + max(0, 1 - abs(turnover - 10) / 18) * 12
            + min(math.log1p(max(amount_yi, 0)) / math.log(31), 1) * 12
            + min(max((row.get("vol_ratio", 0) - 0.8) / 2.2, 0), 1) * 10
            + min(theme_heat / 6, 1) * 13
            + local_score / 100 * 18
            + (8 if row["code"] in broken_codes else 0)
        )
        public_row = {key: value for key, value in row.items() if not key.startswith("_")}
        ranked.append(
            {
                **public_row,
                "intraday_score": round(score, 1),
                "theme_heat": theme_heat,
                "broken_board": row["code"] in broken_codes,
                "local_model_score": local_score or None,
                "local_industry": local_row.get("industry") if local_row else "",
            }
        )
    return sorted(ranked, key=lambda row: row["intraday_score"], reverse=True)[:15]


def publish_web_payload(result: dict[str, Any]) -> Path:
    pools = result.get("pools") or {}
    limit_up = sorted(
        [row for row in pools.get("limit_up", []) if row.get("price", 0) <= 35],
        key=lambda row: (-int(row.get("limit_days") or 0), -float(row.get("seal_fund") or 0)),
    )[:12]
    broken = sorted(
        [row for row in pools.get("broken", []) if row.get("price", 0) <= 35],
        key=lambda row: -float(row.get("pct") or 0),
    )[:12]
    payload = {
        "asOf": result.get("as_of", ""),
        "indices": result.get("indices") or {},
        "sentiment": result.get("sentiment") or {},
        "industryFunds": result.get("industry_fund_flow") or [],
        "conceptFunds": result.get("concept_fund_flow") or [],
        "highBoards": limit_up,
        "brokenBoards": broken,
        "watchlist": result.get("watchlist") or [],
        "errors": result.get("errors") or {},
        "rules": {
            "market": "沪深主板",
            "maxPrice": 35,
            "exclude": ["科创板", "创业板", "北交所", "ST", "退市整理"],
        },
    }
    path = ROOT / "web" / "public" / "data" / "intraday.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) > 1 and sys.argv[1] == "boards":
        boards = {"PCB": "BK0877", "半导体": "BK0917", "通信技术": "BK1650", "种植业": "BK1261"}
        output: dict[str, Any] = {"as_of": datetime.now().astimezone().isoformat(timespec="seconds"), "boards": {}, "errors": {}}
        for name, code in boards.items():
            try:
                output["boards"][name] = board_candidates(code, 10)
            except Exception as exc:
                output["errors"][name] = f"{type(exc).__name__}: {exc}"
        json.dump(output, sys.stdout, ensure_ascii=False, indent=2)
        print()
        return 0
    if len(sys.argv) > 1 and sys.argv[1] == "premarket":
        now = datetime.now().astimezone()
        prior = previous_trade_day(now)
        output: dict[str, Any] = {
            "as_of": now.isoformat(timespec="seconds"),
            "baseline_date": prior.strftime("%Y-%m-%d"),
            "errors": {},
        }
        calls = {
            "indices": lambda: tencent_quotes(["sh000001", "sz399001", "sh000300"]),
            "industry_strength": lambda: industry_comparison(20),
            "industry_fund_flow": lambda: board_fund_flow("industry", 20),
            "concept_fund_flow": lambda: board_fund_flow("concept", 20),
            "pools": lambda: limit_pools(prior.strftime("%Y%m%d")),
            "cls_news": lambda: cls_telegraph(50),
            "eastmoney_news": lambda: eastmoney_global_news(50),
        }
        for name, call in calls.items():
            try:
                output[name] = call()
            except Exception as exc:
                output[name] = {} if name in {"indices", "pools"} else []
                output["errors"][name] = f"{type(exc).__name__}: {exc}"
        pools = output.get("pools") or {}
        limit_up = pools.get("limit_up") or []
        broken = pools.get("broken") or []
        output["sentiment"] = {
            "limit_up_count": len(limit_up),
            "broken_count": len(broken),
            "break_rate": round(len(broken) / (len(limit_up) + len(broken)) * 100, 1) if limit_up or broken else 0,
            "limit_down_count": len(pools.get("limit_down") or []),
            "max_height": max((int(row.get("limit_days") or 1) for row in limit_up), default=0),
        }
        report_path = ROOT / "reports" / f"premarket-{now.strftime('%Y-%m-%d')}.json"
        report_path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        output["output_path"] = str(report_path)
        json.dump(output, sys.stdout, ensure_ascii=False, indent=2)
        print()
        return 0
    if len(sys.argv) > 1 and sys.argv[1] == "publish-cache":
        reports = sorted((ROOT / "reports").glob("intraday-*.json"), reverse=True)
        if not reports:
            raise FileNotFoundError("没有可发布的盘中缓存，请先运行一次盘中分析")
        cached = json.loads(reports[0].read_text(encoding="utf-8"))
        print(publish_web_payload(cached))
        return 0
    now = datetime.now().astimezone()
    date_compact = now.strftime("%Y%m%d")
    date_iso = now.strftime("%Y-%m-%d")
    result: dict[str, Any] = {"as_of": now.isoformat(timespec="seconds"), "errors": {}}

    calls = {
        "indices": lambda: tencent_quotes(["sh000001", "sz399001", "sh000300"]),
        "industry_strength": lambda: industry_comparison(15),
        "industry_fund_flow": lambda: board_fund_flow("industry", 15),
        "concept_fund_flow": lambda: board_fund_flow("concept", 15),
        "pools": lambda: limit_pools(date_compact),
        "hot": lambda: ths_hot(date_iso),
    }
    for name, call in calls.items():
        try:
            result[name] = call()
        except Exception as exc:
            result[name] = {} if name in {"indices", "pools"} else []
            result["errors"][name] = f"{type(exc).__name__}: {exc}"

    # 同花顺热点端点当前只返回代码、名称、题材；用腾讯一次批量补实时价量。
    hot = result.get("hot") or []
    if hot:
        try:
            live = tencent_quotes([row["code"] for row in hot])
            for row in hot:
                quote = live.get(row["code"]) or {}
                row.update(
                    {
                        "name": quote.get("name") or row["name"],
                        "price": quote.get("price", 0),
                        "pct": quote.get("change_pct", 0),
                        "turnover": quote.get("turnover_pct", 0),
                        "amount": quote.get("amount_wan", 0) * 10000,
                        "vol_ratio": quote.get("vol_ratio", 0),
                        "limit_up": quote.get("limit_up", 0),
                    }
                )
        except Exception as exc:
            result["errors"]["hot_quotes"] = f"{type(exc).__name__}: {exc}"

    pools = result.get("pools") or {"limit_up": [], "broken": [], "limit_down": [], "yesterday": []}
    for key in ("limit_up", "broken", "limit_down", "yesterday"):
        pools.setdefault(key, [])
    zt_n, zb_n = len(pools["limit_up"]), len(pools["broken"])
    ladder: dict[str, int] = {}
    for row in pools["limit_up"]:
        level = str(row.get("limit_days") or 1)
        ladder[level] = ladder.get(level, 0) + 1
    result["sentiment"] = {
        "limit_up_count": zt_n,
        "broken_count": zb_n,
        "break_rate": round(zb_n / (zt_n + zb_n) * 100, 1) if zt_n + zb_n else 0,
        "limit_down_count": len(pools["limit_down"]),
        "max_height": max((int(row.get("limit_days") or 1) for row in pools["limit_up"]), default=0),
        "ladder": ladder,
    }
    local = _latest_local_candidates()
    for row in hot:
        row["_origin"] = "hot"
    hot_by_code = {row["code"]: row for row in hot}
    watch_seed = list(hot)
    seen = set(hot_by_code)
    for code, row in local.items():
        if code in seen:
            continue
        watch_seed.append(
            {
                "code": code,
                "name": row.get("name", ""),
                "reason": row.get("reason", "本地收盘模型候选"),
                "price": 0.0,
                "pct": 0.0,
                "turnover": 0.0,
                "amount": 0.0,
                "dde": 0.0,
                "_origin": "local",
            }
        )
        seen.add(code)
    for row in pools["broken"]:
        code = row["code"]
        if code in seen:
            continue
        watch_seed.append(
            {
                "code": code,
                "name": row["name"],
                "reason": f"炸板回封观察+{row.get('industry', '')}",
                "price": row["price"],
                "pct": row["pct"],
                "turnover": row["turnover"],
                "amount": 0.0,
                "dde": 0.0,
                "_origin": "broken",
            }
        )
        seen.add(code)
    missing_codes = [row["code"] for row in watch_seed if not row.get("price")]
    if missing_codes:
        try:
            live = tencent_quotes(missing_codes)
            for row in watch_seed:
                quote = live.get(row["code"]) or {}
                if not quote:
                    continue
                row.update(
                    {
                        "name": quote.get("name") or row["name"],
                        "price": quote.get("price", row.get("price", 0)),
                        "pct": quote.get("change_pct", row.get("pct", 0)),
                        "turnover": quote.get("turnover_pct", row.get("turnover", 0)),
                        "amount": quote.get("amount_wan", 0) * 10000,
                        "vol_ratio": quote.get("vol_ratio", 0),
                        "limit_up": quote.get("limit_up", 0),
                    }
                )
        except Exception as exc:
            result["errors"]["watch_quotes"] = f"{type(exc).__name__}: {exc}"
    result["watchlist"] = rank_watchlist(watch_seed, pools, local)
    output_path = ROOT / "reports" / f"intraday-{date_iso}.json"
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    web_output_path = publish_web_payload(result)
    result["output_path"] = str(output_path)
    result["web_output_path"] = str(web_output_path)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
