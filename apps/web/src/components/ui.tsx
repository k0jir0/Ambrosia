import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function Badge({ children, tone = "neutral" }: { children: React.ReactNode; tone?: "neutral" | "good" | "warn" | "bad" | "info" }) {
  const tones = {
    neutral: "border-line bg-white text-ink",
    good: "border-teal/30 bg-teal/10 text-pine",
    warn: "border-amber/30 bg-amber/10 text-amber",
    bad: "border-coral/30 bg-coral/10 text-coral",
    info: "border-violet/30 bg-violet/10 text-violet"
  };

  return <span className={cn("inline-flex items-center rounded-md border px-2 py-1 text-xs font-medium", tones[tone])}>{children}</span>;
}

export function Panel({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <section className={cn("panel rounded-lg", className)}>{children}</section>;
}

export function SectionTitle({ eyebrow, title }: { eyebrow?: string; title: string }) {
  return (
    <div>
      {eyebrow ? <p className="text-xs font-semibold uppercase tracking-wide text-teal">{eyebrow}</p> : null}
      <h2 className="text-base font-semibold text-ink">{title}</h2>
    </div>
  );
}