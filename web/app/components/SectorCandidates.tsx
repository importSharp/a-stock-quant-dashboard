"use client";

import { useMemo, useState } from "react";
import { StockAnalysisDrawer, type AnalysisCandidate } from "./StockAnalysis";

type SectorGroup = {
  name: string;
  score: number;
  available: number;
  candidates: AnalysisCandidate[];
};

export function SectorCandidates({ sectors }: { sectors: SectorGroup[] }) {
  const [activeName, setActiveName] = useState(sectors[0]?.name ?? "");
  const [selected, setSelected] = useState<AnalysisCandidate | null>(null);
  const verifiedSectors = useMemo(
    () => sectors.map((sector) => {
      const candidates = sector.candidates.filter(
        (candidate) => candidate.industry === sector.name,
      );
      return { ...sector, available: candidates.length, candidates };
    }),
    [sectors],
  );
  const active = useMemo(
    () => verifiedSectors.find((sector) => sector.name === activeName) ?? verifiedSectors[0],
    [activeName, verifiedSectors],
  );

  if (!active) {
    return null;
  }

  return (
    <>
    <section className="panel sector-candidate-section">
      <div className="panel-heading sector-candidate-heading">
        <div>
          <span className="section-label">SECTOR CANDIDATE MATRIX</span>
          <h2>强势板块 · 各取候选前10</h2>
        </div>
        <span className="risk-chip">板块内独立排名</span>
      </div>

      <div className="sector-tabs" role="tablist" aria-label="切换强势板块">
        {verifiedSectors.map((sector) => (
          <button
            aria-selected={active.name === sector.name}
            className={active.name === sector.name ? "active" : ""}
            key={sector.name}
            onClick={() => setActiveName(sector.name)}
            role="tab"
            type="button"
          >
            <strong>{sector.name}</strong>
            <span>{sector.available}只 · 强度 {sector.score.toFixed(1)}</span>
          </button>
        ))}
      </div>

      <div className="sector-candidate-summary">
        <div>
          <span>当前板块</span>
          <strong>{active.name}</strong>
        </div>
        <p>
          已从主板、非ST、35元以下且满足流动性条件的股票中，按模型分独立选出
          {active.available}只；不足10只时不使用低质量股票补位。
        </p>
      </div>

      <div className="sector-candidate-table" role="tabpanel">
        {active.candidates.map((stock) => (
          <div className="sector-candidate-row" key={stock.code}>
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
            <div className="stock-score">
              <strong>{stock.score.toFixed(1)}</strong>
              <span>模型分</span>
            </div>
          </div>
        ))}
      </div>
    </section>
    <StockAnalysisDrawer stock={selected} onClose={() => setSelected(null)} />
    </>
  );
}
