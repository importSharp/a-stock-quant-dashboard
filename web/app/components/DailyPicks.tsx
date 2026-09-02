type PriceLevels = {
  zoneLow: number;
  zoneHigh: number;
  breakout: number;
  chaseCap: number;
  invalidation: number;
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

const yuan = (value: number) => `¥${Number(value || 0).toFixed(2)}`;

function Levels({ row }: { row: DailyPickRow }) {
  const levels = row.priceLevels;
  return <div className="daily-levels">
    <div><span>9:35确认</span><strong>{yuan(row.confirmedPrice)}</strong></div>
    <div><span>参考区间</span><strong>{yuan(levels.zoneLow)}～{yuan(levels.zoneHigh)}</strong></div>
    <div><span>突破确认</span><strong>{yuan(levels.breakout)}</strong></div>
    <div className="warn"><span>禁止追高</span><strong>{yuan(levels.chaseCap)}</strong></div>
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

export function DailyPicks({ pick, asOf }: { pick?: DailyPick; asOf?: string }) {
  if (!pick || pick.status !== "selected") {
    const label = pick?.status === "waiting" ? "WAITING FOR 09:35" : pick?.status === "market_closed" ? "MARKET CLOSED" : "NO QUALIFIED PICK";
    return <section className="daily-picks daily-empty">
      <div><span className="asd-kicker">{label}</span><h2>9:35 今日研究候选</h2><p>{pick?.message || "正在等待行情快照。"}</p></div>
      <aside><strong>3 + 2</strong><span>最多3只核心 · 2只观察<br />数据不完整时不强行推荐</span></aside>
    </section>;
  }
  const rows = [...pick.core, ...pick.watch];
  return <section className="daily-picks">
    <header className="daily-picks-title">
      <div><span className="asd-kicker">FROZEN DAILY SHORTLIST</span><h2>9:35 今日研究候选</h2><p>名单当日固定，盘中只更新价格状态。进入区间不等于必须成交。</p></div>
      <div><strong>{pick.core.length}</strong><span>核心</span><i>+</i><strong>{pick.watch.length}</strong><span>观察</span></div>
    </header>
    {rows.length ? <div className="daily-picks-grid">
      <PickCard row={rows[0]} lead />
      <div className="daily-picks-rail">{rows.slice(1).map((row) => <PickCard row={row} key={row.code} />)}</div>
    </div> : null}
    <div className="daily-disclosure"><span>生成 {pick.generatedAt?.replace("T", " ").slice(0, 19) || "—"} · 快照 {asOf?.replace("T", " ").slice(0, 19) || "—"}</span><strong>{pick.disclosure}</strong></div>
  </section>;
}
