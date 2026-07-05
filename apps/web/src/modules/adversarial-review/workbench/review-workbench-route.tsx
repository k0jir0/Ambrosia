import { Workbench } from "@/components/workbench";

export async function ReviewWorkbenchRoute({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <Workbench initialReviewId={id} />;
}
