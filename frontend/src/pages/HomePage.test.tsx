import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import { HomePage } from "./HomePage";

function renderHomePage(): void {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("HomePage", () => {
  it("renders the project name", () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise<Response>(() => undefined)),
    );

    renderHomePage();

    expect(
      screen.getByRole("heading", { name: "Career Planning Buddy" }),
    ).toBeInTheDocument();
  });

  it("shows the loading state while checking the backend", () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise<Response>(() => undefined)),
    );

    renderHomePage();

    expect(screen.getByText("正在检查后端状态…")).toBeInTheDocument();
  });

  it("shows the healthy state after a successful check", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        Promise.resolve(
          new Response(
            JSON.stringify({
              status: "ok",
              service: "Career Planning Buddy",
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        ),
      ),
    );

    renderHomePage();

    expect(await screen.findByText("后端正常")).toBeInTheDocument();
    expect(
      screen.getByText("Career Planning Buddy", { selector: ".status__detail" }),
    ).toBeInTheDocument();
  });

  it("shows the failure state when the health request fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => Promise.resolve(new Response(null, { status: 503 }))),
    );

    renderHomePage();

    expect(await screen.findByRole("alert")).toHaveTextContent("后端请求失败");
  });
});
