import { AuthFrame, VerifyEmailState } from "@/components/auth-pages";

export default function VerifyEmailPage() {
  return <AuthFrame eyebrow="Email verification" title="Activating your private workspace." copy="The link is single-use and expires after 30 minutes."><VerifyEmailState /></AuthFrame>;
}
