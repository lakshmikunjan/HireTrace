import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { LogOut, Settings as SettingsIcon, LayoutDashboard, BarChart2, TrendingUp, TrendingDown, Minus } from "lucide-react";
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid, PieChart, Pie, Cell, Legend,
} from "recharts";

import { fetchActivity, fetchStats, logout } from "../lib/api";
import { useApplications } from "../hooks/useApplications";
import { useAuth } from "../hooks/useAuth";
import type { Application } from "../lib/types";

// ── helpers ──────────────────────────────────────────────────────────────────

const GHOSTING_MS = 90 * 24 * 60 * 60 * 1000;

function isGhosted(app: Application): boolean {
  return (
    app.status === "applied" &&
    !!app.last_activity_at &&
    Date.now() - new Date(app.last_activity_at).getTime() > GHOSTING_MS
  );
}

function pct(num: number, den: number): string {
  if (den === 0) return "—";
  return (num / den * 100).toFixed(1) + "%";
}

const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

const PLATFORM_COLORS: Record<string, string> = {
  linkedin: "#0a66c2",
  indeed:   "#2164f3",
  direct:   "#9ca3af",
};

const STAGE_ORDER: { key: string; label: string; color: string }[] = [
  { key: "applied",      label: "Applied",      color: "#3b82f6" },
  { key: "phone_screen", label: "Phone Screen", color: "#8b5cf6" },
  { key: "assessment",   label: "Assessment",   color: "#f97316" },
  { key: "technical",    label: "Technical",    color: "#f59e0b" },
  { key: "offer",        label: "Offer",        color: "#10b981" },
];

// Fill gaps so the chart shows a continuous line from first to last date
function fillDailyGaps(points: { date: string; count: number }[]): { date: string; count: number }[] {
  if (points.length === 0) return [];
  const map: Record<string, number> = {};
  points.forEach((p) => { map[p.date] = p.count; });

  const start = new Date(points[0].date);
  const end   = new Date(points[points.length - 1].date);
  const result: { date: string; count: number }[] = [];

  for (const d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
    const key = d.toISOString().slice(0, 10);
    result.push({ date: key, count: map[key] ?? 0 });
  }
  return result;
}

function fmtDate(dateStr: string): string {
  const d = new Date(dateStr + "T12:00:00");
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

// ── stat card ──────────────────────────────────────────────────────────────

function StatCard({ label, value, sub, color = "text-gray-900" }: {
  label: string; value: string | number; sub?: string; color?: string;
}) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 px-5 py-4 flex flex-col gap-1">
      <p className="text-xs text-gray-400 font-medium uppercase tracking-wide">{label}</p>
      <p className={`text-2xl font-bold ${color}`}>{value}</p>
      {sub && <p className="text-xs text-gray-400">{sub}</p>}
    </div>
  );
}

// ── main page ────────────────────────────────────────────────────────────────

export function Stats() {
  const { user } = useAuth();
  const { data: applications = [] } = useApplications({});
  const { data: activityRaw = [] } = useQuery({
    queryKey: ["activity"],
    queryFn: fetchActivity,
    staleTime: 2 * 60 * 1000,
  });
  const { data: stats } = useQuery({
    queryKey: ["stats"],
    queryFn: fetchStats,
    staleTime: 2 * 60 * 1000,
  });

  const handleLogout = async () => {
    await logout();
    window.location.href = "/";
  };

  // ── derived metrics ──────────────────────────────────────────────────────
  const total = applications.length;

  const responded  = applications.filter((a) =>
    ["phone_screen", "assessment", "technical", "offer", "rejected"].includes(a.status)
  ).length;
  const interviewed = applications.filter((a) =>
    ["phone_screen", "assessment", "technical", "offer"].includes(a.status)
  ).length;
  const offers = applications.filter((a) => a.status === "offer").length;
  const ghostedCount = applications.filter(isGhosted).length;

  // Stage funnel counts (cumulative — everyone who reached this stage or beyond)
  const stageCount: Record<string, number> = {
    applied:      total,
    phone_screen: applications.filter((a) => ["phone_screen", "assessment", "technical", "offer"].includes(a.status)).length,
    assessment:   applications.filter((a) => ["assessment", "technical", "offer"].includes(a.status)).length,
    technical:    applications.filter((a) => ["technical", "offer"].includes(a.status)).length,
    offer:        offers,
  };

  // Platform breakdown with response rate
  const byPlatform: Record<string, { total: number; responded: number }> = {};
  applications.forEach((a) => {
    if (!byPlatform[a.platform]) byPlatform[a.platform] = { total: 0, responded: 0 };
    byPlatform[a.platform].total++;
    if (["phone_screen", "assessment", "technical", "offer", "rejected"].includes(a.status)) {
      byPlatform[a.platform].responded++;
    }
  });

  const platformData = Object.entries(byPlatform).map(([platform, { total: t, responded: r }]) => ({
    platform: platform.charAt(0).toUpperCase() + platform.slice(1),
    total: t,
    responded: r,
    responseRate: t > 0 ? Math.round(r / t * 100) : 0,
    color: PLATFORM_COLORS[platform] ?? "#9ca3af",
  }));

  // Day of week
  const dowCounts = Array(7).fill(0);
  applications.forEach((a) => {
    if (a.applied_at) {
      dowCounts[new Date(a.applied_at).getDay()]++;
    }
  });
  const dowData = DAYS.map((day, i) => ({ day, count: dowCounts[i] }));

  // Daily chart
  const activityData = fillDailyGaps(activityRaw);

  // Funnel conversion data for chart
  const funnelData = STAGE_ORDER.map(({ key, label, color }) => ({
    name: label,
    count: stageCount[key] ?? 0,
    color,
    pct: total > 0 ? Math.round((stageCount[key] ?? 0) / total * 100) : 0,
  }));

  // Best performing job titles (min 3 applications, sorted by response rate desc)
  const titleStats = useMemo(() => {
    const map: Record<string, { total: number; responded: number }> = {};
    applications.forEach((a) => {
      const title = a.job_title?.trim();
      if (!title) return;
      const key = title.toLowerCase();
      if (!map[key]) map[key] = { total: 0, responded: 0 };
      map[key].total++;
      if (["phone_screen", "assessment", "technical", "offer", "rejected"].includes(a.status)) {
        map[key].responded++;
      }
    });
    return Object.entries(map)
      .filter(([, v]) => v.total >= 3)
      .map(([key, v]) => ({
        title: applications.find((a) => a.job_title?.toLowerCase() === key)?.job_title ?? key,
        total: v.total,
        responded: v.responded,
        rate: Math.round((v.responded / v.total) * 100),
      }))
      .sort((a, b) => b.rate - a.rate || b.total - a.total)
      .slice(0, 10);
  }, [applications]);

  // Platform outcome breakdown (positive = phone_screen + assessment + technical + offer)
  const platformOutcomes = useMemo(() => {
    const map: Record<string, { total: number; phone_screen: number; assessment: number; technical: number; offer: number }> = {};
    applications.forEach((a) => {
      const p = a.platform;
      if (!map[p]) map[p] = { total: 0, phone_screen: 0, assessment: 0, technical: 0, offer: 0 };
      map[p].total++;
      if (a.status === "phone_screen") map[p].phone_screen++;
      else if (a.status === "assessment") map[p].assessment++;
      else if (a.status === "technical")  map[p].technical++;
      else if (a.status === "offer")      map[p].offer++;
    });
    return Object.entries(map)
      .sort(([, a], [, b]) => b.total - a.total)
      .map(([platform, d]) => {
        const positive = d.phone_screen + d.assessment + d.technical + d.offer;
        return {
          platform,
          label: platform.charAt(0).toUpperCase() + platform.slice(1),
          color: PLATFORM_COLORS[platform] ?? "#9ca3af",
          ...d,
          positive,
          rate: d.total > 0 ? Math.round((positive / d.total) * 100) : 0,
        };
      });
  }, [applications]);

  const bestPlatform = platformOutcomes.reduce<string | null>(
    (best, p) => (p.total >= 10 && (!best || p.rate > (platformOutcomes.find(x => x.platform === best)?.rate ?? -1))) ? p.platform : best,
    null,
  );

  // Monthly response rate trend
  const monthlyTrend = useMemo(() => {
    const map: Record<string, { applied: number; responded: number }> = {};
    applications.forEach((a) => {
      if (!a.applied_at) return;
      const month = a.applied_at.slice(0, 7);
      if (!map[month]) map[month] = { applied: 0, responded: 0 };
      map[month].applied++;
      if (["phone_screen", "assessment", "technical", "offer", "rejected"].includes(a.status))
        map[month].responded++;
    });
    return Object.entries(map)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([month, { applied, responded }]) => ({
        month,
        label: new Date(month + "-15").toLocaleDateString(undefined, { month: "short", year: "2-digit" }),
        applied,
        responded,
        rate: applied > 0 ? parseFloat((responded / applied * 100).toFixed(1)) : 0,
      }));
  }, [applications]);

  const trendSignal = useMemo(() => {
    const currentMonth = new Date().toISOString().slice(0, 7);
    const complete = monthlyTrend.filter((m) => m.month < currentMonth);
    if (complete.length < 2) return null;
    const last = complete[complete.length - 1];
    const prev = complete[complete.length - 2];
    const delta = parseFloat((last.rate - prev.rate).toFixed(1));
    return {
      delta,
      direction: delta > 1 ? "up" : delta < -1 ? "down" : ("flat" as const),
      lastLabel: last.label,
      prevLabel: prev.label,
    };
  }, [monthlyTrend]);

  // ── render ────────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-gray-50">
      {/* Top bar */}
      <header className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="font-bold text-brand-600 text-lg">HireTrace</span>
          {user && <span className="text-sm text-gray-400 ml-2">{user.email}</span>}
        </div>
        <nav className="flex items-center gap-1">
          <Link
            to="/dashboard"
            className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-800 px-3 py-1.5 rounded-lg transition-colors"
          >
            <LayoutDashboard className="w-4 h-4" />
            Dashboard
          </Link>
          <Link
            to="/stats"
            className="flex items-center gap-1.5 text-sm font-medium text-brand-600 bg-brand-50 px-3 py-1.5 rounded-lg"
          >
            <BarChart2 className="w-4 h-4" />
            Analytics
          </Link>
          <Link to="/settings" className="p-2 text-gray-500 hover:text-gray-700 transition-colors ml-1">
            <SettingsIcon className="w-5 h-5" />
          </Link>
          <button onClick={handleLogout} className="p-2 text-gray-500 hover:text-gray-700 transition-colors">
            <LogOut className="w-5 h-5" />
          </button>
        </nav>
      </header>

      <div className="max-w-7xl mx-auto px-6 py-6 space-y-6">

        {/* Title */}
        <div>
          <h1 className="text-xl font-bold text-gray-900">Job Search Analytics</h1>
          <p className="text-sm text-gray-400 mt-0.5">2026 overview · {total} applications tracked</p>
        </div>

        {/* Stat cards */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
          <StatCard label="Total Applied" value={total} sub={`+${stats?.applied_today ?? 0} today`} />
          <StatCard
            label="Got Response"
            value={pct(responded, total)}
            sub={`${responded} applications`}
            color="text-purple-600"
          />
          <StatCard
            label="Got Interview"
            value={pct(interviewed, total)}
            sub={`${interviewed} applications`}
            color="text-blue-600"
          />
          <StatCard
            label="Offer Rate"
            value={pct(offers, total)}
            sub={`${offers} offer${offers !== 1 ? "s" : ""}`}
            color={offers > 0 ? "text-green-600" : "text-gray-900"}
          />
          <StatCard
            label="Ghosted"
            value={pct(ghostedCount, total)}
            sub={`${ghostedCount} apps silent 3+ mo`}
            color={ghostedCount > 0 ? "text-red-500" : "text-gray-900"}
          />
        </div>

        {/* Daily activity chart */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">Applications Over Time</h2>
          {activityData.length > 0 ? (
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={activityData} margin={{ top: 4, right: 4, left: -24, bottom: 40 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 10, fill: "#94a3b8" }}
                  tickFormatter={fmtDate}
                  interval={0}
                  angle={-45}
                  textAnchor="end"
                />
                <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "#94a3b8" }} />
                <Tooltip
                  formatter={(v: number) => [v, "Applications"]}
                  labelFormatter={(l: string) => fmtDate(l)}
                  contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #e2e8f0" }}
                />
                <Line
                  type="monotone"
                  dataKey="count"
                  stroke="#6366f1"
                  strokeWidth={2}
                  dot={{ r: 3, fill: "#6366f1", strokeWidth: 0 }}
                  activeDot={{ r: 5 }}
                />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[220px] flex items-center justify-center text-gray-300 text-sm">
              No activity data yet
            </div>
          )}
        </div>

        {/* Response rate trend */}
        {monthlyTrend.length >= 2 && (
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <div className="flex items-start justify-between mb-4">
              <div>
                <h2 className="text-sm font-semibold text-gray-700">Response Rate Trend</h2>
                <p className="text-xs text-gray-400 mt-0.5">Monthly % of applications that got any response</p>
              </div>
              {trendSignal && (
                <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold ${
                  trendSignal.direction === "up"   ? "bg-green-50 text-green-700" :
                  trendSignal.direction === "down" ? "bg-red-50 text-red-600"    :
                                                     "bg-gray-100 text-gray-500"
                }`}>
                  {trendSignal.direction === "up"   && <TrendingUp className="w-3.5 h-3.5" />}
                  {trendSignal.direction === "down" && <TrendingDown className="w-3.5 h-3.5" />}
                  {trendSignal.direction === "flat" && <Minus className="w-3.5 h-3.5" />}
                  {trendSignal.direction === "up"   && `Market improving  +${trendSignal.delta}pp`}
                  {trendSignal.direction === "down" && `Market cooling  ${trendSignal.delta}pp`}
                  {trendSignal.direction === "flat" && "Market stable"}
                  <span className="font-normal text-[10px] opacity-70 ml-1">
                    ({trendSignal.prevLabel} → {trendSignal.lastLabel})
                  </span>
                </div>
              )}
            </div>
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={monthlyTrend} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="label" tick={{ fontSize: 11, fill: "#94a3b8" }} />
                <YAxis
                  allowDecimals={false}
                  tick={{ fontSize: 11, fill: "#94a3b8" }}
                  tickFormatter={(v) => `${v}%`}
                  domain={[0, "auto"]}
                />
                <Tooltip
                  formatter={(v: number, _: string, props: { payload?: { applied?: number; responded?: number } }) => [
                    `${v}%  (${props.payload?.responded ?? 0} of ${props.payload?.applied ?? 0})`,
                    "Response rate",
                  ]}
                  contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #e2e8f0" }}
                />
                <Line
                  type="monotone"
                  dataKey="rate"
                  stroke="#10b981"
                  strokeWidth={2.5}
                  dot={{ r: 4, fill: "#10b981", strokeWidth: 0 }}
                  activeDot={{ r: 6 }}
                />
              </LineChart>
            </ResponsiveContainer>
            <p className="text-[10px] text-gray-300 mt-2 text-right">
              Current month excluded from trend — responses still incoming
            </p>
          </div>
        )}

        {/* Platform + Stage conversion */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

          {/* Platform outcomes */}
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h2 className="text-sm font-semibold text-gray-700 mb-1">Platform Outcomes</h2>
            <p className="text-xs text-gray-400 mb-4">Which platform leads to positive results</p>
            {platformOutcomes.length > 0 ? (
              <div className="space-y-4">
                {platformOutcomes.map((p) => (
                  <div key={p.platform}>
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: p.color }} />
                        <span className="text-sm font-semibold text-gray-800">{p.label}</span>
                        {bestPlatform === p.platform && (
                          <span className="text-[10px] font-bold bg-green-100 text-green-700 px-1.5 py-0.5 rounded-full">BEST</span>
                        )}
                      </div>
                      <div className="text-right">
                        <span className={`text-sm font-bold ${p.rate >= 10 ? "text-green-600" : p.rate >= 5 ? "text-blue-600" : "text-gray-500"}`}>
                          {p.rate}%
                        </span>
                        <span className="text-xs text-gray-400 ml-1">win rate</span>
                      </div>
                    </div>
                    {/* Stage breakdown pills */}
                    <div className="flex gap-2 flex-wrap ml-4 mb-1">
                      {[
                        { key: "phone_screen", label: "Phone", color: "bg-purple-100 text-purple-700", val: p.phone_screen },
                        { key: "assessment",   label: "Assessment", color: "bg-orange-100 text-orange-700", val: p.assessment },
                        { key: "technical",    label: "Technical", color: "bg-yellow-100 text-yellow-700", val: p.technical },
                        { key: "offer",        label: "Offer", color: "bg-green-100 text-green-700", val: p.offer },
                      ].map(({ key, label, color, val }) => (
                        <span key={key} className={`text-[11px] font-medium px-2 py-0.5 rounded-full ${color}`}>
                          {label}: {val} ({p.total > 0 ? Math.round(val / p.total * 100) : 0}%)
                        </span>
                      ))}
                    </div>
                    {/* Win rate bar */}
                    <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden ml-4">
                      <div
                        className="h-full rounded-full transition-all duration-500"
                        style={{ width: `${Math.min(100, p.rate * 4)}%`, backgroundColor: p.color }}
                      />
                    </div>
                    <p className="text-[10px] text-gray-400 ml-4 mt-0.5">{p.total} applications</p>
                  </div>
                ))}
              </div>
            ) : (
              <div className="h-[180px] flex items-center justify-center text-gray-300 text-sm">No data</div>
            )}
          </div>

          {/* Stage conversion */}
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h2 className="text-sm font-semibold text-gray-700 mb-4">Stage Conversion</h2>
            {total > 0 ? (
              <div className="space-y-3 mt-2">
                {funnelData.map((stage, i) => (
                  <div key={stage.name}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-medium text-gray-600">{stage.name}</span>
                      <span className="text-xs text-gray-400">
                        {stage.count} <span className="text-gray-300 mx-1">·</span>
                        <span className="font-semibold text-gray-600">{stage.pct}%</span>
                      </span>
                    </div>
                    <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all duration-500"
                        style={{
                          width: `${stage.pct}%`,
                          backgroundColor: stage.color,
                        }}
                      />
                    </div>
                    {i < funnelData.length - 1 && funnelData[i].count > 0 && (
                      <p className="text-right text-[10px] text-gray-300 mt-0.5">
                        {pct(funnelData[i + 1].count, funnelData[i].count)} advanced →
                      </p>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="h-[180px] flex items-center justify-center text-gray-300 text-sm">No data</div>
            )}
          </div>
        </div>

        {/* Best performing job titles */}
        {titleStats.length > 0 && (
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h2 className="text-sm font-semibold text-gray-700 mb-1">Best Performing Job Titles</h2>
            <p className="text-xs text-gray-400 mb-4">Response rate by role (min. 3 applications)</p>
            <div className="space-y-3">
              {titleStats.map((t, i) => (
                <div key={t.title}>
                  <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="text-xs font-medium text-gray-400 w-4 shrink-0">{i + 1}</span>
                      <span className="text-sm font-medium text-gray-800 truncate">{t.title}</span>
                    </div>
                    <div className="flex items-center gap-3 shrink-0 ml-4">
                      <span className="text-xs text-gray-400">{t.responded}/{t.total}</span>
                      <span className={`text-sm font-bold w-12 text-right ${t.rate >= 30 ? "text-green-600" : t.rate >= 15 ? "text-blue-600" : "text-gray-600"}`}>
                        {t.rate}%
                      </span>
                    </div>
                  </div>
                  <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden ml-6">
                    <div
                      className={`h-full rounded-full ${t.rate >= 30 ? "bg-green-500" : t.rate >= 15 ? "bg-blue-500" : "bg-gray-400"}`}
                      style={{ width: `${t.rate}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Day of week + Platform pie */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

          {/* Day of week */}
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h2 className="text-sm font-semibold text-gray-700 mb-1">When Do You Apply?</h2>
            <p className="text-xs text-gray-400 mb-4">Applications submitted by day of week</p>
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={dowData} margin={{ top: 0, right: 0, left: -28, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                <XAxis dataKey="day" tick={{ fontSize: 12, fill: "#374151" }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "#94a3b8" }} />
                <Tooltip
                  formatter={(v: number) => [v, "Applications"]}
                  contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #e2e8f0" }}
                />
                <Bar dataKey="count" fill="#6366f1" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Platform pie */}
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h2 className="text-sm font-semibold text-gray-700 mb-1">Platform Share</h2>
            <p className="text-xs text-gray-400 mb-2">Where applications were submitted</p>
            {platformData.length > 0 ? (
              <div className="flex items-center gap-4">
                <ResponsiveContainer width="55%" height={180}>
                  <PieChart>
                    <Pie
                      data={platformData}
                      dataKey="total"
                      nameKey="platform"
                      cx="50%"
                      cy="50%"
                      innerRadius={48}
                      outerRadius={72}
                      paddingAngle={2}
                    >
                      {platformData.map((entry) => (
                        <Cell key={entry.platform} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip
                      formatter={(v: number) => [v, "Applications"]}
                      contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #e2e8f0" }}
                    />
                  </PieChart>
                </ResponsiveContainer>
                <div className="flex flex-col gap-2">
                  {platformData.map((p) => (
                    <div key={p.platform} className="flex items-center gap-2">
                      <span
                        className="w-3 h-3 rounded-full shrink-0"
                        style={{ backgroundColor: p.color }}
                      />
                      <span className="text-sm text-gray-700 font-medium">{p.platform}</span>
                      <span className="text-sm text-gray-400">{p.total}</span>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="h-[180px] flex items-center justify-center text-gray-300 text-sm">No data</div>
            )}
          </div>
        </div>

      </div>
    </div>
  );
}
