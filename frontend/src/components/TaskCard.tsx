import { useState } from "react";
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

const TASK_TYPE_LABEL: Record<string, string> = {
  learning: "学习",
  project: "项目",
  interview: "面试",
  application: "投递",
  resume: "简历",
  other: "其他",
};

const ABANDONED_REASON_LABEL: Record<AbandonedReason, string> = {
  too_hard: "太难",
  too_easy: "太简单",
  no_time: "没时间",
  lost_interest: "失去兴趣",
  blocked: "被阻塞",
  other: "其他",
};

export function TaskCard({ task }: { task: TaskResponse }): JSX.Element {
  const updateTask = useUpdateTask();
  const [abandonOpen, setAbandonOpen] = useState(false);
  const [completeOpen, setCompleteOpen] = useState(false);
  const [actualMinutes, setActualMinutes] = useState(task.estimated_minutes);
  const [reason, setReason] = useState<AbandonedReason>("too_hard");
  const [reasonText, setReasonText] = useState("");

  const stateLabel: Record<string, string> = {
    pending: "未开始",
    in_progress: "进行中",
    completed: "已完成",
    abandoned: "已放弃",
    expired: "已过期",
  };

  const isCompleted = task.state === "completed";
  const isAbandoned = task.state === "abandoned";

  function startTask(): void {
    updateTask.mutate({
      taskId: task.task_id,
      payload: { state: "in_progress", version: task.version },
    });
  }

  function confirmComplete(): void {
    updateTask.mutate(
      {
        taskId: task.task_id,
        payload: { state: "completed", version: task.version, actual_minutes: actualMinutes },
      },
      { onSettled: () => setCompleteOpen(false) }
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
      { onSettled: () => setAbandonOpen(false) }
    );
  }

  return (
    <Card className={isCompleted || isAbandoned ? "opacity-70" : ""}>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-3">
          <div className="space-y-1">
            <CardTitle className="text-base">
              {task.title}
              <Badge variant="outline" className="ml-2 text-xs">
                {TASK_TYPE_LABEL[task.task_type] ?? task.task_type}
              </Badge>
            </CardTitle>
            <CardDescription className="text-xs">
              预计 {task.estimated_minutes} 分钟 · {task.scheduled_date}
            </CardDescription>
          </div>
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
            {stateLabel[task.state] ?? task.state}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-3 pt-0">
        <div className="text-sm">
          <span className="text-muted-foreground">开始动作：</span>
          {task.starter_action}
        </div>
        <div className="text-sm">
          <span className="text-muted-foreground">交付物：</span>
          {task.deliverable}
        </div>

        {/* 状态机操作 */}
        <div className="flex flex-wrap gap-2">
          {task.state === "pending" && (
            <Button size="sm" onClick={startTask} disabled={updateTask.isPending}>
              开始
            </Button>
          )}
          {task.state === "in_progress" && (
            <>
              <Button size="sm" onClick={() => setCompleteOpen(true)} disabled={updateTask.isPending}>
                完成
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => setAbandonOpen(true)}
                disabled={updateTask.isPending}
              >
                放弃
              </Button>
            </>
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
              <DialogDescription>选一个最贴近的真实原因，便于后续调整。</DialogDescription>
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
                <Label htmlFor="reason_text">具体说明（可空）</Label>
                <Input
                  id="reason_text"
                  value={reasonText}
                  onChange={(e) => setReasonText(e.target.value)}
                  placeholder="如：信息检索失败、依赖卡住…"
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="destructive" onClick={confirmAbandon} disabled={updateTask.isPending}>
                确认放弃
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </CardContent>
    </Card>
  );
}
