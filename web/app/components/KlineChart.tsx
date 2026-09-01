"use client";

import { useEffect, useMemo, useRef, useState } from "react";

type Bar = {
  date: string;
  open: number;
  close: number;
  high: number;
  low: number;
  volume: number;
  ma5: number | null;
  ma10: number | null;
  ma20: number | null;
};

type KlinePayload = { code: string; days: number; bars: Bar[] };

function analyze(bars: Bar[]) {
  const last = bars.at(-1)!;
  const recent20 = bars.slice(-20);
  const priorVolumes = bars.slice(-6, -1).map((bar) => bar.volume);
  const averageVolume = priorVolumes.reduce((sum, value) => sum + value, 0) /
    Math.max(priorVolumes.length, 1);
  const volumeRatio = averageVolume ? last.volume / averageVolume : 0;
  const support = Math.min(...recent20.map((bar) => bar.low));
  const resistance = Math.max(...recent20.map((bar) => bar.high));
  const trend = last.ma5 && last.ma10 && last.ma20
    ? last.ma5 > last.ma10 && last.ma10 > last.ma20 && last.close > last.ma5
      ? "均线多头排列，短线趋势偏强"
      : last.ma5 < last.ma10 && last.ma10 < last.ma20
        ? "均线空头排列，趋势仍偏弱"
        : last.close >= last.ma20
          ? "站在MA20上方，但均线尚未完全多头"
          : "收盘位于MA20下方，趋势确认不足"
    : "均线数据不足";
  const position = resistance === support
    ? 0.5
    : (last.close - support) / (resistance - support);
  const positionText = position >= 0.8
    ? "接近20日压力区"
    : position <= 0.2
      ? "接近20日支撑区"
      : "位于20日区间中部";
  const volumeText = volumeRatio >= 1.5
    ? `量能明显放大（约${volumeRatio.toFixed(2)}倍）`
    : volumeRatio <= 0.75
      ? `量能收缩（约${volumeRatio.toFixed(2)}倍）`
      : `量能接近5日常态（约${volumeRatio.toFixed(2)}倍）`;
  return { last, support, resistance, trend, positionText, volumeText };
}

function drawChart(canvas: HTMLCanvasElement, bars: Bar[]) {
  const width = canvas.clientWidth;
  const height = 330;
  const ratio = window.devicePixelRatio || 1;
  canvas.width = Math.round(width * ratio);
  canvas.height = Math.round(height * ratio);
  canvas.style.height = `${height}px`;
  const context = canvas.getContext("2d");
  if (!context || !width) return;
  context.scale(ratio, ratio);
  context.clearRect(0, 0, width, height);

  const left = 8;
  const right = 50;
  const top = 18;
  const priceBottom = 242;
  const volumeTop = 262;
  const volumeBottom = 306;
  const plotWidth = width - left - right;
  const low = Math.min(...bars.map((bar) => bar.low));
  const high = Math.max(...bars.map((bar) => bar.high));
  const padding = Math.max((high - low) * 0.06, high * 0.005);
  const minPrice = low - padding;
  const maxPrice = high + padding;
  const priceHeight = priceBottom - top;
  const maxVolume = Math.max(...bars.map((bar) => bar.volume), 1);
  const step = plotWidth / bars.length;
  const candleWidth = Math.max(1, Math.min(5, step * 0.58));
  const x = (index: number) => left + step * (index + 0.5);
  const y = (price: number) => top + (maxPrice - price) / (maxPrice - minPrice) * priceHeight;

  context.font = "10px ui-monospace, Consolas";
  context.textAlign = "left";
  context.textBaseline = "middle";
  for (let line = 0; line <= 4; line += 1) {
    const lineY = top + priceHeight * line / 4;
    const price = maxPrice - (maxPrice - minPrice) * line / 4;
    context.strokeStyle = "#e1dfd8";
    context.lineWidth = 1;
    context.beginPath();
    context.moveTo(left, lineY);
    context.lineTo(width - right, lineY);
    context.stroke();
    context.fillStyle = "#777d78";
    context.fillText(price.toFixed(2), width - right + 7, lineY);
  }

  bars.forEach((bar, index) => {
    const color = bar.close >= bar.open ? "#d93d29" : "#16815b";
    const center = x(index);
    context.strokeStyle = color;
    context.fillStyle = color;
    context.lineWidth = 1;
    context.beginPath();
    context.moveTo(center, y(bar.high));
    context.lineTo(center, y(bar.low));
    context.stroke();
    const bodyTop = Math.min(y(bar.open), y(bar.close));
    const bodyHeight = Math.max(1, Math.abs(y(bar.open) - y(bar.close)));
    context.fillRect(center - candleWidth / 2, bodyTop, candleWidth, bodyHeight);
    const volumeHeight = bar.volume / maxVolume * (volumeBottom - volumeTop);
    context.globalAlpha = 0.55;
    context.fillRect(center - candleWidth / 2, volumeBottom - volumeHeight, candleWidth, volumeHeight);
    context.globalAlpha = 1;
  });

  const drawAverage = (key: "ma5" | "ma10" | "ma20", color: string) => {
    context.strokeStyle = color;
    context.lineWidth = 1.25;
    context.beginPath();
    let started = false;
    bars.forEach((bar, index) => {
      const value = bar[key];
      if (value === null) return;
      if (!started) {
        context.moveTo(x(index), y(value));
        started = true;
      } else {
        context.lineTo(x(index), y(value));
      }
    });
    context.stroke();
  };
  drawAverage("ma5", "#d49a00");
  drawAverage("ma10", "#3568d4");
  drawAverage("ma20", "#8250a5");

  context.fillStyle = "#777d78";
  context.textBaseline = "top";
  context.fillText(bars[0].date.slice(5), left, 312);
  context.textAlign = "center";
  context.fillText(bars[Math.floor(bars.length / 2)].date.slice(5), width / 2, 312);
  context.textAlign = "right";
  context.fillText(bars.at(-1)!.date.slice(5), width - right, 312);
}

export function KlineChart({ code, name }: { code: string; name: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [payload, setPayload] = useState<KlinePayload | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setPayload(null);
    setError("");
    fetch(`/data/klines/${code}.json`)
      .then((response) => {
        if (!response.ok) throw new Error("K线数据尚未生成");
        return response.json() as Promise<KlinePayload>;
      })
      .then((data) => !cancelled && setPayload(data))
      .catch((reason: Error) => !cancelled && setError(reason.message));
    return () => { cancelled = true; };
  }, [code]);

  useEffect(() => {
    if (!payload?.bars.length || !canvasRef.current) return;
    const canvas = canvasRef.current;
    const render = () => drawChart(canvas, payload.bars);
    render();
    const observer = new ResizeObserver(render);
    observer.observe(canvas);
    return () => observer.disconnect();
  }, [payload]);

  const summary = useMemo(
    () => payload?.bars.length ? analyze(payload.bars) : null,
    [payload],
  );

  return (
    <section className="kline-section">
      <div className="analysis-block-heading">
        <span className="analysis-index">K</span>
        <h3>日K线与均线分析</h3>
        <span className="kline-range">最近{payload?.days ?? 120}个交易日</span>
      </div>
      {payload?.bars.length ? (
        <>
          <div className="kline-legend">
            <span>红涨 / 绿跌</span><i className="ma5" />MA5<i className="ma10" />MA10<i className="ma20" />MA20
          </div>
          <canvas
            aria-label={`${name}最近${payload.days}个交易日K线图`}
            className="kline-canvas"
            ref={canvasRef}
            role="img"
          />
          {summary ? (
            <div className="kline-summary">
              <p>{summary.trend}</p>
              <p>{summary.positionText}，20日参考支撑 {summary.support.toFixed(2)}，压力 {summary.resistance.toFixed(2)}</p>
              <p>{summary.volumeText}</p>
              <div>
                <span>MA5 {summary.last.ma5?.toFixed(2) ?? "—"}</span>
                <span>MA10 {summary.last.ma10?.toFixed(2) ?? "—"}</span>
                <span>MA20 {summary.last.ma20?.toFixed(2) ?? "—"}</span>
              </div>
            </div>
          ) : null}
        </>
      ) : (
        <p className="kline-loading">{error || "正在读取K线数据…"}</p>
      )}
    </section>
  );
}
