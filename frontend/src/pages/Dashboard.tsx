import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { RefreshCw, LogOut, Settings as SettingsIcon, BarChart2, Copy, X, CheckCheck, Sparkles, Search } from "lucide-react";
import { Link } from "react-router-dom";

import { fetchStats, logout } from "../lib/api";
import { useApplications, useTriggerScan, usePotentialDuplicates, useAutoCleanDuplicates } from "../hooks/useApplications";
import { useAuth } from "../hooks/useAuth";
import { ApplicationTable } from "../components/ApplicationTable";
import { FunnelChart } from "../components/FunnelChart";
import { DailyDigest } from "../components/DailyDigest";
import { TodayUpdates } from "../components/TodayUpdates";
import { DuplicateReviewModal } from "../components/DuplicateReviewModal";
import { Filters } from "../components/Filters";
import type { ApplicationFilters } from "../lib/types";

export function Dashboard() {
  const { user } = useAuth();
  const [filters, setFilters] = useState<ApplicationFilters>({});
  const { data: applications = [], isLoading } = useApplications(filters);
  const { data: stats } = useQuery({
    queryKey: ["stats"],
    queryFn: fetchStats,
    refetchInterval: 30 * 1000,
    refetchOnWindowFocus: true,
  });
  const scan       = useTriggerScan();
  const autoClean  = useAutoCleanDuplicates();
  const { data: duplicateGroups = [] } = usePotentialDuplicates();

  const [showDuplicates,  setShowDuplicates]  = useState(false);
  const [bannerDismissed, setBannerDismissed] = useState(false);
  const [searchQuery,     setSearchQuery]     = useState("");
  const [scanResult, setScanResult] = useState<{ new_applications: number; emails_checked: number } | null>(null);
  // After auto-clean runs: store the result to show a summary
  const [cleanResult, setCleanResult] = useState<{ merged_orphans: number; deleted_dupes: number } | null>(null);

  const handleLogout = async () => {
    await logout();
    window.location.href = "/";
  };

  function handleAutoClean() {
    autoClean.mutate(undefined, {
      onSuccess: (result) => {
        setCleanResult(result);
        setBannerDismissed(false); // keep banner visible so user sees the result
      },
    });
  }

  const totalCleaned = (cleanResult?.merged_orphans ?? 0) + (cleanResult?.deleted_dupes ?? 0);

  const WEEKLY_GOAL = 150;
  const weeklyProgress = stats?.applied_this_week ?? 0;
  const weeklyPct = Math.min(100, Math.round((weeklyProgress / WEEKLY_GOAL) * 100));

  const filteredApplications = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return applications;
    return applications.filter(
      (a) =>
        (a.company_name?.toLowerCase().includes(q) ?? false) ||
        (a.job_title?.toLowerCase().includes(q) ?? false),
    );
  }, [applications, searchQuery]);

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Top bar */}
      <header className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="font-bold text-brand-600 text-lg">HireTrace</span>
          {user && (
            <span className="text-sm text-gray-400 ml-2">{user.email}</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-2">
            <button
              onClick={() => scan.mutate(undefined, { onSuccess: (r) => setScanResult(r) })}
              disabled={scan.isPending}
              className="flex items-center gap-2 text-sm bg-brand-600 hover:bg-brand-700 text-white rounded-lg px-4 py-2 transition-colors disabled:opacity-60"
            >
              <RefreshCw className={`w-4 h-4 ${scan.isPending ? "animate-spin" : ""}`} />
              {scan.isPending ? "Scanning…" : "Scan Now"}
            </button>
            {/* Show scan result for a few seconds after completing */}
            {!scan.isPending && scanResult !== null && (
              <span className="text-xs text-gray-500">
                {scanResult.new_applications > 0
                  ? <span className="text-green-600 font-medium">+{scanResult.new_applications} new</span>
                  : <span>{scanResult.emails_checked} emails checked, 0 new</span>
                }
              </span>
            )}
          </div>
          <Link
            to="/stats"
            className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-800 px-3 py-2 rounded-lg transition-colors"
          >
            <BarChart2 className="w-4 h-4" />
            Analytics
          </Link>
          <Link
            to="/settings"
            className="p-2 text-gray-500 hover:text-gray-700 transition-colors"
          >
            <SettingsIcon className="w-5 h-5" />
          </Link>
          <button
            onClick={handleLogout}
            className="p-2 text-gray-500 hover:text-gray-700 transition-colors"
          >
            <LogOut className="w-5 h-5" />
          </button>
        </div>
      </header>

      {/* Duplicate review modal — only for remaining cases after auto-clean */}
      {showDuplicates && duplicateGroups.length > 0 && (
        <DuplicateReviewModal
          groups={duplicateGroups}
          onClose={() => setShowDuplicates(false)}
        />
      )}

      <div className="max-w-7xl mx-auto px-6 py-6 space-y-6">
        {/* Daily digest */}
        <DailyDigest />

        {/* Today's updates — only shown when there are events */}
        <TodayUpdates />

        {/* Duplicate banner */}
        {!bannerDismissed && (duplicateGroups.length > 0 || cleanResult) && (
          <div className={`flex items-center gap-3 rounded-lg px-4 py-3 text-sm border ${
            cleanResult
              ? "bg-green-50 border-green-200 text-green-800"
              : "bg-amber-50 border-amber-200 text-amber-800"
          }`}>
            {cleanResult ? (
              <CheckCheck className="w-4 h-4 shrink-0 text-green-500" />
            ) : (
              <Copy className="w-4 h-4 shrink-0 text-amber-500" />
            )}

            <span className="flex-1">
              {cleanResult ? (
                <>
                  <strong>{totalCleaned}</strong> duplicate{totalCleaned !== 1 ? "s" : ""} cleaned automatically
                  {cleanResult.merged_orphans > 0 && ` (${cleanResult.merged_orphans} rejection${cleanResult.merged_orphans !== 1 ? "s" : ""} merged`}
                  {cleanResult.merged_orphans > 0 && cleanResult.deleted_dupes > 0 && `, `}
                  {cleanResult.deleted_dupes > 0 && `${cleanResult.deleted_dupes} exact duplicate${cleanResult.deleted_dupes !== 1 ? "s" : ""} removed`}
                  {cleanResult.merged_orphans > 0 && `)`}
                  {duplicateGroups.length > 0 && (
                    <span className="ml-1 text-amber-700">
                      · <strong>{duplicateGroups.length}</strong> case{duplicateGroups.length !== 1 ? "s" : ""} need your review
                    </span>
                  )}
                </>
              ) : (
                <>
                  <strong>{duplicateGroups.length}</strong> possible duplicate{duplicateGroups.length !== 1 ? "s" : ""} found
                </>
              )}
            </span>

            <div className="flex items-center gap-2 shrink-0">
              {/* Auto-clean button — only shown before running */}
              {!cleanResult && (
                <button
                  onClick={handleAutoClean}
                  disabled={autoClean.isPending}
                  className="flex items-center gap-1.5 text-xs font-semibold bg-amber-700 hover:bg-amber-800 text-white rounded-md px-3 py-1.5 transition-colors disabled:opacity-50"
                >
                  <Sparkles className="w-3 h-3" />
                  {autoClean.isPending ? "Cleaning…" : "Auto-clean"}
                </button>
              )}

              {/* Review remaining button — always shown when groups exist */}
              {duplicateGroups.length > 0 && (
                <button
                  onClick={() => setShowDuplicates(true)}
                  className={`text-xs font-medium underline underline-offset-2 transition-colors ${
                    cleanResult
                      ? "text-amber-700 hover:text-amber-900"
                      : "text-amber-700 hover:text-amber-900"
                  }`}
                >
                  Review {cleanResult ? "remaining" : "manually"}
                </button>
              )}

              <button
                onClick={() => setBannerDismissed(true)}
                className="text-current opacity-40 hover:opacity-70 transition-opacity ml-1"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}

        {/* Funnel chart — full width */}
        {stats && <FunnelChart stats={stats} />}

        {/* Weekly goal */}
        {stats && (
          <div className="bg-white rounded-xl border border-gray-200 px-5 py-4">
            <div className="flex items-center justify-between mb-2">
              <div>
                <p className="text-sm font-semibold text-gray-700">Weekly Application Goal</p>
                <p className="text-xs text-gray-400 mt-0.5">
                  {weeklyProgress} of {WEEKLY_GOAL} applications this week
                  {weeklyPct >= 100 && <span className="ml-2 text-green-600 font-medium">Goal reached!</span>}
                </p>
              </div>
              <span className={`text-lg font-bold ${weeklyPct >= 100 ? "text-green-600" : weeklyPct >= 50 ? "text-blue-600" : "text-gray-700"}`}>
                {weeklyPct}%
              </span>
            </div>
            <div className="h-2.5 bg-gray-100 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-700 ${weeklyPct >= 100 ? "bg-green-500" : weeklyPct >= 50 ? "bg-blue-500" : "bg-brand-500"}`}
                style={{ width: `${weeklyPct}%` }}
              />
            </div>
          </div>
        )}

        {/* Filters + table */}
        <div className="flex gap-6">
          <Filters filters={filters} onChange={setFilters} />

          <div className="flex-1 min-w-0 bg-white rounded-xl border border-gray-200 p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-semibold text-gray-700">
                Applications{" "}
                <span className="text-gray-400 font-normal">
                  ({filteredApplications.length}{searchQuery && applications.length !== filteredApplications.length ? ` of ${applications.length}` : ""})
                </span>
              </h2>
              <div className="relative">
                <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
                <input
                  type="text"
                  placeholder="Search company or role…"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-8 pr-3 py-1.5 text-xs border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-300 w-52"
                />
              </div>
            </div>
            {isLoading ? (
              <div className="text-center py-20 text-gray-400 text-sm">
                Loading…
              </div>
            ) : (
              <ApplicationTable applications={filteredApplications} />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
