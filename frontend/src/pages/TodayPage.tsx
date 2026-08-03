import { useState } from "react";
import {
  ArrowRight,
  CheckCircle2,
  ChevronDown,
  CircleDot,
  Clock3,
  Map,
  RefreshCw,
  Sparkles,
  WifiOff,
} from "lucide-react";
import { Link } from "react-router-dom";
import { useMe } from "@/api/auth";
import { useCancelRun, useCreateRun, useRun } from "@/api/agent-runs";
import { useRunEventStream, type RunStreamState } from "@/api/sse";
import type { AgentRunResponse, TaskResponse } from "@/api/types";
import { TaskCard } from "@/components/TaskCard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { toUserFacingError } from "@/lib/errors";
import { GOAL_LABELS, STAGE_LABELS } from "@/lib/labels";

const TERMINAL = new Set(["completed", "degraded", "failed", "cancelled"]);
const QUICK_INTENTS = [
  "从零规划求职准备",
  "做一个能写进简历的项目",
  "开始准备投递",
  "准备下一场面试",
];

function displayDate(): string {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "long",
    day: "numeric",
    weekday: "long",
  }).format(new Date());
}

function nextActionTask(tasks: TaskResponse[]): TaskResponse | undefined {
  return tasks.find((task) => task.state === "in_progress") ?? tasks.find((task) => task.state === "pending");
}

export function TodayPage(): JSX.Element {
  const me = useMe();
  const createRun = useCreateRun();
  const cancelRun = useCancelRun();
  const [message, setMessage] = useState("");
  const [submittedRunId, setSubmittedRunId] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);

  const activeRunId = submittedRunId ?? me.data?.active_run?.run_id ?? null;
  const stream = useRunEventStream(activeRunId ?? undefined);
  const runQuery = useRun(activeRunId ?? undefined);

  if (me.isLoading || me.data === undefined || me.data === null) {
    return <div className="text-sm text-muted-foreground">正在准备今天的行动…</div>;
  }

  const activePlan = me.data.active_plan;
  const tasks = me.data.today_tasks;
  const firstTask = nextActionTask(tasks);
  const remainingTasks = firstTask === undefined ? [] : tasks.filter((task) => task.task_id !== firstTask.task_id);
  const allSettled = tasks.length > 0 && tasks.every((task) => ["completed", "abandoned", "expired"].includes(task.state));
  const completedCount = tasks.filter((task) => task.state === "completed").length;
  const totalMinutes = tasks.reduce((sum, task) => sum + task.estimated_minutes, 0);
  const run = runQuery.data;
  const isPlanning = run?.status === "pending" || run?.status === "running";

  function submitPlan(event: React.FormEvent): void {
    event.preventDefault();
    const trimmed = message.trim();
    if (trimmed.length === 0 || createRun.isPending || isPlanning) return;
    createRun.mutate(
      {
        payload: {
          message: trimmed,
          hint_intent: activePlan === null ? "create_plan" : "replan",
          source_plan_id: activePlan?.plan_id ?? null,
        },
        idempotencyKey: `create-${Date.now()}`,
      },
      {
        onSuccess: (created) => {
          setSubmittedRunId(created.run_id);
          setMessage("");
          setFeedback(null);
          void me.refetch();
        },
      },
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6 sm:space-y-8">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-sm font-medium text-primary">{displayDate()}</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight sm:text-3xl">
            {firstTask !== undefined ? "今天只推进一个关键结果" : allSettled ? "今天已经收好尾了" : "把方向变成今天的一步"}
          </h1>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            {me.data.profile === null
              ? ""
              : `${GOAL_LABELS[me.data.profile.goal_type]} · ${STAGE_LABELS[me.data.profile.stage]} · 每天约 ${me.data.profile.time_budget_minutes} 分钟`}
          </p>
        </div>
        <Link to="/settings/profile" className="text-sm font-medium text-primary hover:underline">
          调整目标与时间
        </Link>
      </header>

      {run !== undefined && (
        <RunPanel
          run={run}
          stream={stream}
          onCancel={() => activeRunId !== null && cancelRun.mutate(activeRunId)}
          onRetry={() => setSubmittedRunId(null)}
        />
      )}

      {feedback !== null && (
        <div className="flex items-start gap-3 rounded-2xl border border-primary/20 bg-accent/55 p-4 text-sm leading-6">
          <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
          <div>
            <div className="font-medium">搭子反馈</div>
            <p className="text-muted-foreground">{feedback}</p>
          </div>
        </div>
      )}

      {!isPlanning && activePlan === null && (
        <CreatePlanPanel
          message={message}
          onMessageChange={setMessage}
          onSubmit={submitPlan}
          pending={createRun.isPending}
          error={createRun.error}
        />
      )}

      {!isPlanning && firstTask !== undefined && (
        <section className="space-y-4" aria-labelledby="first-step-heading">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-primary">建议先做</p>
              <h2 id="first-step-heading" className="mt-1 text-lg font-semibold">你的第一步</h2>
            </div>
            <Badge variant="outline" className="gap-1 py-1">
              <Clock3 className="h-3.5 w-3.5" />{firstTask.estimated_minutes} 分钟
            </Badge>
          </div>
          <TaskCard task={firstTask} featured onFeedback={setFeedback} />

          {remainingTasks.length > 0 && (
            <details className="group rounded-2xl border bg-card">
              <summary className="flex min-h-14 cursor-pointer list-none items-center justify-between px-4 text-sm font-medium sm:px-5">
                <span>完成后还有 {remainingTasks.length} 步 · 今日共 {totalMinutes} 分钟</span>
                <ChevronDown className="h-4 w-4 text-muted-foreground transition-transform group-open:rotate-180" />
              </summary>
              <div className="space-y-3 border-t p-3 sm:p-4">
                {remainingTasks.map((task) => (
                  <TaskCard key={task.task_id} task={task} onFeedback={setFeedback} />
                ))}
              </div>
            </details>
          )}
        </section>
      )}

      {allSettled && !isPlanning && activePlan !== null && (
        <Card className="border-primary/20 bg-gradient-to-br from-card to-accent/40">
          <CardContent className="space-y-4 p-5 sm:p-6">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary text-primary-foreground">
              <CheckCircle2 className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-lg font-semibold">收下今天的进展</h2>
              <p className="mt-1 text-sm leading-6 text-muted-foreground">
                完成 {completedCount} 步。用 30 秒记下阻碍，明天的计划会更贴合真实节奏。
              </p>
            </div>
            <Button asChild><Link to="/reviews">开始今日复盘 <ArrowRight className="h-4 w-4" /></Link></Button>
          </CardContent>
        </Card>
      )}

      {activePlan !== null && (
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold">这一步在路线中的位置</h2>
            <Link to="/journey" className="inline-flex min-h-11 items-center gap-1 text-sm font-medium text-primary hover:underline">
              查看完整路线 <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
          <Card className="overflow-hidden">
            <CardContent className="grid gap-4 p-5 sm:grid-cols-[1fr_auto] sm:items-center">
              <div className="min-w-0">
                <div className="flex items-center gap-2 text-sm font-medium">
                  <Map className="h-4 w-4 text-primary" />{activePlan.overall_direction}
                </div>
                <p className="mt-2 line-clamp-2 text-sm leading-6 text-muted-foreground">{activePlan.rationale}</p>
              </div>
              <Badge variant="secondary">{activePlan.weekly_focus.length} 周路线</Badge>
            </CardContent>
          </Card>
          {!isPlanning && (
            <details className="rounded-xl">
              <summary className="cursor-pointer py-2 text-sm text-muted-foreground hover:text-foreground">需要调整今天或方向？</summary>
              <form onSubmit={submitPlan} className="space-y-3 rounded-2xl border bg-card p-4">
                <Textarea value={message} onChange={(event) => setMessage(event.target.value)} rows={3} maxLength={2000} placeholder="例如：今天只有 30 分钟，请减少任务量" />
                <Button type="submit" size="sm" disabled={createRun.isPending || message.trim().length === 0}>生成调整方案</Button>
              </form>
            </details>
          )}
        </section>
      )}
    </div>
  );
}

function CreatePlanPanel({
  message,
  onMessageChange,
  onSubmit,
  pending,
  error,
}: {
  message: string;
  onMessageChange: (value: string) => void;
  onSubmit: (event: React.FormEvent) => void;
  pending: boolean;
  error: unknown;
}): JSX.Element {
  const displayError = error === null ? null : toUserFacingError(error);
  return (
    <Card className="overflow-hidden border-primary/20 shadow-[0_18px_60px_-36px_rgba(24,122,112,0.5)]">
      <CardHeader className="bg-gradient-to-br from-accent/60 to-card pb-5">
        <div className="mb-2 flex h-10 w-10 items-center justify-center rounded-xl bg-primary text-primary-foreground">
          <Sparkles className="h-5 w-5" />
        </div>
        <CardTitle>今天想解决什么？</CardTitle>
        <CardDescription className="leading-6">先选一个常见目标，也可以直接说出你当下最需要解决的问题。</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 p-5 sm:p-6">
        <div className="flex flex-wrap gap-2">
          {QUICK_INTENTS.map((intent) => (
            <Button key={intent} type="button" variant={message === intent ? "default" : "outline"} size="sm" onClick={() => onMessageChange(intent)}>
              {intent}
            </Button>
          ))}
        </div>
        <form onSubmit={onSubmit} className="space-y-3">
          <Textarea rows={4} value={message} onChange={(event) => onMessageChange(event.target.value)} maxLength={2000} placeholder="例如：两周内做出一个能写进简历的 Agent 项目" />
          {displayError !== null && (
            <div className="rounded-xl bg-destructive/10 p-3 text-sm text-destructive">
              <div className="font-medium">{displayError.title}</div>
              <div className="mt-1">{displayError.message}</div>
            </div>
          )}
          <Button type="submit" className="w-full sm:w-auto" disabled={pending || message.trim().length === 0}>
            {pending ? "正在提交…" : "为我生成路线"}<ArrowRight className="h-4 w-4" />
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

function RunPanel({
  run,
  stream,
  onCancel,
  onRetry,
}: {
  run: AgentRunResponse;
  stream: RunStreamState;
  onCancel: () => void;
  onRetry: () => void;
}): JSX.Element | null {
  if (run.status === "pending" || run.status === "running") {
    const progress = stream.progressMessage ?? (run.status === "pending" ? "正在进入规划队列" : "正在整理适合你的行动路径");
    return (
      <Card className="border-primary/25 bg-accent/35">
        <CardContent className="space-y-4 p-5">
          <div className="flex items-start justify-between gap-4">
            <div className="flex min-w-0 gap-3">
              <span className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground">
                <RefreshCw className="h-4 w-4 animate-spin" />
              </span>
              <div>
                <div className="font-medium">正在为你生成路线</div>
                <p className="mt-1 text-sm leading-6 text-muted-foreground">{progress}</p>
              </div>
            </div>
            <Button variant="ghost" size="sm" onClick={onCancel}>取消</Button>
          </div>
          <div className="grid gap-2 text-xs text-muted-foreground sm:grid-cols-3">
            <span className="flex items-center gap-1.5"><CheckCircle2 className="h-3.5 w-3.5 text-primary" />理解目标与限制</span>
            <span className="flex items-center gap-1.5"><CircleDot className="h-3.5 w-3.5 animate-pulse text-primary" />整理行动路径</span>
            <span className="flex items-center gap-1.5"><CircleDot className="h-3.5 w-3.5" />检查今日任务</span>
          </div>
          {stream.connectionState === "reconnecting" && (
            <p className="flex items-center gap-2 rounded-xl bg-background/70 p-3 text-xs text-muted-foreground">
              <WifiOff className="h-4 w-4" />连接中断，正在恢复；你的进度不会丢失。
            </p>
          )}
        </CardContent>
      </Card>
    );
  }

  if (run.result_kind === "clarification" && run.result !== null && "questions" in run.result) {
    return (
      <Card className="border-amber-300/60 bg-amber-50/60">
        <CardContent className="space-y-3 p-5 text-sm">
          <div className="font-medium">还需要补充一点信息</div>
          <ul className="list-disc space-y-1 pl-5 text-muted-foreground">{run.result.questions.map((question) => <li key={question}>{question}</li>)}</ul>
          <Button asChild variant="outline" size="sm"><Link to="/settings/profile">补充画像</Link></Button>
        </CardContent>
      </Card>
    );
  }
  if (run.result_kind === "safe_response" && run.result !== null && "message" in run.result) {
    return <Card><CardContent className="p-5 text-sm leading-6">{run.result.message}</CardContent></Card>;
  }
  if (run.status === "failed") {
    return (
      <Card className="border-destructive/25">
        <CardContent className="space-y-3 p-5">
          <div className="font-medium">暂时没能完成这份路线</div>
          <p className="text-sm text-muted-foreground">稍后重试即可，已经保存的画像和任务不会丢失。</p>
          <Button variant="outline" size="sm" onClick={onRetry}><RefreshCw className="h-4 w-4" />重新尝试</Button>
        </CardContent>
      </Card>
    );
  }
  if (run.status === "cancelled") {
    return <div className="rounded-xl bg-muted px-4 py-3 text-sm text-muted-foreground">本次生成已取消。</div>;
  }
  if (TERMINAL.has(run.status) && run.result_kind === "plan") {
    return null;
  }
  return null;
}
