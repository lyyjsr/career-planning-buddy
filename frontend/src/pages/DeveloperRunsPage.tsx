import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { fetchDevRun, fetchDevRuns, replayDevRun } from "../api/dev";

function initialToken(): string {
  return window.localStorage.getItem("career_buddy_dev_token") ?? "";
}

export function DeveloperRunsPage(): JSX.Element {
  const [token, setToken] = useState(initialToken);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const runs = useQuery({
    queryKey: ["dev-runs", token],
    queryFn: () => fetchDevRuns(token),
    enabled: token.length > 0,
    retry: false,
  });
  const detail = useQuery({
    queryKey: ["dev-run", token, selectedRunId],
    queryFn: () => fetchDevRun(token, selectedRunId ?? ""),
    enabled: token.length > 0 && selectedRunId !== null,
    retry: false,
  });
  const replay = useMutation({
    mutationFn: (runId: string) => replayDevRun(token, runId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["dev-runs", token] });
    },
  });

  function updateToken(value: string): void {
    setToken(value);
    setSelectedRunId(null);
    window.localStorage.setItem("career_buddy_dev_token", value);
  }

  return (
    <main className="trace-shell">
      <header className="trace-header">
        <div>
          <p className="eyebrow">Stage 5 · Developer Console</p>
          <h1>Agent Run Trace</h1>
          <p>Inspect persisted steps, Tool calls, events, snapshots, and Replay invariants.</p>
        </div>
        <Link to="/">Back to health</Link>
      </header>

      <label className="token-field">
        Developer JWT
        <input
          aria-label="Developer JWT"
          type="password"
          value={token}
          onChange={(event) => updateToken(event.target.value)}
          placeholder="Stored only in this browser"
        />
      </label>

      {token.length === 0 ? <p>Enter a developer token to load Runs.</p> : null}
      {runs.isPending && token.length > 0 ? <p>Loading Runs…</p> : null}
      {runs.isError ? <p role="alert">Unable to load developer Runs.</p> : null}

      <div className="trace-grid">
        <section aria-label="Run list" className="trace-panel">
          <h2>Runs</h2>
          <ol className="run-list">
            {runs.data?.items.map((run) => (
              <li key={run.run_id}>
                <button type="button" onClick={() => setSelectedRunId(run.run_id)}>
                  <strong>{run.status}</strong>
                  <span>{run.run_id.slice(0, 8)}</span>
                  <small>{run.result_kind ?? run.error_code ?? "pending"}</small>
                </button>
              </li>
            ))}
          </ol>
        </section>

        <section aria-label="Run detail" className="trace-panel trace-detail">
          <h2>Trace detail</h2>
          {selectedRunId === null ? <p>Select a Run.</p> : null}
          {detail.isPending && selectedRunId !== null ? <p>Loading Trace…</p> : null}
          {detail.isError ? <p role="alert">Unable to load Trace detail.</p> : null}
          {detail.data ? (
            <>
              <dl className="trace-facts">
                <dt>Terminal invariant</dt>
                <dd>{detail.data.terminal_invariant.valid ? "valid" : "invalid"}</dd>
                <dt>Graph / model</dt>
                <dd>{detail.data.run.graph_version} / {detail.data.run.model_id ?? "—"}</dd>
                <dt>Latency / tokens</dt>
                <dd>{detail.data.run.total_latency_ms} ms / {detail.data.run.total_tokens_in + detail.data.run.total_tokens_out}</dd>
                <dt>Input snapshot SHA-256</dt>
                <dd>{detail.data.input_snapshot?.sha256 ?? "—"}</dd>
              </dl>
              <button
                type="button"
                disabled={replay.isPending}
                onClick={() => replay.mutate(detail.data.run.run_id)}
              >
                Replay with fixtures
              </button>
              {replay.isSuccess ? <p role="status">Replay created.</p> : null}
              {replay.isError ? <p role="alert">Replay failed.</p> : null}
              <h3>Steps</h3>
              <ol>{detail.data.steps.map((step) => <li key={step.sequence}>{step.sequence}. {step.node_name} — {step.status} ({step.latency_ms} ms)</li>)}</ol>
              <h3>Tools</h3>
              <ol>{detail.data.tools.map((tool) => <li key={tool.tool_call_id}>{tool.tool_name} — {tool.success ? "ok" : tool.error_code}</li>)}</ol>
              <h3>Events</h3>
              <ol>{detail.data.events.map((event) => <li key={event.sequence}>{event.sequence}. {event.event_type}</li>)}</ol>
              <details>
                <summary>Redacted snapshots and result</summary>
                <pre>{JSON.stringify({ input: detail.data.input_snapshot?.data, config: detail.data.config_snapshot.data, result: detail.data.result }, null, 2)}</pre>
              </details>
            </>
          ) : null}
        </section>
      </div>
    </main>
  );
}
