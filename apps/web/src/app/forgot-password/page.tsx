import { AuthFrame, ForgotPasswordForm } from "@/components/auth-pages";

export default function ForgotPasswordPage() {
  return <AuthFrame eyebrow="Account recovery" title="Reset your password securely." copy="For privacy, the response is the same whether or not an account exists."><ForgotPasswordForm /></AuthFrame>;
}
