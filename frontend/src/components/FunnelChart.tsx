import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import type { DashboardStats } from "../lib/types";

const FUNNEL_ORDER = [
  { key: "applied", label: "Applied", color: "#3b82f6" },
  { key: "phone_screen", label: "Phone Screen", color: "#8b5cf6" },
  { key: "assessment", label: "Assessment", color: "#f97316" },
  { key: "technical", label: "Technical", color: "#f59e0b" },
  { key: "offer", label: "Offer", color: "#10b981" },
  { key: "rejected", label: "Rejected", color: "#ef4444" },
  { key: "ghosted", label: "Ghosted", color: "#6b7280" },
];

interface Props {
  stats: DashboardStats;
}

export function FunnelChart({ stats }: Props) {
  const data = FUNNEL_ORDER.map(({ key, label, color }) => ({
    name: label,
    value: stats.funnel[key as keyof typeof stats.funnel] ?? 0,
    color,
  }));

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <h2 className="text-sm font-semibold text-gray-700 mb-4">Application Funnel</h2>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={data} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
          <XAxis dataKey="name" tick={{ fontSize: 11 }} />
          <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
          <Tooltip />
          <Bar dataKey="value" radius={[4, 4, 0, 0]}>
            {data.map((entry) => (
              <Cell key={entry.name} fill={entry.color} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
