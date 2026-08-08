import { Link, useNavigate } from "react-router-dom";
import { useState } from "react";
import { useMe } from "@/api/auth";
import { useCreateReview, useReviews, useStartNextPlan } from "@/api/reviews";
import { useActivePlan } from "@/api/plans";
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
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { ReviewResponse } from "@/api/types";
import { toUserFacingError } from "@/lib/errors";

const MOOD_EMOJI = ["😞", "😕", "😐", "🙂", "😄"];

function moodLabel(mood: number): string {
  return MOOD_EMOJI[mood - 1] ?? "—";
}

function ReviewForm({ planId, onClose }: { planId: string; onClose: () => void }) {
  const today = new Date().toISOString().slice(0, 10);
  const createReview = useCreateReview();
  const [mood, setMood] = useState(3);
  const [blockers, setBlockers] = useState("");
  const [adjustmentRequest, setAdjustmentRequest] = useState("");
  const [freeText, setFreeText] = useState("");
  const displayError = createReview.error === null ? null : toUserFacingError(createReview.error);

  function submit(): void {
    if (createReview.isPending) return;
    createReview.mutate(
      {
        payload: {
          plan_id: planId,
          review_date: today,
          mood,
          blockers: blockers.trim() || null,
          adjustment_request: adjustmentRequest.trim() || null,
          free_text: freeText.trim() || null,
        },
        idempotencyKey: `review-${Date.now()}`,
      },
      { onSuccess: () => onClose() }
    );
  }

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>今日复盘</DialogTitle>
          <DialogDescription>记录今天的状态，便于下一份计划做出调整。</DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-2">
            <Label>今天的整体感受</Label>
            <div className="flex gap-2">
              {MOOD_EMOJI.map((e, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => setMood(i + 1)}
                  className={`rounded-md p-2 text-xl transition-colors ${
                    mood === i + 1 ? "bg-accent" : "hover:bg-secondary"
                  }`}
                >
                  {e}
                </button>
              ))}
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="blockers">遇到的阻碍（可空）</Label>
            <Textarea
              id="blockers"
              rows={2}
              value={blockers}
              onChange={(e) => setBlockers(e.target.value)}
              placeholder="比如：知识点太散、时间不够…"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="adjust">想做的调整（可空）</Label>
            <Textarea
              id="adjust"
              rows={2}
              value={adjustmentRequest}
              onChange={(e) => setAdjustmentRequest(e.target.value)}
              placeholder="比如：减少每日任务量、换重点方向…"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="free">自由记录（可空）</Label>
            <Textarea
              id="free"
              rows={2}
              value={freeText}
              onChange={(e) => setFreeText(e.target.value)}
            />
          </div>
        </div>
        <DialogFooter>
          {displayError !== null && <p className="mr-auto text-sm text-destructive">{displayError.message}</p>}
          <Button onClick={submit} disabled={createReview.isPending}>
            {createReview.isPending ? "提交中…" : "提交复盘"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function ReviewItem({
  review,
  onStartNext,
}: {
  review: ReviewResponse;
  onStartNext: (id: string) => void;
}) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span className="text-xl">{moodLabel(review.mood)}</span>
            <CardTitle className="text-base">{review.review_date}</CardTitle>
          </div>
          {review.suggested_replan && <Badge variant="warning">建议调整</Badge>}
        </div>
        <CardDescription>
          完成 {review.completed_count} · 放弃 {review.abandoned_count}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        {review.blockers !== null && (
          <p>
            <span className="text-muted-foreground">阻碍：</span>
            {review.blockers}
          </p>
        )}
        {review.adjustment_request !== null && (
          <p>
            <span className="text-muted-foreground">调整：</span>
            {review.adjustment_request}
          </p>
        )}
        {review.free_text !== null && (
          <p>
            <span className="text-muted-foreground">记录：</span>
            {review.free_text}
          </p>
        )}
        <p className="text-muted-foreground">{review.companion_message}</p>
        {review.next_plan_run_id === null && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => onStartNext(review.review_id)}
            className="mt-2"
          >
            基于本次复盘生成下一份计划 →
          </Button>
        )}
      </CardContent>
    </Card>
  );
}

export function ReviewsPage(): JSX.Element {
  const me = useMe();
  const reviews = useReviews();
  const activePlan = useActivePlan();
  const startNext = useStartNextPlan();
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  const resolvedPlan = me.data?.active_plan ?? activePlan.data;
  const hasPlan =
    me.data?.profile_complete === true &&
    resolvedPlan !== null &&
    resolvedPlan !== undefined;

  function onStartNext(reviewId: string): void {
    if (startNext.isPending) return;
    setError(null);
    startNext.mutate(
      { reviewId, idempotencyKey: `next-${Date.now()}` },
      {
        onSuccess: () => {
          navigate("/today");
        },
        onError: (err: unknown) => {
          setError(toUserFacingError(err).message);
        },
      }
    );
  }

  if (reviews.isLoading) {
    return <div className="text-muted-foreground">正在加载复盘…</div>;
  }

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <div className="flex items-end justify-between gap-4">
        <div><p className="text-sm font-medium text-primary">看见真实节奏</p><h1 className="mt-1 text-2xl font-semibold tracking-tight sm:text-3xl">复盘</h1><p className="mt-2 text-sm text-muted-foreground">不是评判完成多少，而是让下一步更合适。</p></div>
        {hasPlan && (
          <Button size="sm" onClick={() => setShowForm(true)}>
            新建复盘
          </Button>
        )}
      </div>

      {!hasPlan && me.data?.profile_complete === true && (
        <Card>
          <CardContent className="py-6 text-sm text-muted-foreground">
            需要先生成至少一份计划才能开始复盘。
            <Link to="/today" className="ml-2 text-primary hover:underline">去生成 →</Link>
          </CardContent>
        </Card>
      )}

      {error !== null && <p className="text-sm text-destructive">{error}</p>}

      {showForm && activePlan.data !== undefined && activePlan.data !== null && (
        <ReviewForm
          planId={activePlan.data.plan_id}
          onClose={() => setShowForm(false)}
        />
      )}

      {!reviews.isLoading && (reviews.data?.items.length ?? 0) === 0 ? (
        <Card>
          <CardContent className="py-8 text-center text-sm text-muted-foreground">
            还没有复盘记录。
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {(reviews.data?.items ?? []).map((r) => (
            <ReviewItem key={r.review_id} review={r} onStartNext={onStartNext} />
          ))}
        </div>
      )}
    </div>
  );
}
