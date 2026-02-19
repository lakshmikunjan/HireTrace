import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { RefreshCw, LogOut, Settings as SettingsIcon } from "lucide-react";
import { Link } from "react-router-dom";

import { fetchStats, logout } from "../lib/api";
import { useApplications, useTriggerScan } from "../hooks/useApplications";
import { useAuth } from "../hooks/useAuth";
import { ApplicationTable } from "../components/ApplicationTable";
import { FunnelChart } from "../components/FunnelChart";
import { DailyDigest } from "../components/DailyDigest";
import { Filters } from "../components/Filters";
import type { ApplicationFilters } from "../lib/types";

export function Dashboard() {
  const { user } = useAuth();
  const [filters, setFilters] = useState<ApplicationFilters>({});
  const { data: applications = [], isLoading } = useApplications(filters);
  const { data: stats } = useQuery({ queryKey: ["stats"], queryFn: fetchStats });
  const scan = useTriggerScan();

  const handleLogout = async () => {
    await logout();
    window.location.href = "/";
  };

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
        <div className="flex items-center gap-3">
          <button
            onClick={() => scan.mutate()}
            disabled={scan.isPending}
            className="flex items-center gap-2 text-sm bg-brand-600 hover:bg-brand-700 text-white rounded-lg px-4 py-2 transition-colors disabled:opacity-60"
          >
            <RefreshCw className={`w-4 h-4 ${scan.isPending ? "animate-spin" : ""}`} />
            {scan.isPending ? "Scanning…" : "Scan Now"}
          </button>
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

      <div className="max-w-7xl mx-auto px-6 py-6 space-y-6">
        {/* Daily digest */}
        <DailyDigest />

        {/* Funnel chart */}
        {stats && <FunnelChart stats={stats} />}

        {/* Main content: filters + table */}
        <div className="flex gap-6">
          <Filters filters={filters} onChange={setFilters} />

          <div className="flex-1 bg-white rounded-xl border border-gray-200 p-5">
            <h2 className="text-sm font-semibold text-gray-700 mb-4">
              Applications{" "}
              <span className="text-gray-400 font-normal">
                ({applications.length})
              </span>
            </h2>
            {isLoading ? (
              <div className="text-center py-20 text-gray-400 text-sm">
                Loading…
              </div>
            ) : (
              <ApplicationTable applications={applications} />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
