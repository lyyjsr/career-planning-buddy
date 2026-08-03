import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiRequest, getAuthToken } from "./client";
import type { GuestLoginResponse, MeResponse } from "./types";

const DEVICE_KEY = "cpb_device_id";

function getOrCreateDeviceId(): string {
  const existing = localStorage.getItem(DEVICE_KEY);
  if (existing !== null) return existing;
  const created = crypto.randomUUID();
  localStorage.setItem(DEVICE_KEY, created);
  return created;
}

export function useGuestLogin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiRequest<GuestLoginResponse>("/api/v1/auth/guest", {
        method: "POST",
        body: { device_id: getOrCreateDeviceId() },
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
    enabled: getAuthToken() !== null,
    retry: false,
  });
}
