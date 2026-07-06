import { NewReviewFlow } from "@/modules/adversarial-review";

type IntakeSearchParams = Record<string, string | string[] | undefined>;

export default async function NewReviewPage({ searchParams }: { searchParams: Promise<IntakeSearchParams> }) {
  const params = await searchParams;
  return <NewReviewFlow initialParams={params} />;
}
