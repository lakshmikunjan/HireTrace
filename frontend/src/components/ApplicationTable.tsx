import { useState } from "react";
import { Trash2 } from "lucide-react";
import { GhostingBadge } from "./GhostingBadge";
import { InterviewStageTracker } from "./InterviewStageTracker";
import { useUpdateStatus, useDeleteApplication, useUpdateFields } from "../hooks/useApplications";
import type { Application, ApplicationStatus } from "../lib/types";

const STATUS_COLORS: Record<ApplicationStatus, string> = {
  applied:      "bg-blue-100 text-blue-700",
  phone_screen: "bg-purple-100 text-purple-700",
  assessment:   "bg-orange-100 text-orange-700",
  technical:    "bg-yellow-100 text-yellow-700",
  offer:        "bg-green-100 text-green-700",
  rejected:     "bg-red-100 text-red-700",
  ghosted:      "bg-gray-100 text-gray-600",
};

const STATUS_LABELS: Record<ApplicationStatus, string> = {
  applied:      "Applied",
  phone_screen: "Phone Screen",
  assessment:   "Assessment",
  technical:    "Technical",
  offer:        "Offer",
  rejected:     "Rejected",
  ghosted:      "Ghosted",
};

const STATUSES: ApplicationStatus[] = [
  "applied", "phone_screen", "assessment", "technical", "offer", "rejected", "ghosted",
];

const INTERVIEW_STATUSES: ApplicationStatus[] = ["phone_screen", "assessment", "technical"];

const PLATFORM_STYLES: Record<string, { label: string; className: string }> = {
  linkedin: { label: "LinkedIn", className: "bg-blue-600 text-white" },
  indeed:   { label: "Indeed",   className: "bg-[#2164f3] text-white" },
  direct:   { label: "Direct",   className: "bg-gray-200 text-gray-700" },
};

interface Props {
  applications: Application[];
}

export function ApplicationTable({ applications }: Props) {
  const updateStatus = useUpdateStatus();
  const updateFields = useUpdateFields();
  const deleteApp = useDeleteApplication();
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingField, setEditingField] = useState<{ id: string; field: "company_name" | "job_title" } | null>(null);
  const [editValue, setEditValue] = useState("");

  function startFieldEdit(appId: string, field: "company_name" | "job_title", current: string | null) {
    setEditingField({ id: appId, field });
    setEditValue(current ?? "");
  }

  function commitFieldEdit() {
    if (!editingField) return;
    updateFields.mutate({ id: editingField.id, fields: { [editingField.field]: editValue.trim() || null } });
    setEditingField(null);
  }

  if (applications.length === 0) {
    return (
      <div className="text-center py-20 text-gray-400 text-sm">
        No applications yet. Connect Gmail and click <strong>Scan Now</strong>.
      </div>
    );
  }

  return (
    <table className="w-full text-sm text-left">
      <thead>
        <tr className="border-b border-gray-200 text-xs uppercase tracking-wide text-gray-400">
          <th className="pb-3 pr-6 font-semibold">Company & Role</th>
          <th className="pb-3 pr-6 font-semibold">Status</th>
          <th className="pb-3 pr-6 font-semibold">Interview Stages</th>
          <th className="pb-3 pr-4 font-semibold">Applied</th>
          <th className="pb-3 font-semibold w-6"></th>
        </tr>
      </thead>
      <tbody className="divide-y divide-gray-100">
        {applications.map((app) => (
          <tr key={app.id} className="hover:bg-gray-50 transition-colors group">

            {/* Company + Role + Location + Platform */}
            <td className="py-3 pr-6 max-w-[240px]">
              {editingField?.id === app.id && editingField.field === "company_name" ? (
                <input
                  autoFocus
                  value={editValue}
                  onChange={(e) => setEditValue(e.target.value)}
                  onBlur={commitFieldEdit}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") commitFieldEdit();
                    if (e.key === "Escape") setEditingField(null);
                  }}
                  className="font-semibold text-gray-900 text-sm border-b-2 border-blue-400 bg-transparent outline-none w-full"
                  placeholder="Company name"
                />
              ) : (
                <p
                  className="font-semibold text-gray-900 truncate cursor-pointer hover:text-blue-600 transition-colors"
                  onClick={() => startFieldEdit(app.id, "company_name", app.company_name)}
                  title="Click to edit"
                >
                  {app.company_name ?? <span className="text-gray-300 font-normal italic">Unknown — click to edit</span>}
                </p>
              )}

              {editingField?.id === app.id && editingField.field === "job_title" ? (
                <input
                  autoFocus
                  value={editValue}
                  onChange={(e) => setEditValue(e.target.value)}
                  onBlur={commitFieldEdit}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") commitFieldEdit();
                    if (e.key === "Escape") setEditingField(null);
                  }}
                  className="text-xs text-gray-500 border-b-2 border-blue-400 bg-transparent outline-none w-full mt-0.5"
                  placeholder="Job title"
                />
              ) : (
                <p
                  className="text-xs text-gray-500 truncate mt-0.5 cursor-pointer hover:text-blue-600 transition-colors"
                  onClick={() => startFieldEdit(app.id, "job_title", app.job_title)}
                  title="Click to edit"
                >
                  {app.job_title ?? <span className="text-gray-400 italic">—</span>}
                  {app.location && <span className="text-gray-400"> · {app.location}</span>}
                </p>
              )}
            </td>

            {/* Status */}
            <td className="py-3 pr-6">
              {editingId === app.id ? (
                <select
                  autoFocus
                  defaultValue={app.status}
                  className="text-xs border border-gray-300 rounded-lg px-2 py-1 focus:outline-none focus:ring-2 focus:ring-brand-400"
                  onBlur={() => setEditingId(null)}
                  onChange={(e) => {
                    updateStatus.mutate({ id: app.id, status: e.target.value as ApplicationStatus });
                    setEditingId(null);
                  }}
                >
                  {STATUSES.map((s) => (
                    <option key={s} value={s}>{STATUS_LABELS[s]}</option>
                  ))}
                </select>
              ) : (
                <div className="flex flex-col gap-1">
                  <span
                    className={`inline-block w-fit text-xs rounded-full px-2.5 py-0.5 font-medium cursor-pointer select-none ${STATUS_COLORS[app.status]}`}
                    onClick={() => setEditingId(app.id)}
                    title="Click to change status"
                  >
                    {STATUS_LABELS[app.status]}
                  </span>
                  <GhostingBadge lastActivityAt={app.last_activity_at} status={app.status} />
                </div>
              )}
            </td>

            {/* Interview Stages */}
            <td className="py-3 pr-6">
              {INTERVIEW_STATUSES.includes(app.status) ? (
                <InterviewStageTracker application={app} />
              ) : (
                <span className="text-gray-300 text-xs">—</span>
              )}
            </td>

            {/* Applied date + Platform */}
            <td className="py-3 pr-4">
              <p className="text-gray-700 text-xs whitespace-nowrap">
                {app.applied_at
                  ? new Date(app.applied_at).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })
                  : "—"}
              </p>
              <span className={`inline-block text-xs rounded-full px-2 py-0.5 font-medium mt-1 ${(PLATFORM_STYLES[app.platform] ?? PLATFORM_STYLES.direct).className}`}>
                {(PLATFORM_STYLES[app.platform] ?? PLATFORM_STYLES.direct).label}
              </span>
            </td>

            {/* Delete */}
            <td className="py-3">
              <button
                onClick={() => { if (confirm("Delete this application?")) deleteApp.mutate(app.id); }}
                className="text-gray-300 hover:text-red-500 transition-colors opacity-0 group-hover:opacity-100"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </td>

          </tr>
        ))}
      </tbody>
    </table>
  );
}
