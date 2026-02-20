import type { ApplicationFilters, ApplicationPlatform, ApplicationStatus } from "../lib/types";

interface Props {
  filters: ApplicationFilters;
  onChange: (f: ApplicationFilters) => void;
}

const STATUSES: ApplicationStatus[] = [
  "applied", "phone_screen", "assessment", "technical", "offer", "rejected", "ghosted",
];

const PLATFORMS: ApplicationPlatform[] = ["linkedin", "indeed", "direct"];

export function Filters({ filters, onChange }: Props) {
  return (
    <aside className="w-52 shrink-0 space-y-5">
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-2">
          Platform
        </p>
        <div className="space-y-1">
          <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
            <input
              type="radio"
              name="platform"
              checked={!filters.platform}
              onChange={() => onChange({ ...filters, platform: undefined })}
            />
            All
          </label>
          {PLATFORMS.map((p) => (
            <label key={p} className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer capitalize">
              <input
                type="radio"
                name="platform"
                checked={filters.platform === p}
                onChange={() => onChange({ ...filters, platform: p })}
              />
              {p}
            </label>
          ))}
        </div>
      </div>

      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-2">
          Status
        </p>
        <div className="space-y-1">
          <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
            <input
              type="radio"
              name="status"
              checked={!filters.status}
              onChange={() => onChange({ ...filters, status: undefined })}
            />
            All
          </label>
          {STATUSES.map((s) => (
            <label key={s} className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
              <input
                type="radio"
                name="status"
                checked={filters.status === s}
                onChange={() => onChange({ ...filters, status: s })}
              />
              {s.replace("_", " ")}
            </label>
          ))}
        </div>
      </div>

      <div className="space-y-2">
        <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
          <input
            type="checkbox"
            checked={!!filters.remote_only}
            onChange={(e) => onChange({ ...filters, remote_only: e.target.checked })}
          />
          Remote only
        </label>
        <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
          <input
            type="checkbox"
            checked={!!filters.has_salary}
            onChange={(e) => onChange({ ...filters, has_salary: e.target.checked })}
          />
          Has salary
        </label>
      </div>
    </aside>
  );
}
