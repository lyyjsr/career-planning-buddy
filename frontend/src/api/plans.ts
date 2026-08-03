import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "./client";
import type { ActivePlanResponse, TaskUpdateRequest, TaskUpdateResponse } from "./types";

export function useActivePlan() {
  return useQuery({
    queryKey: ["plans", "active"],
    queryFn: () => apiRequest<ActivePlanResponse>("/api/v1/plans/active"),
    retry: false,
  });
}

export function usePlan(planId: string | undefined) {
  return useQuery({
    queryKey: ["plans", planId],
    queryFn: () => apiRequest<ActivePlanResponse>(`/api/v1/plans/${planId}`),
    enabled: planId !== undefined,
    retry: false,
  });
}

export function useUpdateTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ taskId, payload }: { taskId: string; payload: TaskUpdateRequest }) =>
      apiRequest<TaskUpdateResponse>(`/api/v1/tasks/${taskId}`, {
        method: "PATCH",
        body: payload,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["plans"] });
      qc.invalidateQueries({ queryKey: ["tasks"] });
      qc.invalidateQueries({ queryKey: ["me"] });
    },
  });
}
