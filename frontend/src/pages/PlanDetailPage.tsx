import { useParams } from "react-router-dom";
import { usePlan } from "@/api/plans";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { TaskCard } from "@/components/TaskCard";

// 简易周次 Tabs：用一组按钮切换
function WeekTabs({
  total,
  current,
  onChange,
}: {
  total: number;
  current: number;
  onChange: (w: number) => void;
}) {
  return (
    <div className="flex flex-wrap gap-1">
      {Array.from({ length: total }, (_, i) => i + 1).map((w) => (
        <button
          key={w}
          type="button"
          onClick={() => onChange(w)}
          className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
            w === current
              ? "bg-primary text-primary-foreground"
              : "bg-secondary text-secondary-foreground hover:bg-accent"
          }`}
        >
          第 {w} 周
        </button>
      ))}
    </div>
  );
}

export function PlanDetailPage(): JSX.Element {
  const { planId } = useParams<{ planId: string }>();
  const planQuery = usePlan(planId);

  if (planQuery.isLoading) {
    return <div className="text-muted-foreground">正在加载计划…</div>;
  }
  if (planQuery.isError || planQuery.data === undefined) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-sm text-muted-foreground">
          计划不存在或加载失败。
        </CardContent>
      </Card>
    );
  }

  const plan = planQuery.data;
  const today = new Date().toISOString().slice(0, 10);
  const todayTasks = plan.tasks.filter((t) => t.scheduled_date === today);
  const otherTasks = plan.tasks.filter((t) => t.scheduled_date !== today);

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <section>
        <div className="flex items-center gap-2">
          <h1 className="text-2xl font-semibold tracking-tight">计划详情</h1>
          <Badge variant="outline">{plan.status}</Badge>
        </div>
        <p className="mt-1 text-sm text-muted-foreground">
          {plan.horizon_start} ~ {plan.horizon_end} · v{plan.version}
        </p>
      </section>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">大方向</CardTitle>
          <CardDescription>{plan.overall_direction}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <p>
            <span className="text-muted-foreground">摘要：</span>
            {plan.summary}
          </p>
          <p className="text-muted-foreground">{plan.rationale}</p>
          {plan.adjustment_reason !== null && (
            <p className="text-amber-800">
              <span className="text-muted-foreground">调整原因：</span>
              {plan.adjustment_reason}
            </p>
          )}
        </CardContent>
      </Card>

      <section className="space-y-3">
        <h2 className="text-lg font-medium">每周重点</h2>
        <Card>
          <CardContent className="pt-6">
            <ol className="space-y-4">
              {plan.weekly_focus.map((w) => (
                <li key={w.week_index} className="space-y-1">
                  <div className="flex items-center gap-2 text-sm font-medium">
                    <span className="text-primary">第 {w.week_index} 周</span>
                  </div>
                  <div className="text-sm">{w.focus}</div>
                  <div className="text-xs text-muted-foreground">
                    成功信号：{w.success_signal}
                  </div>
                  {w.week_index < plan.weekly_focus.length && <Separator className="my-2" />}
                </li>
              ))}
            </ol>
          </CardContent>
        </Card>
      </section>

      {plan.tasks.length > 0 && (
        <section className="space-y-3">
          <WeekTabs
            total={plan.weekly_focus.length || 1}
            current={1}
            onChange={() => {
              /* 当前按整体展示任务，周内精细切换可后续迭代 */
            }}
          />
          {todayTasks.length > 0 && (
            <div className="space-y-2">
              <h3 className="text-sm font-medium text-muted-foreground">今日任务</h3>
              {todayTasks.map((t) => (
                <TaskCard key={t.task_id} task={t} />
              ))}
            </div>
          )}
          {otherTasks.length > 0 && (
            <div className="space-y-2">
              <h3 className="text-sm font-medium text-muted-foreground">其它任务</h3>
              {otherTasks.map((t) => (
                <TaskCard key={t.task_id} task={t} />
              ))}
            </div>
          )}
        </section>
      )}

      {plan.sources.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-lg font-medium">引用来源</h2>
          <Card>
            <CardContent className="pt-6">
              <ul className="space-y-3 text-sm">
                {plan.sources.map((s, i) => (
                  <li key={i} className="space-y-1">
                    <div className="font-medium">{s.kind}{s.title !== null ? ` · ${s.title}` : ""}</div>
                    {s.snippet !== undefined && s.snippet !== null && (
                      <div className="text-xs text-muted-foreground">{s.snippet}</div>
                    )}
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        </section>
      )}
    </div>
  );
}
