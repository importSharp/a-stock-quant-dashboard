"use client";

import { useEffect, useMemo, useState } from "react";
import { DailyPicks, type ConfirmedPick, type DailyPick } from "./DailyPicks";
import { FunctionGuide } from "./FunctionGuide";

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
  confirmedPicks?: ConfirmedPick[];
  marketValidation?: {
    status: "green" | "yellow" | "red";
    label: string;
    allowRecommendations: boolean;
    summary: string;
    method: string;
    checks: { key: string; label: string; status: "pass" | "warn" | "fail"; detail: string; meaning: string; blocking: boolean }[];
  };
};

const tabs = ["今日建议", "市场验证", "板块研究"] as const;
const tabCodes = ["ACTION", "VERIFY", "SECTOR"];
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
  const [tab, setTab] = useState<(typeof tabs)[number]>("今日建议");
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
        <span className="asd-session">建议 · 验证 · 板块</span>
        <button className="asd-fresh" type="button" onClick={refresh} disabled={refreshing}>
          <i /><div><strong>{refreshing ? "正在刷新" : data ? "数据链路在线" : "正在载入"}</strong><small>{data?.meta?.asOf?.replace("T", " ").slice(0, 19) || "—"}</small></div><em>↻</em>
        </button>
      </div>
    </header>

    <section className="asd-contract">
      <div className="asd-hero-copy"><span className="asd-kicker">THREE DECISION WORKSPACES</span><h2>先验证市场，<em>再查看建议。</em></h2><p>今日建议给结果，市场验证解释能不能使用，板块研究说明资金为什么选择这个方向。</p><div className="asd-hero-tags"><span>沪深主板</span><span>价格 ≤ 35</span><span>真实性闸门</span><span>已触板 / 未触板双池</span></div></div>
      <div className="asd-live-summary">
        <div><small>涨停</small><strong className="up">{data?.sentiment?.limitUp ?? "—"}</strong><span>只</span></div>
        <div><small>炸板率</small><strong>{data?.sentiment?.breakRate ?? "—"}</strong><span>%</span></div>
        <div><small>端点健康</small><strong>{healthy}</strong><span>/{data?.endpointStatus?.length || 0}</span></div>
        <p><i /> {data?.marketValidation?.label || "等待真实性校验"} · 自动刷新</p>
      </div>
    </section>

    {error ? <div className="asd-alert">{error}</div> : null}
    {failures.length ? <details className="asd-alert warn"><summary><strong>{failures.length} 个端点暂不可用</strong><span>点击查看</span></summary><div>{failures.map((item) => <span key={item.key}>{item.label}：{item.error}</span>)}</div></details> : null}

    <nav className="asd-tabs asd-tabs-three" aria-label="三个决策工作区">
      {tabs.map((item, index) => <button className={tab === item ? "active" : ""} onClick={() => setTab(item)} key={item}><small>{tabCodes[index]}</small><span>{item}</span></button>)}
    </nav>

    {tab === "今日建议" && <>
      <FunctionGuide eyebrow="01 · ACTION" title="今日建议怎么用" summary="这里是最终研究结果，不需要再从几十只股票里自行挑选。先看市场验证状态，再看双池和价格边界。" items={[
        { title: "未触板潜力池", watch: "9:35冻结的3只核心与2只观察", purpose: "寻找当天仍可能成交、尚未触板的股票", impact: "只有真实性闸门允许且研究分达标才生成" },
        { title: "已触板强势池", watch: "封板、炸板、连板高度和所属板块", purpose: "确认资金真正进攻的方向，不用于封板排队", impact: "作为板块证据和下一交易日观察，不替代未触板候选" },
        { title: "价格计划", watch: "参考区间、追高上限、T+1止盈与失效价", purpose: "把模糊的看好转成可复盘边界", impact: "价格超限或结构失效时，候选状态会转为风险" },
      ]} />
      <DailyPicks pick={data?.dailyPick} confirmed={data?.confirmedPicks} asOf={data?.meta?.asOf} />
    </>}

    {tab === "市场验证" && <>
      <FunctionGuide eyebrow="02 · VERIFY" title="市场验证有什么用" summary="它不再推荐股票，只负责确认行情是否新鲜、市场是否支持追涨，以及双池结论能否使用。" items={[
        { title: "数据真实性", watch: "更新时间、关键端点、价格高低值和涨停价", purpose: "阻止旧数据、缺字段和异常价格进入模型", impact: "关键项失败直接红灯，不生成新的9:35建议" },
        { title: "竞价与开盘", watch: "高开幅度、量比、换手和是否守住开盘价", purpose: "区分真实承接与无量虚涨", impact: "影响开盘分、量能分以及核心/观察排序" },
        { title: "市场情绪", watch: "指数、涨停数、炸板率和连板高度", purpose: "判断今天是进攻、谨慎还是退潮环境", impact: "弱市或高炸板率会降级，严重时停止建议" },
      ]} />
      <section className={`validation-board ${data?.marketValidation?.status || "red"}`}>
        <header><div><span className="asd-kicker">DATA & MARKET GATE</span><h2>{data?.marketValidation?.label || "等待市场验证"}</h2><p>{data?.marketValidation?.summary || "尚未取得校验结果。"}</p></div><strong>{data?.marketValidation?.allowRecommendations ? "可使用候选" : "停止生成建议"}</strong></header>
        <div>{(data?.marketValidation?.checks || []).map((check) => <article key={check.key} className={check.status}><span>{check.status === "pass" ? "通过" : check.status === "warn" ? "谨慎" : "失败"}</span><h3>{check.label}</h3><strong>{check.detail}</strong><p>{check.meaning}</p></article>)}</div>
        <footer>数据：a-stock-data文档端点 · 校验：本地确定性规则</footer>
      </section>
      <section className="asd-auction-summary">
        <div><span>未涨停观察</span><strong>{auctionRows.length}</strong><small>只</small></div>
        <div><span>涨停池</span><strong>{data?.sentiment?.limitUp ?? "—"}</strong><small>只</small></div>
        <div><span>炸板率</span><strong>{data?.sentiment?.breakRate ?? "—"}</strong><small>%</small></div>
        <p><b>作用：</b>用竞价强度和炸板反馈判断追涨环境。单只股票高开不等于可以买，必须与板块和量能同时成立。</p>
      </section>
      <section className="asd-two">
        <article className="asd-panel"><div className="asd-title"><div><span className="asd-kicker">AUCTION WATCH</span><h2>竞价后未涨停观察</h2><p className="asd-title-note">作用：确认高开是否有量、有承接，只作为开盘验证，不直接等同于买入名单。</p></div><Source>同花顺热点 + 腾讯行情</Source></div><StockRows rows={auctionRows} /></article>
        <article className="asd-panel"><div className="asd-title"><div><span className="asd-kicker">BOARD CONFIRMATION</span><h2>竞价板块确认</h2><p className="asd-title-note">作用：确认候选不是孤立异动，而是有板块上涨家数和领涨股支持。</p></div><Source>{data?.industryStrength?.[0]?.source || "东方财富行业板块"}</Source></div>{(data?.industryStrength || []).length ? <div className="asd-ranking">{data!.industryStrength.slice(0, 12).map((row, i) => <div key={row.code}><span>{String(i + 1).padStart(2, "0")}</span><strong>{row.name}</strong><small>{row.up_count}涨 / {row.down_count}跌 · 领涨 {row.leader || "—"}</small><b className={row.change_pct >= 0 ? "up" : "down"}>{pct(row.change_pct)}</b></div>)}</div> : <Empty />}</article>
      </section>
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

    {tab === "板块研究" && <>
      <FunctionGuide eyebrow="03 · SECTOR" title="板块研究怎么看" summary="这里解释资金选择了什么方向，以及未触板候选是否拥有同板块支撑；它是今日建议的证据层，不是另一份推荐榜。" items={[
        { title: "板块涨幅与宽度", watch: "排名、上涨/下跌家数和领涨股", purpose: "识别真正多股联动，而非单股异动", impact: "板块越强、覆盖越广，候选板块分越高" },
        { title: "行业与概念资金", watch: "主力净流入和资金占比", purpose: "判断涨幅背后是否有持续资金", impact: "用于板块确认；数据商加工指标不会单独决定买入" },
        { title: "板块内候选", watch: "每个强势板块尚未触板的股票", purpose: "查看最终双池之外的备选和联动结构", impact: "只有通过硬过滤和真实性校验的股票才展示" },
      ]} />
      <section className="asd-panel asd-spaced-panel"><div className="asd-title"><div><span className="asd-kicker">INDUSTRY STRENGTH</span><h2>实时板块涨幅排名</h2><p className="asd-title-note">作用：确定市场主攻方向；排名靠前但上涨家数少的板块需要谨慎。</p></div><Source>{data?.industryStrength?.[0]?.source || "东方财富行业板块"}</Source></div>{(data?.industryStrength || []).length ? <div className="asd-ranking">{data!.industryStrength.slice(0, 20).map((row, i) => <div key={row.code}><span>{String(i + 1).padStart(2, "0")}</span><strong>{row.name}</strong><small>{row.up_count}涨 / {row.down_count}跌 · 领涨 {row.leader || "—"}</small><b className={row.change_pct >= 0 ? "up" : "down"}>{pct(row.change_pct)}</b></div>)}</div> : <Empty />}</section>
      <section className="asd-panel asd-spaced-panel"><div className="asd-title"><div><span className="asd-kicker">SECTOR BREADTH</span><h2>强势板块多股结构</h2><p className="asd-title-note">每个板块展示5只用于快速确认联动；完整未涨停候选仍在“候选”页查看前10。</p></div><Source>a-stock-data 板块成分 + 打板池</Source></div>{sectorClusters.length ? <div className="asd-sector-grid">{sectorClusters.map((board, index) => <article key={`${board.code}-${board.name}`}><header><span>{String(index + 1).padStart(2, "0")}</span><div><strong>{board.name}</strong><small>{board.code}</small></div><b className={board.change_pct >= 0 ? "up" : "down"}>{pct(board.change_pct)}</b></header><SectorStocks rows={board.rows} /></article>)}</div> : <Empty />}</section>
      <section className="asd-two">
        {[["行业主力资金", data?.industryFunds], ["概念主力资金", data?.conceptFunds]].map(([title, rows]) => <article className="asd-panel" key={String(title)}><div className="asd-title"><h2>{String(title)}</h2><Source>东方财富板块资金</Source></div>{(rows as AnyRow[] || []).length ? <div className="asd-flow">{(rows as AnyRow[]).slice(0, 15).map((row, i) => <div key={row.code}><span>{i + 1}</span><strong>{row.name}</strong><small>{pct(row.change_pct)} · {row.leader || ""}</small><b className={row.main_net >= 0 ? "up" : "down"}>{money(row.main_net)}</b></div>)}</div> : <Empty />}</article>)}
      </section>
      <section className="asd-panel asd-spaced-panel"><div className="asd-title"><div><span className="asd-kicker">UNTOUCHED LIMIT-UP POTENTIAL</span><h2>板块内未触板候选</h2><p className="asd-title-note">作用：查看最终3+2名单之外的备选。点击板块标题即可展开股票，不代表全部都应买入。</p></div><Source>{data?.boardCandidates?.length ? "东方财富板块成分 + 腾讯行情" : "同花顺题材归因 + 腾讯行情"}</Source></div>{candidateBoards.length ? <div className="asd-board-grid">{candidateBoards.map((board) => <details className="asd-board-detail" key={board.code + "-" + board.name}><summary><h3>{board.name}<small>{board.code}</small></h3><span>{board.rows.length}只候选</span><i>＋</i></summary><StockRows rows={board.rows} /></details>)}</div> : <Empty text="当前没有满足未触板条件的板块候选" />}</section>
    </>}

    <footer className="asd-footer"><span>{data?.meta?.filters || "沪深主板 · 35元以下 · 排除ST"}</span><span>数据仅供量化研究，不构成投资建议</span></footer>
  </main>;
}
