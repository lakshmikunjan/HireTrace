import axios from "axios";
import type {
  Application,
  ActivityPoint,
  ApplicationFilters,
  ApplicationStatus,
  DashboardStats,
  InterviewStageUpdate,
  RecentUpdate,
  User,
} from "./types";

const api = axios.create({
  baseURL: "http://localhost:8000",
  withCredentials: true,
});

// Auth
export const fetchMe = (): Promise<User> =>
  api.get<User>("/auth/me").then((r) => r.data);

export const logout = (): Promise<void> =>
  api.post("/auth/logout").then(() => undefined);

// Applications
export const fetchApplications = (filters: ApplicationFilters = {}): Promise<Application[]> => {
  const params: Record<string, string | boolean> = {};
  if (filters.platform) params.platform = filters.platform;
  if (filters.status) params.status = filters.status;
  if (filters.remote_only) params.remote_only = true;
  if (filters.has_salary) params.has_salary = true;
  return api.get<Application[]>("/applications", { params }).then((r) => r.data);
};

export const updateStatus = (
  id: string,
  status: ApplicationStatus
): Promise<Application> =>
  api.patch<Application>(`/applications/${id}`, { status }).then((r) => r.data);

export const updateInterviewStages = (
  id: string,
  stages: InterviewStageUpdate
): Promise<Application> =>
  api.patch<Application>(`/applications/${id}/interview-stages`, stages).then((r) => r.data);

export const updateFields = (
  id: string,
  fields: { company_name?: string | null; job_title?: string | null; location?: string | null }
): Promise<Application> =>
  api.patch<Application>(`/applications/${id}/fields`, fields).then((r) => r.data);

export const fetchPotentialDuplicates = (): Promise<Application[][]> =>
  api.get<Application[][]>("/applications/potential-duplicates").then((r) => r.data);

export const autoCleanDuplicates = (): Promise<{ merged_orphans: number; deleted_dupes: number }> =>
  api.post("/applications/auto-clean-duplicates").then((r) => r.data);

export const deleteApplication = (id: string): Promise<void> =>
  api.delete(`/applications/${id}`).then(() => undefined);

export const triggerScan = (): Promise<{ new_applications: number; emails_checked: number }> =>
  api.post("/applications/scan").then((r) => r.data);

export const deleteAccount = (): Promise<void> =>
  api.delete("/applications/users/me").then(() => undefined);

// Dashboard
export const fetchStats = (): Promise<DashboardStats> =>
  api.get<DashboardStats>("/dashboard/stats").then((r) => r.data);

export const fetchActivity = (): Promise<ActivityPoint[]> =>
  api.get<ActivityPoint[]>("/dashboard/activity").then((r) => r.data);

export const fetchRecentUpdates = (): Promise<RecentUpdate[]> =>
  api.get<RecentUpdate[]>("/dashboard/recent-updates").then((r) => r.data);
