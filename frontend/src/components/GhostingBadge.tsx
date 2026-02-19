import { Ghost } from "lucide-react";

interface Props {
  lastActivityAt: string | null;
}

const GHOSTING_MS = 14 * 24 * 60 * 60 * 1000; // 14 days

export function GhostingBadge({ lastActivityAt }: Props) {
  if (!lastActivityAt) return null;

  const isGhosted =
    Date.now() - new Date(lastActivityAt).getTime() > GHOSTING_MS;

  if (!isGhosted) return null;

  return (
    <span
      title="No email activity in 14+ days"
      className="inline-flex items-center gap-1 text-xs text-red-600 bg-red-50 rounded-full px-2 py-0.5"
    >
      <Ghost className="w-3 h-3" />
      Ghosted
    </span>
  );
}
