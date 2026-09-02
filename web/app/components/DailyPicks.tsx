"use client";

import { useState } from "react";

type PriceLevels = {
  zoneLow: number;
  zoneHigh: number;
  breakout: number;
  chaseCap: number;
  invalidation: number;
  takeProfitLow: number;
  takeProfitHigh: number;
  exitTiming: string;
  priceSource: string;
  degraded?: boolean;
};

export type DailyPickRow = {
  rank: number;
  tier: "核心" | "观察";
  code: string;
  name: string;
  sector: string;
  score: number;
  confirmedPrice: number;
  currentPrice: number;
  changePct: number;
  limitPrice: number;
  distanceToLimit: number;
  untouchedAtSelection: boolean;
  liveState: string;
  reasons: string[];
  scoreBreakdown: Record<string, number>;
  priceLevels: PriceLevels;
};

export type DailyPick = {
  date: string;
  generatedAt: string | null;
  status: "waiting" | "selected" | "no_pick" | "source_error" | "market_closed";
  message: string;
  frozen: boolean;
  core: DailyPickRow[];
  watch: DailyPickRow[];
  disclosure: string;
};

export type ConfirmedPick = {
  kind: "limit_up" | "broken";
  signal: "封板" | "炸板";
  code: string;
  name: string;
  sector: string;
  price: number;
  changePct: number;
  limitDays: number;
  breakTimes: number;
  action: string;
  plan: {
    buyLabel: string;
    buyLow: number;
    buyHigh: number;
    takeProfitLow: number;
    takeProfitHigh: number;
    invalidation: number;
    exitTiming: string;
  };
};

const yuan = (value: number) => `¥${Number(value || 0).toFixed(2)}`;

function Levels({ row }: { row: DailyPickRow }) {
  const levels = row.priceLevels;
  return <div className="daily-levels">
    <div><span>9:35确认</span><strong>{yuan(row.confirmedPrice)}</strong></div>
    <div><span>参考区间</span><strong>{yuan(levels.zoneLow)}～{yuan(levels.zoneHigh)}</strong></div>
    <div><span>突破确认</span><strong>{yuan(levels.breakout)}</strong></div>
    <div className="warn"><span>禁止追高</span><strong>{yuan(levels.chaseCap)}</strong></div>
    <div className="profit"><span>T+1参考止盈</span><strong>{yuan(levels.takeProfitLow)}～{yuan(levels.takeProfitHigh)}</strong></div>
    <div className="risk"><span>结构失效</span><strong>{yuan(levels.invalidation)}</strong></div>
  </div>;
}

function PickCard({ row, lead = false }: { row: DailyPickRow; lead?: boolean }) {
  const stateClass = row.liveState.includes("失效") || row.liveState.includes("追高") ? "risk" : row.liveState.includes("进入") || row.liveState.includes("突破") ? "ready" : "waiting";
  return <article className={`daily-pick-card ${lead ? "lead" : ""}`}>
    <header>
      <div className="daily-rank"><small>{row.tier === "核心" ? "CORE" : "WATCH"}</small><strong>{String(row.rank).padStart(2, "0")}</strong></div>
      <div className="daily-identity"><span>{row.tier}候选 · {row.sector}</span><h3>{row.name}<small>{row.code}</small></h3></div>
      <div className="daily-score"><small>研究分</small><strong>{row.score.toFixed(1)}</strong></div>
    </header>
    <div className="daily-now"><span>最新价 <b>{yuan(row.currentPrice)}</b></span><em className={stateClass}>{row.liveState}</em></div>
    <Levels row={row} />
    <ul>{row.reasons.slice(0, 3).map((reason) => <li key={reason}>{reason}</li>)}</ul>
    <div className="daily-breakdown">{Object.entries(row.scoreBreakdown).map(([label, value]) => <span key={label}>{label}<b>{Number(value).toFixed(1)}</b></span>)}</div>
    <footer>{row.priceLevels.priceSource}{row.priceLevels.degraded ? " · 降级估算" : ""}</footer>
  </article>;
}

function ConfirmedCard({ row }: { row: ConfirmedPick }) {
  return <article className={`confirmed-card ${row.kind === "broken" ? "broken" : "sealed"}`}>
    <header><span>{row.signal}</span><div><h3>{row.name}<small>{row.code}</small></h3><p>{row.sector} · {row.limitDays || 1}板{row.breakTimes ? ` · 炸板${row.breakTimes}次` : ""}</p></div><strong>{row.changePct > 0 ? "+" : ""}{row.changePct.toFixed(2)}%</strong></header>
    <div className="confirmed-action">{row.action}</div>
    <div className="confirmed-levels">
      <div><span>现价</span><strong>{yuan(row.price)}</strong></div>
      <div><span>{row.plan.buyLabel}</span><strong>{yuan(row.plan.buyLow)}～{yuan(row.plan.buyHigh)}</strong></div>
      <div className="profit"><span>T+1参考止盈</span><strong>{yuan(row.plan.takeProfitLow)}～{yuan(row.plan.takeProfitHigh)}</strong></div>
      <div className="risk"><span>T+1结构失效</span><strong>{yuan(row.plan.invalidation)}</strong></div>
    </div>
  </article>;
}

function UntouchedPool({ pick }: { pick?: DailyPick }) {
  if (!pick || pick.status !== "selected") {
    const label = pick?.status === "waiting" ? "WAITING FOR 09:35" : pick?.status === "market_closed" ? "MARKET CLOSED" : "NO QUALIFIED PICK";
    return <div className="daily-empty">
      <div><span className="asd-kicker">{label}</span><h2>9:35 未触板涨停候选</h2><p>{pick?.message || "正在等待行情快照。"}</p></div>
      <aside><strong>3 + 2</strong><span>最多3只核心 · 2只观察<br />数据不完整时不强行推荐</span></aside>
    </div>;
  }
  const rows = [...pick.core, ...pick.watch];
  return <>
    {rows.length ? <div className="daily-picks-grid">
      <PickCard row={rows[0]} lead />
      <div className="daily-picks-rail">{rows.slice(1).map((row) => <PickCard row={row} key={row.code} />)}</div>
    </div> : null}
  </>;
}

export function DailyPicks({ pick, confirmed = [], asOf }: { pick?: DailyPick; confirmed?: ConfirmedPick[]; asOf?: string }) {
  const [pool, setPool] = useState<"untouched" | "confirmed">("untouched");
  return <section className="daily-picks">
    <header className="daily-picks-title">
      <div><span className="asd-kicker">DUAL-POOL LIMIT-UP RADAR</span><h2>涨停双池策略</h2><p>{pool === "untouched" ? "生成时从未触板，用于当天仍可成交的潜力观察。" : "封板和炸板只用于确认强度；封板中不排队追买。"}</p></div>
      <nav className="daily-pool-tabs" aria-label="涨停候选池切换">
        <button type="button" className={pool === "untouched" ? "active" : ""} onClick={() => setPool("untouched")}><strong>{(pick?.core?.length || 0) + (pick?.watch?.length || 0)}</strong><span>未触板潜力</span></button>
        <button type="button" className={pool === "confirmed" ? "active" : ""} onClick={() => setPool("confirmed")}><strong>{confirmed.length}</strong><span>已触板强势</span></button>
      </nav>
    </header>
    {pool === "untouched" ? <UntouchedPool pick={pick} /> : confirmed.length ? <div className="confirmed-grid">{confirmed.map((row) => <ConfirmedCard key={`${row.kind}-${row.code}`} row={row} />)}</div> : <div className="daily-empty"><div><span className="asd-kicker">NO CONFIRMED SIGNAL</span><h2>当前没有已触板强势股</h2><p>涨停池或炸板池暂无可用数据。</p></div></div>}
    <div className="daily-disclosure"><span>生成 {pick?.generatedAt?.replace("T", " ").slice(0, 19) || "—"} · 快照 {asOf?.replace("T", " ").slice(0, 19) || "—"}</span><strong>买卖价格均为规则参考区间，未经完整样本外回测；A股新买仓位下一交易日起才能执行卖出计划。</strong></div>
  </section>;
}
