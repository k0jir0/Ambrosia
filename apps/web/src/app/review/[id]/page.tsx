import { ReviewWorkbenchRoute } from "@/modules/adversarial-review";

export default async function ReviewWorkbenchPage({ params }: { params: Promise<{ id: string }> }) {
  return <ReviewWorkbenchRoute params={params} />;
}
