export type ConditionCode = "t2d" | "htn" | "gout" | "obesity";
export type AllergenCode = "seafood" | "peanut" | "milk" | "egg" | "gluten" | "soy";
export type ActivityLevel = "sedentary" | "light" | "moderate" | "active" | "very_active";
export type SexType = "male" | "female";
export type MealType = "breakfast" | "lunch" | "dinner" | "snack";
export type DemoRole = "patient" | "expert" | "admin";

export interface PatientProfileInput {
  patient_code: string;
  age: number;
  sex: SexType;
  height_cm: number;
  weight_kg: number;
  activity_level: ActivityLevel;
  conditions: ConditionCode[];
  allergens: AllergenCode[];
  pregnancy: boolean;
  lactating: boolean;
  ckd_stage: number;
  dialysis: boolean;
  eating_disorder: boolean;
  preferences_text: string;
  days: number;
}

export interface SamplePatient extends PatientProfileInput {
  display_name: string;
}

export interface NutritionTargets {
  bmi: number;
  bmr: number;
  tdee: number;
  target_kcal: number;
  protein_g: number;
  fat_g: number;
  carb_g: number;
  fiber_min_g: number;
  sodium_max_mg: number;
  sugar_max_g: number;
  kcal_floor: number;
  rationale: string[];
}

export interface NeedsResult {
  needs: string[];
  rule_refs: string[];
}

export interface RiskResult {
  high_risk: boolean;
  reasons: string[];
  message_vi: string;
}

export interface MealItem {
  id?: number | null;
  day: number;
  meal: MealType | string;
  food_id: number;
  name_vi: string;
  grams: number;
  kcal: number;
  protein_g: number;
  fat_g: number;
  carb_g: number;
  sodium_mg: number;
  fiber_g: number;
  sugar_g: number;
}

export interface DailyTotal {
  day: number;
  kcal: number;
  protein_g: number;
  fat_g: number;
  carb_g: number;
  sodium_mg: number;
  fiber_g: number;
  sugar_g: number;
}

export interface Violation {
  code: string;
  message_vi: string;
  day?: number | null;
  meal?: string | null;
  food_id?: number | null;
}

export interface GuidelineSnippet {
  text: string;
  source_name: string;
  year: number | string;
  page: number | string;
  disease: string;
  score: number;
}

export interface PatientSummary {
  patient_code: string;
  display_name: string;
  age: number;
  sex: SexType;
  height_cm: number;
  weight_kg: number;
  conditions: string[];
  allergens: string[];
  days: number;
  preferences_text: string;
}

export interface MealPlanRunResponse {
  status: string;
  meal_plan_id: number | null;
  thread_id: string;
  session_id: string;
  trace_id: string;
  retry_count: number;
  input_flags: string[];
  output_flags: string[];
  patient?: PatientSummary | null;
  risk: RiskResult | null;
  targets: NutritionTargets | null;
  needs: NeedsResult | null;
  items: MealItem[];
  daily_totals: DailyTotal[];
  violations: Violation[];
  snippets: GuidelineSnippet[];
  explanation_md: string;
  metrics: Record<string, unknown>;
  execution: Record<string, unknown>;
  trace_notes: string[];
}

export interface MealPlanSummary {
  id: number;
  thread_id: string;
  status: string;
  patient_code: string;
  display_name: string;
  conditions: string[];
  retry_count: number;
  verifier_passed_first_try: boolean;
  created_at: string;
}

export interface MealPlanQueueCounts {
  pending_review: number;
  needs_human_review: number;
  approved: number;
  rejected: number;
  total: number;
}

export interface MealPlanListResponse {
  counts: MealPlanQueueCounts;
  items: MealPlanSummary[];
}

export interface ReviewRecord {
  id: number;
  reviewer_name: string;
  decision: string;
  note: string;
  created_at: string;
}

export interface GuardrailEventRecord {
  id: number;
  layer: string;
  type: string;
  reason: string;
  created_at: string;
}

export interface MealPlanDetailResponse {
  meal_plan: {
    id: number;
    thread_id: string;
    status: string;
    explanation_md: string;
    retry_count: number;
    verifier_passed_first_try: boolean;
    created_at: string;
  };
  patient: {
    code: string;
    display_name: string;
    age: number;
    sex: SexType;
    height_cm: number;
    weight_kg: number;
    activity_level: ActivityLevel;
    conditions: string[];
    allergens: string[];
    pregnancy: boolean;
    lactating: boolean;
    ckd_stage: number;
    dialysis: boolean;
    eating_disorder: boolean;
    preferences_text: string;
    days: number;
  };
  targets: Partial<NutritionTargets>;
  needs: Partial<NeedsResult>;
  risk?: RiskResult | null;
  snippets?: GuidelineSnippet[];
  violations?: Violation[];
  items: MealItem[];
  by_day: Record<string, Record<string, MealItem[]>>;
  daily_totals: DailyTotal[];
  reviews: ReviewRecord[];
  guardrail_events: GuardrailEventRecord[];
}

export interface EditedItemInput {
  day: number;
  meal: MealType;
  food_id: number;
  grams: number;
}

export interface PreviewEditResponse {
  is_valid: boolean;
  violations: Violation[];
  daily_totals: DailyTotal[];
  scored_items: Array<{
    food_id: number;
    grams: number;
    name_vi: string;
    kcal: number;
    protein_g: number;
    fat_g: number;
    carb_g: number;
    sodium_mg: number;
    fiber_g: number;
    sugar_g: number;
  }>;
}

export interface AllowedFood {
  id: number;
  code: string;
  name_vi: string;
  food_group: string;
  unit_default_g: number;
  kcal: number;
  protein_g: number;
  fat_g: number;
  carb_g: number;
  fiber_g: number;
  sugar_g: number;
  sodium_mg: number;
  purine_level: string;
}

export interface ReviewSubmitRequest {
  decision: "approve" | "edit" | "reject";
  reviewer_name: string;
  note: string;
  edited_items?: EditedItemInput[];
}

export interface ReviewSubmitResponse {
  meal_plan_id: number;
  thread_id: string;
  status: string;
  decision: string;
  note: string;
  violations: Violation[];
  daily_totals: DailyTotal[];
  detail: MealPlanDetailResponse;
}

export interface SystemWarnings {
  has_warnings: boolean;
  todo_verify_count: number;
  todo_verify_items: string[];
  is_sample_food: boolean;
  sample_food_warning: string | null;
  llm_warning: string | null;
  warnings: string[];
}

export interface SystemStatusResponse {
  llm_mode: string;
  llm_provider: string;
  active_model: string;
  chat_model?: string;
  chat_uses_dedicated_key?: boolean;
  tools_mode: string;
  safety_llm: string;
  langfuse_enabled: boolean;
  disclaimer_vi: string;
  warnings: SystemWarnings;
}

export interface DashboardKpis {
  total_requests: number;
  approved_count: number;
  approval_rate_pct: number;
  pending_count: number;
  redirect_count: number;
  redirect_rate_pct: number;
  blocked_count: number;
  blocked_rate_pct: number;
  first_pass_verifier_rate_pct: number;
  avg_latency_ms: number;
  p95_latency_ms: number;
  total_tokens: number;
  est_cost_usd: number;
  guardrail_trigger_count: number;
}

export interface QueryLogRow {
  id: number;
  created_at: string;
  session_id: string;
  patient_code: string;
  status: string;
  latency_ms: number;
  llm_calls: number;
  tokens_in: number;
  tokens_out: number;
  est_cost_usd: number;
  retry_count: number;
  violation_codes: string;
  trace_id: string;
  trace_url: string;
  is_synthetic_log: boolean;
}

export interface DashboardResponse {
  kpis: DashboardKpis;
  charts: {
    trend_by_date: Array<{
      date: string;
      approved: number;
      pending: number;
      redirect: number;
      blocked: number;
      total: number;
    }>;
    condition_distribution: {
      labels: string[];
      codes: string[];
      values: number[];
    };
    guardrails_by_type: {
      labels: string[];
      counts: number[];
    };
    latency_distribution: {
      latencies: number[];
      avg: number;
      p95: number;
    };
  };
  logs: QueryLogRow[];
  is_synthetic_included: boolean;
}

export type GuardrailTier = "hard_block" | "soft_boundary" | "normal";

export interface ChatMessageItem {
  role: "user" | "assistant";
  content: string;
}

export interface ChatRequest {
  message: string;
  meal_plan_id?: number | null;
  session_id?: string | null;
  history: ChatMessageItem[];
}

export interface ChatCitation {
  source: string;
  page: string;
  score: number;
  excerpt: string;
}

export interface ChatFoodSuggestion {
  food_id: number;
  name_vi: string;
  category: string;
  kcal: number;
  protein_g: number;
  fat_g: number;
  carb_g: number;
  sodium_mg: number;
  fiber_g: number;
  purine_level: string;
}

export interface ChatContextSummary {
  meal_plan_id: number | null;
  status: string | null;
  conditions: string[];
  kcal_target: number | null;
}

export interface ChatResponse {
  session_id: string;
  reply_md: string;
  guardrail_tier: GuardrailTier;
  flags: string[];
  citations: ChatCitation[];
  suggested_foods: ChatFoodSuggestion[];
  context_summary: ChatContextSummary;
  disclaimer_vi: string;
  latency_ms: number;
}
