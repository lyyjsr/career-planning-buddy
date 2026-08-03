import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "./client";
import type { MemoryCandidateResponse, MemoryResponse } from "./types";

export function useMemories() {
  return useQuery({
    queryKey: ["memories"],
    queryFn: () => apiRequest<{ items: MemoryResponse[] }>(`/api/v1/memories`),
    retry: false,
  });
}

export function useMemoryCandidates() {
  return useQuery({
    queryKey: ["memory-candidates"],
    queryFn: () =>
      apiRequest<{ items: MemoryCandidateResponse[] }>(`/api/v1/memory-candidates`),
    retry: false,
  });
}

export function useDecideCandidate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ candidateId, decision }: { candidateId: string; decision: "confirm" | "reject" }) =>
      apiRequest<{ candidate_id: string; status: string }>(
        `/api/v1/memory-candidates/${candidateId}/${decision}`,
        { method: "POST", body: {} }
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["memory-candidates"] });
      qc.invalidateQueries({ queryKey: ["memories"] });
    },
  });
}

export function usePatchMemory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      memoryId,
      payload,
    }: {
      memoryId: string;
      payload: { status: "active" | "closed"; version: number };
    }) =>
      apiRequest<MemoryResponse>(`/api/v1/memories/${memoryId}`, {
        method: "PATCH",
        body: payload,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["memories"] });
    },
  });
}
