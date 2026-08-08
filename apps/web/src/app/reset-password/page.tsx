import { AuthFrame, ResetPasswordForm } from "@/components/auth-pages";

export default function ResetPasswordPage() {
  return <AuthFrame eyebrow="Choose a new password" title="Restore access and revoke old sessions." copy="Use a memorable passphrase of at least 15 characters."><ResetPasswordForm /></AuthFrame>;
}
