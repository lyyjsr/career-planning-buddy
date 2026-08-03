/**
 * 后端契约类型，从 OpenAPI 精确对齐。
 */

export type GoalType =
  | "ai_backend"
  | "agent_app"
  | "backend_java"
  | "data_engineer"
  | "fullstack"
  | "other";

export type CareerStage = "exploring" | "preparing" | "applying" | "interviewing";
export type SkillLevel = "beginner" | "intermediate" | "advanced";

export type TaskType =
  | "learning"
  | "project"
  | "interview"
  | "application"
  | "resume"
  | "other";

export type TaskStatus =
  | "pending"
  | "in_progress"
  | "completed"
  | "abandoned"
  | "expired";

export type AbandonedReason =
  | "too_hard"
  | "too_easy"
  | "no_time"
  | "lost_interest"
  | "blocked"
  | "other";

export type RunStatus =
  | "pending"
  | "running"
  | "completed"
  | "degraded"
  | "failed"
  | "cancelled";

export type RunResultKind = "plan" | "clarification" | "safe_response";
export type RunIntent = "create_plan" | "replan" | "unsupported";
export type ReplanMode = "initial" | "continue" | "adjust";
export type NextPlanAction = "continue" | "adjust";
export type PlanStatus = "generated" | "active" | "completed" | "archived";

export interface ProfilePreferences {
  target_companies?: string[];
  preferred_time_slot?: string | null;
  weekly_available_days?: number[];
}

export interface ProfileResponse {
  goal_type: GoalType;
  stage: CareerStage;
  time_budget_minutes: number;
  skill_level: SkillLevel;
  skill_summary: string | null;
  deadline: string | null;
  preferences: ProfilePreferences;
  version: number;
}

export interface ProfilePutRequest {
  goal_type: GoalType;
  stage: CareerStage;
  time_budget_minutes: number;
  skill_level: SkillLevel;
  skill_summary?: string | null;
  deadline?: string | null;
  preferences?: ProfilePreferences;
}

export interface ProfilePatchRequest {
  version: number;
  goal_type?: GoalType;
  stage?: CareerStage;
  time_budget_minutes?: number;
  skill_level?: SkillLevel;
  skill_summary?: string | null;
  deadline?: string | null;
  preferences?: ProfilePreferences;
}

export interface WeeklyFocus {
  week_index: number;
  focus: string;
  success_signal: string;
}

export interface TaskResponse {
  task_id: string;
  plan_id: string;
  title: string;
  task_type: TaskType;
  scheduled_date: string;
  order_index: number;
  state: TaskStatus;
  starter_action: string;
  deliverable: string;
  rationale: string | null;
  estimated_minutes: number;
  actual_minutes: number | null;
  abandoned_reason: AbandonedReason | null;
  abandoned_reason_text: string | null;
  version: number;
  started_at: string | null;
  completed_at: string | null;
  abandoned_at: string | null;
  created_at: string;
}

export interface PlanSourceResponse {
  kind: string;
  id: string;
  available: boolean;
  title: string | null;
  url?: string | null;
  snippet?: string | null;
  reliability?: number | null;
}

export interface ActivePlanResponse {
  plan_id: string;
  status: PlanStatus;
  plan_date: string;
  horizon_start: string;
  horizon_end: string;
  overall_direction: string;
  weekly_focus: WeeklyFocus[];
  summary: string;
  rationale: string;
  adjustment_reason: string | null;
  sources: PlanSourceResponse[];
  tasks: TaskResponse[];
  companion_message: string | null;
  version: number;
  adopted_at: string | null;
  created_at: string;
}

export interface PlanResultSummary {
  plan_id: string;
  status: PlanStatus;
  plan_date: string;
  horizon_end: string;
  summary: string;
  task_count: number;
}

export interface ClarificationRequestPayload {
  questions: string[];
  slot_names: string[];
  hint_options: Record<string, string[]>;
  reason: string;
}

export interface SafeResponsePayload {
  message: string;
  resource_ids: string[];
  disclaimer: string;
}

export interface AgentRunResponse {
  run_id: string;
  status: RunStatus;
  resolved_intent: RunIntent | null;
  replan_mode: ReplanMode | null;
  result_kind: RunResultKind | null;
  result: PlanResultSummary | ClarificationRequestPayload | SafeResponsePayload | null;
  final_plan_id: string | null;
  fallback_reason: string | null;
  error_code: string | null;
  risk_category: string | null;
  total_tokens_in: number;
  total_tokens_out: number;
  total_cost_cny: string;
  total_latency_ms: number;
  created_at: string;
  finished_at: string | null;
}

export interface AgentRunCreatedResponse {
  run_id: string;
  status: RunStatus;
  events_url: string;
}

export interface AgentRunCreateRequest {
  message: string;
  hint_intent?: "create_plan" | "replan" | null;
  goal_type_override?: GoalType | null;
  source_plan_id?: string | null;
}

export interface UserSummary {
  id: string;
  display_name: string | null;
  role: "user" | "dev";
}

export interface MeResponse {
  user: UserSummary;
  profile_complete: boolean;
  profile: ProfileResponse | null;
  active_plan: ActivePlanResponse | null;
  today_tasks: TaskResponse[];
  latest_review: unknown | null;
  active_run: AgentRunResponse | null;
}

export interface GuestLoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: UserSummary;
}

export interface ReviewResponse {
  review_id: string;
  plan_id: string;
  review_date: string;
  mood: number;
  blockers: string | null;
  adjustment_request: string | null;
  free_text: string | null;
  completed_count: number;
  abandoned_count: number;
  suggested_replan: boolean;
  replan_reason: string | null;
  next_plan_action: NextPlanAction;
  companion_message: string;
  next_plan_run_id: string | null;
  created_at: string;
}

export interface ReviewCreateRequest {
  plan_id: string;
  review_date: string;
  mood: number;
  blockers?: string | null;
  adjustment_request?: string | null;
  free_text?: string | null;
}

export interface StartNextPlanResponse {
  run_id: string;
  status: RunStatus;
  replan_mode: ReplanMode;
  events_url: string;
}

export interface TaskUpdateRequest {
  state: TaskStatus;
  version: number;
  actual_minutes?: number | null;
  abandoned_reason?: AbandonedReason | null;
  abandoned_reason_text?: string | null;
}

export interface TaskUpdateResponse {
  task: TaskResponse;
  plan_status: PlanStatus;
  companion_message: string;
}

export interface MemoryResponse {
  memory_id: string;
  memory_type: "profile_fact" | "stable_preference" | "execution_pattern";
  summary: string;
  content: Record<string, unknown>;
  sensitivity: "normal" | "sensitive";
  status: "active" | "closed";
  source_run_id: string | null;
  version: number;
  last_used_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface MemoryCandidateResponse {
  candidate_id: string;
  memory_type: "profile_fact" | "stable_preference" | "execution_pattern";
  summary: string;
  content: Record<string, unknown>;
  sensitivity: "sensitive" | "highly_sensitive";
  status: "pending" | "confirmed" | "rejected" | "expired";
  proposed_by_run_id: string | null;
  activated_memory_id: string | null;
  expires_at: string;
  created_at: string;
  decided_at: string | null;
}

export interface MemoryCandidateDecisionResponse {
  candidate: MemoryCandidateResponse;
  memory: MemoryResponse | null;
}
