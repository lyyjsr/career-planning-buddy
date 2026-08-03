import { describe, expect, it } from "vitest";
import { ApiError } from "@/api/client";
import { toUserFacingError } from "@/lib/errors";

describe("toUserFacingError", () => {
  it("turns network failures into a recoverable product message", () => {
    const result = toUserFacingError(new ApiError(0, "NETWORK_UNREACHABLE", "raw", null));
    expect(result.title).toBe("网络似乎断开了");
    expect(result.action).toBe("retry");
    expect(result.message).not.toContain("NETWORK_UNREACHABLE");
  });

  it("does not expose an active-run error code to the user", () => {
    const result = toUserFacingError(
      new ApiError(409, "STATE_RUN_ALREADY_ACTIVE", "raw", "request-1"),
    );
    expect(result.title).toBe("已有一份路线正在生成");
    expect(result.action).toBe("view-progress");
    expect(result.requestId).toBe("request-1");
  });

  it("maps optimistic locking conflicts to refresh", () => {
    const result = toUserFacingError(new ApiError(409, "VERSION_CONFLICT", "raw", null));
    expect(result.action).toBe("refresh");
  });
});
