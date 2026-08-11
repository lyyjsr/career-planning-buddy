import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "./client";
import type {
  ActivePlanResponse,
  TaskAdjustmentProposalResponse,
  TaskDetailResponse,
  TaskEditRequest,
  TaskEditResponse,
  TaskUpdateRequest,
  TaskUpdateResponse,
} from "./types";

export interface PlanListResponse {
  items: ActivePlanResponse[];
  next_cursor: string | null;
}

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

export function usePlans() {
  return useQuery({
    queryKey: ["plans"],
    queryFn: () => apiRequest<PlanListResponse>("/api/v1/plans"),
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

export function useTaskDetail(taskId: string | undefined) {
  return useQuery({
    queryKey: ["tasks", taskId, "detail"],
    queryFn: () => apiRequest<TaskDetailResponse>(`/api/v1/tasks/${taskId}`),
    enabled: taskId !== undefined,
    retry: false,
  });
}

function invalidateTaskData(qc: ReturnType<typeof useQueryClient>, taskId: string): void {
  qc.invalidateQueries({ queryKey: ["tasks", taskId, "detail"] });
  qc.invalidateQueries({ queryKey: ["plans"] });
  qc.invalidateQueries({ queryKey: ["me"] });
}

export function useEditTaskDetails() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      taskId,
      payload,
      idempotencyKey,
    }: {
      taskId: string;
      payload: TaskEditRequest;
      idempotencyKey: string;
    }) => apiRequest<TaskEditResponse>(`/api/v1/tasks/${taskId}/details`, {
      method: "PATCH",
      body: payload,
      idempotencyKey,
    }),
    onSuccess: (result) => invalidateTaskData(qc, result.task.task_id),
  });
}

export function useCreateTaskAdjustmentProposal() {
  return useMutation({
    mutationFn: ({
      taskId,
      version,
      message,
      idempotencyKey,
    }: {
      taskId: string;
      version: number;
      message: string;
      idempotencyKey: string;
    }) => apiRequest<TaskAdjustmentProposalResponse>(
      `/api/v1/tasks/${taskId}/adjustment-proposals`,
      {
        method: "POST",
        body: { version, message },
        idempotencyKey,
      },
    ),
  });
}

export function useConfirmTaskAdjustment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ adjustmentId, version }: { adjustmentId: string; version: number }) =>
      apiRequest<TaskEditResponse>(
        `/api/v1/task-adjustment-proposals/${adjustmentId}/confirm`,
        { method: "POST", body: { version } },
      ),
    onSuccess: (result) => invalidateTaskData(qc, result.task.task_id),
  });
}

export function useRejectTaskAdjustment() {
  return useMutation({
    mutationFn: ({ adjustmentId, version }: { adjustmentId: string; version: number }) =>
      apiRequest<TaskAdjustmentProposalResponse>(
        `/api/v1/task-adjustment-proposals/${adjustmentId}/reject`,
        { method: "POST", body: { version } },
      ),
  });
}
