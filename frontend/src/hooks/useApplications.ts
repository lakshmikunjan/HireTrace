import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchApplications,
  updateStatus,
  updateInterviewStages,
  updateFields,
  deleteApplication,
  fetchPotentialDuplicates,
  autoCleanDuplicates,
  triggerScan,
  fetchMe,
} from "../lib/api";
import type { ApplicationFilters, ApplicationStatus, InterviewStageUpdate } from "../lib/types";

export function useApplications(filters: ApplicationFilters = {}) {
  return useQuery({
    queryKey: ["applications", filters],
    queryFn: () => fetchApplications(filters),
    refetchInterval: 2 * 60 * 1000, // re-fetch every 2 min to pick up periodic scans
    refetchOnWindowFocus: true,      // also refetch immediately when tab regains focus
  });
}

export function useUpdateStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status }: { id: string; status: ApplicationStatus }) =>
      updateStatus(id, status),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["applications"] });
      qc.invalidateQueries({ queryKey: ["potential-duplicates"] });
    },
  });
}

export function useUpdateInterviewStages() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, stages }: { id: string; stages: InterviewStageUpdate }) =>
      updateInterviewStages(id, stages),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["applications"] }),
  });
}

export function useUpdateFields() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, fields }: { id: string; fields: { company_name?: string | null; job_title?: string | null; location?: string | null } }) =>
      updateFields(id, fields),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["applications"] }),
  });
}

export function useAutoCleanDuplicates() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: autoCleanDuplicates,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["applications"] });
      qc.invalidateQueries({ queryKey: ["stats"] });
      qc.invalidateQueries({ queryKey: ["potential-duplicates"] });
    },
  });
}

export function usePotentialDuplicates() {
  return useQuery({
    queryKey: ["potential-duplicates"],
    queryFn: fetchPotentialDuplicates,
    staleTime: 5 * 60 * 1000,
  });
}

export function useDeleteApplication() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteApplication(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["applications"] });
      qc.invalidateQueries({ queryKey: ["stats"] });
      qc.invalidateQueries({ queryKey: ["potential-duplicates"] });
    },
  });
}

export function useTriggerScan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: triggerScan,
    onSuccess: async () => {
      // Poll last_scan_at until it changes (background task completed),
      // then refresh application data. Give up after ~60 seconds.
      const baseline = await fetchMe().then((u) => u.last_scan_at).catch(() => null);
      let attempts = 0;
      const poll = async () => {
        attempts++;
        const current = await fetchMe().then((u) => u.last_scan_at).catch(() => null);
        if (current !== baseline || attempts >= 20) {
          qc.invalidateQueries({ queryKey: ["applications"] });
          qc.invalidateQueries({ queryKey: ["stats"] });
        } else {
          setTimeout(poll, 3000);
        }
      };
      setTimeout(poll, 4000); // first check after 4 seconds
    },
  });
}
