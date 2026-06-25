export type OhlcPoint = {
  index: number;
  label: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

export type CorrelationPoint = {
  row: string;
  col: string;
  value: number;
};

export type RiskReturnPoint = {
  ticker: string;
  risk: number;
  ret: number;
  liquidity: number;
};

export function seedFromTicker(ticker: string) {
  return ticker
    .toUpperCase()
    .split("")
    .reduce((sum, char) => sum + char.charCodeAt(0), 0);
}

export function buildOhlcSeries(ticker: string, length = 72): OhlcPoint[] {
  const seed = seedFromTicker(ticker);
  let price = 80 + (seed % 140);

  return Array.from({ length }, (_, idx) => {
    const phase = Math.sin((idx + seed) / 4.7) * 1.2 + Math.cos((idx + seed) / 9.2) * 0.8;
    const drift = ((seed % 9) - 4) * 0.02;
    const open = Math.max(1, price + phase * 0.7 + drift);
    const close = Math.max(1, open + Math.sin((idx + seed) / 3.1) * 1.3 + drift * 2);
    const high = Math.max(open, close) + 0.6 + Math.abs(Math.cos((idx + seed) / 2.9));
    const low = Math.min(open, close) - 0.6 - Math.abs(Math.sin((idx + seed) / 2.7));
    const volume = Math.round(1_200_000 + Math.abs(Math.sin((idx + seed) / 2.4)) * 3_000_000 + (seed % 1000) * 120);

    price = close;

    return {
      index: idx,
      label: `T${idx + 1}`,
      open: round2(open),
      high: round2(high),
      low: round2(Math.max(0.5, low)),
      close: round2(close),
      volume
    };
  });
}

export function withMovingAverages(series: OhlcPoint[]) {
  return series.map((point, index) => ({
    ...point,
    sma20: average(series, index, 20),
    sma50: average(series, index, 50),
    ema21: ema(series, index, 21)
  }));
}

export function buildYieldCurve(seedTicker: string) {
  const seed = seedFromTicker(seedTicker);
  const base = [4.95, 4.7, 4.45, 4.26, 4.11];
  const shift = ((seed % 13) - 6) * 0.02;
  const prevShift = shift + 0.16;
  return ["3M", "2Y", "5Y", "10Y", "30Y"].map((tenor, idx) => ({
    tenor,
    today: round2(base[idx] + shift - idx * 0.03),
    previous: round2(base[idx] + prevShift - idx * 0.02)
  }));
}

export function buildEquityCurve(series: OhlcPoint[]) {
  let value = 100;
  const output = series.map((point) => {
    const stepReturn = (point.close - point.open) / point.open;
    value *= 1 + stepReturn * 0.7;
    return { label: point.label, equity: round2(value) };
  });

  let peak = output[0]?.equity ?? 100;
  const drawdown = output.map((point) => {
    peak = Math.max(peak, point.equity);
    const dd = ((point.equity - peak) / peak) * 100;
    return { label: point.label, drawdown: round2(dd) };
  });

  return { equity: output, drawdown };
}

export function buildCorrelationMatrix(primaryTicker: string) {
  const basket = [primaryTicker.toUpperCase(), "QQQ", "SPY", "XLK", "IWM"];
  const seed = seedFromTicker(primaryTicker);
  const points: CorrelationPoint[] = [];

  for (let r = 0; r < basket.length; r += 1) {
    for (let c = 0; c < basket.length; c += 1) {
      const value = r === c ? 1 : Math.max(-0.95, Math.min(0.98, Math.cos((seed + r * 9 + c * 13) / 11) * 0.65 + 0.2));
      points.push({ row: basket[r], col: basket[c], value: round2(value) });
    }
  }

  return { symbols: basket, points };
}

export function buildRiskReturn(primaryTicker: string): RiskReturnPoint[] {
  const seed = seedFromTicker(primaryTicker);
  const tickers = [primaryTicker.toUpperCase(), "MSFT", "NVDA", "QQQ", "SPY", "XLF"];
  return tickers.map((ticker, idx) => ({
    ticker,
    risk: round2(10 + idx * 3 + Math.abs(Math.sin((seed + idx) / 4)) * 8),
    ret: round2(6 + idx * 2 + Math.abs(Math.cos((seed + idx) / 5)) * 11),
    liquidity: Math.round(20 + Math.abs(Math.sin((seed + idx) / 3)) * 80)
  }));
}

export function buildEfficientFrontier(primaryTicker: string) {
  const seed = seedFromTicker(primaryTicker);
  const curve = Array.from({ length: 18 }, (_, idx) => {
    const risk = 8 + idx * 1.6;
    const ret = 4 + 0.45 * risk - 0.007 * risk * risk + Math.sin((seed + idx) / 10) * 0.25;
    return { risk: round2(risk), ret: round2(ret) };
  });

  const current = { risk: 18, ret: 8.4 };
  const maxSharpe = curve.reduce((best, point) => (point.ret / point.risk > best.ret / best.risk ? point : best), curve[0]);
  const minVar = curve[0];

  return { curve, current, maxSharpe, minVar };
}

export function summarizeTicker(ticker: string, series: ReturnType<typeof withMovingAverages>) {
  const latest = series[series.length - 1];
  const previous = series[series.length - 2] ?? latest;
  const changePct = ((latest.close - previous.close) / previous.close) * 100;
  const trend = latest.close > latest.sma50 ? "positive" : "mixed";
  const volumeTrend = latest.volume > previous.volume ? "rising" : "cooling";

  return {
    headline: `${ticker.toUpperCase()} intelligence`,
    line: `${ticker.toUpperCase()} is in a ${trend} trend regime with ${round2(changePct)}% session momentum and ${volumeTrend} participation versus the prior bar.`
  };
}

function average(series: OhlcPoint[], index: number, period: number) {
  const start = Math.max(0, index - period + 1);
  const slice = series.slice(start, index + 1);
  const value = slice.reduce((sum, point) => sum + point.close, 0) / slice.length;
  return round2(value);
}

function ema(series: OhlcPoint[], index: number, period: number) {
  const k = 2 / (period + 1);
  let result = series[0]?.close ?? 0;
  for (let i = 1; i <= index; i += 1) {
    result = series[i].close * k + result * (1 - k);
  }
  return round2(result);
}

function round2(value: number) {
  return Math.round(value * 100) / 100;
}
