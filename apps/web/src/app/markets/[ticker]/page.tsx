import { MarketIntelligencePage } from "@/components/market-intelligence-page";

export default async function MarketsTickerPage({
  params,
  searchParams
}: {
  params: Promise<{ ticker: string }>;
  searchParams: Promise<{ compare?: string }>;
}) {
  const { ticker } = await params;
  const { compare } = await searchParams;
  const peers = compare ? compare.split(",").map((item) => item.trim().toUpperCase()).filter(Boolean) : [];
  return <MarketIntelligencePage ticker={ticker} compare={peers} />;
}
