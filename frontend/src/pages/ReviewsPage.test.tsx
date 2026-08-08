import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import { useMe } from "@/api/auth";
import { useActivePlan } from "@/api/plans";
import { useReviews, useStartNextPlan } from "@/api/reviews";
import { ReviewsPage } from "./ReviewsPage";

vi.mock("@/api/auth", () => ({ useMe: vi.fn() }));
vi.mock("@/api/plans", () => ({ useActivePlan: vi.fn() }));
vi.mock("@/api/reviews", () => ({
  useCreateReview: vi.fn(),
  useReviews: vi.fn(),
  useStartNextPlan: vi.fn(),
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("ReviewsPage", () => {
  it("shows the no-plan state without an unusable create button", () => {
    vi.mocked(useMe).mockReturnValue({
      data: { profile_complete: true, active_plan: null },
    } as unknown as ReturnType<typeof useMe>);
    vi.mocked(useActivePlan).mockReturnValue({
      data: undefined,
      isLoading: false,
    } as unknown as ReturnType<typeof useActivePlan>);
    vi.mocked(useReviews).mockReturnValue({
      data: { items: [] },
      isLoading: false,
    } as unknown as ReturnType<typeof useReviews>);
    vi.mocked(useStartNextPlan).mockReturnValue({
      isPending: false,
      mutate: vi.fn(),
    } as unknown as ReturnType<typeof useStartNextPlan>);

    render(
      <MemoryRouter>
        <ReviewsPage />
      </MemoryRouter>,
    );

    expect(
      screen.getByText("需要先生成至少一份计划才能开始复盘。"),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "新建复盘" }),
    ).not.toBeInTheDocument();
  });
});
