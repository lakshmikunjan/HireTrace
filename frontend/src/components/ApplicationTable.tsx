import { useState } from "react";
import { Trash2 } from "lucide-react";
import { GhostingBadge } from "./GhostingBadge";
import { useUpdateStatus, useDeleteApplication } from "../hooks/useApplications";
import type { Application, ApplicationStatus } from "../lib/types";

const STATUS_COLORS: Record<ApplicationStatus, string> = {
  applied: "bg-blue-100 text-blue-700",
  phone_screen: "bg-purple-100 text-purple-700",
  technical: "bg-yellow-100 text-yellow-700",
  offer: "bg-green-100 text-green-700",
  rejected: "bg-red-100 text-red-700",
  ghosted: "bg-gray-100 text-gray-600",
};

const STATUSES: ApplicationStatus[] = [
  "applied", "phone_screen", "technical", "offer", "rejected", "ghosted",
];

interface Props {
  applications: Application[];
}

export function ApplicationTable({ applications }: Props) {
  const updateStatus = useUpdateStatus();
  const deleteApp = useDeleteApplication();
  const [editingId, setEditingId] = useState<string | null>(null);

  if (applications.length === 0) {
    return (
      <div className="text-center py-20 text-gray-400 text-sm">
        No applications yet. Connect Gmail and click <strong>Scan Now</strong>.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm text-left">
        <thead>
          <tr className="border-b border-gray-200 text-xs uppercase tracking-wide text-gray-500">
            <th className="py-3 pr-4 font-medium">Company</th>
            <th className="py-3 pr-4 font-medium">Role</th>
            <th className="py-3 pr-4 font-medium">Location</th>
            <th className="py-3 pr-4 font-medium">Salary</th>
            <th className="py-3 pr-4 font-medium">Platform</th>
            <th className="py-3 pr-4 font-medium">Status</th>
            <th className="py-3 pr-4 font-medium">Applied</th>
            <th className="py-3 font-medium"></th>
          </tr>
        </thead>
        <tbody>
          {applications.map((app) => (
            <tr
              key={app.id}
              className="border-b border-gray-100 hover:bg-gray-50 transition-colors"
            >
              <td className="py-3 pr-4 font-medium text-gray-900">
                {app.company_name ?? <span className="text-gray-400 italic">Unknown</span>}
              </td>
              <td className="py-3 pr-4 text-gray-700">
                {app.job_title ?? <span className="text-gray-400 italic">—</span>}
              </td>
              <td className="py-3 pr-4 text-gray-600">
                {app.location ?? "—"}
              </td>
              <td className="py-3 pr-4 text-gray-600">
                {app.salary_range ?? "—"}
              </td>
              <td className="py-3 pr-4">
                <span className="capitalize text-gray-600">{app.platform}</span>
              </td>
              <td className="py-3 pr-4">
                {editingId === app.id ? (
                  <select
                    autoFocus
                    defaultValue={app.status}
                    className="text-xs border border-gray-300 rounded px-2 py-1"
                    onBlur={() => setEditingId(null)}
                    onChange={(e) => {
                      updateStatus.mutate({
                        id: app.id,
                        status: e.target.value as ApplicationStatus,
                      });
                      setEditingId(null);
                    }}
                  >
                    {STATUSES.map((s) => (
                      <option key={s} value={s}>
                        {s.replace("_", " ")}
                      </option>
                    ))}
                  </select>
                ) : (
                  <div className="flex items-center gap-2">
                    <span
                      className={`inline-block text-xs rounded-full px-2 py-0.5 font-medium cursor-pointer ${STATUS_COLORS[app.status]}`}
                      onClick={() => setEditingId(app.id)}
                      title="Click to change status"
                    >
                      {app.status.replace("_", " ")}
                    </span>
                    <GhostingBadge lastActivityAt={app.last_activity_at} />
                  </div>
                )}
              </td>
              <td className="py-3 pr-4 text-gray-500">
                {app.applied_at
                  ? new Date(app.applied_at).toLocaleDateString()
                  : "—"}
              </td>
              <td className="py-3">
                <button
                  onClick={() => {
                    if (confirm("Delete this application?")) {
                      deleteApp.mutate(app.id);
                    }
                  }}
                  className="text-gray-400 hover:text-red-500 transition-colors"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
