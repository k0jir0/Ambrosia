import type { Metadata } from "next";
import "./globals.css";
import { AppShell } from "@/components/app-shell";

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000"),
  title: {
    default: "Ambrosia — Governed Investment Decisions",
    template: "%s · Ambrosia",
  },
  description: "Turn an investment thesis into a traceable, challenged, human-owned decision before capital is put at risk.",
  openGraph: {
    type: "website",
    title: "Ambrosia — Governed Investment Decisions",
    description: "Evidence, disagreement, deterministic controls, and human judgment in one traceable investment workflow.",
    images: [{ url: "/ambrosia-decision-path.png", width: 1680, height: 945, alt: "Ambrosia governed decision path" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "Ambrosia — Governed Investment Decisions",
    description: "Turn an investment thesis into a decision you can defend.",
    images: ["/ambrosia-decision-path.png"],
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
