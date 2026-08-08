import { AcceptInviteForm, AuthFrame } from "@/components/auth-pages";

export default function AcceptInvitePage() {
  return <AuthFrame eyebrow="Team invitation" title="Join a governed decision workspace." copy="Your invitation is single-use and expires after seven days. New members verify ownership through this emailed link."><AcceptInviteForm /></AuthFrame>;
}
