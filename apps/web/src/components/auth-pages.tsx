"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, CheckCircle2, Eye, EyeOff, Loader2 } from "lucide-react";

import {
  acceptTeamInvitation,
  loginAccount,
  requestPasswordReset,
  resendAccountVerification,
  resetAccountPassword,
  signupAccount,
  verifyAccountEmail,
} from "@/lib/api";

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message.replace(/^API request failed: \d+ - /, "") : "Something went wrong. Try again.";
}

export function AuthFrame({ eyebrow, title, copy, children }: {
  eyebrow: string;
  title: string;
  copy: string;
  children: React.ReactNode;
}) {
  return (
    <main className="grid min-h-screen bg-fog text-ink lg:grid-cols-[0.88fr_1.12fr]">
      <section className="relative hidden overflow-hidden border-r border-line bg-paper/75 p-12 lg:flex lg:flex-col lg:justify-between">
        <div className="absolute -left-32 -top-32 h-96 w-96 rounded-full bg-teal/10 blur-3xl" aria-hidden="true" />
        <Link href="/" className="focus-ring relative w-fit rounded-md text-xs font-bold uppercase tracking-[0.24em] text-teal">Ambrosia</Link>
        <div className="relative max-w-lg">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-teal">Private by default</p>
          <h2 className="mt-5 text-4xl font-semibold leading-tight tracking-[-0.035em]">Your team’s evidence, decisions, and outcomes stay inside its own workspace.</h2>
          <ul className="mt-8 space-y-4 text-sm leading-6 text-ink/65">
            {["Server-enforced organization boundaries", "Evidence and model provenance on material claims", "Human authority preserved at every decision gate"].map((item) => (
              <li key={item} className="flex items-center gap-3"><CheckCircle2 className="h-4 w-4 shrink-0 text-teal" /> {item}</li>
            ))}
          </ul>
        </div>
        <p className="relative text-xs text-ink/38">Investment analysis is advisory; Ambrosia does not execute live trades.</p>
      </section>
      <section className="flex items-center justify-center px-5 py-12 sm:px-8">
        <div className="w-full max-w-lg">
          <Link href="/" className="focus-ring mb-10 inline-block rounded-md text-xs font-bold uppercase tracking-[0.24em] text-teal lg:hidden">Ambrosia</Link>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-teal">{eyebrow}</p>
          <h1 className="mt-3 text-3xl font-semibold tracking-[-0.03em] sm:text-4xl">{title}</h1>
          <p className="mt-3 text-sm leading-6 text-ink/58">{copy}</p>
          <div className="mt-8">{children}</div>
        </div>
      </section>
    </main>
  );
}

const inputClass = "focus-ring mt-2 w-full rounded-md border border-line bg-paper px-3.5 py-3 text-sm text-ink placeholder:text-ink/30";
const buttonClass = "focus-ring flex w-full items-center justify-center gap-2 rounded-md bg-teal px-4 py-3.5 text-sm font-bold text-[#071411] disabled:cursor-not-allowed disabled:opacity-55";

export function SignupForm() {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [sent, setSent] = useState<{ email: string; token?: string; deliveryFailed?: boolean } | null>(null);
  const [showPassword, setShowPassword] = useState(false);
  const [resent, setResent] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError("");
    const data = new FormData(event.currentTarget);
    try {
      const result = await signupAccount({
        email: String(data.get("email")),
        password: String(data.get("password")),
        organizationName: String(data.get("organization")),
        displayName: String(data.get("name")),
        professionalRole: String(data.get("role")),
        acceptedTerms: data.get("terms") === "on",
      });
      setSent({
        email: String(data.get("email")),
        token: result.developmentVerificationToken,
        deliveryFailed: result.deliveryStatus === "retry_required",
      });
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setPending(false);
    }
  }

  if (sent) {
    return (
      <div className="rounded-xl border border-teal/25 bg-teal/5 p-6">
        <CheckCircle2 className="h-7 w-7 text-teal" />
        <h2 className="mt-5 text-xl font-semibold">{sent.token ? "Verify this account" : sent.deliveryFailed ? "Workspace created" : "Check your email"}</h2>
        <p className="mt-2 text-sm leading-6 text-ink/60">{sent.token ? "Email delivery is disabled in this non-production environment. Use the single-use verification link below; it expires in 30 minutes." : sent.deliveryFailed ? "Email delivery did not complete. Request a new link below; your pending workspace is safe." : <>We sent a verification link to <strong className="text-ink">{sent.email}</strong>. It expires in 30 minutes.</>}</p>
        {sent.token ? (
          <Link href={`/verify-email?token=${encodeURIComponent(sent.token)}`} className="focus-ring mt-5 inline-flex items-center gap-2 rounded-md bg-teal px-4 py-3 text-sm font-bold text-[#071411]">
            Verify development account <ArrowRight className="h-4 w-4" />
          </Link>
        ) : null}
        <button
          type="button"
          className="focus-ring mt-5 block text-sm font-semibold text-teal hover:underline"
          onClick={async () => {
            const result = await resendAccountVerification(sent.email);
            setResent(true);
            setSent({ ...sent, token: result.developmentVerificationToken ?? sent.token, deliveryFailed: false });
          }}
        >
          {resent ? "Verification link sent again" : "Send a new verification link"}
        </button>
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="space-y-5">
      <label className="block text-sm font-medium">Work email<input className={inputClass} name="email" type="email" autoComplete="email" required /></label>
      <label className="block text-sm font-medium">Name<input className={inputClass} name="name" autoComplete="name" maxLength={100} required /></label>
      <label className="block text-sm font-medium">Your role
        <select className={inputClass} name="role" defaultValue="analyst">
          <option value="analyst">Analyst</option>
          <option value="portfolio_manager">Portfolio manager</option>
          <option value="risk">Risk or compliance</option>
          <option value="cio_founder">CIO or founder</option>
          <option value="other">Other</option>
        </select>
      </label>
      <label className="block text-sm font-medium">Organization<input className={inputClass} name="organization" autoComplete="organization" required minLength={2} maxLength={120} /></label>
      <label className="block text-sm font-medium">Password
        <span className="relative block">
          <input className={`${inputClass} pr-12`} name="password" type={showPassword ? "text" : "password"} autoComplete="new-password" required minLength={15} maxLength={256} aria-describedby="password-help" />
          <button type="button" onClick={() => setShowPassword((value) => !value)} className="focus-ring absolute right-2 top-[18px] rounded p-2 text-ink/55" aria-label={showPassword ? "Hide password" : "Show password"}>{showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}</button>
        </span>
      </label>
      <p id="password-help" className="-mt-3 text-xs leading-5 text-ink/45">Use at least 15 characters. A memorable passphrase is welcome; forced symbol rules are not.</p>
      <label className="flex items-start gap-3 text-xs leading-5 text-ink/58">
        <input name="terms" type="checkbox" required className="focus-ring mt-1 h-4 w-4 rounded border-line accent-teal" />
        <span>I accept the <Link href="/terms" className="font-semibold text-teal hover:underline">terms</Link> and <Link href="/privacy" className="font-semibold text-teal hover:underline">privacy notice</Link> and understand that outputs are decision-support, not investment advice.</span>
      </label>
      {error ? <p role="alert" className="rounded-md border border-rose-300/25 bg-rose-300/10 p-3 text-sm text-rose-100">{error}</p> : null}
      <button className={buttonClass} disabled={pending}>{pending ? <Loader2 className="h-4 w-4 animate-spin" /> : null} Create private workspace</button>
      <p className="text-center text-sm text-ink/50">Already have an account? <Link href="/login" className="font-semibold text-teal hover:underline">Sign in</Link></p>
    </form>
  );
}

export function LoginForm() {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setPending(true); setError("");
    const data = new FormData(event.currentTarget);
    try {
      await loginAccount(String(data.get("email")), String(data.get("password")));
      const returnTo = new URLSearchParams(window.location.search).get("returnTo");
      window.location.assign(returnTo?.startsWith("/") && !returnTo.startsWith("//") ? returnTo : "/app");
    } catch (cause) { setError(errorMessage(cause)); } finally { setPending(false); }
  }
  return (
    <form onSubmit={submit} className="space-y-5">
      <label className="block text-sm font-medium">Email<input className={inputClass} name="email" type="email" autoComplete="email" required /></label>
      <label className="block text-sm font-medium">Password<input className={inputClass} name="password" type="password" autoComplete="current-password" required /></label>
      <div className="text-right"><Link href="/forgot-password" className="text-xs font-semibold text-teal hover:underline">Forgot password?</Link></div>
      {error ? <p role="alert" className="rounded-md border border-rose-300/25 bg-rose-300/10 p-3 text-sm text-rose-100">{error}</p> : null}
      <button className={buttonClass} disabled={pending}>{pending ? <Loader2 className="h-4 w-4 animate-spin" /> : null} Sign in</button>
      <p className="text-center text-sm text-ink/50">New to Ambrosia? <Link href="/signup" className="font-semibold text-teal hover:underline">Create a workspace</Link></p>
    </form>
  );
}

export function ForgotPasswordForm() {
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [token, setToken] = useState<string | undefined>();
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setPending(true); setError("");
    const data = new FormData(event.currentTarget);
    try { const result = await requestPasswordReset(String(data.get("email"))); setMessage(result.message); setToken(result.developmentResetToken); }
    catch { setError("Password recovery is temporarily unavailable. Contact support for an assisted reset."); }
    finally { setPending(false); }
  }
  if (message) return <div className="rounded-xl border border-line bg-paper p-5 text-sm leading-6 text-ink/68"><CheckCircle2 className="mb-3 h-6 w-6 text-teal" />{message}{token ? <Link href={`/reset-password?token=${encodeURIComponent(token)}`} className="mt-4 flex items-center gap-2 font-semibold text-teal">Open development reset <ArrowRight className="h-4 w-4" /></Link> : <p className="mt-3 text-xs text-ink/58">Need help immediately? Contact support for assisted recovery.</p>}</div>;
  return <form onSubmit={submit} className="space-y-5"><label className="block text-sm font-medium">Email<input className={inputClass} name="email" type="email" autoComplete="email" required /></label>{error ? <p role="alert" className="rounded-md border border-rose-300/25 bg-rose-300/10 p-3 text-sm text-rose-100">{error}</p> : null}<p className="text-xs leading-5 text-ink/52">If email delivery is unavailable, support can issue an assisted one-time reset link after identity verification.</p><button className={buttonClass} disabled={pending}>{pending ? <Loader2 className="h-4 w-4 animate-spin" /> : null} Send reset link</button><Link href="/login" className="block text-center text-sm font-semibold text-teal">Back to sign in</Link></form>;
}

export function ResetPasswordForm() {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setPending(true); setError("");
    const token = new URLSearchParams(window.location.search).get("token") ?? "";
    const data = new FormData(event.currentTarget);
    try { await resetAccountPassword(token, String(data.get("password"))); setDone(true); }
    catch (cause) { setError(errorMessage(cause)); } finally { setPending(false); }
  }
  if (done) return <div className="rounded-xl border border-teal/25 bg-teal/5 p-5"><CheckCircle2 className="h-6 w-6 text-teal" /><p className="mt-3 text-sm text-ink/68">Password updated. All previous sessions were revoked.</p><Link href="/login" className="mt-4 inline-flex items-center gap-2 font-semibold text-teal">Sign in <ArrowRight className="h-4 w-4" /></Link></div>;
  return <form onSubmit={submit} className="space-y-5"><label className="block text-sm font-medium">New password<input className={inputClass} name="password" type="password" autoComplete="new-password" minLength={15} maxLength={256} required /></label>{error ? <p role="alert" className="rounded-md border border-rose-300/25 bg-rose-300/10 p-3 text-sm text-rose-100">{error}</p> : null}<button className={buttonClass} disabled={pending}>{pending ? <Loader2 className="h-4 w-4 animate-spin" /> : null} Update password</button></form>;
}

export function VerifyEmailState() {
  const [state, setState] = useState<"working" | "error">("working");
  useEffect(() => {
    const token = new URLSearchParams(window.location.search).get("token") ?? "";
    verifyAccountEmail(token).then(() => window.location.assign("/onboarding")).catch(() => setState("error"));
  }, []);
  if (state === "error") return <div className="rounded-xl border border-rose-300/25 bg-rose-300/10 p-5"><p className="text-sm text-rose-100">This verification link is invalid or expired.</p><Link href="/signup" className="mt-4 inline-block font-semibold text-teal">Return to signup</Link></div>;
  return <div className="flex items-center gap-3 rounded-xl border border-line bg-paper p-5 text-sm text-ink/65"><Loader2 className="h-5 w-5 animate-spin text-teal" /> Verifying your private workspace…</div>;
}

export function AcceptInviteForm() {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setPending(true); setError("");
    const data = new FormData(event.currentTarget);
    try {
      await acceptTeamInvitation({
        token: new URLSearchParams(window.location.search).get("token") ?? "",
        password: String(data.get("password") || "") || undefined,
        displayName: String(data.get("name") || ""),
        professionalRole: String(data.get("role") || "other"),
        acceptedTerms: data.get("terms") === "on",
      });
      window.location.assign("/onboarding");
    } catch (cause) { setError(errorMessage(cause)); } finally { setPending(false); }
  }
  return (
    <form onSubmit={submit} className="space-y-5">
      <p className="rounded-md border border-line bg-paper p-3 text-xs leading-5 text-ink/58">Already have an Ambrosia account with the invited email? Sign in first, reopen this link, and leave the password blank.</p>
      <label className="block text-sm font-medium">Name<input className={inputClass} name="name" autoComplete="name" maxLength={100} /></label>
      <label className="block text-sm font-medium">Your role<select className={inputClass} name="role" defaultValue="analyst"><option value="analyst">Analyst</option><option value="portfolio_manager">Portfolio manager</option><option value="risk">Risk or compliance</option><option value="cio_founder">CIO or founder</option><option value="other">Other</option></select></label>
      <label className="block text-sm font-medium">Create a password
        <span className="relative block"><input className={`${inputClass} pr-12`} name="password" type={showPassword ? "text" : "password"} autoComplete="new-password" minLength={15} maxLength={256} /><button type="button" onClick={() => setShowPassword((value) => !value)} className="focus-ring absolute right-2 top-[18px] rounded p-2 text-ink/55" aria-label={showPassword ? "Hide password" : "Show password"}>{showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}</button></span>
      </label>
      <label className="flex items-start gap-3 text-xs leading-5 text-ink/58"><input name="terms" type="checkbox" className="focus-ring mt-1 h-4 w-4 rounded border-line accent-teal" /><span>I accept the <Link href="/terms" className="font-semibold text-teal">terms</Link> and <Link href="/privacy" className="font-semibold text-teal">privacy notice</Link>.</span></label>
      {error ? <p role="alert" className="rounded-md border border-rose-300/25 bg-rose-300/10 p-3 text-sm text-rose-100">{error}</p> : null}
      <button className={buttonClass} disabled={pending}>{pending ? <Loader2 className="h-4 w-4 animate-spin" /> : null} Join private workspace</button>
    </form>
  );
}
