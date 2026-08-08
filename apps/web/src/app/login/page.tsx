import { AuthFrame, LoginForm } from "@/components/auth-pages";

export default function LoginPage() {
  return <AuthFrame eyebrow="Welcome back" title="Return to the decisions that need attention." copy="Sign in to your organization’s private evidence, review, and outcome history."><LoginForm /></AuthFrame>;
}
