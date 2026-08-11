import { useState } from "react";
import { Check, Circle, CircleDot, Minus } from "lucide-react";
import { Link } from "react-router-dom";
import { useUpdateTask } from "@/api/plans";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type {
  AbandonedReason,
  TaskResponse,
} from "@/api/types";
import { toUserFacingError } from "@/lib/errors";
import { TASK_STATUS_LABELS, TASK_TYPE_LABELS } from "@/lib/labels";

const ABANDONED_REASON_LABEL: Record<AbandonedReason, string> = {
  too_hard: "太难",
  too_easy: "太简单",
  no_time: "没时间",
  lost_interest: "失去兴趣",
  blocked: "被阻塞",
  other: "其他",
};

export function TaskCard({
  task,
  featured = false,
  onFeedback,
}: {
  task: TaskResponse;
  featured?: boolean;
  onFeedback?: (message: string) => void;
}): JSX.Element {
  const updateTask = useUpdateTask();
  const [abandonOpen, setAbandonOpen] = useState(false);
  const [completeOpen, setCompleteOpen] = useState(false);
  const [actualMinutes, setActualMinutes] = useState(task.estimated_minutes);
  const [reason, setReason] = useState<AbandonedReason>("too_hard");
  const [reasonText, setReasonText] = useState("");

  const isCompleted = task.state === "completed";
  const isAbandoned = task.state === "abandoned";

  function startTask(): void {
    updateTask.mutate(
      {
        taskId: task.task_id,
        payload: { state: "in_progress", version: task.version },
      },
      { onSuccess: (result) => onFeedback?.(result.companion_message) },
    );
  }

  function confirmComplete(): void {
    updateTask.mutate(
      {
        taskId: task.task_id,
        payload: { state: "completed", version: task.version, actual_minutes: actualMinutes },
      },
      {
        onSuccess: (result) => {
          setCompleteOpen(false);
          onFeedback?.(result.companion_message);
        },
      }
    );
  }

  function confirmAbandon(): void {
    updateTask.mutate(
      {
        taskId: task.task_id,
        payload: {
          state: "abandoned",
          version: task.version,
          abandoned_reason: reason,
          abandoned_reason_text: reasonText.trim() || null,
        },
      },
      {
        onSuccess: (result) => {
          setAbandonOpen(false);
          onFeedback?.(result.companion_message);
        },
      }
    );
  }

  function statusAction(): void {
    if (task.state === "pending") startTask();
    if (task.state === "in_progress") setCompleteOpen(true);
  }

  function reopenTask(): void {
    updateTask.mutate(
      {
        taskId: task.task_id,
        payload: { state: "in_progress", version: task.version },
      },
      { onSuccess: (result) => onFeedback?.(result.companion_message) },
    );
  }

  const statusActionLabel = task.state === "pending"
    ? `开始：${task.title}`
    : task.state === "in_progress"
      ? `完成：${task.title}`
      : task.state === "completed"
        ? `已完成：${task.title}`
        : `${TASK_STATUS_LABELS[task.state]}：${task.title}`;

  return (
    <Card
      className={`${isCompleted || isAbandoned ? "opacity-70" : ""} ${featured ? "overflow-hidden border-primary/25 shadow-[0_22px_70px_-42px_rgba(24,122,112,0.7)]" : ""}`}
    >
      <CardHeader className="pb-3">
        <div className="flex items-start gap-3">
          <button
            type="button"
            aria-label={statusActionLabel}
            title={statusActionLabel}
            onClick={statusAction}
            disabled={updateTask.isPending || !["pending", "in_progress"].includes(task.state)}
            className={`mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ${
              task.state === "completed"
                ? "border-primary bg-primary text-primary-foreground"
                : task.state === "in_progress"
                  ? "border-primary bg-accent text-primary"
                  : task.state === "pending"
                    ? "border-muted-foreground/45 text-muted-foreground hover:border-primary hover:text-primary"
                    : "border-muted text-muted-foreground"
            }`}
          >
            {task.state === "completed" ? (
              <Check className="h-5 w-5" />
            ) : task.state === "in_progress" ? (
              <CircleDot className="h-5 w-5" />
            ) : task.state === "pending" ? (
              <Circle className="h-5 w-5" />
            ) : (
              <Minus className="h-5 w-5" />
            )}
          </button>
          <div className="min-w-0 flex-1 space-y-1">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <CardTitle className="min-w-0 text-base">
                <Link
                  to={`/journey/${task.plan_id}/day/${task.scheduled_date}`}
                  className="hover:text-primary hover:underline"
                >
                  {task.title}
                </Link>
                <Badge variant="outline" className="ml-2 text-xs">
                  {TASK_TYPE_LABELS[task.task_type]}
                </Badge>
              </CardTitle>
              <Badge
                variant={
                  task.state === "completed"
                    ? "success"
                    : task.state === "abandoned"
                      ? "destructive"
                      : task.state === "in_progress"
                        ? "default"
                        : "secondary"
                }
              >
                {TASK_STATUS_LABELS[task.state]}
              </Badge>
            </div>
            <CardDescription className="text-xs">
              预计 {task.estimated_minutes} 分钟
            </CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3 pt-0">
        <div className={featured ? "rounded-xl bg-accent/45 p-4" : "text-sm"}>
          <span className="block text-xs font-medium text-muted-foreground">第一步</span>
          <span className="mt-1 block text-sm font-medium leading-6">{task.starter_action}</span>
        </div>
        <div className="text-sm">
          <span className="text-muted-foreground">完成标志：</span>
          {task.deliverable}
        </div>
        {task.rationale && (
          <div className="text-sm">
            <span className="text-muted-foreground">为什么现在做：</span>
            {task.rationale}
          </div>
        )}

        {updateTask.isError && (
          <div className="rounded-xl bg-destructive/10 p-3 text-sm text-destructive">
            {toUserFacingError(updateTask.error).message}
          </div>
        )}

        <div className="flex flex-wrap items-center gap-2">
          {task.state === "in_progress" && (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => setAbandonOpen(true)}
              disabled={updateTask.isPending}
            >
              今天先放下
            </Button>
          )}

          {task.state === "completed" && (
            <Button
              size="sm"
              variant="ghost"
              onClick={reopenTask}
              disabled={updateTask.isPending}
            >
              标记为未完成
            </Button>
          )}

          {task.state === "pending" && (
            <span className="text-xs text-muted-foreground">点击左侧圆圈开始</span>
          )}
          {task.state === "in_progress" && (
            <span className="text-xs text-muted-foreground">再次点击左侧圆圈完成</span>
          )}

          {task.actual_minutes !== null && (
            <span className="self-center text-xs text-muted-foreground">
              实际 {task.actual_minutes} 分钟
            </span>
          )}
        </div>

        {/* 完成对话框 */}
        <Dialog open={completeOpen} onOpenChange={setCompleteOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>记录实际时长</DialogTitle>
              <DialogDescription>填上完成 {task.title} 实际花费的分钟数。</DialogDescription>
            </DialogHeader>
            <div className="space-y-2">
              <Label htmlFor="actual_minutes">实际分钟</Label>
              <Input
                id="actual_minutes"
                type="number"
                min={1}
                value={actualMinutes}
                onChange={(e) => setActualMinutes(Number(e.target.value))}
              />
            </div>
            <DialogFooter>
              <Button onClick={confirmComplete} disabled={updateTask.isPending}>
                确认完成
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* 放弃对话框 */}
        <Dialog open={abandonOpen} onOpenChange={setAbandonOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>放弃 {task.title}</DialogTitle>
              <DialogDescription>选一个最贴近的真实原因，搭子会据此调整后续计划。</DialogDescription>
            </DialogHeader>
            <div className="space-y-3">
              <div className="space-y-2">
                <Label>原因</Label>
                <Select value={reason} onValueChange={(v) => setReason(v as AbandonedReason)}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {(Object.keys(ABANDONED_REASON_LABEL) as AbandonedReason[]).map((r) => (
                      <SelectItem key={r} value={r}>
                        {ABANDONED_REASON_LABEL[r]}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="reason_text">具体说明（{reason === "other" ? "必填" : "可空"}）</Label>
                <Input
                  id="reason_text"
                  value={reasonText}
                  onChange={(e) => setReasonText(e.target.value)}
                  placeholder="如：信息检索失败、依赖卡住…"
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={confirmAbandon} disabled={updateTask.isPending || (reason === "other" && reasonText.trim().length === 0)}>
                今天先放下
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </CardContent>
    </Card>
  );
}
