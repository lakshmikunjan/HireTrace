import { useState } from "react";
import { X, Trash2, CheckCheck, ChevronLeft, ChevronRight, Copy, GitMerge } from "lucide-react";
import { useDeleteApplication, useUpdateStatus } from "../hooks/useApplications";
import type { Application } from "../lib/types";

const STATUS_COLORS: Record<string, string> = {
  applied:      "bg-blue-100 text-blue-700",
  phone_screen: "bg-purple-100 text-purple-700",
  assessment:   "bg-orange-100 text-orange-700",
  technical:    "bg-yellow-100 text-yellow-700",
  offer:        "bg-green-100 text-green-700",
  rejected:     "bg-red-100 text-red-700",
  ghosted:      "bg-gray-100 text-gray-600",
};

const STATUS_LABELS: Record<string, string> = {
  applied:      "Applied",
  phone_screen: "Phone Screen",
  assessment:   "Assessment",
  technical:    "Technical",
  offer:        "Offer",
  rejected:     "Rejected",
  ghosted:      "Ghosted",
};

const PLATFORM_STYLES: Record<string, { label: string; className: string }> = {
  linkedin: { label: "LinkedIn", className: "bg-blue-600 text-white" },
  indeed:   { label: "Indeed",   className: "bg-[#2164f3] text-white" },
  direct:   { label: "Direct",   className: "bg-gray-200 text-gray-700" },
};

function fmtDate(d: string | null) {
  if (!d) return "—";
  return new Date(d).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

/** An orphan is a rejected app that has no job_title — created when the scanner
 *  couldn't match the rejection email to an existing application. */
function findOrphan(group: Application[]): { orphan: Application; proper: Application } | null {
  const orphan = group.find((a) => a.status === "rejected" && !a.job_title);
  const proper = group.find((a) => a.id !== orphan?.id);
  if (orphan && proper) return { orphan, proper };
  return null;
}

interface Props {
  groups: Application[][];
  onClose: () => void;
}

export function DuplicateReviewModal({ groups: initialGroups, onClose }: Props) {
  const deleteApp    = useDeleteApplication();
  const updateStatus = useUpdateStatus();

  const [pending, setPending] = useState<Application[][]>(initialGroups);
  const [index, setIndex]     = useState(0);
  const [merging, setMerging] = useState(false);

  const current    = pending[index];
  const orphanPair = current ? findOrphan(current) : null;

  function resolveGroup() {
    const next = pending.filter((_, i) => i !== index);
    setPending(next);
    setIndex(Math.min(index, Math.max(0, next.length - 1)));
  }

  function keepGroup() {
    resolveGroup();
  }

  function deleteOne(appId: string) {
    deleteApp.mutate(appId, {
      onSuccess: () => {
        const updatedGroup = current.filter((a) => a.id !== appId);
        if (updatedGroup.length < 2) {
          resolveGroup();
        } else {
          const next = pending.map((g, i) => (i === index ? updatedGroup : g));
          setPending(next);
          setIndex(Math.min(index, Math.max(0, next.length - 1)));
        }
      },
    });
  }

  /** Merge an orphaned rejection into the proper application:
   *  1. Mark the proper application as "rejected" (preserving its job_title + location)
   *  2. Delete the orphan record */
  function mergeOrphan(orphanId: string, properId: string) {
    setMerging(true);
    updateStatus.mutate(
      { id: properId, status: "rejected" },
      {
        onSuccess: () => {
          deleteApp.mutate(orphanId, {
            onSuccess: () => {
              setMerging(false);
              resolveGroup();
            },
            onError: () => setMerging(false),
          });
        },
        onError: () => setMerging(false),
      },
    );
  }

  if (pending.length === 0) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
        <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4 p-8 text-center">
          <CheckCheck className="w-12 h-12 text-green-500 mx-auto mb-4" />
          <h2 className="text-lg font-semibold text-gray-900 mb-2">All clear!</h2>
          <p className="text-sm text-gray-500 mb-6">No more potential duplicates to review.</p>
          <button
            onClick={onClose}
            className="bg-brand-600 hover:bg-brand-700 text-white text-sm font-medium rounded-lg px-6 py-2 transition-colors"
          >
            Done
          </button>
        </div>
      </div>
    );
  }

  const platformStyle = (p: string) => PLATFORM_STYLES[p] ?? PLATFORM_STYLES.direct;
  const isBusy = deleteApp.isPending || updateStatus.isPending || merging;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl flex flex-col max-h-[90vh]">

        {/* Header */}
        <div className="flex items-start justify-between px-6 pt-6 pb-4 border-b border-gray-100">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Copy className="w-4 h-4 text-amber-500" />
              <h2 className="text-base font-semibold text-gray-900">
                {orphanPair ? "Unmatched Rejection" : "Possible Duplicate"}
              </h2>
            </div>
            <p className="text-xs text-gray-400">
              {orphanPair
                ? "A rejection email couldn't be matched to your existing application — merge them to keep your data clean."
                : "These applications look identical — is one a duplicate?"}
            </p>
          </div>
          <div className="flex items-center gap-3">
            {pending.length > 1 && (
              <span className="text-xs text-gray-400 font-medium">
                {index + 1} of {pending.length}
              </span>
            )}
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600 transition-colors">
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Group label */}
        <div className={`px-6 py-3 border-b ${orphanPair ? "bg-red-50 border-red-100" : "bg-amber-50 border-amber-100"}`}>
          <p className={`text-sm font-medium ${orphanPair ? "text-red-800" : "text-amber-800"}`}>
            {current[0].company_name ?? "Unknown"}
            {current[0].job_title ? ` · ${current[0].job_title}` : ""}
          </p>
          <p className={`text-xs mt-0.5 ${orphanPair ? "text-red-500" : "text-amber-600"}`}>
            {orphanPair
              ? "Rejection email created a separate record — the original has the job title and location"
              : `${current.length} matching applications found`}
          </p>
        </div>

        {/* Application cards */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-3">
          {current.map((app) => {
            const isOrphan = orphanPair?.orphan.id === app.id;
            return (
              <div
                key={app.id}
                className={`flex items-start gap-4 p-4 rounded-xl border transition-colors ${
                  isOrphan ? "border-red-200 bg-red-50/40" : "border-gray-200 hover:border-gray-300"
                }`}
              >
                <div className="flex-1 min-w-0">
                  {isOrphan && (
                    <p className="text-[10px] font-semibold text-red-500 uppercase tracking-wide mb-1.5">
                      Orphan — no job title or location
                    </p>
                  )}
                  <div className="flex items-center gap-2 flex-wrap mb-1.5">
                    <span className={`text-xs rounded-full px-2 py-0.5 font-medium ${STATUS_COLORS[app.status] ?? "bg-gray-100 text-gray-600"}`}>
                      {STATUS_LABELS[app.status] ?? app.status}
                    </span>
                    <span className={`text-xs rounded-full px-2 py-0.5 font-medium ${platformStyle(app.platform).className}`}>
                      {platformStyle(app.platform).label}
                    </span>
                  </div>
                  <p className="text-sm font-medium text-gray-900 truncate">{app.company_name ?? "Unknown"}</p>
                  <p className={`text-xs truncate ${app.job_title ? "text-gray-500" : "text-gray-300 italic"}`}>
                    {app.job_title ?? "no job title"}
                  </p>
                  {app.location
                    ? <p className="text-xs text-gray-400 mt-0.5">{app.location}</p>
                    : isOrphan && <p className="text-xs text-red-300 italic mt-0.5">no location</p>
                  }
                  <p className="text-xs text-gray-400 mt-1">{fmtDate(app.applied_at)}</p>
                </div>

                {!orphanPair && (
                  <button
                    onClick={() => deleteOne(app.id)}
                    disabled={isBusy}
                    className="shrink-0 flex items-center gap-1.5 text-xs text-red-500 hover:text-red-700 hover:bg-red-50 rounded-lg px-2.5 py-1.5 transition-colors disabled:opacity-50"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    Delete
                  </button>
                )}
              </div>
            );
          })}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-gray-100">
          <div>
            {index > 0 && (
              <button
                onClick={() => setIndex(index - 1)}
                disabled={isBusy}
                className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700 px-3 py-1.5 rounded-lg hover:bg-gray-100 transition-colors disabled:opacity-50"
              >
                <ChevronLeft className="w-4 h-4" />
                Prev
              </button>
            )}
          </div>

          <div className="flex gap-2">
            {orphanPair ? (
              <>
                <button
                  onClick={keepGroup}
                  disabled={isBusy}
                  className="text-sm text-gray-500 hover:text-gray-700 border border-gray-200 px-3 py-1.5 rounded-lg transition-colors disabled:opacity-50"
                >
                  Skip
                </button>
                <button
                  onClick={() => mergeOrphan(orphanPair.orphan.id, orphanPair.proper.id)}
                  disabled={isBusy}
                  className="flex items-center gap-1.5 text-sm bg-red-600 hover:bg-red-700 text-white font-medium px-4 py-1.5 rounded-lg transition-colors disabled:opacity-60"
                >
                  <GitMerge className="w-3.5 h-3.5" />
                  {merging ? "Merging…" : "Merge & mark rejected"}
                </button>
              </>
            ) : (
              <button
                onClick={keepGroup}
                disabled={isBusy}
                className="text-sm text-gray-600 hover:text-gray-800 border border-gray-200 hover:border-gray-300 px-4 py-1.5 rounded-lg transition-colors disabled:opacity-50"
              >
                Keep all, not duplicates
              </button>
            )}

            {index < pending.length - 1 && (
              <button
                onClick={() => setIndex(index + 1)}
                disabled={isBusy}
                className="flex items-center gap-1 text-sm bg-brand-600 hover:bg-brand-700 text-white px-4 py-1.5 rounded-lg transition-colors disabled:opacity-50"
              >
                Next
                <ChevronRight className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>

      </div>
    </div>
  );
}
