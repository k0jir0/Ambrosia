import { Workbench } from "@/components/workbench";

export default async function ReviewWorkbenchPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <Workbench initialReviewId={id} />;
}
