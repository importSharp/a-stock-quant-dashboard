type IndexQuote = {
  name: string;
  price: number;
  change_pct: number;
  amount_wan: number;
};

type FundRow = {
  name: string;
  change_pct: number;
  main_net: number;
  main_pct: number;
  leader: string;
};

type BoardStock = {
  code: string;
  name: string;
  price: number;
  pct: number;
  industry: string;
  limit_days?: number;
  seal_fund?: number;
  break_times?: number;
};

type IntradayData = {
  asOf: string;
  indices: Record<string, IndexQuote>;
  sentiment: {
    limit_up_count?: number;
    broken_count?: number;
    break_rate?: number;
    limit_down_count?: number;
    max_height?: number;
  };
  industryFunds: FundRow[];
  conceptFunds: FundRow[];
  highBoards: BoardStock[];
  brokenBoards: BoardStock[];
  errors: Record<string, string>;
};

const broadConcepts = new Set(["融资融券", "深股通", "沪股通", "MSCI中国", "富时罗素", "百元股", "高市净率"]);

function yi(value: number) {
  return `${(value / 1e8).toFixed(1)}亿`;
}

export function IntradayOverview({ data }: { data: IntradayData }) {
  const indices = Object.values(data.indices);
  const funds = [...data.industryFunds, ...data.conceptFunds]
    .filter((row) => !broadConcepts.has(row.name))
    .sort((a, b) => b.main_net - a.main_net)
    .slice(0, 8);
  const maxFlow = Math.max(...funds.map((row) => row.main_net), 1);
  const asOf = data.asOf ? data.asOf.replace("T", " ").slice(0, 19) : "等待刷新";

  return (
    <section className="intraday-section" aria-labelledby="intraday-title">
      <div className="intraday-heading">
        <div>
          <span className="section-label">LIVE MARKET · A-STOCK-DATA</span>
          <h2 id="intraday-title">盘中作战台</h2>
        </div>
        <div className="intraday-time">
          <span className="pulse-dot" />
          <span>{asOf}</span>
        </div>
      </div>

      <div className="intraday-index-grid">
        {indices.map((quote) => (
          <article className="index-tile" key={quote.name}>
            <span>{quote.name}</span>
            <strong>{quote.price.toFixed(2)}</strong>
            <em className={quote.change_pct >= 0 ? "positive" : "negative"}>
              {quote.change_pct >= 0 ? "+" : ""}{quote.change_pct.toFixed(2)}%
            </em>
            <small>成交额 {(quote.amount_wan / 10000).toFixed(0)}亿</small>
          </article>
        ))}
        <article className="sentiment-tile">
          <span>涨停 / 炸板 / 跌停</span>
          <strong>
            {data.sentiment.limit_up_count ?? "—"}
            <i>/</i>
            {data.sentiment.broken_count ?? "—"}
            <i>/</i>
            {data.sentiment.limit_down_count ?? "—"}
          </strong>
          <small>炸板率 {data.sentiment.break_rate?.toFixed(1) ?? "—"}% · 最高 {data.sentiment.max_height ?? "—"} 板</small>
        </article>
      </div>

      <div className="intraday-main-grid">
        <article className="intraday-panel">
          <div className="intraday-panel-title">
            <div>
              <span className="section-label">CAPITAL ROTATION</span>
              <h3>行业与概念资金主线</h3>
            </div>
            <span>主力净流入</span>
          </div>
          <div className="flow-list">
            {funds.map((row, index) => (
              <div className="flow-row" key={`${row.name}-${index}`}>
                <span>{String(index + 1).padStart(2, "0")}</span>
                <div>
                  <strong>{row.name}</strong>
                  <small>领涨 {row.leader || "—"} · 板块 {row.change_pct >= 0 ? "+" : ""}{row.change_pct.toFixed(2)}%</small>
                  <i style={{ width: `${Math.max(5, row.main_net / maxFlow * 100)}%` }} />
                </div>
                <b>{yi(row.main_net)}</b>
              </div>
            ))}
            {!funds.length ? <p className="intraday-empty">资金接口本轮未返回，保留涨停情绪数据。</p> : null}
          </div>
        </article>

        <article className="intraday-panel">
          <div className="intraday-panel-title">
            <div>
              <span className="section-label">LIMIT-UP LADDER</span>
              <h3>主板连板梯队</h3>
            </div>
            <span>35元以下</span>
          </div>
          <div className="ladder-list">
            {data.highBoards.slice(0, 8).map((stock) => (
              <div className="ladder-row" key={stock.code}>
                <span className="ladder-height">{stock.limit_days ?? 1}板</span>
                <div>
                  <strong>{stock.name}</strong>
                  <small>{stock.code} · {stock.industry}</small>
                </div>
                <div>
                  <b>{stock.price.toFixed(2)}</b>
                  <small>封单 {yi(stock.seal_fund ?? 0)}</small>
                </div>
              </div>
            ))}
          </div>
        </article>
      </div>

      {Object.keys(data.errors).length ? (
        <p className="source-notice">部分公开接口本轮连接失败；页面仅显示成功返回的数据，不把空响应解释为零资金。</p>
      ) : null}
    </section>
  );
}

export function DataCapabilityMap() {
  const groups = [
    ["行情", "实时行情 · K线 · 涨跌停价", "online"],
    ["信号", "热点 · 板块资金 · 龙虎榜", "online"],
    ["打板", "涨停池 · 炸板池 · 连板梯队", "online"],
    ["个股", "资金流 · 筹码 · 估值 · F10", "next"],
    ["研报", "个股/行业研报 · 一致预期", "next"],
    ["公告", "巨潮公告 · 互动易 · 新闻", "next"],
    ["风险", "重点监控 · 解禁 · 异动", "next"],
    ["宏观", "社融 · PMI · 行业变迁", "next"],
  ] as const;
  return (
    <section className="capability-map">
      <div className="panel-heading">
        <div>
          <span className="section-label">DATA CAPABILITY MAP</span>
          <h2>a-stock-data 能力接入图</h2>
        </div>
        <span className="asof-chip">统一缓存 · 分层接入</span>
      </div>
      <div className="capability-grid">
        {groups.map(([name, detail, status]) => (
          <article key={name}>
            <span className={status === "online" ? "capability-online" : "capability-next"}>
              {status === "online" ? "已接入" : "下一阶段"}
            </span>
            <strong>{name}</strong>
            <p>{detail}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
