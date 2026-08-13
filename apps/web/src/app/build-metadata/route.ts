import { NextResponse } from "next/server";

export const dynamic = "force-static";

export function GET() {
  return NextResponse.json(
    {
      service: "ambrosia-web",
      buildSha: process.env.NEXT_PUBLIC_BUILD_SHA ?? "development",
      apiBasePath: process.env.NEXT_PUBLIC_API_BASE_URL ?? null,
      governedReportExport: process.env.NEXT_PUBLIC_ENABLE_REVIEW_EXPORT === "true",
    },
    { headers: { "Cache-Control": "no-store" } },
  );
}
