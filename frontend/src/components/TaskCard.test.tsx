import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { TaskResponse } from "@/api/types";
import { TaskCard } from "./TaskCard";

const task: TaskResponse = {
  task_id: "task-1",
  plan_id: "plan-1",
  title: "整理项目经历",
  task_type: "resume",
  scheduled_date: "2026-08-04",
  order_index: 0,
  state: "pending",
  starter_action: "打开简历",
  deliverable: "一段 STAR 描述",
  rationale: null,
  estimated_minutes: 30,
  actual_minutes: null,
  abandoned_reason: null,
  abandoned_reason_text: null,
  version: 1,
  started_at: null,
  completed_at: null,
  abandoned_at: null,
  created_at: "2026-08-04T00:00:00Z",
};

beforeEach(() => {
  localStorage.setItem("cpb_access_token", "guest-token");
});

afterEach(() => {
  cleanup();
  localStorage.clear();
  vi.unstubAllGlobals();
});

describe("TaskCard", () => {
  it("updates a pending task to in_progress with its optimistic-lock version", async () => {
    const feedback = vi.fn();
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) =>
      new Response(
        JSON.stringify({
          task: { ...task, state: "in_progress", version: 2 },
          plan_status: "active",
          companion_message: "已经开始，先完成第一步。",
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <TaskCard task={task} onFeedback={feedback} />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    expect(screen.getByRole("link", { name: /整理项目经历/ })).toHaveAttribute(
      "href",
      "/journey/plan-1/day/2026-08-04",
    );
    fireEvent.click(screen.getByRole("button", { name: "开始：整理项目经历" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const call = fetchMock.mock.calls[0];
    expect(call).toBeDefined();
    if (call === undefined) throw new Error("expected one task update request");
    const [url, init] = call;
    expect(String(url)).toContain("/api/v1/tasks/task-1");
    expect(init?.method).toBe("PATCH");
    expect(JSON.parse(String(init?.body))).toEqual({ state: "in_progress", version: 1 });
    await waitFor(() => expect(feedback).toHaveBeenCalledWith("已经开始，先完成第一步。"));
  });

  it("uses the same status circle to open completion for an in-progress task", () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <TaskCard task={{ ...task, state: "in_progress", version: 2 }} />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "完成：整理项目经历" }));

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "确认完成" })).toBeInTheDocument();
  });

  it("keeps a completed task visible and lets the user mark it incomplete", async () => {
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) =>
      new Response(
        JSON.stringify({
          task: {
            ...task,
            state: "in_progress",
            version: 4,
            actual_minutes: null,
            completed_at: null,
          },
          plan_status: "active",
          companion_message: "已恢复为进行中。",
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <TaskCard
            task={{
              ...task,
              state: "completed",
              version: 3,
              actual_minutes: 25,
              completed_at: "2026-08-04T01:00:00Z",
            }}
          />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    expect(screen.getByRole("button", { name: "已完成：整理项目经历" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "标记为未完成" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const [, init] = fetchMock.mock.calls[0] ?? [];
    expect(init?.method).toBe("PATCH");
    expect(JSON.parse(String(init?.body))).toEqual({ state: "in_progress", version: 3 });
  });
});
