# 产品导航与页面状态

## 主导航

Today / Plans / Reviews / Memories；开发模式额外显示 Dev Trace。

## 首次进入

```text
无 token → /login 自动 guest 登录
有 token + profile_complete=false → /onboarding
有 token + profile_complete=true → /today
```

## Today 页面

- active Run 卡片：连接 SSE；
- 今日任务；
- 无计划时显示“生成计划”；
- Run 终态后重新拉 `/me` 和 `/plans/active`；
- SSE 断线显示重连，不清空已有权威数据。

## 前端状态来源

TanStack Query 管理 API 数据；SSE 事件只更新临时进度并触发 Query invalidate。不要把完整业务事实只放在 Zustand 或组件内存。
