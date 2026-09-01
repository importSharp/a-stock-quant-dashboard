"use client";

import { FormEvent, useState } from "react";
import { StockAnalysisDrawer, type AnalysisCandidate } from "./StockAnalysis";

export function StockCodeSearch({ stocks }: { stocks: AnalysisCandidate[] }) {
  const [query, setQuery] = useState("");
  const [message, setMessage] = useState("支持本地已同步且历史数据足够的主板股票");
  const [selected, setSelected] = useState<AnalysisCandidate | null>(null);

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const code = query.replace(/\D/g, "").slice(-6);
    if (code.length !== 6) {
      setMessage("请输入完整的6位股票代码");
      return;
    }
    const stock = stocks.find((item) => item.code === code);
    if (!stock) {
      setMessage(`未找到 ${code}：可能尚未同步，或历史数据不足`);
      return;
    }
    setMessage(`${stock.name} · 数据日分析已生成`);
    setSelected(stock);
  };

  return (
    <>
      <section className="stock-search-panel">
        <div>
          <span className="section-label">STOCK LOOKUP</span>
          <h2>输入代码，分析任意已同步个股</h2>
        </div>
        <form onSubmit={submit}>
          <label htmlFor="stock-code">股票代码</label>
          <div className="stock-search-control">
            <input
              autoComplete="off"
              id="stock-code"
              inputMode="numeric"
              maxLength={8}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="例如 000021"
              value={query}
            />
            <button type="submit">开始分析</button>
          </div>
          <p aria-live="polite">{message} · 当前可分析 {stocks.length} 只</p>
        </form>
      </section>
      <StockAnalysisDrawer stock={selected} onClose={() => setSelected(null)} />
    </>
  );
}
