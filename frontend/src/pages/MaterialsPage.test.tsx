import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MaterialsPage } from "./MaterialsPage";

afterEach(() => vi.restoreAllMocks());

function renderPage(): void {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter><MaterialsPage /></MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("MaterialsPage", () => {
  it("extracts an uploaded resume into an editable preview before saving", async () => {
    const requests: Array<{ url: string; init?: RequestInit }> = [];
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      requests.push({ url, init });
      if (url.endsWith("/resume-versions/extract")) {
        expect(init?.body).toBeInstanceOf(FormData);
        return new Response(JSON.stringify({
          filename: "backend-resume.txt",
          media_type: "text/plain",
          character_count: 27,
          source_text: "后端工程师\n负责 FastAPI 与 PostgreSQL 服务开发。",
        }), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      if (url.endsWith("/resume-versions") && init?.method === "POST") {
        return new Response(JSON.stringify({ resume_version_id: "resume-1" }), {
          status: 201, headers: { "Content-Type": "application/json" },
        });
      }
      return new Response(JSON.stringify({ items: [] }), {
        status: 200, headers: { "Content-Type": "application/json" },
      });
    });
    renderPage();

    fireEvent.change(screen.getByLabelText("上传简历文件"), {
      target: { files: [new File(["resume"], "backend-resume.txt", { type: "text/plain" })] },
    });

    expect(await screen.findByText(/已解析 backend-resume.txt/)).toBeInTheDocument();
    expect(screen.getByLabelText("简历文本")).toHaveValue("后端工程师\n负责 FastAPI 与 PostgreSQL 服务开发。");
    fireEvent.change(screen.getByLabelText("简历文本"), {
      target: { value: "后端工程师\n负责 FastAPI、PostgreSQL 服务开发与自动化测试。" },
    });
    fireEvent.click(screen.getByRole("button", { name: "保存简历版本" }));

    await waitFor(() => expect(requests.some(({ url, init }) =>
      url.endsWith("/resume-versions") && init?.method === "POST"
    )).toBe(true));
    const save = requests.find(({ url, init }) => url.endsWith("/resume-versions") && init?.method === "POST");
    expect(JSON.parse(String(save?.init?.body))).toMatchObject({
      label: "backend-resume",
      source_type: "uploaded_file",
      source_filename: "backend-resume.txt",
      source_media_type: "text/plain",
      source_text: "后端工程师\n负责 FastAPI、PostgreSQL 服务开发与自动化测试。",
    });
  });
});
