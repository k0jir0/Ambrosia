import { MarketIntelligencePage } from "@/components/market-intelligence-page";
import { normalizeCompareSymbols, normalizeMarketTicker } from "@/lib/market-intelligence";
import { notFound } from "next/navigation";

export default async function MarketsTickerPage({
  params,
  searchParams
}: {
  params: Promise<{ ticker: string }>;
  searchParams: Promise<{ compare?: string }>;
}) {
  const { ticker } = await params;
  const { compare } = await searchParams;
  const normalizedTicker = normalizeMarketTicker(ticker);
  if (!normalizedTicker) notFound();
  const peers = normalizeCompareSymbols(compare?.split(",") ?? [], normalizedTicker);
  return <MarketIntelligencePage ticker={normalizedTicker} compare={peers} />;
}
