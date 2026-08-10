import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { TaskResponse } from "@/api/types";
import { WeeklyTaskSchedule } from "./WeeklyTaskSchedule";

const task: TaskResponse = {
  task_id: "task-1",
  plan_id: "plan-1",
  title: "梳理岗位要求",
  task_type: "learning",
  scheduled_date: "2026-08-10",
  order_index: 0,
  state: "completed",
  starter_action: "打开岗位描述",
  deliverable: "岗位要求清单",
  rationale: "先明确岗位要求，再决定项目补强顺序",
  estimated_minutes: 30,
  actual_minutes: 28,
  abandoned_reason: null,
  abandoned_reason_text: null,
  version: 2,
  started_at: "2026-08-10T01:00:00Z",
  completed_at: "2026-08-10T01:28:00Z",
  abandoned_at: null,
  created_at: "2026-08-10T00:00:00Z",
};

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date(2026, 7, 10, 12, 0, 0));
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("WeeklyTaskSchedule", () => {
  it("shows seven dates and keeps completion attached to its scheduled day", () => {
    render(<WeeklyTaskSchedule startDate="2026-08-10" tasks={[task]} />);

    expect(screen.getByText("梳理岗位要求")).toBeInTheDocument();
    expect(screen.getByText("已完成")).toBeInTheDocument();
    expect(screen.getByText("今天")).toBeInTheDocument();
    expect(screen.getByText("岗位要求清单")).toBeInTheDocument();
    expect(screen.getByText("打开岗位描述")).toBeInTheDocument();
    expect(screen.getByText("先明确岗位要求，再决定项目补强顺序")).toBeInTheDocument();
    expect(screen.getAllByText("当天暂无安排")).toHaveLength(6);
  });
});
