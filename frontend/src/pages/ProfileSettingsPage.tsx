import { useEffect, useState } from "react";
import { ArrowLeft } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { useCreateRun } from "@/api/agent-runs";
import { useMe } from "@/api/auth";
import { usePlans } from "@/api/plans";
import { usePatchProfile, useProfile } from "@/api/profile";
import type { CareerStage, GoalType, SkillLevel } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { toUserFacingError } from "@/lib/errors";
import { GOAL_LABELS, SKILL_LABELS, STAGE_LABELS } from "@/lib/labels";

const TIME_OPTIONS = [30, 45, 60, 90, 120];

export function ProfileSettingsPage(): JSX.Element {
  const profile = useProfile();
  const me = useMe();
  const plans = usePlans();
  const patchProfile = usePatchProfile();
  const createRun = useCreateRun();
  const navigate = useNavigate();
  const [goalType, setGoalType] = useState<GoalType>("agent_app");
  const [stage, setStage] = useState<CareerStage>("preparing");
  const [skillLevel, setSkillLevel] = useState<SkillLevel>("intermediate");
  const [timeBudget, setTimeBudget] = useState(60);
  const [deadline, setDeadline] = useState("");
  const [skillSummary, setSkillSummary] = useState("");

  useEffect(() => {
    if (profile.data === undefined) return;
    setGoalType(profile.data.goal_type);
    setStage(profile.data.stage);
    setSkillLevel(profile.data.skill_level);
    setTimeBudget(profile.data.time_budget_minutes);
    setDeadline(profile.data.deadline ?? "");
    setSkillSummary(profile.data.skill_summary ?? "");
  }, [profile.data]);

  if (profile.isLoading || profile.data === undefined) {
    return <div className="text-sm text-muted-foreground">正在加载画像…</div>;
  }

  const mutationError = createRun.error ?? patchProfile.error;
  const error = mutationError === null ? null : toUserFacingError(mutationError);
  const sourcePlan = me.data?.active_plan
    ?? plans.data?.items.find((plan) => ["generated", "active", "completed"].includes(plan.status))
    ?? null;
  const isPending = patchProfile.isPending || createRun.isPending;

  async function save(regeneratePlan: boolean): Promise<void> {
    if (profile.data === undefined || isPending) return;
    try {
      const updated = await patchProfile.mutateAsync({
        payload: {
          version: profile.data.version,
          goal_type: goalType,
          stage,
          skill_level: skillLevel,
          time_budget_minutes: timeBudget,
          deadline: deadline || null,
          skill_summary: skillSummary.trim() || null,
        },
        idempotencyKey: `profile-patch-${profile.data.version}-${regeneratePlan ? "replan" : "save"}`,
      });
      if (regeneratePlan && sourcePlan !== null) {
        const created = await createRun.mutateAsync({
          payload: {
            message: `我已更新求职画像：目标为${GOAL_LABELS[updated.goal_type]}，当前阶段为${STAGE_LABELS[updated.stage]}，每天可投入${updated.time_budget_minutes}分钟。请结合当前计划中已经完成、进行中和放弃的任务，调整后续路线并生成新的七天每日计划。`,
            hint_intent: "replan",
            goal_type_override: updated.goal_type,
            source_plan_id: sourcePlan.plan_id,
          },
          idempotencyKey: `profile-replan-${updated.version}-${sourcePlan.plan_id}`,
        });
        navigate(`/today?run_id=${created.run_id}`);
        return;
      }
      navigate("/me");
    } catch {
      // Mutation hooks retain the API error for the inline error panel.
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-5">
      <Link to="/me" className="inline-flex min-h-11 items-center gap-2 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="h-4 w-4" />返回我的
      </Link>
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">目标与时间</h1>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">
          计划会按这里的目标和每日时间控制任务强度；已有计划需要确认后才会重新生成。
        </p>
      </header>

      <form onSubmit={(event) => event.preventDefault()}>
        <Card>
          <CardHeader><CardTitle className="text-lg">当前画像</CardTitle></CardHeader>
          <CardContent className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="settings-goal">目标方向</Label>
              <Select value={goalType} onValueChange={(value) => setGoalType(value as GoalType)}>
                <SelectTrigger id="settings-goal"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {(Object.keys(GOAL_LABELS) as GoalType[]).map((value) => (
                    <SelectItem key={value} value={value}>{GOAL_LABELS[value]}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="grid gap-5 sm:grid-cols-2">
              <div className="space-y-2">
                <Label>当前阶段</Label>
                <Select value={stage} onValueChange={(value) => setStage(value as CareerStage)}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {(Object.keys(STAGE_LABELS) as CareerStage[]).map((value) => (
                      <SelectItem key={value} value={value}>{STAGE_LABELS[value]}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>基础水平</Label>
                <Select value={skillLevel} onValueChange={(value) => setSkillLevel(value as SkillLevel)}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {(Object.keys(SKILL_LABELS) as SkillLevel[]).map((value) => (
                      <SelectItem key={value} value={value}>{SKILL_LABELS[value]}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="space-y-2">
              <Label>每天可投入时间</Label>
              <div className="flex flex-wrap gap-2">
                {TIME_OPTIONS.map((minutes) => (
                  <Button
                    key={minutes}
                    type="button"
                    variant={timeBudget === minutes ? "default" : "outline"}
                    size="sm"
                    onClick={() => setTimeBudget(minutes)}
                  >
                    {minutes} 分钟
                  </Button>
                ))}
              </div>
              <Input
                type="number"
                min={15}
                max={480}
                value={timeBudget}
                onChange={(event) => setTimeBudget(Number(event.target.value))}
                aria-label="自定义每日分钟数"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="settings-deadline">目标日期（可选）</Label>
              <Input id="settings-deadline" type="date" min={new Date().toISOString().slice(0, 10)} value={deadline} onChange={(event) => setDeadline(event.target.value)} />
            </div>

            <div className="space-y-2">
              <Label htmlFor="settings-summary">技能与背景（可选）</Label>
              <Textarea id="settings-summary" rows={4} value={skillSummary} onChange={(event) => setSkillSummary(event.target.value)} />
            </div>

            {error !== null && (
              <div className="rounded-xl bg-destructive/10 p-3 text-sm text-destructive">
                <div className="font-medium">{error.title}</div>
                <div className="mt-1">{error.message}</div>
              </div>
            )}

            <div className="flex flex-col gap-2 sm:flex-row">
              {sourcePlan !== null && (
                <Button type="button" variant="outline" onClick={() => void save(false)} disabled={isPending || timeBudget < 15 || timeBudget > 480}>
                  仅保存资料
                </Button>
              )}
              <Button type="button" onClick={() => void save(sourcePlan !== null)} disabled={isPending || timeBudget < 15 || timeBudget > 480}>
                {isPending ? "处理中…" : sourcePlan !== null ? "保存并按当前进度重新规划" : "保存调整"}
              </Button>
            </div>
            {sourcePlan !== null && (
              <p className="text-xs leading-5 text-muted-foreground">
                重新规划会读取最近计划中的完成、进行中和放弃记录；新计划成功后，来源计划会归档。
              </p>
            )}
          </CardContent>
        </Card>
      </form>
    </div>
  );
}
