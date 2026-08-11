import { Brain, ChartNoAxesCombined, ChevronRight, Clock3, Code2, Settings2, ShieldCheck, Target } from "lucide-react";
import { Link } from "react-router-dom";
import { useMe } from "@/api/auth";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { GOAL_LABELS, SKILL_LABELS, STAGE_LABELS } from "@/lib/labels";

function MenuLink({
  to,
  icon: Icon,
  title,
  description,
}: {
  to: string;
  icon: typeof Brain;
  title: string;
  description: string;
}): JSX.Element {
  return (
    <Link
      to={to}
      className="flex min-h-16 items-center gap-3 border-b px-4 py-3 transition-colors last:border-b-0 hover:bg-accent/40"
    >
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-accent text-accent-foreground">
        <Icon className="h-4 w-4" aria-hidden="true" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-sm font-medium">{title}</span>
        <span className="block truncate text-xs text-muted-foreground">{description}</span>
      </span>
      <ChevronRight className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
    </Link>
  );
}

export function MyPage(): JSX.Element {
  const me = useMe();
  const profile = me.data?.profile;

  if (profile === null || profile === undefined) {
    return <div className="text-sm text-muted-foreground">正在加载你的资料…</div>;
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <header>
        <p className="text-sm font-medium text-primary">我的搭子设置</p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight sm:text-3xl">让计划更懂你的节奏</h1>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">
          目标、时间和记忆都由你控制，随时可以调整。
        </p>
      </header>

      <Card className="overflow-hidden border-primary/15 bg-gradient-to-br from-card to-accent/30">
        <CardContent className="space-y-5 p-5 sm:p-6">
          <div className="flex flex-wrap items-center gap-2">
            <Badge>{GOAL_LABELS[profile.goal_type]}</Badge>
            <Badge variant="outline">{STAGE_LABELS[profile.stage]}</Badge>
            <Badge variant="outline">{SKILL_LABELS[profile.skill_level]}</Badge>
          </div>
          <div className="grid gap-3 text-sm sm:grid-cols-2">
            <div className="flex items-center gap-2 text-muted-foreground">
              <Clock3 className="h-4 w-4 text-primary" />每天约 {profile.time_budget_minutes} 分钟
            </div>
            <div className="flex items-center gap-2 text-muted-foreground">
              <Target className="h-4 w-4 text-primary" />
              {profile.start_date === null || profile.deadline === null
                ? "暂未设置完整时间段"
                : `计划时间 ${profile.start_date} 至 ${profile.deadline}`}
            </div>
          </div>
          {profile.skill_summary !== null && (
            <p className="rounded-xl bg-background/70 p-3 text-sm leading-6 text-muted-foreground">
              {profile.skill_summary}
            </p>
          )}
        </CardContent>
      </Card>

      <Card className="overflow-hidden">
        <MenuLink
          to="/settings/profile"
          icon={Settings2}
          title="目标与时间"
          description="调整方向、阶段、每日可投入时间"
        />
        <MenuLink
          to="/memories"
          icon={Brain}
          title="搭子记住了什么"
          description="查看、停用或删除长期记忆"
        />
        <MenuLink
          to="/memories"
          icon={ShieldCheck}
          title="隐私与数据控制"
          description="敏感信息只有确认后才会保留"
        />
        {me.data?.user.role === "dev" && (
          <>
            <MenuLink
              to="/dev/runs"
              icon={Code2}
              title="Run Trace"
              description="查看 Run、Trace、成本与兼容回放"
            />
            <MenuLink
              to="/dev/evals"
              icon={ChartNoAxesCombined}
              title="Eval Harness V2"
              description="运行确定性评测并查看报告与校准状态"
            />
          </>
        )}
      </Card>
    </div>
  );
}
