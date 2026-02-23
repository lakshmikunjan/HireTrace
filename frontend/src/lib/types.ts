export type ApplicationStatus =
  | "applied"
  | "phone_screen"
  | "assessment"
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
  rejected_at: string | null;
  last_activity_at: string | null;
  phone_screen_completed: boolean;
  phone_screen_completed_at: string | null;
  phone_screen_scheduled: string | null;
  phone_screen_missed: boolean;
  assessment_completed: boolean;
  assessment_completed_at: string | null;
  assessment_scheduled: string | null;
  assessment_missed: boolean;
  technical_completed: boolean;
  technical_completed_at: string | null;
  technical_scheduled: string | null;
  technical_missed: boolean;
  parse_confidence: number | null;
  manually_overridden: boolean;
  created_at: string;
}

// Helper type for stage keys
export type StageKey = 'phone_screen' | 'assessment' | 'technical';

export interface DashboardStats {
  funnel: Record<ApplicationStatus, number>;
  platform_breakdown: Record<string, number>;
  ghosting_count: number;
  total_applications: number;
  applied_today: number;
  applied_this_week: number;
  applied_this_month: number;
}

export interface ActivityPoint {
  date: string;   // "YYYY-MM-DD"
  count: number;
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

export interface RecentUpdate {
  company_name: string | null;
  job_title: string | null;
  status: ApplicationStatus;
  last_activity_at: string | null;
}

export interface InterviewStageUpdate {
  phone_screen_completed?: boolean;
  phone_screen_scheduled?: string;
  phone_screen_missed?: boolean;
  assessment_completed?: boolean;
  assessment_scheduled?: string;
  assessment_missed?: boolean;
  technical_completed?: boolean;
  technical_scheduled?: string;
  technical_missed?: boolean;
}
