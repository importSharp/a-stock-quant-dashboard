import { NextRequest, NextResponse } from "next/server";

function prefix(code: string) {
  return code.startsWith("6") || code.startsWith("5") ? `sh${code}` : `sz${code}`;
}

function number(value: string | undefined) {
  const result = Number(value || 0);
  return Number.isFinite(result) ? result : 0;
}

async function safeJson(url: string, headers: Record<string, string> = {}) {
  try {
    const response = await fetch(url, { cache: "no-store", headers });
    if (!response.ok) return null;
    const text = await response.text();
    try { return JSON.parse(text); } catch {
      const start = text.indexOf("[");
      const end = text.lastIndexOf("]");
      return start >= 0 && end > start ? JSON.parse(text.slice(start, end + 1)) : null;
    }
  } catch { return null; }
}

function reportRows(body: any) {
  const reports = body?.result?.data?.report_list || {};
  return Object.keys(reports).sort().reverse().slice(0, 4).map((period) => {
    const items: Record<string, any> = {};
    for (const item of reports[period]?.data || []) {
      if (item?.item_title && item?.item_value != null) items[item.item_title] = item.item_value;
    }
    return { period: `${period.slice(0, 4)}-${period.slice(4, 6)}-${period.slice(6, 8)}`, items };
  });
}

export async function GET(request: NextRequest) {
  const code = request.nextUrl.searchParams.get("code") || "";
  if (!/^\d{6}$/.test(code)) return NextResponse.json({ error: "请输入6位A股代码" }, { status: 400 });
  try {
    const symbol = prefix(code);
    const financeBase = "https://quotes.sina.cn/cn/api/openapi.php/CompanyFinanceService.getFinanceReport2022";
    const [quoteResponse, klineResponse, fundBody, profitBody, balanceBody, cashBody] = await Promise.all([
      fetch(`https://qt.gtimg.cn/q=${symbol}`, { cache: "no-store" }),
      fetch(`https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=${symbol},day,,,120,qfq`, { cache: "no-store" }),
      safeJson(`https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/MoneyFlow.ssl_qsfx_zjlrqs?page=1&num=20&sort=opendate&asc=0&daima=${symbol}`, { Referer: "https://finance.sina.com.cn/" }),
      safeJson(`${financeBase}?paperCode=${symbol}&source=lrb&type=0&page=1&num=4`),
      safeJson(`${financeBase}?paperCode=${symbol}&source=fzb&type=0&page=1&num=4`),
      safeJson(`${financeBase}?paperCode=${symbol}&source=llb&type=0&page=1&num=4`),
    ]);
    const raw = await quoteResponse.arrayBuffer();
    const text = new TextDecoder("gbk").decode(raw);
    const values = text.split('"')[1]?.split("~") || [];
    if (values.length < 50 || !values[1]) throw new Error("腾讯行情未返回该代码");
    const klineBody = await klineResponse.json();
    const node = klineBody?.data?.[symbol] || {};
    const klines = (node.qfqday || node.day || []).slice(-60);
    const closes = klines.map((row: any[]) => number(row[2])).filter((v: number) => v > 0);
    const min = Math.min(...closes);
    const max = Math.max(...closes);
    const span = Math.max(max - min, 0.01);
    const points = closes.map((value: number, index: number) => `${(index / Math.max(closes.length - 1, 1) * 600).toFixed(1)},${(170 - (value - min) / span * 160).toFixed(1)}`).join(" ");
    return NextResponse.json({
      source: "a-stock-data / 腾讯行情与腾讯K线",
      quote: { code, name: values[1], price: number(values[3]), last_close: number(values[4]), open: number(values[5]), change_pct: number(values[32]), high: number(values[33]), low: number(values[34]), amount_wan: number(values[37]), turnover_pct: number(values[38]), pe_ttm: number(values[39]), mcap_yi: number(values[45]), pb: number(values[46]), limit_up: number(values[47]), limit_down: number(values[48]), vol_ratio: number(values[49]) },
      chart: { count: closes.length, min, max, points },
      fundFlow: Array.isArray(fundBody) ? fundBody.slice(0, 20).map((row: any) => ({ date: row.opendate, close: number(row.trade), net_amount: number(row.netamount), turnover: number(row.turnover) })) : [],
      financials: { profit: reportRows(profitBody), balance: reportRows(balanceBody), cash: reportRows(cashBody) },
      sourceStatus: {
        quote: "腾讯行情", kline: "腾讯K线",
        fundFlow: Array.isArray(fundBody) ? "新浪资金流（a-stock-data备用源）" : "不可用",
        financials: profitBody || balanceBody || cashBody ? "新浪财报三表" : "不可用",
      },
      updatedAt: new Date().toISOString(),
    });
  } catch (reason) {
    return NextResponse.json({ error: `个股数据读取失败：${String(reason)}` }, { status: 502 });
  }
}
