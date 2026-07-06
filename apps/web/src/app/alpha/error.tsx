"use client";

import { RouteErrorView } from "@/components/route-error";

export default function Error({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return <RouteErrorView title="Alpha page failed" message="Alpha route hit an unexpected error." reset={reset} />;
}
