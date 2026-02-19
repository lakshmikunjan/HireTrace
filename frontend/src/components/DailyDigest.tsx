import { useQuery } from "@tanstack/react-query";
import { fetchStats } from "../lib/api";
import { TrendingUp } from "lucide-react";

export function DailyDigest() {
  const { data: stats } = useQuery({ queryKey: ["stats"], queryFn: fetchStats });

  if (!stats) return null;

  return (
    <div className="flex items-center gap-3 bg-brand-50 border border-brand-100 rounded-lg px-4 py-3 text-sm text-brand-700">
      <TrendingUp className="w-4 h-4 shrink-0" />
      <span>
        You applied to{" "}
        <strong>{stats.applied_today}</strong>{" "}
        {stats.applied_today === 1 ? "job" : "jobs"} today.
        Total this week:{" "}
        <strong>{stats.applied_this_week}</strong>.
        {stats.ghosting_count > 0 && (
          <span className="text-red-600 ml-2">
            ⚠ {stats.ghosting_count} ghosted.
          </span>
        )}
      </span>
    </div>
  );
}
