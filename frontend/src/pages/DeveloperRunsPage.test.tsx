import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DeveloperRunsPage } from "./DeveloperRunsPage";

function renderPage(): void {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter><DeveloperRunsPage /></MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  window.localStorage.clear();
  vi.unstubAllGlobals();
});

describe("DeveloperRunsPage", () => {
  it("requires a developer token before loading", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    renderPage();
    expect(screen.getByText("Enter a developer token to load Runs.")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("renders a persisted trace and terminal invariant", async () => {
    const run = {
      run_id: "11111111-1111-1111-1111-111111111111",
      replay_of_run_id: null,
      user_ref: "0123456789ab",
      status: "completed",
      result_kind: "plan",
      resolved_intent: "create_plan",
      graph_version: "stage5-v1",
      model_id: "mock-career-planner-v1",
      total_tokens_in: 100,
      total_tokens_out: 200,
      total_cost_cny: "0",
      total_latency_ms: 12,
      fallback_reason: null,
      error_code: null,
      created_at: "2026-08-01T00:00:00Z",
      finished_at: "2026-08-01T00:00:01Z",
    };
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      const payload = url.endsWith("/api/v1/dev/runs")
        ? { items: [run], next_cursor: null }
        : {
            run,
            request_text: "Create a plan",
            input_snapshot: { data: { profile: "redacted" }, sha256: "a".repeat(64) },
            config_snapshot: { data: { provider: "mock" }, sha256: "b".repeat(64) },
            result: { plan_id: "p" },
            steps: [{ sequence: 1, node_name: "risk_gate", status: "completed", latency_ms: 1, error_code: null }],
            tools: [],
            events: [{ sequence: 1, event_type: "run.completed", payload: {} }],
            terminal_invariant: { terminal_count: 1, terminal_is_last: true, valid: true },
          };
      return new Response(JSON.stringify(payload), { status: 200, headers: { "Content-Type": "application/json" } });
    }));

    renderPage();
    fireEvent.change(screen.getByLabelText("Developer JWT"), { target: { value: "dev-token" } });
    fireEvent.click(await screen.findByRole("button", { name: /completed/ }));

    expect(await screen.findByText("valid")).toBeInTheDocument();
    expect(screen.getByText(/risk_gate/)).toBeInTheDocument();
    expect(screen.getByText(/run.completed/)).toBeInTheDocument();
  });
});
