import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Ambrosia Trade Review",
  description: "Pre-trade adversarial review workbench"
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}