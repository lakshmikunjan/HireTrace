import { Ghost } from "lucide-react";
import type { ApplicationStatus } from "../lib/types";

interface Props {
  lastActivityAt: string | null;
  status: ApplicationStatus;
}

const GHOSTING_MS = 90 * 24 * 60 * 60 * 1000; // 3 months

export function GhostingBadge({ lastActivityAt, status }: Props) {
  // Only flag ghosted if still at "applied" (no follow-up emails received)
  // and no activity for 3+ months
  if (status !== "applied" || !lastActivityAt) return null;

  const isGhosted =
    Date.now() - new Date(lastActivityAt).getTime() > GHOSTING_MS;

  if (!isGhosted) return null;

  return (
    <span
      title="No email activity in 3+ months"
      className="inline-flex items-center gap-1 text-xs text-red-600 bg-red-50 rounded-full px-2 py-0.5"
    >
      <Ghost className="w-3 h-3" />
      Ghosted
    </span>
  );
}
