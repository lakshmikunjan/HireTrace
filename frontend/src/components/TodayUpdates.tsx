import { useQuery } from "@tanstack/react-query";
import { Phone, ClipboardList, Code2, Gift, XCircle, Send } from "lucide-react";
import { fetchRecentUpdates } from "../lib/api";
import type { RecentUpdate } from "../lib/types";

const STATUS_CONFIG: Record<
  string,
  { label: string; icon: React.ReactNode; pill: string }
> = {
  applied: {
    label: "Applied",
    icon: <Send className="w-3.5 h-3.5" />,
    pill: "bg-gray-100 text-gray-600",
  },
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
  if (mins < 2) return "just now";
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

  const newApps = updates.filter((u) => u.status === "applied");
  const statusChanges = updates.filter((u) => u.status !== "applied");
  const rejections = statusChanges.filter((u) => u.status === "rejected");
  const advancements = statusChanges.filter((u) => u.status !== "rejected");

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-gray-700">Today's Activity</h2>
        <span className="text-xs text-gray-400">
          {updates.length === 0 ? "Nothing yet" : `${updates.length} event${updates.length !== 1 ? "s" : ""}`}
        </span>
      </div>

      {updates.length === 0 ? (
        <p className="text-sm text-gray-400 py-2">No activity recorded today yet. Hit <span className="font-medium text-gray-500">Scan Now</span> to check for new emails.</p>
      ) : (
        <>
          <div className="space-y-2">
            {/* Show new applications as a single grouped row if there are many */}
            {newApps.length > 3 ? (
              <div className="flex items-center gap-3 py-2 border-b border-gray-50">
                <span className="inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-full shrink-0 bg-gray-100 text-gray-600">
                  <Send className="w-3.5 h-3.5" />
                  Applied
                </span>
                <p className="text-sm text-gray-700 flex-1">
                  <span className="font-medium">{newApps.length}</span> new applications submitted
                </p>
                <span className="text-xs text-gray-400 shrink-0">
                  {timeAgo(newApps[newApps.length - 1].last_activity_at)}
                </span>
              </div>
            ) : (
              newApps.map((u: RecentUpdate, i: number) => (
                <div key={`applied-${i}`} className="flex items-center gap-3 py-2 border-b border-gray-50 last:border-0">
                  <span className="inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-full shrink-0 bg-gray-100 text-gray-600">
                    <Send className="w-3.5 h-3.5" />
                    Applied
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-800 truncate">
                      {u.company_name ?? "Unknown Company"}
                    </p>
                    {u.job_title && (
                      <p className="text-xs text-gray-400 truncate">{u.job_title}</p>
                    )}
                  </div>
                  <span className="text-xs text-gray-400 shrink-0">{timeAgo(u.last_activity_at)}</span>
                </div>
              ))
            )}

            {/* Status changes — always show individually */}
            {statusChanges.map((u: RecentUpdate, i: number) => {
              const cfg = STATUS_CONFIG[u.status];
              if (!cfg) return null;
              return (
                <div key={`change-${i}`} className="flex items-center gap-3 py-2 border-b border-gray-50 last:border-0">
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
                  <span className="text-xs text-gray-400 shrink-0">{timeAgo(u.last_activity_at)}</span>
                </div>
              );
            })}
          </div>

          {/* Summary */}
          <div className="mt-3 pt-3 border-t border-gray-100 flex items-center gap-4 text-xs text-gray-500">
            {newApps.length > 0 && (
              <span>{newApps.length} applied</span>
            )}
            {advancements.length > 0 && (
              <span className="text-green-600 font-medium">
                ↑ {advancements.length} advancement{advancements.length !== 1 ? "s" : ""}
              </span>
            )}
            {rejections.length > 0 && (
              <span className="text-red-500">
                {rejections.length} rejection{rejections.length !== 1 ? "s" : ""}
              </span>
            )}
          </div>
        </>
      )}
    </div>
  );
}
