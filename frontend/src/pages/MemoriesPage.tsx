import { useState } from "react";
import { useDecideCandidate, useMemories, useMemoryCandidates, usePatchMemory } from "@/api/memories";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

const TYPE_LABEL: Record<string, string> = {
  profile_fact: "画像事实",
  stable_preference: "稳定偏好",
  execution_pattern: "执行模式",
};

const SENSITIVITY_LABEL: Record<string, string> = {
  normal: "常规",
  sensitive: "敏感",
  highly_sensitive: "高度敏感",
};

function MemoryCandidateItem({
  candidateId,
  type,
  summary,
  sensitivity,
}: {
  candidateId: string;
  type: string;
  summary: string;
  sensitivity: string;
}) {
  const decide = useDecideCandidate();
  return (
    <Card className={decide.isPending ? "opacity-70" : ""}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="text-base">{summary}</CardTitle>
          <Badge variant="secondary">{SENSITIVITY_LABEL[sensitivity] ?? sensitivity}</Badge>
        </div>
        <CardDescription>{TYPE_LABEL[type] ?? type} · 待确认</CardDescription>
      </CardHeader>
      <CardContent className="flex gap-2">
        <Button
          size="sm"
          disabled={decide.isPending}
          onClick={() =>
            decide.mutate({ candidateId, decision: "confirm" })
          }
        >
          确认
        </Button>
        <Button
          size="sm"
          variant="outline"
          disabled={decide.isPending}
          onClick={() =>
            decide.mutate({ candidateId, decision: "reject" })
          }
        >
          拒绝
        </Button>
      </CardContent>
    </Card>
  );
}

function MemoryItem({
  memoryId,
  version,
  type,
  summary,
  sensitivity,
  status,
}: {
  memoryId: string;
  version: number;
  type: string;
  summary: string;
  sensitivity: string;
  status: "active" | "closed";
}) {
  const patchMemory = usePatchMemory();
  const [localStatus, setLocalStatus] = useState(status);

  function toggle(): void {
    if (patchMemory.isPending) return;
    const nextStatus = localStatus === "active" ? "closed" : "active";
    patchMemory.mutate(
      { memoryId, payload: { status: nextStatus, version } },
      { onSuccess: () => setLocalStatus(nextStatus) }
    );
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="text-base">{summary}</CardTitle>
          <div className="flex items-center gap-2">
            <Badge variant="outline">{SENSITIVITY_LABEL[sensitivity] ?? sensitivity}</Badge>
            <Badge variant={localStatus === "active" ? "success" : "secondary"}>
              {localStatus === "active" ? "已启用" : "已停用"}
            </Badge>
          </div>
        </div>
        <CardDescription>{TYPE_LABEL[type] ?? type}</CardDescription>
      </CardHeader>
      <CardContent>
        <Button variant="outline" size="sm" onClick={toggle} disabled={patchMemory.isPending}>
          {localStatus === "active" ? "停用" : "启用"}
        </Button>
      </CardContent>
    </Card>
  );
}

export function MemoriesPage(): JSX.Element {
  const memories = useMemories();
  const candidates = useMemoryCandidates();

  const isLoading = memories.isLoading || candidates.isLoading;
  if (isLoading) {
    return <div className="text-muted-foreground">正在加载记忆…</div>;
  }

  const pendingCandidates = (candidates.data?.items ?? []).filter(
    (c) => c.status === "pending"
  );
  const activeMemories = memories.data?.items ?? [];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">长期记忆</h1>

      {pendingCandidates.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-lg font-medium">待确认（{pendingCandidates.length}）</h2>
          <div className="space-y-3">
            {pendingCandidates.map((c) => (
              <MemoryCandidateItem
                key={c.candidate_id}
                candidateId={c.candidate_id}
                type={c.memory_type}
                summary={c.summary}
                sensitivity={c.sensitivity}
              />
            ))}
          </div>
        </section>
      )}

      <section className="space-y-3">
        <h2 className="text-lg font-medium">已激活记忆</h2>
        {activeMemories.length === 0 ? (
          <Card>
            <CardContent className="py-8 text-center text-sm text-muted-foreground">
              还没有已激活的长时记忆。多跑几份计划后，系统会从中识别值得保留的事实与偏好。
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-3">
            {activeMemories.map((m) => (
              <MemoryItem
                key={m.memory_id}
                memoryId={m.memory_id}
                version={m.version}
                type={m.memory_type}
                summary={m.summary}
                sensitivity={m.sensitivity}
                status={m.status}
              />
            ))}
          </div>
        )}
      </section>

      {activeMemories.length > 0 && pendingCandidates.length > 0 && <Separator />}
    </div>
  );
}
