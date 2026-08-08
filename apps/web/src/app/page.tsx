import Link from "next/link";
import Image from "next/image";
import { ArrowRight, Check, Eye, GitBranch, ShieldCheck } from "lucide-react";

const proofPoints = [
  "Every material claim keeps its source and as-of time",
  "The strongest disagreement is required—not hidden",
  "Risk controls are deterministic and replayable",
  "A human records the decision and owns the outcome",
];

export default function LandingPage() {
  return (
    <main className="min-h-screen overflow-hidden bg-fog text-ink">
      <header className="mx-auto flex w-full max-w-7xl items-center justify-between px-5 py-5 sm:px-8">
        <Link href="/" className="focus-ring rounded-md">
          <span className="text-xs font-bold uppercase tracking-[0.24em] text-teal">Ambrosia</span>
        </Link>
        <nav className="flex items-center gap-2 sm:gap-4" aria-label="Account navigation">
          <Link href="/company-proof" className="focus-ring hidden rounded-md px-3 py-2 text-sm text-ink/70 hover:text-ink sm:block">Company proof</Link>
          <Link href="/login" className="focus-ring rounded-md px-3 py-2 text-sm text-ink/70 hover:text-ink">
            Sign in
          </Link>
          <Link href="/signup" className="focus-ring rounded-md bg-teal px-4 py-2 text-sm font-semibold text-[#071411] shadow-lg shadow-teal/10 transition hover:bg-[#62d8ca]">
            Create workspace
          </Link>
        </nav>
      </header>

      <section className="relative mx-auto grid w-full max-w-7xl gap-12 px-5 pb-20 pt-14 sm:px-8 lg:grid-cols-[1.08fr_0.92fr] lg:items-center lg:pb-28 lg:pt-24">
        <Image
          src="/ambrosia-decision-path.png"
          alt=""
          fill
          priority
          sizes="(max-width: 1280px) 100vw, 1280px"
          className="pointer-events-none object-cover opacity-[0.16] mix-blend-screen"
        />
        <div className="pointer-events-none absolute inset-0 bg-gradient-to-r from-fog via-fog/90 to-fog/35" aria-hidden="true" />
        <div className="absolute -left-48 top-0 h-96 w-96 rounded-full bg-teal/10 blur-3xl" aria-hidden="true" />
        <div className="relative">
          <p className="mb-5 text-xs font-semibold uppercase tracking-[0.2em] text-teal">Decision infrastructure for investment teams</p>
          <h1 className="max-w-4xl text-4xl font-semibold leading-[1.05] tracking-[-0.04em] text-ink sm:text-6xl lg:text-7xl">
            Turn an investment thesis into a decision you can defend.
          </h1>
          <p className="mt-7 max-w-2xl text-lg leading-8 text-ink/66 sm:text-xl">
            Ambrosia makes evidence, disagreement, controls, human judgment, and outcomes part of one governed workflow—before capital is put at risk.
          </p>
          <div className="mt-9 flex flex-col gap-3 sm:flex-row">
            <Link href="/signup" className="focus-ring inline-flex items-center justify-center gap-2 rounded-md bg-teal px-6 py-3.5 text-sm font-bold text-[#071411] transition hover:bg-[#62d8ca]">
              Start the guided decision <ArrowRight className="h-4 w-4" />
            </Link>
            <a href="#workflow" className="focus-ring inline-flex items-center justify-center rounded-md border border-line bg-paper/60 px-6 py-3.5 text-sm font-semibold text-ink/80 hover:bg-paper">
              See the workflow
            </a>
          </div>
          <p className="mt-4 text-xs text-ink/45">Built for professional teams. Advisory analysis only; humans retain decision authority.</p>
        </div>

        <div className="relative rounded-2xl border border-line bg-paper/90 p-4 shadow-2xl shadow-black/30 sm:p-6">
          <div className="flex items-center justify-between border-b border-line pb-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-teal">Decision packet</p>
              <p className="mt-1 text-lg font-semibold">AI infrastructure concentration</p>
            </div>
            <span className="rounded-full border border-amber-300/30 bg-amber-300/10 px-3 py-1 text-xs font-semibold text-amber-200">Needs evidence</span>
          </div>
          <div className="grid gap-3 py-5 sm:grid-cols-2">
            <ProofTile icon={Eye} label="Evidence health" value="2 sources stale" tone="text-amber-200" />
            <ProofTile icon={GitBranch} label="Strongest disagreement" value="Demand is priced in" tone="text-ink" />
            <ProofTile icon={ShieldCheck} label="Risk gate" value="Concentration blocked" tone="text-rose-200" />
            <ProofTile icon={Check} label="Human decision" value="Not yet recorded" tone="text-ink/65" />
          </div>
          <div className="rounded-xl border border-teal/20 bg-teal/5 p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-teal">Next best action</p>
            <p className="mt-2 text-sm leading-6 text-ink/75">Refresh point-in-time demand evidence, then rerun the disconfirmation test before committee review.</p>
          </div>
          <p className="mt-3 text-[11px] text-ink/40">Illustrative guided sample · dated August 7, 2026 · not live performance</p>
        </div>
      </section>

      <section id="workflow" className="border-y border-line/80 bg-paper/55">
        <div className="mx-auto w-full max-w-7xl px-5 py-20 sm:px-8">
          <div className="max-w-3xl">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal">One continuous decision record</p>
            <h2 className="mt-4 text-3xl font-semibold tracking-[-0.03em] sm:text-5xl">Less dashboard theatre. More decision discipline.</h2>
          </div>
          <ol className="mt-12 grid gap-4 lg:grid-cols-5">
            {[
              ["01", "Intake", "State the thesis, horizon, expression, and falsifiable conditions."],
              ["02", "Evidence", "Attach point-in-time sources with permission, provenance, and freshness."],
              ["03", "Challenge", "Surface contradictions, alternatives, and the strongest bear case."],
              ["04", "Control", "Apply deterministic tradeability, concentration, and policy gates."],
              ["05", "Remember", "Record the human decision, revisit date, and eventual outcome."],
            ].map(([number, title, copy]) => (
              <li key={number} className="rounded-xl border border-line bg-fog/70 p-5">
                <span className="text-xs font-semibold text-teal">{number}</span>
                <h3 className="mt-6 text-lg font-semibold">{title}</h3>
                <p className="mt-2 text-sm leading-6 text-ink/58">{copy}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="mx-auto grid w-full max-w-7xl gap-12 px-5 py-20 sm:px-8 lg:grid-cols-2 lg:py-28">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal">Designed for governed teams</p>
          <h2 className="mt-4 text-3xl font-semibold tracking-[-0.03em] sm:text-5xl">A shared memory for decisions—not another generic finance chatbot.</h2>
          <p className="mt-6 max-w-xl text-base leading-7 text-ink/62">For boutique managers, family offices, OCIOs, RIAs, and emerging investment teams that need repeatable review without losing human accountability.</p>
        </div>
        <ul className="grid gap-3">
          {proofPoints.map((point) => (
            <li key={point} className="flex items-start gap-3 rounded-xl border border-line bg-paper/65 p-4 text-sm leading-6 text-ink/75">
              <span className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full bg-teal/10 text-teal"><Check className="h-3 w-3" /></span>
              {point}
            </li>
          ))}
        </ul>
      </section>

      <section className="mx-auto w-full max-w-7xl px-5 pb-20 sm:px-8 lg:pb-28">
        <div className="rounded-2xl border border-teal/25 bg-gradient-to-br from-teal/10 to-paper p-7 sm:p-12">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal">See it with your own judgment</p>
          <div className="mt-4 flex flex-col justify-between gap-7 lg:flex-row lg:items-end">
            <h2 className="max-w-3xl text-3xl font-semibold tracking-[-0.03em] sm:text-5xl">Create a private workspace and finish one governed decision in minutes.</h2>
            <Link href="/signup" className="focus-ring inline-flex shrink-0 items-center justify-center gap-2 rounded-md bg-teal px-6 py-3.5 text-sm font-bold text-[#071411]">
              Create workspace <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </div>
      </section>

      <footer className="border-t border-line px-5 py-8 text-center text-xs text-ink/45">
        © 2026 Ambrosia · Human-governed investment decision infrastructure
        <div className="mt-3 flex justify-center gap-4"><Link href="/terms">Terms</Link><Link href="/privacy">Privacy</Link><Link href="/company-proof">Company proof</Link></div>
      </footer>
    </main>
  );
}

function ProofTile({ icon: Icon, label, value, tone }: {
  icon: typeof Eye;
  label: string;
  value: string;
  tone: string;
}) {
  return (
    <div className="rounded-xl border border-line bg-fog/70 p-4">
      <Icon className="h-4 w-4 text-teal" />
      <p className="mt-5 text-[11px] font-semibold uppercase tracking-wide text-ink/45">{label}</p>
      <p className={`mt-1 text-sm font-medium ${tone}`}>{value}</p>
    </div>
  );
}
