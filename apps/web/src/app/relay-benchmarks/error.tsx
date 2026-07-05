"use client";

import { RouteErrorView } from "@/components/route-error";

export default function Error({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return <RouteErrorView title="Relay + Benchmarks page failed" message="Relay route hit an unexpected error." reset={reset} />;
}
