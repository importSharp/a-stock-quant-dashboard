"use client";

import { useMemo, useState } from "react";
import { StockAnalysisDrawer, type AnalysisCandidate } from "./StockAnalysis";

const filters = ["全部", "首板", "1进2", "趋势板"] as const;

export function CandidateTable({
  candidates,
  compact = false,
}: {
  candidates: AnalysisCandidate[];
  compact?: boolean;
}) {
  const [active, setActive] = useState<(typeof filters)[number]>("全部");
  const [selected, setSelected] = useState<AnalysisCandidate | null>(null);
  const visible = useMemo(() => {
    const filtered = active === "全部"
      ? candidates
      : candidates.filter((candidate) => candidate.type.includes(active));
    return compact ? filtered.slice(0, 5) : filtered;
  }, [active, candidates, compact]);

  return (
    <>
    <article className={compact ? "panel watch-panel" : "candidate-table-wrap"}>
      {compact ? (
        <div className="panel-heading">
          <div>
            <span className="section-label">MARKET-WIDE WATCHLIST</span>
            <h2>全市场候选前五</h2>
          </div>
          <span className="risk-chip">仅观察</span>
        </div>
      ) : (
        <div className="filter-row" role="group" aria-label="候选类型筛选">
          {filters.map((filter) => (
            <button
              className={active === filter ? "active" : ""}
              key={filter}
              onClick={() => setActive(filter)}
              type="button"
            >
              {filter}
            </button>
          ))}
        </div>
      )}

      <div className={compact ? "candidate-list" : "candidate-table"}>
        {visible.map((stock) => (
          <div className={compact ? "candidate-row" : "candidate-detail-row"} key={stock.code}>
            <span className="rank-number">{String(stock.rank).padStart(2, "0")}</span>
            <button
              aria-label={`分析${stock.name}`}
              className="stock-name stock-analyze-trigger"
              onClick={() => setSelected(stock)}
              type="button"
            >
              <strong>{stock.name}</strong>
              <span>{stock.code} · {stock.industry} · 查看分析</span>
            </button>
            <span className="strategy-tag">{stock.type.replace("观察", "")}</span>
            {!compact ? (
              <>
                <div className="mini-metric">
                  <span>20日</span>
                  <strong className={stock.return20 >= 0 ? "positive" : "negative"}>
                    {stock.return20 >= 0 ? "+" : ""}{stock.return20.toFixed(1)}%
                  </strong>
                </div>
                <div className="mini-metric">
                  <span>量比</span>
                  <strong>{stock.amountRatio.toFixed(2)}</strong>
                </div>
                <p className="candidate-reason">{stock.reason}</p>
              </>
            ) : null}
            <div className="stock-score">
              <strong>{stock.score.toFixed(1)}</strong>
              <span>模型分</span>
            </div>
          </div>
        ))}
        {!visible.length ? <p className="empty-state">当前分类没有候选股票</p> : null}
      </div>
    </article>
    <StockAnalysisDrawer stock={selected} onClose={() => setSelected(null)} />
    </>
  );
}
