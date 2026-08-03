import { ApiError } from "@/api/client";

export interface UserFacingError {
  title: string;
  message: string;
  action: "retry" | "refresh" | "view-progress";
  requestId: string | null;
}

export function toUserFacingError(error: unknown): UserFacingError {
  if (!(error instanceof ApiError)) {
    return {
      title: "暂时没能完成这一步",
      message: "请稍后再试，你已经保存的内容不会丢失。",
      action: "retry",
      requestId: null,
    };
  }

  if (error.code === "NETWORK_UNREACHABLE") {
    return {
      title: "网络似乎断开了",
      message: "正在等待重新连接，你已经完成的进度不会丢失。",
      action: "retry",
      requestId: error.requestId,
    };
  }
  if (error.code === "STATE_RUN_ALREADY_ACTIVE") {
    return {
      title: "已有一份路线正在生成",
      message: "返回今天页面即可继续查看生成进度。",
      action: "view-progress",
      requestId: error.requestId,
    };
  }
  if (error.code?.includes("VERSION") === true || error.status === 409) {
    return {
      title: "内容已经更新",
      message: "请刷新后再继续操作。",
      action: "refresh",
      requestId: error.requestId,
    };
  }
  if (error.status === 429 || error.code?.includes("RATE") === true) {
    return {
      title: "规划服务有点忙",
      message: "稍等片刻后重试即可。",
      action: "retry",
      requestId: error.requestId,
    };
  }
  return {
    title: "暂时没能完成这一步",
    message: "请稍后重试；如果问题持续，可把请求编号提供给开发者。",
    action: "retry",
    requestId: error.requestId,
  };
}
