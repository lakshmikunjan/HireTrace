import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchApplications,
  updateStatus,
  deleteApplication,
  triggerScan,
} from "../lib/api";
import type { ApplicationFilters, ApplicationStatus } from "../lib/types";

export function useApplications(filters: ApplicationFilters = {}) {
  return useQuery({
    queryKey: ["applications", filters],
    queryFn: () => fetchApplications(filters),
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
    onSuccess: () => {
      setTimeout(() => {
        qc.invalidateQueries({ queryKey: ["applications"] });
        qc.invalidateQueries({ queryKey: ["stats"] });
      }, 3000); // give the worker a few seconds
    },
  });
}
