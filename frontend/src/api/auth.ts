import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "./client";
import type { GuestLoginResponse, MeResponse } from "./types";

export function useGuestLogin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiRequest<GuestLoginResponse>("/api/v1/auth/guest", {
        method: "POST",
        body: {},
      }),
    onSuccess: (data) => {
      qc.setQueryData(["me"], null);
      return data;
    },
  });
}

export function useMe() {
  return useQuery({
    queryKey: ["me"],
    queryFn: () => apiRequest<MeResponse>("/api/v1/me"),
    retry: false,
  });
}
