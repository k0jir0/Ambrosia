"use client";

import { RouteErrorView } from "@/components/route-error";

export default function Error({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return <RouteErrorView title="Market Scanner page failed" message="Market Scanner route hit an unexpected error." reset={reset} />;
}
