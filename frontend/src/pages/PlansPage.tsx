import { ArrowRight, Check, Circle, Flag, Map, Sparkles } from "lucide-react";
import { Link } from "react-router-dom";
import { useActivePlan, usePlans } from "@/api/plans";
import type { ActivePlanResponse } from "@/api/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { PLAN_STATUS_LABELS } from "@/lib/labels";

function currentWeek(plan: ActivePlanResponse): number {
  const start = new Date(`${plan.horizon_start}T00:00:00`);
  const now = new Date();
  const elapsed = Math.floor((now.getTime() - start.getTime()) / 86_400_000);
  return Math.min(Math.max(Math.floor(elapsed / 7) + 1, 1), Math.max(plan.weekly_focus.length, 1));
}

export function PlansPage(): JSX.Element {
  const active = useActivePlan();
  const plans = usePlans();

  if (active.isLoading || plans.isLoading) {
    return <div className="text-sm text-muted-foreground">正在整理你的路线…</div>;
  }

  const plan = active.data;
  const history = (plans.data?.items ?? []).filter((item) => item.plan_id !== plan?.plan_id);

  if (plan === undefined) {
    return (
      <div className="mx-auto max-w-3xl space-y-6">
        <header>
          <p className="text-sm font-medium text-primary">你的路线</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight sm:text-3xl">先生成第一份求职路线</h1>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">路线看中期方向，行动只展开到今天。</p>
        </header>
        <Card className="border-dashed">
          <CardContent className="flex flex-col items-start gap-4 p-6 sm:p-8">
            <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-accent text-primary"><Map className="h-6 w-6" /></span>
            <div><h2 className="font-semibold">还没有正在进行的路线</h2><p className="mt-1 text-sm text-muted-foreground">告诉搭子你的目标，它会给出 1~8 周方向和今天的第一步。</p></div>
            <Button asChild><Link to="/today">去生成路线 <ArrowRight className="h-4 w-4" /></Link></Button>
          </CardContent>
        </Card>
        {history.length > 0 && <HistoryList plans={history} />}
      </div>
    );
  }

  const week = currentWeek(plan);
  const currentFocus = plan.weekly_focus.find((item) => item.week_index === week);
  const progress = Math.round((week / Math.max(plan.weekly_focus.length, 1)) * 100);

  return (
    <div className="mx-auto max-w-4xl space-y-7">
      <header className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-sm font-medium text-primary">你的求职路线</p>
          <Badge variant="outline">{PLAN_STATUS_LABELS[plan.status]}</Badge>
        </div>
        <h1 className="max-w-3xl text-2xl font-semibold leading-tight tracking-tight sm:text-3xl">{plan.overall_direction}</h1>
        <p className="max-w-2xl text-sm leading-6 text-muted-foreground">{plan.summary}</p>
      </header>

      <Card className="overflow-hidden border-primary/20 bg-gradient-to-br from-card via-card to-accent/45">
        <CardContent className="grid gap-6 p-5 sm:p-6 md:grid-cols-[1fr_220px] md:items-center">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-primary">当前进度 · 第 {week} 周</p>
            <h2 className="mt-2 text-xl font-semibold">{currentFocus?.focus ?? plan.overall_direction}</h2>
            <p className="mt-3 text-sm leading-6 text-muted-foreground">
              成功信号：{currentFocus?.success_signal ?? "完成今天可验证的第一步"}
            </p>
          </div>
          <div className="space-y-3">
            <div className="flex items-center justify-between text-xs text-muted-foreground"><span>{plan.horizon_start}</span><span>{plan.horizon_end}</span></div>
            <div className="h-2 overflow-hidden rounded-full bg-secondary"><div className="h-full rounded-full bg-primary transition-all" style={{ width: `${progress}%` }} /></div>
            <p className="text-right text-xs text-muted-foreground">路线进度 {progress}%</p>
          </div>
        </CardContent>
      </Card>

      <section className="space-y-4">
        <div className="flex items-center justify-between"><h2 className="text-lg font-semibold">每周重点</h2><span className="text-sm text-muted-foreground">共 {plan.weekly_focus.length} 周</span></div>
        <Card>
          <CardContent className="p-5 sm:p-6">
            <ol className="space-y-0">
              {plan.weekly_focus.map((item, index) => {
                const complete = item.week_index < week;
                const current = item.week_index === week;
                return (
                  <li key={item.week_index} className="relative grid grid-cols-[32px_minmax(0,1fr)] gap-3 pb-6 last:pb-0">
                    {index < plan.weekly_focus.length - 1 && <span className="absolute bottom-0 left-[15px] top-8 w-px bg-border" />}
                    <span className={`relative z-10 flex h-8 w-8 items-center justify-center rounded-full border ${current ? "border-primary bg-primary text-primary-foreground" : complete ? "border-primary/30 bg-accent text-primary" : "bg-card text-muted-foreground"}`}>
                      {complete ? <Check className="h-4 w-4" /> : current ? <Sparkles className="h-4 w-4" /> : <Circle className="h-3 w-3" />}
                    </span>
                    <div className="min-w-0 pt-1">
                      <div className="flex flex-wrap items-center gap-2"><span className="text-sm font-semibold">第 {item.week_index} 周</span>{current && <Badge>当前</Badge>}</div>
                      <p className="mt-1 text-sm leading-6">{item.focus}</p>
                      <p className="mt-1 text-xs leading-5 text-muted-foreground">成功信号：{item.success_signal}</p>
                    </div>
                  </li>
                );
              })}
            </ol>
          </CardContent>
        </Card>
      </section>

      {plan.adjustment_reason !== null && (
        <Card className="border-amber-300/60 bg-amber-50/60">
          <CardContent className="flex gap-3 p-5 text-sm leading-6"><Flag className="mt-0.5 h-4 w-4 shrink-0 text-amber-700" /><div><div className="font-medium">上次调整</div><p className="text-muted-foreground">{plan.adjustment_reason}</p></div></CardContent>
        </Card>
      )}

      <div className="flex flex-wrap gap-3">
        <Button asChild><Link to={`/journey/${plan.plan_id}`}>查看每日计划 <ArrowRight className="h-4 w-4" /></Link></Button>
        <Button asChild variant="outline"><Link to="/today">去完成今天</Link></Button>
      </div>

      {history.length > 0 && <HistoryList plans={history} />}
    </div>
  );
}

function HistoryList({ plans }: { plans: ActivePlanResponse[] }): JSX.Element {
  return (
    <section className="space-y-3">
      <h2 className="text-lg font-semibold">历史路线</h2>
      <div className="grid gap-3 sm:grid-cols-2">
        {plans.map((plan) => (
          <Link key={plan.plan_id} to={`/journey/${plan.plan_id}`} className="block min-w-0">
            <Card className="h-full transition-colors hover:border-primary/35">
              <CardHeader className="p-5"><div className="flex items-start justify-between gap-2"><CardTitle className="text-base leading-6">{plan.overall_direction}</CardTitle><Badge variant="secondary">v{plan.version}</Badge></div><CardDescription className="line-clamp-2 leading-5">{plan.summary}</CardDescription></CardHeader>
            </Card>
          </Link>
        ))}
      </div>
    </section>
  );
}
