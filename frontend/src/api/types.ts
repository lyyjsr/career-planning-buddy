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

export type RunResultKind = "plan" | "clarification" | "safe_response" | "navigation";
export type RunIntent = "create_plan" | "replan" | "navigate" | "unsupported";
export type RunUserStatus =
  | "queued"
  | "generating"
  | "recovering"
  | "stopping"
  | "ready"
  | "action_required"
  | "failed"
  | "cancelled";
export type ReplanMode = "initial" | "continue" | "adjust";
export type NextPlanAction = "continue" | "adjust";
export type PlanStatus = "generated" | "active" | "completed" | "archived";

export interface ProfilePreferences {
  target_companies: string[];
  preferred_time_slot: string | null;
  weekly_available_days: number[];
}

export type ProfilePreferencesInput = Partial<ProfilePreferences>;

export interface ProfileResponse {
  goal_type: GoalType;
  stage: CareerStage;
  time_budget_minutes: number;
  skill_level: SkillLevel;
  skill_summary: string | null;
  start_date: string | null;
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
  start_date: string;
  deadline: string;
  preferences?: ProfilePreferencesInput;
}

export interface ProfilePatchRequest {
  version: number;
  goal_type?: GoalType;
  stage?: CareerStage;
  time_budget_minutes?: number;
  skill_level?: SkillLevel;
  skill_summary?: string | null;
  start_date?: string | null;
  deadline?: string | null;
  preferences?: ProfilePreferencesInput;
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
  execution_steps: TaskExecutionStep[];
  deliverable: string;
  deliverable_verified: boolean;
  verification_status: "not_ready" | "ready" | "failed" | "passed";
  completion_ready: boolean;
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

export interface TaskExecutionStep {
  index: number;
  text: string;
  completed: boolean;
}

export interface TaskDetailResponse {
  task: TaskResponse;
  week_focus: string;
  week_success_signal: string;
  editable: boolean;
  edit_reason: string | null;
}

export interface TaskEditFields {
  title?: string;
  starter_action?: string;
  deliverable?: string;
  rationale?: string;
  estimated_minutes?: number;
}

export interface TaskEditRequest extends TaskEditFields {
  version: number;
}

export interface TaskEditResponse {
  task: TaskResponse;
  adjustment_id: string;
  companion_message: string;
}

export interface TaskAdjustmentProposalResponse {
  adjustment_id: string;
  plan_id: string;
  task_id: string;
  status: "pending" | "applied" | "rejected";
  request_text: string;
  original_task: Record<string, unknown>;
  proposed_patch: TaskEditFields;
  rationale: string;
  generation_method: "manual" | "rule" | "model" | "rule_fallback";
  model_id: string | null;
  task_version: number;
  version: number;
  created_at: string;
}

export interface PlanSourceResponse {
  kind: "memory" | "experience_atom" | "search_source";
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
  message: string;
  suggested_actions: SuggestedAction[];
  target_route: "/settings/profile" | "/journey" | "/today" | null;
}

export interface SuggestedAction {
  action: "complete_profile" | "create_plan" | "continue_plan" | "adjust_plan" | "view_current_plan" | "view_today_tasks";
  label: string;
  target_route: "/settings/profile" | "/journey" | "/today" | "/reviews";
}

export interface NavigationResultPayload {
  action: "view_current_plan" | "view_today_tasks";
  label: string;
  target_route: "/journey" | "/today";
  message: string;
}

export interface SafeResponsePayload {
  message: string;
  resource_ids: string[];
  disclaimer: string;
}

export interface AgentRunResponse {
  run_id: string;
  status: RunStatus;
  user_status: RunUserStatus;
  status_message: string;
  resolved_intent: RunIntent | null;
  replan_mode: ReplanMode | null;
  result_kind: RunResultKind | null;
  result: PlanResultSummary | ClarificationRequestPayload | SafeResponsePayload | NavigationResultPayload | null;
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
  cancel_requested_at: string | null;
}

export interface AgentRunCreatedResponse {
  run_id: string;
  status: RunStatus;
  events_url: string;
}

export type GoalBriefStatus = "clarification_required" | "awaiting_confirmation" | "confirmed" | "cancelled";
export type ObjectiveType = "career_plan" | "project" | "application" | "interview" | "skill_transition";

export interface GoalBriefResponse {
  goal_brief_id: string;
  status: GoalBriefStatus;
  source_message: string;
  hint_intent: "create_plan" | "replan";
  source_plan_id: string | null;
  objective_type: ObjectiveType | null;
  target_role: string | null;
  objective: string | null;
  capability_focus: string[];
  tech_stack: string[];
  duration_weeks: number | null;
  deliverables: string[];
  success_criteria: string[];
  assumptions: string[];
  missing_fields: string[];
  questions: string[];
  extraction_method: "rule" | "model" | "rule_fallback";
  model_id: string | null;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface GoalBriefCreateRequest {
  message: string;
  hint_intent: "create_plan" | "replan";
  source_plan_id?: string | null;
}

export interface GoalBriefConfirmResponse {
  goal_brief: GoalBriefResponse;
  run: AgentRunCreatedResponse;
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
  latest_review: ReviewResponse | null;
  active_run: AgentRunResponse | null;
  active_goal_brief: GoalBriefResponse | null;
}

export interface GuestLoginResponse {
  access_token: string;
  token_type: "bearer";
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
  version: number;
  created_at: string;
  updated_at: string;
}

export interface ReviewCreateRequest {
  plan_id: string;
  review_date: string;
  mood: number;
  blockers?: string | null;
  adjustment_request?: string | null;
  free_text?: string | null;
}

export interface ReviewUpdateRequest {
  version: number;
  mood?: number;
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
  state: "in_progress" | "completed" | "abandoned";
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

export interface TaskChecklistUpdateRequest {
  version: number;
  step_index: number;
  step_completed: boolean;
}

export interface TaskVerificationRequest {
  version: number;
  passed: boolean;
  actual_minutes?: number;
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
