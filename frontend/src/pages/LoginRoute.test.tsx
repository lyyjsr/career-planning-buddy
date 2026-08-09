import { StrictMode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { RequireAuth, RequireDev } from "./LoginRoute";

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("RequireAuth", () => {
  it("performs one guest login under StrictMode and opens the protected route", async () => {
    let guestRequests = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith("/api/v1/auth/guest")) {
          guestRequests += 1;
          return new Response(
            JSON.stringify({
              access_token: "guest-token",
              token_type: "bearer",
              expires_in: 3600,
              user: { id: "user-1", display_name: null, role: "user" },
            }),
            { status: 201, headers: { "Content-Type": "application/json" } },
          );
        }
        if (url.endsWith("/api/v1/me")) {
          expect((init?.headers as Record<string, string>).Authorization).toBe(
            "Bearer guest-token",
          );
          return new Response(
            JSON.stringify({
              user: { id: "user-1", display_name: null, role: "user" },
              profile_complete: true,
              profile: null,
              active_plan: null,
              today_tasks: [],
              latest_review: null,
              active_run: null,
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          );
        }
        return new Response(null, { status: 404 });
      }),
    );

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    render(
      <StrictMode>
        <QueryClientProvider client={queryClient}>
          <MemoryRouter initialEntries={["/today"]}>
            <Routes>
              <Route element={<RequireAuth requireProfile />}>
                <Route path="/today" element={<p>受保护的今日页面</p>} />
              </Route>
            </Routes>
          </MemoryRouter>
        </QueryClientProvider>
      </StrictMode>,
    );

    expect(await screen.findByText("受保护的今日页面")).toBeInTheDocument();
    await waitFor(() => expect(guestRequests).toBe(1));
    expect(localStorage.getItem("cpb_access_token")).toBe("guest-token");
  });
});

describe("RequireDev", () => {
  it("redirects a normal authenticated user away from developer routes", async () => {
    localStorage.setItem("cpb_access_token", "user-token");
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(
        JSON.stringify({
          user: { id: "user-1", display_name: null, role: "user" },
          profile_complete: true,
          profile: null,
          active_plan: null,
          today_tasks: [],
          latest_review: null,
          active_run: null,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      )),
    );
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/dev/evals"]}>
          <Routes>
            <Route element={<RequireDev />}>
              <Route path="/dev/evals" element={<p>开发者评测</p>} />
            </Route>
            <Route path="/me" element={<p>我的页面</p>} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );

    expect(await screen.findByText("我的页面")).toBeInTheDocument();
    expect(screen.queryByText("开发者评测")).not.toBeInTheDocument();
  });
});
