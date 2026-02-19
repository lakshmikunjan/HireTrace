export type ApplicationStatus =
  | "applied"
  | "phone_screen"
  | "technical"
  | "offer"
  | "rejected"
  | "ghosted";

export type ApplicationPlatform = "linkedin" | "indeed" | "direct";

export interface Application {
  id: string;
  company_name: string | null;
  job_title: string | null;
  location: string | null;
  salary_range: string | null;
  platform: ApplicationPlatform;
  status: ApplicationStatus;
  applied_at: string | null;
  last_activity_at: string | null;
  parse_confidence: number | null;
  manually_overridden: boolean;
  created_at: string;
}

export interface DashboardStats {
  funnel: Record<ApplicationStatus, number>;
  platform_breakdown: Record<string, number>;
  ghosting_count: number;
  applied_today: number;
  applied_this_week: number;
}

export interface User {
  id: string;
  email: string;
  last_scan_at: string | null;
  created_at: string;
}

export interface ApplicationFilters {
  platform?: ApplicationPlatform;
  status?: ApplicationStatus;
  remote_only?: boolean;
  has_salary?: boolean;
}
