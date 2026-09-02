"use client";

import { useEffect, useMemo, useState } from "react";
import { DailyPicks, type DailyPick } from "./DailyPicks";

type AnyRow = Record<string, any>;
type Snapshot = {
  meta: { version: string; asOf: string; policy: string; filters: string };
  endpointStatus: AnyRow[];
  indices: Record<string, AnyRow>;
  industryStrength: AnyRow[];
  industryFunds: AnyRow[];
  conceptFunds: AnyRow[];
  pools: Record<string, AnyRow[]>;
  sentiment: AnyRow;
  boardCandidates: { name: string; code: string; rows: AnyRow[] }[];
  themeCandidates: { name: string; code: string; source: string; rows: AnyRow[] }[];
  hot: AnyRow[];
  dailyPick?: DailyPick;
};

const tabs = ["竞价", "盘中", "板块", "候选"] as const;
const tabCodes = ["09:15", "LIVE", "TOP", "10×N"];
const money = (value: number) => (value >= 0 ? "+" : "") + (Number(value || 0) / 1e8).toFixed(2) + "亿";
const pct = (value: number) => (value > 0 ? "+" : "") + Number(value || 0).toFixed(2) + "%";

function Empty({ text = "当前端点没有返回数据" }: { text?: string }) {
  return <p className="asd-empty">{text}</p>;
}

function Source({ children }: { children: React.ReactNode }) {
  return <span className="asd-source">来源：{children}</span>;
}

function StockRows({ rows }: { rows: AnyRow[] }) {
  if (!rows?.length) return <Empty />;
  return <div className="asd-stock-list">{rows.slice(0, 10).map((row, index) => (
    <div className="asd-stock" key={row.code + "-" + index}>
      <span>{String(index + 1).padStart(2, "0")}</span>
      <div><strong>{row.name}</strong><small>{row.code} · {row.industry || "主板"}</small></div>
      <b className={(row.pct || 0) >= 0 ? "up" : "down"}>{pct(row.pct)}</b>
      <em>¥{Number(row.price || 0).toFixed(2)}</em>
      <small>量比 {Number(row.vol_ratio || 0).toFixed(2)} · 换手 {Number(row.turnover || 0).toFixed(1)}%</small>
    </div>
  ))}</div>;
}

function SectorStocks({ rows }: { rows: AnyRow[] }) {
  if (!rows.length) return <Empty text="当前仅识别到领涨股，板块成分端点恢复后会补齐多股" />;
  return <div className="asd-sector-stocks">{rows.slice(0, 5).map((row, index) => (
    <div key={`${row.code}-${row.role}-${index}`}>
      <span>{row.role}</span>
      <strong>{row.name}</strong>
      <small>{row.code}</small>
      <b className={(row.pct || 0) >= 0 ? "up" : "down"}>{pct(row.pct)}</b>
    </div>
  ))}</div>;
}

export function AStockDataDashboard() {
  const [data, setData] = useState<Snapshot | null>(null);
  const [tab, setTab] = useState<(typeof tabs)[number]>("竞价");
  const [error, setError] = useState("");
  const [refreshing, setRefreshing] = useState(false);

  async function refresh() {
    setRefreshing(true);
    try {
      const response = await fetch("/api/snapshot?t=" + Date.now(), { cache: "no-store" });
      if (!response.ok) throw new Error("HTTP " + response.status);
      setData(await response.json());
      setError("");
    } catch (reason) {
      setError("快照读取失败：" + String(reason));
    } finally {
      setRefreshing(false);
    }
  }

  useEffect(() => {
    refresh();
    const timer = window.setInterval(refresh, 15000);
    return () => window.clearInterval(timer);
  }, []);

  const failures = useMemo(() => data?.endpointStatus?.filter((item) => item.status !== "ok") || [], [data]);
  const healthy = (data?.endpointStatus?.length || 0) - failures.length;
  const auctionRows = useMemo(() => (data?.hot || [])
    .filter((row) => row.price > 0 && row.price <= 35 && row.pct >= 0.5 && row.pct < 9.85)
    .sort((a, b) => (b.pct * 2 + b.vol_ratio) - (a.pct * 2 + a.vol_ratio))
    .slice(0, 20), [data]);
  const candidateBoards = data?.boardCandidates?.length ? data.boardCandidates : data?.themeCandidates || [];
  const sectorClusters = useMemo(() => {
    const pools = data?.pools || {};
    const tagged = [
      ...(pools.limit_up || []).map((row) => ({ ...row, role: "涨停核心", roleOrder: 1 })),
      ...(pools.broken || []).map((row) => ({ ...row, role: "炸板回封", roleOrder: 2 })),
      ...(pools.yesterday || []).map((row) => ({ ...row, role: "昨板观察", roleOrder: 4 })),
    ];
    return (data?.industryStrength || []).slice(0, 8).map((board) => {
      const exact = candidateBoards.find((item) => item.code === board.code || item.name === board.name);
      const tradable = (exact?.rows || []).map((row) => ({ ...row, role: "未板候选", roleOrder: 3 }));
      const related = tagged.filter((row) => row.industry === board.name);
      const seen = new Set<string>();
      const rows = [...related, ...tradable]
        .sort((a, b) => (a.roleOrder - b.roleOrder) || (Number(b.pct || 0) - Number(a.pct || 0)))
        .filter((row) => row.code && !seen.has(row.code) && seen.add(row.code))
        .slice(0, 5);
      return { ...board, rows };
    });
  }, [data, candidateBoards]);

  return <main className="asd-shell">
    <header className="asd-header">
      <div className="asd-brand"><span>AS</span><div><small>A-STOCK-DATA · LIMIT-UP RADAR</small><h1>竞价与盘中 <b>作战台</b></h1></div></div>
      <div className="asd-header-actions">
        <span className="asd-session">竞价 · 盘中 · 板块 · 候选</span>
        <button className="asd-fresh" type="button" onClick={refresh} disabled={refreshing}>
          <i /><div><strong>{refreshing ? "正在刷新" : data ? "数据链路在线" : "正在载入"}</strong><small>{data?.meta?.asOf?.replace("T", " ").slice(0, 19) || "—"}</small></div><em>↻</em>
        </button>
      </div>
    </header>

    <section className="asd-contract">
      <div className="asd-hero-copy"><span className="asd-kicker">FOUR CORE WORKSPACES</span><h2>只看最影响交易的，<em>四组实时信号。</em></h2><p>9:15～9:25集合竞价、盘中涨停与炸板、强势板块排名、每个强势板块候选前10。</p><div className="asd-hero-tags"><span>沪深主板</span><span>价格 ≤ 35</span><span>排除 ST / 退市</span><span>15秒读取快照</span></div></div>
      <div className="asd-live-summary">
        <div><small>涨停</small><strong className="up">{data?.sentiment?.limitUp ?? "—"}</strong><span>只</span></div>
        <div><small>炸板率</small><strong>{data?.sentiment?.breakRate ?? "—"}</strong><span>%</span></div>
        <div><small>端点健康</small><strong>{healthy}</strong><span>/{data?.endpointStatus?.length || 0}</span></div>
        <p><i /> a-stock-data v{data?.meta?.version || "3.7.1"} · 自动刷新</p>
      </div>
    </section>

    <DailyPicks pick={data?.dailyPick} asOf={data?.meta?.asOf} />

    {error ? <div className="asd-alert">{error}</div> : null}
    {failures.length ? <details className="asd-alert warn"><summary><strong>{failures.length} 个端点暂不可用</strong><span>点击查看</span></summary><div>{failures.map((item) => <span key={item.key}>{item.label}：{item.error}</span>)}</div></details> : null}

    <nav className="asd-tabs asd-tabs-four" aria-label="四个核心功能">
      {tabs.map((item, index) => <button className={tab === item ? "active" : ""} onClick={() => setTab(item)} key={item}><small>{tabCodes[index]}</small><span>{item}</span></button>)}
    </nav>

    {tab === "竞价" && <>
      <section className="asd-auction-summary">
        <div><span>未涨停观察</span><strong>{auctionRows.length}</strong><small>只</small></div>
        <div><span>涨停池</span><strong>{data?.sentiment?.limitUp ?? "—"}</strong><small>只</small></div>
        <div><span>炸板率</span><strong>{data?.sentiment?.breakRate ?? "—"}</strong><small>%</small></div>
        <p>按实时涨幅与量比排序，仅保留35元以下、尚未涨停的沪深主板股票。9:25后结合板块强度复核，不把单只高开直接等同于买入信号。</p>
      </section>
      <section className="asd-two">
        <article className="asd-panel"><div className="asd-title"><div><span className="asd-kicker">AUCTION WATCH</span><h2>竞价后未涨停观察池</h2></div><Source>同花顺热点 + 腾讯行情</Source></div><StockRows rows={auctionRows} /></article>
        <article className="asd-panel"><div className="asd-title"><div><span className="asd-kicker">BOARD CONFIRMATION</span><h2>竞价板块确认</h2></div><Source>{data?.industryStrength?.[0]?.source || "东方财富行业板块"}</Source></div>{(data?.industryStrength || []).length ? <div className="asd-ranking">{data!.industryStrength.slice(0, 12).map((row, i) => <div key={row.code}><span>{String(i + 1).padStart(2, "0")}</span><strong>{row.name}</strong><small>{row.up_count}涨 / {row.down_count}跌 · 领涨 {row.leader || "—"}</small><b className={row.change_pct >= 0 ? "up" : "down"}>{pct(row.change_pct)}</b></div>)}</div> : <Empty />}</article>
      </section>
    </>}

    {tab === "盘中" && <>
      <section className="asd-index-grid">
        {Object.entries(data?.indices || {}).map(([key, row]) => <article key={key}><Source>腾讯行情</Source><small>{row.name || key}</small><strong>{Number(row.price || 0).toFixed(2)}</strong><b className={row.change_pct >= 0 ? "up" : "down"}>{pct(row.change_pct)}</b></article>)}
        <article className="sentiment"><Source>东方财富涨停专题</Source><small>涨停 / 炸板</small><strong>{data?.sentiment?.limitUp ?? "—"} <i>/</i> {data?.sentiment?.broken ?? "—"}</strong><b>最高 {data?.sentiment?.maxHeight ?? "—"} 板</b></article>
      </section>
      <section className="asd-three">
        <article className="asd-panel"><div className="asd-title"><h2>涨停池</h2><Source>东方财富</Source></div><StockRows rows={data?.pools?.limit_up || []} /></article>
        <article className="asd-panel"><div className="asd-title"><h2>炸板回封观察</h2><Source>东方财富</Source></div><StockRows rows={data?.pools?.broken || []} /></article>
        <article className="asd-panel"><div className="asd-title"><h2>昨涨停表现</h2><Source>东方财富</Source></div><StockRows rows={data?.pools?.yesterday || []} /></article>
      </section>
    </>}

    {tab === "板块" && <>
      <section className="asd-panel asd-spaced-panel"><div className="asd-title"><div><span className="asd-kicker">INDUSTRY STRENGTH</span><h2>实时板块涨幅排名</h2></div><Source>{data?.industryStrength?.[0]?.source || "东方财富行业板块"}</Source></div>{(data?.industryStrength || []).length ? <div className="asd-ranking">{data!.industryStrength.slice(0, 20).map((row, i) => <div key={row.code}><span>{String(i + 1).padStart(2, "0")}</span><strong>{row.name}</strong><small>{row.up_count}涨 / {row.down_count}跌 · 领涨 {row.leader || "—"}</small><b className={row.change_pct >= 0 ? "up" : "down"}>{pct(row.change_pct)}</b></div>)}</div> : <Empty />}</section>
      <section className="asd-panel asd-spaced-panel"><div className="asd-title"><div><span className="asd-kicker">SECTOR BREADTH</span><h2>强势板块多股结构</h2><p className="asd-title-note">每个板块展示5只用于快速确认联动；完整未涨停候选仍在“候选”页查看前10。</p></div><Source>a-stock-data 板块成分 + 打板池</Source></div>{sectorClusters.length ? <div className="asd-sector-grid">{sectorClusters.map((board, index) => <article key={`${board.code}-${board.name}`}><header><span>{String(index + 1).padStart(2, "0")}</span><div><strong>{board.name}</strong><small>{board.code}</small></div><b className={board.change_pct >= 0 ? "up" : "down"}>{pct(board.change_pct)}</b></header><SectorStocks rows={board.rows} /></article>)}</div> : <Empty />}</section>
      <section className="asd-two">
        {[["行业主力资金", data?.industryFunds], ["概念主力资金", data?.conceptFunds]].map(([title, rows]) => <article className="asd-panel" key={String(title)}><div className="asd-title"><h2>{String(title)}</h2><Source>东方财富板块资金</Source></div>{(rows as AnyRow[] || []).length ? <div className="asd-flow">{(rows as AnyRow[]).slice(0, 15).map((row, i) => <div key={row.code}><span>{i + 1}</span><strong>{row.name}</strong><small>{pct(row.change_pct)} · {row.leader || ""}</small><b className={row.main_net >= 0 ? "up" : "down"}>{money(row.main_net)}</b></div>)}</div> : <Empty />}</article>)}
      </section>
    </>}

    {tab === "候选" && <section className="asd-panel"><div className="asd-title"><div><span className="asd-kicker">TOP 10 PER STRONG BOARD</span><h2>强势板块候选前10</h2></div><Source>{data?.boardCandidates?.length ? "东方财富板块成分" : "同花顺题材归因 + 腾讯行情"}</Source></div>{candidateBoards.length ? <div className="asd-board-grid">{candidateBoards.map((board) => <article key={board.code + "-" + board.name}><h3>{board.name}<small>{board.code}</small></h3><StockRows rows={board.rows} /></article>)}</div> : <Empty text="板块或题材端点暂未返回足够候选" />}</section>}

    <footer className="asd-footer"><span>{data?.meta?.filters || "沪深主板 · 35元以下 · 排除ST"}</span><span>数据仅供量化研究，不构成投资建议</span></footer>
  </main>;
}
