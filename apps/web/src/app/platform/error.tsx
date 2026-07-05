"use client";

import { RouteErrorView } from "@/components/route-error";

export default function Error({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return <RouteErrorView title="Platform page failed" message="Platform route hit an unexpected error." reset={reset} />;
}
