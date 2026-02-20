import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchApplications,
  updateStatus,
  deleteApplication,
  triggerScan,
  fetchMe,
} from "../lib/api";
import type { ApplicationFilters, ApplicationStatus } from "../lib/types";

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
    onSuccess: () => qc.invalidateQueries({ queryKey: ["applications"] }),
  });
}

export function useDeleteApplication() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteApplication(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["applications"] });
      qc.invalidateQueries({ queryKey: ["stats"] });
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
