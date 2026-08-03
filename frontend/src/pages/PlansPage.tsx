import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "@/api/client";
import type { ActivePlanResponse } from "@/api/types";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

const STATUS_LABEL: Record<string, string> = {
  generated: "新生成",
  active: "进行中",
  completed: "已完成",
  archived: "已归档",
};

function usePlans() {
  return useQuery({
    queryKey: ["plans"],
    queryFn: () => apiRequest<{ items: ActivePlanResponse[] }>("/api/v1/plans"),
    retry: false,
  });
}

export function PlansPage(): JSX.Element {
  const plans = usePlans();

  if (plans.isLoading) {
    return <div className="text-muted-foreground">正在加载计划…</div>;
  }
  if (plans.isError || plans.data === undefined) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-sm text-muted-foreground">
          计划加载失败，请确认已登录。
        </CardContent>
      </Card>
    );
  }

  if (plans.data.items.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>还没有计划</CardTitle>
          <CardDescription>去「今天」生成你的第一份求职准备计划。</CardDescription>
        </CardHeader>
        <CardContent>
          <Link to="/today" className="text-sm text-primary hover:underline">
            前往今天 →
          </Link>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold tracking-tight">我的计划</h1>
      <div className="space-y-3">
        {plans.data.items.map((plan) => (
          <Link key={plan.plan_id} to={`/plans/${plan.plan_id}`} className="block">
            <Card className="transition-colors hover:border-primary/40">
              <CardHeader>
                <div className="flex items-center justify-between gap-2">
                  <CardTitle className="text-base">{plan.overall_direction}</CardTitle>
                  <Badge variant="outline">{STATUS_LABEL[plan.status] ?? plan.status}</Badge>
                </div>
                <CardDescription>{plan.summary}</CardDescription>
              </CardHeader>
              <CardContent className="text-sm text-muted-foreground">
                {plan.horizon_start} ~ {plan.horizon_end} · {plan.weekly_focus.length} 周 · v{plan.version}
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
