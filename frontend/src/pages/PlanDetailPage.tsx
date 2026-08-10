import { ArrowLeft, ExternalLink, Lightbulb, Link2 } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { usePlan } from "@/api/plans";
import { WeeklyTaskSchedule } from "@/components/WeeklyTaskSchedule";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PLAN_STATUS_LABELS } from "@/lib/labels";

export function PlanDetailPage(): JSX.Element {
  const { planId } = useParams<{ planId: string }>();
  const planQuery = usePlan(planId);

  if (planQuery.isLoading) return <div className="text-sm text-muted-foreground">正在加载路线详情…</div>;
  if (planQuery.isError || planQuery.data === undefined) {
    return <Card><CardContent className="p-8 text-center text-sm text-muted-foreground">路线不存在或暂时无法加载。</CardContent></Card>;
  }

  const plan = planQuery.data;
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <Link to="/journey" className="inline-flex min-h-11 items-center gap-2 text-sm text-muted-foreground hover:text-foreground"><ArrowLeft className="h-4 w-4" />返回路线</Link>
      <header>
        <div className="flex flex-wrap items-center gap-2"><Badge variant="outline">{PLAN_STATUS_LABELS[plan.status]}</Badge><span className="text-xs text-muted-foreground">v{plan.version} · {plan.horizon_start} 至 {plan.horizon_end}</span></div>
        <h1 className="mt-3 text-2xl font-semibold leading-tight tracking-tight sm:text-3xl">{plan.overall_direction}</h1>
        <p className="mt-3 text-sm leading-6 text-muted-foreground">{plan.summary}</p>
      </header>

      <Card className="border-primary/15 bg-accent/30">
        <CardContent className="flex gap-3 p-5 sm:p-6"><Lightbulb className="mt-0.5 h-5 w-5 shrink-0 text-primary" /><div><h2 className="font-semibold">为什么这样安排</h2><p className="mt-2 text-sm leading-6 text-muted-foreground">{plan.rationale}</p></div></CardContent>
      </Card>

      <section className="space-y-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-primary">从 {plan.plan_date} 开始</p>
          <h2 className="mt-1 text-lg font-semibold">每日计划</h2>
          <p className="mt-1 text-sm leading-6 text-muted-foreground">每天只安排一个关键结果；任务状态只记录在对应日期。</p>
        </div>
        <WeeklyTaskSchedule startDate={plan.plan_date} tasks={plan.tasks} detailed />
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">安排依据与来源</h2>
        {plan.sources.length === 0 ? <Card><CardContent className="p-6 text-sm text-muted-foreground">这份路线没有使用需要单独展示的外部来源。</CardContent></Card> : (
          <div className="space-y-3">{plan.sources.map((source) => <Card key={source.id}><CardContent className="flex items-start gap-3 p-5"><span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-accent text-primary"><Link2 className="h-4 w-4" /></span><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><span className="text-sm font-medium">{source.title ?? source.kind}</span>{!source.available && <Badge variant="secondary">当前不可用</Badge>}</div>{source.snippet && <p className="mt-1 text-xs leading-5 text-muted-foreground">{source.snippet}</p>}{source.url && source.available && <a className="mt-2 inline-flex min-h-9 items-center gap-1 text-xs font-medium text-primary hover:underline" href={source.url} target="_blank" rel="noreferrer">打开来源 <ExternalLink className="h-3.5 w-3.5" /></a>}</div></CardContent></Card>)}</div>
        )}
      </section>
    </div>
  );
}
