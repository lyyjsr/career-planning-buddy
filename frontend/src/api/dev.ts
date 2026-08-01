export interface DevRunSummary {
  run_id: string;
  replay_of_run_id: string | null;
  user_ref: string;
  status: string;
  result_kind: string | null;
  resolved_intent: string | null;
  graph_version: string;
  model_id: string | null;
  total_tokens_in: number;
  total_tokens_out: number;
  total_cost_cny: string;
  total_latency_ms: number;
  fallback_reason: string | null;
  error_code: string | null;
  created_at: string;
  finished_at: string | null;
}

export interface DevRunListResponse {
  items: DevRunSummary[];
  next_cursor: string | null;
}

export interface DevRunDetail {
  run: DevRunSummary;
  request_text: string;
  input_snapshot: { data: unknown; sha256: string } | null;
  config_snapshot: { data: unknown; sha256: string };
  result: unknown;
  steps: Array<{
    sequence: number;
    node_name: string;
    status: string;
    latency_ms: number;
    error_code: string | null;
  }>;
  tools: Array<{
    tool_call_id: string;
    tool_name: string;
    success: boolean;
    provider: string | null;
    latency_ms: number;
    error_code: string | null;
  }>;
  events: Array<{ sequence: number; event_type: string; payload: unknown }>;
  terminal_invariant: {
    terminal_count: number;
    terminal_is_last: boolean;
    valid: boolean;
  };
}

function apiUrl(path: string): string {
  const baseUrl = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/+$/, "");
  return `${baseUrl}${path}`;
}

async function requestJson(path: string, token: string, init?: RequestInit): Promise<unknown> {
  const response = await fetch(apiUrl(path), {
    ...init,
    headers: {
      Accept: "application/json",
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
  if (!response.ok) {
    throw new Error(`Developer API failed with status ${response.status}`);
  }
  return response.json();
}

export async function fetchDevRuns(token: string): Promise<DevRunListResponse> {
  return (await requestJson("/api/v1/dev/runs", token)) as DevRunListResponse;
}

export async function fetchDevRun(token: string, runId: string): Promise<DevRunDetail> {
  return (await requestJson(`/api/v1/dev/runs/${runId}`, token)) as DevRunDetail;
}

export async function replayDevRun(token: string, runId: string): Promise<void> {
  await requestJson(`/api/v1/dev/runs/${runId}/replay`, token, {
    method: "POST",
    body: JSON.stringify({ tool_mode: "fixture" }),
  });
}
