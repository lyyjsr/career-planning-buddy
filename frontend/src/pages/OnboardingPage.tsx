import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useMe } from "@/api/auth";
import { usePutProfile } from "@/api/profile";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import type {
  CareerStage,
  GoalType,
  ProfilePutRequest,
  SkillLevel,
} from "@/api/types";
import { ApiError } from "@/api/client";

const GOAL_LABELS: Record<GoalType, string> = {
  ai_backend: "AI 后端",
  agent_app: "Agent 应用",
  backend_java: "Java 后端",
  data_engineer: "数据工程",
  fullstack: "全栈",
  other: "其他",
};

const STAGE_LABELS: Record<CareerStage, string> = {
  exploring: "探索期",
  preparing: "准备期",
  applying: "投递期",
  interviewing: "面试期",
};

const SKILL_LABELS: Record<SkillLevel, string> = {
  beginner: "入门",
  intermediate: "中级",
  advanced: "高级",
};

export function OnboardingPage(): JSX.Element {
  const me = useMe();
  const putProfile = usePutProfile();
  const navigate = useNavigate();

  const [goalType, setGoalType] = useState<GoalType>("agent_app");
  const [stage, setStage] = useState<CareerStage>("preparing");
  const [timeBudget, setTimeBudget] = useState(75);
  const [skillLevel, setSkillLevel] = useState<SkillLevel>("intermediate");
  const [skillSummary, setSkillSummary] = useState("");
  const [deadline, setDeadline] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (me.data === undefined || me.data === null) {
    return <div className="container py-6 text-muted-foreground">正在加载…</div>;
  }
  if (me.data.profile_complete) {
    return <Navigate to="/today" replace />;
  }

  function onSubmit(e: React.FormEvent): void {
    e.preventDefault();
    if (putProfile.isPending) return;
    setSubmitting(true);
    const payload: ProfilePutRequest = {
      goal_type: goalType,
      stage,
      time_budget_minutes: timeBudget,
      skill_level: skillLevel,
      skill_summary: skillSummary.trim() || null,
      deadline: deadline.trim() ? deadline.trim() : null,
      preferences: {},
    };
    putProfile.mutate(
      { payload, idempotencyKey: `profile-${Date.now()}` },
      {
        onSuccess: () => {
          navigate("/today");
        },
        onSettled: () => setSubmitting(false),
      }
    );
  }

  const error = putProfile.error;
  const errorMessage =
    error instanceof ApiError ? error.message : error !== null ? "提交失败，请重试" : null;

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-6">
      <Card className="w-full max-w-2xl">
        <CardHeader>
          <CardTitle>完善你的画像</CardTitle>
          <CardDescription>
            这些信息会决定计划的方向和强度，可以在设置里随时调整。
          </CardDescription>
        </CardHeader>
        <form onSubmit={onSubmit}>
          <CardContent className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="goal_type">目标岗位类型</Label>
              <Select
                value={goalType}
                onValueChange={(v) => setGoalType(v as GoalType)}
              >
                <SelectTrigger id="goal_type">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {(Object.keys(GOAL_LABELS) as GoalType[]).map((g) => (
                    <SelectItem key={g} value={g}>
                      {GOAL_LABELS[g]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="grid gap-5 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="stage">当前阶段</Label>
                <Select value={stage} onValueChange={(v) => setStage(v as CareerStage)}>
                  <SelectTrigger id="stage">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {(Object.keys(STAGE_LABELS) as CareerStage[]).map((s) => (
                      <SelectItem key={s} value={s}>
                        {STAGE_LABELS[s]}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="skill_level">技能水平</Label>
                <Select
                  value={skillLevel}
                  onValueChange={(v) => setSkillLevel(v as SkillLevel)}
                >
                  <SelectTrigger id="skill_level">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {(Object.keys(SKILL_LABELS) as SkillLevel[]).map((s) => (
                      <SelectItem key={s} value={s}>
                        {SKILL_LABELS[s]}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="time_budget">每天可投入时间（分钟：15~480）</Label>
              <Input
                id="time_budget"
                type="number"
                min={15}
                max={480}
                value={timeBudget}
                onChange={(e) => setTimeBudget(Number(e.target.value))}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="deadline">期望倒计时日期（可空）</Label>
              <Input
                id="deadline"
                type="date"
                value={deadline}
                onChange={(e) => setDeadline(e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="skill_summary">技能与背景（可空）</Label>
              <Textarea
                id="skill_summary"
                rows={3}
                placeholder="如：3 年 Python 后端经验，有 LLM 应用基础"
                value={skillSummary}
                onChange={(e) => setSkillSummary(e.target.value)}
              />
            </div>

            {errorMessage !== null && (
              <p className="text-sm text-destructive">{errorMessage}</p>
            )}

            <Button type="submit" disabled={submitting} className="w-full">
              {submitting ? "提交中…" : "保存并开始"}
            </Button>
          </CardContent>
        </form>
      </Card>
    </div>
  );
}
