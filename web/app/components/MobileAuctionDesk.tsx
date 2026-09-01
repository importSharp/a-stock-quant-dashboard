"use client";

import { useCallback, useEffect, useState } from "react";

type AuctionStock = {
  code: string;
  name: string;
  industry: string;
  price: number;
  pct: number;
  auctionGap: number;
  vsOpen: number;
  distanceToLimit: number;
  amountYi: number;
  volumeRatio: number;
  score: number;
  trigger: string;
  invalidate: string;
};

type AuctionPayload = {
  asOf: string;
  market: string;
  firstAttack: AuctionStock[];
  reseal: AuctionStock[];
  rejected: AuctionStock[];
  rules: { warning: string };
};

const tabs = [
  ["firstAttack", "首次冲板"],
  ["reseal", "回封观察"],
  ["rejected", "淘汰池"],
] as const;

export function MobileAuctionDesk() {
  const [data, setData] = useState<AuctionPayload | null>(null);
  const [active, setActive] = useState<(typeof tabs)[number][0]>("firstAttack");
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const response = await fetch(`/data/auction-mobile.json?t=${Date.now()}`, { cache: "no-store" });
      if (!response.ok) throw new Error("竞价缓存暂不可用");
      setData(await response.json());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 15_000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  const stocks = data?.[active] ?? [];
  const asOf = data?.asOf?.replace("T", " ").slice(5, 19) ?? "等待首次扫描";

  return (
    <section className="mobile-auction" id="auction-radar" aria-labelledby="auction-radar-title">
      <div className="mobile-auction-head">
        <div>
          <span className="section-label">09:25 AUCTION RADAR</span>
          <h2 id="auction-radar-title">竞价后冲板雷达</h2>
          <p>{data?.market ?? "沪深主板 · 非ST · 35元以下"} · {asOf}</p>
        </div>
        <button type="button" onClick={() => void refresh()} disabled={loading}>
          {loading ? "刷新中" : "立即刷新"}
        </button>
      </div>

      <div className="auction-tabs" role="tablist" aria-label="冲板候选类型">
        {tabs.map(([key, label]) => (
          <button
            type="button"
            role="tab"
            aria-selected={active === key}
            className={active === key ? "active" : ""}
            onClick={() => setActive(key)}
            key={key}
          >
            <strong>{data?.[key]?.length ?? 0}</strong>
            <span>{label}</span>
          </button>
        ))}
      </div>

      <div className="auction-card-list">
        {stocks.map((stock, index) => (
          <article className="auction-stock-card" key={stock.code}>
            <div className="auction-rank">{String(index + 1).padStart(2, "0")}</div>
            <div className="auction-stock-title">
              <div>
                <strong>{stock.name}</strong>
                <span>{stock.code} · {stock.industry}</span>
              </div>
              <b>{stock.score ? stock.score.toFixed(1) : "—"}</b>
            </div>
            <div className="auction-metrics">
              <span>现涨幅 <b className={stock.pct >= 0 ? "positive" : "negative"}>{stock.pct >= 0 ? "+" : ""}{stock.pct.toFixed(2)}%</b></span>
              <span>竞价 <b>{stock.auctionGap >= 0 ? "+" : ""}{stock.auctionGap.toFixed(2)}%</b></span>
              <span>开盘后 <b>{stock.vsOpen >= 0 ? "+" : ""}{stock.vsOpen.toFixed(2)}%</b></span>
              <span>距涨停 <b>{stock.distanceToLimit.toFixed(2)}%</b></span>
              <span>量比 <b>{stock.volumeRatio.toFixed(1)}</b></span>
              <span>成交 <b>{stock.amountYi.toFixed(2)}亿</b></span>
            </div>
            <div className="auction-conditions">
              <p><i>触发</i>{stock.trigger}</p>
              <p><i>失效</i>{stock.invalidate}</p>
            </div>
          </article>
        ))}
        {!stocks.length ? <p className="auction-empty">当前没有满足严格条件的股票，不为凑数降低标准。</p> : null}
      </div>
      <p className="auction-warning">{data?.rules?.warning ?? "模型分是排序分，不是涨停概率。"}</p>
    </section>
  );
}
