import { useState } from "react";
import { Link } from "react-router-dom";
import { useMe } from "@/api/auth";
import { useCancelRun, useCreateRun, useRun } from "@/api/agent-runs";
import { useRunEventStream } from "@/api/sse";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Textarea } from "@/components/ui/textarea";
import { TaskCard } from "@/components/TaskCard";
import type { AgentRunResponse } from "@/api/types";

const TERMINAL = new Set(["completed", "degraded", "failed", "cancelled"]);

const STATUS_LABEL: Record<string, string> = {
  pending: "排队中",
  running: "规划中…",
  completed: "已完成",
  degraded: "已降级",
  failed: "失败",
  cancelled: "已取消",
  generated: "已生成",
  active: "进行中",
  archived: "已归档",
  planning: "规划中",
};

export function TodayPage(): JSX.Element {
  const me = useMe();
  const createRun = useCreateRun();
  const [message, setMessage] = useState("");
  const [submittedRunId, setSubmittedRunId] = useState<string | null>(null);

  // 优先用本次刚提交的 run id；否则用 /me 返回的活跃 Run（刷新后仍能恢复）
  const activeRunId = submittedRunId ?? me.data?.active_run?.run_id ?? null;

  useRunEventStream(activeRunId ?? undefined);
  const runQuery = useRun(activeRunId ?? undefined);
  const cancelRun = useCancelRun();

  function onSubmit(e: React.FormEvent): void {
    e.preventDefault();
    const trimmed = message.trim();
    if (trimmed.length === 0 || createRun.isPending) return;
    const key = `create-${Date.now()}`;
    createRun.mutate(
      {
        payload: { message: trimmed, hint_intent: "create_plan" },
        idempotencyKey: key,
      },
      {
        onSuccess: (created) => {
          setSubmittedRunId(created.run_id);
          setMessage("");
          // 通知 /me 失效，让活跃 run 同步
          void me.refetch();
        },
      }
    );
  }

  if (me.isLoading || me.data === undefined || me.data === null) {
    return <div className="text-muted-foreground">正在加载…</div>;
  }

  const meData = me.data;
  const todayTasks = meData.today_tasks ?? [];
  const activePlan = meData.active_plan;
  const run = runQuery.data;

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <section>
        <h1 className="text-2xl font-semibold tracking-tight">今天</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          把方向变成今天能开始、能复用的下一步行动。
        </p>
      </section>

      <RunStatusCard run={run} onCancel={() => activeRunId && cancelRun.mutate(activeRunId)} />

      {/* 发起 Plan —— 仅当上一 Run 不是 clarification 时才显示，避免和澄清卡片重复 */}
      {(run === undefined || TERMINAL.has(run.status)) && run?.result_kind !== "clarification" && (
        <Card>
          <CardHeader>
            <CardTitle>{activePlan ? "想要调整？" : "生成你的下一份计划"}</CardTitle>
            <CardDescription>
              描述需求，例如「帮我制定未来两周 agent 应用的求职准备计划」。
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={onSubmit} className="space-y-3">
              <Textarea
                rows={3}
                placeholder="说说你现在的目标和当下的需求…"
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                maxLength={2000}
              />
              <div className="flex justify-end">
                <Button type="submit" disabled={createRun.isPending || message.trim().length === 0}>
                  {createRun.isPending ? "提交中…" : "生成计划"}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      {/* 今日任务 */}
      <section className="space-y-3">
        <div className="flex items-baseline justify-between">
          <h2 className="text-lg font-medium">今日任务</h2>
          <span className="text-sm text-muted-foreground">{todayTasks.length} 个</span>
        </div>
        {todayTasks.length === 0 ? (
          <Card>
            <CardContent className="py-8 text-center text-sm text-muted-foreground">
              今天还没有任务。先生成一份计划。
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-3">
            {todayTasks.map((task) => (
              <TaskCard key={task.task_id} task={task} />
            ))}
          </div>
        )}
      </section>

      {/* Active Plan 摘要 */}
      {activePlan !== null && (
        <section className="space-y-3">
          <Separator />
          <div className="flex items-baseline justify-between">
            <h2 className="text-lg font-medium">当前计划</h2>
            <Link to={`/plans/${activePlan.plan_id}`} className="text-sm text-primary hover:underline">
              详情 →
            </Link>
          </div>
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <CardTitle className="text-base">{activePlan.overall_direction}</CardTitle>
                <Badge variant="outline">{STATUS_LABEL[activePlan.status] ?? activePlan.status}</Badge>
              </div>
              <CardDescription>{activePlan.summary}</CardDescription>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              {activePlan.horizon_start} ~ {activePlan.horizon_end} · {activePlan.weekly_focus.length} 周
            </CardContent>
          </Card>
        </section>
      )}
    </div>
  );
}

function RunStatusCard({
  run,
  onCancel,
}: {
  run: AgentRunResponse | undefined;
  onCancel: () => void;
}): JSX.Element | null {
  if (run === undefined) return null;

  const isTerminal = TERMINAL.has(run.status);
  if (run.status === "pending" || run.status === "running") {
    return (
      <Card className="border-primary/30 bg-accent/30">
        <CardContent className="flex items-center justify-between py-4">
          <div className="flex items-center gap-3">
            <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-primary" />
            <span className="text-sm font-medium">
              {run.status === "pending" ? "正在排队…" : "正在生成计划…"}
            </span>
            <span className="text-xs text-muted-foreground">
              大约需要 30~60 秒
            </span>
          </div>
          <Button variant="outline" size="sm" onClick={onCancel}>
            取消
          </Button>
        </CardContent>
      </Card>
    );
  }

  // 终态展示
  let body: JSX.Element;
  const kind = run.result_kind;
  if (isTerminal && kind === "plan" && run.result !== null && "plan_id" in run.result) {
    body = (
      <div className="text-sm">
        <span className="text-muted-foreground">计划已生成 · </span>
        {run.fallback_reason !== null && <span className="text-amber-700">降级原因：{run.fallback_reason}</span>}
      </div>
    );
  } else if (isTerminal && kind === "clarification" && run.result !== null && "questions" in run.result) {
    body = (
      <div className="space-y-3 text-sm">
        <p className="text-muted-foreground">需要补充一些信息才能继续：</p>
        <ul className="list-disc space-y-1 pl-5">
          {(run.result as { questions: string[] }).questions.map((q, i) => (
            <li key={i}>{q}</li>
          ))}
        </ul>
        <Link to="/onboarding">
          <Button variant="outline" size="sm">去补全画像 →</Button>
        </Link>
      </div>
    );
  } else if (isTerminal && kind === "safe_response" && run.result !== null && "message" in run.result) {
    body = (
      <p className="text-sm">{(run.result as { message: string }).message}</p>
    );
  } else if (run.status === "failed") {
    body = (
      <p className="text-sm text-destructive">
        生成失败：{run.error_code ?? "未知错误"}。请稍后重试。
      </p>
    );
  } else if (run.status === "cancelled") {
    body = <p className="text-sm text-muted-foreground">已取消。</p>;
  } else {
    body = <p className="text-sm text-muted-foreground">{STATUS_LABEL[run.status] ?? run.status}</p>;
  }

  return (
    <Card>
      <CardContent className="py-4">{body}</CardContent>
    </Card>
  );
}
