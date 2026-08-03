import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "./client";
import type {
  ReviewCreateRequest,
  ReviewResponse,
  StartNextPlanResponse,
} from "./types";

export function useReviews() {
  return useQuery({
    queryKey: ["reviews"],
    queryFn: () => apiRequest<{ items: ReviewResponse[] }>(`/api/v1/reviews`),
    retry: false,
  });
}

export function useCreateReview() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      payload,
      idempotencyKey,
    }: {
      payload: ReviewCreateRequest;
      idempotencyKey: string;
    }) =>
      apiRequest<ReviewResponse>("/api/v1/reviews", {
        method: "POST",
        body: payload,
        idempotencyKey,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["reviews"] });
    },
  });
}

export function useStartNextPlan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      reviewId,
      idempotencyKey,
    }: {
      reviewId: string;
      idempotencyKey: string;
    }) =>
      apiRequest<StartNextPlanResponse>(
        `/api/v1/reviews/${reviewId}/start-next-plan`,
        { method: "POST", body: {}, idempotencyKey }
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["runs"] });
      qc.invalidateQueries({ queryKey: ["me"] });
    },
  });
}
