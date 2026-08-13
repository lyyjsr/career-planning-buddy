import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "./client";
import type { JobTargetResponse, ResumeAssessmentResponse, ResumeDocumentExtractResponse, ResumeVersionResponse } from "./types";

export function useResumeVersions() {
  return useQuery({
    queryKey: ["resume-versions"],
    queryFn: () => apiRequest<{ items: ResumeVersionResponse[] }>("/api/v1/resume-versions"),
  });
}

export function useCreateResumeAssessment() {
  return useMutation({
    mutationFn: (body: { resume_version_id: string; job_target_id: string; interview_session_id: string }) =>
      apiRequest<ResumeAssessmentResponse>("/api/v1/resume-assessments", {
        method: "POST", body, idempotencyKey: crypto.randomUUID(),
      }),
  });
}

export function useJobTargets() {
  return useQuery({
    queryKey: ["job-targets"],
    queryFn: () => apiRequest<{ items: JobTargetResponse[] }>("/api/v1/job-targets"),
  });
}

export function useCreateResumeVersion() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      label: string;
      source_text: string;
      source_type?: "pasted_text" | "uploaded_file";
      source_filename?: string;
      source_media_type?: string;
    }) =>
      apiRequest<ResumeVersionResponse>("/api/v1/resume-versions", {
        method: "POST",
        body,
        idempotencyKey: crypto.randomUUID(),
      }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["resume-versions"] }),
  });
}

export function useExtractResumeDocument() {
  return useMutation({
    mutationFn: (file: File) => {
      const body = new FormData();
      body.append("file", file);
      return apiRequest<ResumeDocumentExtractResponse>("/api/v1/resume-versions/extract", {
        method: "POST",
        body,
        timeoutMs: 30_000,
      });
    },
  });
}

export function useCreateJobTarget() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { title: string; company?: string; jd_text: string }) =>
      apiRequest<JobTargetResponse>("/api/v1/job-targets", {
        method: "POST",
        body,
        idempotencyKey: crypto.randomUUID(),
      }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["job-targets"] }),
  });
}

export function useDeleteResumeVersion() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (resumeId: string) => apiRequest<void>(`/api/v1/resume-versions/${resumeId}`, { method: "DELETE" }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["resume-versions"] }),
  });
}

export function useDeleteJobTarget() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (targetId: string) => apiRequest<void>(`/api/v1/job-targets/${targetId}`, { method: "DELETE" }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["job-targets"] }),
  });
}
