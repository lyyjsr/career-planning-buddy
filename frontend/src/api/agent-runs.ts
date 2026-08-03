import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "./client";
import type {
  AgentRunCreateRequest,
  AgentRunCreatedResponse,
  AgentRunResponse,
} from "./types";

export function useCreateRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      payload,
      idempotencyKey,
    }: {
      payload: AgentRunCreateRequest;
      idempotencyKey: string;
    }) =>
      apiRequest<AgentRunCreatedResponse>("/api/v1/agent-runs", {
        method: "POST",
        body: payload,
        idempotencyKey,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["me"] });
    },
  });
}

export function useRun(runId: string | undefined) {
  return useQuery({
    queryKey: ["runs", runId],
    queryFn: () => apiRequest<AgentRunResponse>(`/api/v1/agent-runs/${runId}`),
    enabled: runId !== undefined,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data === undefined) return false;
      // 终态后停止轮询；非终态每 1.2s 拉一次
      if (["completed", "degraded", "failed", "cancelled"].includes(data.status)) {
        return false;
      }
      return 1200;
    },
  });
}

export function useCancelRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (runId: string) =>
      apiRequest<{ run_id: string; status: string }>(
        `/api/v1/agent-runs/${runId}/cancel`,
        { method: "POST", body: {} }
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["runs"] });
    },
  });
}
