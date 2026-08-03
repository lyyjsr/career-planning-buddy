import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { apiBaseUrl, getAuthToken } from "./client";

const TERMINAL_EVENTS: readonly string[] = [
  "run.completed",
  "run.degraded",
  "run.failed",
  "run.cancelled",
];

/**
 * 订阅 Run 的 SSE 事件流。事件只用于刷新进度条，
 * 真正的权威数据始终通过 invalidate Query 重新 GET。
 *
 * 由于浏览器 EventSource 不能设置 Header，token 通过 query 参数发送；
 * 后端 SSE 端点对 Bearer 与 ?access_token 双通道鉴权。
 */
export type RunConnectionState = "idle" | "connecting" | "live" | "reconnecting" | "closed";

export interface RunStreamState {
  connectionState: RunConnectionState;
  progressMessage: string | null;
}

export function useRunEventStream(runId: string | undefined): RunStreamState {
  const qc = useQueryClient();
  const esRef = useRef<EventSource | null>(null);
  const [connectionState, setConnectionState] = useState<RunConnectionState>("idle");
  const [progressMessage, setProgressMessage] = useState<string | null>(null);

  useEffect(() => {
    if (runId === undefined) {
      setConnectionState("idle");
      setProgressMessage(null);
      return;
    }
    const token = getAuthToken();
    if (token === null) return;

    setConnectionState("connecting");

    const url = `${apiBaseUrl()}/api/v1/agent-runs/${runId}/events?access_token=${encodeURIComponent(token)}`;
    let es: EventSource;
    try {
      es = new EventSource(url, { withCredentials: false });
    } catch {
      return;
    }
    esRef.current = es;
    es.onopen = () => setConnectionState("live");

    // 默认 message + 显式 event 名都触发"拉权威 GET"
    es.onmessage = () => {
      qc.invalidateQueries({ queryKey: ["runs", runId] });
    };

    const handleTerminal = () => {
      qc.invalidateQueries({ queryKey: ["runs", runId] });
      qc.invalidateQueries({ queryKey: ["plans"] });
      qc.invalidateQueries({ queryKey: ["tasks"] });
      qc.invalidateQueries({ queryKey: ["me"] });
      es.close();
      setConnectionState("closed");
    };
    for (const evType of TERMINAL_EVENTS) {
      es.addEventListener(evType, handleTerminal);
    }

    es.addEventListener("plan.ready", () => {
      qc.invalidateQueries({ queryKey: ["plans"] });
      qc.invalidateQueries({ queryKey: ["tasks"] });
      qc.invalidateQueries({ queryKey: ["me"] });
    });

    es.addEventListener("progress", (event) => {
      try {
        const payload = JSON.parse((event as MessageEvent<string>).data) as {
          message?: unknown;
        };
        if (typeof payload.message === "string") setProgressMessage(payload.message);
      } catch {
        // Malformed progress must not interrupt the authoritative GET fallback.
      }
      qc.invalidateQueries({ queryKey: ["runs", runId] });
    });

    for (const eventType of ["node.started", "node.completed", "tool.called", "tool.returned"]) {
      es.addEventListener(eventType, () => {
        qc.invalidateQueries({ queryKey: ["runs", runId] });
      });
    }

    // 错误时不主动 close，浏览器 EventSource 会自动重试；
    // 同时 useRun 也在非终态时每 1.2s 轮询，作为权威兜底。
    es.onerror = () => setConnectionState("reconnecting");

    return () => {
      es.close();
      esRef.current = null;
      setConnectionState("closed");
    };
  }, [runId, qc]);

  return { connectionState, progressMessage };
}
