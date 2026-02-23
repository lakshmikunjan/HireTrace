import { useQuery } from "@tanstack/react-query";
import { Phone, ClipboardList, Code2, Gift, XCircle } from "lucide-react";
import { fetchRecentUpdates } from "../lib/api";
import type { RecentUpdate } from "../lib/types";

const STATUS_CONFIG: Record<
  string,
  { label: string; icon: React.ReactNode; pill: string }
> = {
  phone_screen: {
    label: "Phone Screen",
    icon: <Phone className="w-3.5 h-3.5" />,
    pill: "bg-violet-100 text-violet-700",
  },
  assessment: {
    label: "Assessment",
    icon: <ClipboardList className="w-3.5 h-3.5" />,
    pill: "bg-orange-100 text-orange-700",
  },
  technical: {
    label: "Technical",
    icon: <Code2 className="w-3.5 h-3.5" />,
    pill: "bg-amber-100 text-amber-700",
  },
  offer: {
    label: "Offer",
    icon: <Gift className="w-3.5 h-3.5" />,
    pill: "bg-green-100 text-green-700",
  },
  rejected: {
    label: "Rejected",
    icon: <XCircle className="w-3.5 h-3.5" />,
    pill: "bg-red-100 text-red-600",
  },
};

function timeAgo(isoString: string | null): string {
  if (!isoString) return "";
  const diff = Date.now() - new Date(isoString).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  return `${hrs}h ago`;
}

export function TodayUpdates() {
  const { data: updates = [] } = useQuery({
    queryKey: ["recent-updates"],
    queryFn: fetchRecentUpdates,
    refetchInterval: 2 * 60 * 1000,
    refetchOnWindowFocus: true,
  });

  if (updates.length === 0) return null;

  const rejections = updates.filter((u) => u.status === "rejected");
  const positive = updates.filter((u) => u.status !== "rejected");

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-gray-700">Today's Updates</h2>
        <span className="text-xs text-gray-400">{updates.length} event{updates.length !== 1 ? "s" : ""}</span>
      </div>

      <div className="space-y-2">
        {updates.map((u: RecentUpdate, i: number) => {
          const cfg = STATUS_CONFIG[u.status];
          if (!cfg) return null;
          return (
            <div
              key={i}
              className="flex items-center gap-3 py-2 border-b border-gray-50 last:border-0"
            >
              <span className={`inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-full shrink-0 ${cfg.pill}`}>
                {cfg.icon}
                {cfg.label}
              </span>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-800 truncate">
                  {u.company_name ?? "Unknown Company"}
                </p>
                {u.job_title && (
                  <p className="text-xs text-gray-400 truncate">{u.job_title}</p>
                )}
              </div>
              <span className="text-xs text-gray-400 shrink-0">
                {timeAgo(u.last_activity_at)}
              </span>
            </div>
          );
        })}
      </div>

      {/* Summary line */}
      <div className="mt-3 pt-3 border-t border-gray-100 flex items-center gap-4 text-xs text-gray-500">
        {positive.length > 0 && (
          <span className="text-green-600 font-medium">
            ↑ {positive.length} advancement{positive.length !== 1 ? "s" : ""}
          </span>
        )}
        {rejections.length > 0 && (
          <span className="text-red-500">
            {rejections.length} rejection{rejections.length !== 1 ? "s" : ""}
          </span>
        )}
      </div>
    </div>
  );
}
