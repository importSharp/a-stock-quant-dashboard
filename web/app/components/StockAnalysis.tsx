"use client";

import { useEffect, useMemo, useRef } from "react";
import { KlineChart } from "./KlineChart";

export type AnalysisCandidate = {
  rank: number;
  code: string;
  name: string;
  industry: string;
  close: number;
  change: number;
  type: string;
  score: number;
  sectorScore: number;
  return20: number;
  return60: number;
  amountRatio: number;
  turnover5: number;
  reason: string;
  eligible: boolean;
  eligibilityReason: string;
};

function buildAnalysis(stock: AnalysisCandidate) {
  const level = !stock.eligible
    ? "不在当前观察池"
    : stock.score >= 70 && stock.sectorScore >= 65
    ? "重点观察"
    : stock.score >= 60
      ? "次级观察"
      : "普通观察";
  const trend = stock.return20 >= 20
    ? "20日强趋势"
    : stock.return20 >= 5
      ? "20日上升趋势"
      : stock.return20 >= 0
        ? "趋势偏平"
        : "20日趋势偏弱";
  const volume = stock.amountRatio >= 1.2 && stock.amountRatio <= 3.5
    ? "成交额温和放大"
    : stock.amountRatio > 3.5
      ? "成交额异常放大"
      : stock.amountRatio < 0.8
        ? "成交额缩量"
        : "成交额接近常态";
  const sector = stock.sectorScore >= 70
    ? "板块处于强势区"
    : stock.sectorScore >= 50
      ? "板块强度中性"
      : "板块暂未形成强共振";

  const risks: string[] = [];
  if (!stock.eligible) risks.push(`未入选原因：${stock.eligibilityReason}`);
  if (stock.return20 >= 30) risks.push("20日涨幅较大，存在高位分歧与回撤风险");
  if (stock.reason.includes("高位过热")) risks.push("价格偏离短期均线较大，不宜忽略追高风险");
  if (stock.change >= 9.5) risks.push("当日接近或已经涨停，次日成交可得性需要竞价确认");
  if (stock.amountRatio > 3.5) risks.push("放量过快，需区分资金承接与高位派发");
  if (stock.amountRatio < 0.8) risks.push("当前量能不足，向上突破的确认度偏低");
  if (stock.turnover5 >= 20) risks.push("短期换手较高，资金博弈剧烈");
  if (stock.return60 < 0 && stock.return20 > 0) risks.push("20日反弹尚未扭转60日弱势结构");
  if (stock.sectorScore < 50) risks.push("板块联动较弱，个股独立走强的持续性需验证");
  if (!risks.length) risks.push("未出现突出的量化过热项，但仍需确认竞价与板块开盘强度");

  const checklist = stock.type.includes("1进2")
    ? ["竞价不出现明显抢跑或大幅低开", "同板块涨停股与核心股保持强度", "开盘后换手承接正常，避免一字板成交假设"]
    : stock.type.includes("首板")
      ? ["9:25后仍处于板块前排", "量能继续放大但不过度", "突破位置有承接，避免冲高回落"]
      : ["板块指数与龙头同步走强", "个股不出现高开过度", "20日趋势结构不被放量跌破"];

  return { level, trend, volume, sector, risks, checklist };
}

export function StockAnalysisDrawer({
  stock,
  onClose,
}: {
  stock: AnalysisCandidate | null;
  onClose: () => void;
}) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const analysis = useMemo(() => stock ? buildAnalysis(stock) : null, [stock]);

  useEffect(() => {
    if (!stock) return;
    const previousOverflow = document.body.style.overflow;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.body.style.overflow = "hidden";
    document.addEventListener("keydown", handleKeyDown);
    closeRef.current?.focus();
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [stock, onClose]);

  if (!stock || !analysis) return null;

  const metrics = [
    ["收盘价", stock.close.toFixed(2)],
    ["当日涨跌", `${stock.change >= 0 ? "+" : ""}${stock.change.toFixed(2)}%`],
    ["模型分", stock.score.toFixed(1)],
    ["板块强度", stock.sectorScore.toFixed(1)],
    ["20日收益", `${stock.return20 >= 0 ? "+" : ""}${stock.return20.toFixed(1)}%`],
    ["60日收益", `${stock.return60 >= 0 ? "+" : ""}${stock.return60.toFixed(1)}%`],
    ["成交额量比", stock.amountRatio.toFixed(2)],
    ["5日平均换手", `${stock.turnover5.toFixed(2)}%`],
  ];

  return (
    <div
      className="analysis-backdrop"
      onMouseDown={(event) => event.currentTarget === event.target && onClose()}
    >
      <aside
        aria-labelledby={`analysis-title-${stock.code}`}
        aria-modal="true"
        className="analysis-drawer"
        role="dialog"
      >
        <div className="analysis-topbar">
          <div>
            <span className="section-label">STOCK ANALYSIS · {stock.code}</span>
            <h2 id={`analysis-title-${stock.code}`}>{stock.name}</h2>
            <p>{stock.industry} · {stock.type}</p>
          </div>
          <button aria-label="关闭个股分析" onClick={onClose} ref={closeRef} type="button">关闭</button>
        </div>

        <div className="analysis-verdict">
          <span>模型结论</span>
          <strong>{analysis.level}</strong>
          <p>
            {analysis.trend}，{analysis.volume}，{analysis.sector}。当前结论是观察优先级，
            不是买入信号，也不是涨停概率。
          </p>
          {!stock.eligible ? (
            <div className="analysis-exclusion">当前规则：{stock.eligibilityReason}</div>
          ) : null}
        </div>

        <div className="analysis-metrics">
          {metrics.map(([label, value]) => (
            <div key={label}>
              <span>{label}</span>
              <strong>{value}</strong>
            </div>
          ))}
        </div>

        <KlineChart code={stock.code} name={stock.name} />

        <section className="analysis-block">
          <div className="analysis-block-heading">
            <span className="analysis-index">01</span>
            <h3>入选逻辑</h3>
          </div>
          <div className="analysis-tags">
            {stock.reason.split("、").map((item) => <span key={item}>{item}</span>)}
          </div>
        </section>

        <section className="analysis-block">
          <div className="analysis-block-heading">
            <span className="analysis-index">02</span>
            <h3>主要风险</h3>
          </div>
          <ul>
            {analysis.risks.map((risk) => <li key={risk}>{risk}</li>)}
          </ul>
        </section>

        <section className="analysis-block">
          <div className="analysis-block-heading">
            <span className="analysis-index">03</span>
            <h3>次日确认清单</h3>
          </div>
          <ol>
            {analysis.checklist.map((item) => <li key={item}>{item}</li>)}
          </ol>
        </section>

        <p className="analysis-footnote">
          分析基于{stock.code}截至当前数据日的量价与板块指标，仅用于量化研究。
        </p>
      </aside>
    </div>
  );
}
