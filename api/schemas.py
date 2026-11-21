"""Schema Pydantic cho tầng FastAPI wrapper (đối chiếu 1-1 với core/schemas.py và db/repo.py)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from core.schemas import (
    GuidelineSnippet,
    MealType,
    NeedsResult,
    NutritionTargets,
    RiskResult,
    ScoredItem,
    Violation,
)


class HealthResponse(BaseModel):
    """Phản hồi kiểm tra sức khỏe dịch vụ và kết nối SQLite."""

    ok: bool
    db_ready: bool
    patient_count: int
    food_count: int


class SystemWarningsOut(BaseModel):
    """Cảnh báo cấu hình TODO_VERIFY, dữ liệu mẫu và khóa LLM."""

    has_warnings: bool
    todo_verify_count: int
    todo_verify_items: list[str] = Field(default_factory=list)
    is_sample_food: bool
    sample_food_warning: str | None = None
    llm_warning: str | None = None
    warnings: list[str] = Field(default_factory=list)


class SystemStatusResponse(BaseModel):
    """Trạng thái cấu hình hệ thống phục vụ giao diện Chuyên gia / Quản trị."""

    llm_mode: str
    llm_provider: str
    active_model: str
    chat_model: str = ""
    chat_uses_dedicated_key: bool = False
    tools_mode: str
    safety_llm: str
    langfuse_enabled: bool
    disclaimer_vi: str
    warnings: SystemWarningsOut


class GraphMermaidResponse(BaseModel):
    """Chuỗi sơ đồ Mermaid của AgentGraph 11 nodes."""

    mermaid: str


class SamplePatientOut(BaseModel):
    """Hồ sơ bệnh nhân mẫu giả lập nạp từ data/patients_seed.json."""

    patient_code: str
    display_name: str = ""
    age: int
    sex: Literal["male", "female"]
    height_cm: float
    weight_kg: float
    activity_level: Literal["sedentary", "light", "moderate", "active", "very_active"]
    conditions: list[Literal["t2d", "htn", "gout", "obesity"]] = Field(default_factory=list)
    allergens: list[Literal["seafood", "peanut", "milk", "egg", "gluten", "soy"]] = Field(
        default_factory=list
    )
    pregnancy: bool = False
    lactating: bool = False
    ckd_stage: int = 0
    dialysis: bool = False
    eating_disorder: bool = False
    preferences_text: str = ""
    days: int = 3


class SamplePatientsResponse(BaseModel):
    """Danh sách 30 bệnh nhân mẫu."""

    patients: list[SamplePatientOut]


class MealItemOut(BaseModel):
    """Món ăn chi tiết trong từng ngày/bữa kèm chỉ số dinh dưỡng đã tính từ food DB."""

    id: int | None = None
    day: int
    meal: str
    food_id: int
    name_vi: str
    grams: float
    kcal: float
    protein_g: float
    fat_g: float
    carb_g: float
    sodium_mg: float
    fiber_g: float = 0.0
    sugar_g: float = 0.0


class DailyTotalOut(BaseModel):
    """Tổng hợp dinh dưỡng theo từng ngày."""

    day: int
    kcal: float
    protein_g: float
    fat_g: float
    carb_g: float
    sodium_mg: float
    fiber_g: float = 0.0
    sugar_g: float = 0.0


class PatientSummaryOut(BaseModel):
    """Tóm tắt thông tin hồ sơ & bệnh lý nền trả về cùng kết quả tạo thực đơn."""

    patient_code: str
    display_name: str = ""
    age: int = 0
    sex: Literal["male", "female"] = "male"
    height_cm: float = 0.0
    weight_kg: float = 0.0
    conditions: list[str] = Field(default_factory=list)
    allergens: list[str] = Field(default_factory=list)
    days: int = 3
    preferences_text: str = ""


class MealPlanRunResponse(BaseModel):
    """Kết quả trả về khi gọi agent.graph.run_request(profile)."""

    status: str
    meal_plan_id: int | None = None
    thread_id: str
    session_id: str
    trace_id: str
    retry_count: int = 0
    input_flags: list[str] = Field(default_factory=list)
    output_flags: list[str] = Field(default_factory=list)
    patient: PatientSummaryOut | None = None
    risk: RiskResult | None = None
    targets: NutritionTargets | None = None
    needs: NeedsResult | None = None
    items: list[MealItemOut] = Field(default_factory=list)
    daily_totals: list[DailyTotalOut] = Field(default_factory=list)
    violations: list[Violation] = Field(default_factory=list)
    snippets: list[GuidelineSnippet] = Field(default_factory=list)
    explanation_md: str = ""
    metrics: dict[str, Any] = Field(default_factory=dict)
    execution: dict[str, Any] = Field(default_factory=dict)
    trace_notes: list[str] = Field(default_factory=list)


class MealPlanSummary(BaseModel):
    """Tóm tắt một ca thực đơn trong danh sách hàng đợi."""

    id: int
    thread_id: str
    status: str
    patient_code: str
    display_name: str
    conditions: list[str] = Field(default_factory=list)
    retry_count: int = 0
    verifier_passed_first_try: bool = False
    created_at: str = ""


class MealPlanQueueCounts(BaseModel):
    """Bộ đếm số ca theo nhóm trạng thái phục vụ tab bộ lọc."""

    pending_review: int = 0
    needs_human_review: int = 0
    approved: int = 0
    rejected: int = 0
    total: int = 0


class MealPlanListResponse(BaseModel):
    """Danh sách thực đơn kèm bộ đếm trạng thái."""

    counts: MealPlanQueueCounts
    items: list[MealPlanSummary]


class ReviewRecordOut(BaseModel):
    """Lịch sử một lượt duyệt của chuyên gia."""

    id: int
    reviewer_name: str
    decision: str
    note: str
    created_at: str = ""


class GuardrailEventOut(BaseModel):
    """Sự kiện guardrail ghi nhận trên session/thread."""

    id: int
    layer: str
    type: str
    reason: str
    created_at: str = ""


class MealPlanDetailResponse(BaseModel):
    """Chi tiết thực đơn từ get_meal_plan_detail (kèm fiber/sugar, giải trình và guardrail)."""

    meal_plan: dict[str, Any]
    patient: dict[str, Any]
    targets: dict[str, Any]
    needs: dict[str, Any]
    risk: RiskResult | None = None
    snippets: list[GuidelineSnippet] = Field(default_factory=list)
    violations: list[Violation] = Field(default_factory=list)
    items: list[MealItemOut] = Field(default_factory=list)
    by_day: dict[str, dict[str, list[MealItemOut]]] = Field(default_factory=dict)
    daily_totals: list[DailyTotalOut] = Field(default_factory=list)
    reviews: list[ReviewRecordOut] = Field(default_factory=list)
    guardrail_events: list[GuardrailEventOut] = Field(default_factory=list)


class EditedItemInput(BaseModel):
    """Một dòng định lượng do chuyên gia chỉnh sửa."""

    day: int = Field(..., ge=1, le=7)
    meal: MealType
    food_id: int = Field(..., ge=1)
    grams: float = Field(..., ge=0.0, le=1000.0)


class PreviewEditRequest(BaseModel):
    """Payload kiểm chứng khô (dry-run) bản sửa định lượng."""

    edited_items: list[EditedItemInput] = Field(default_factory=list)


class PreviewEditResponse(BaseModel):
    """Kết quả kiểm chứng khô 11 tiêu chí (không ghi DB)."""

    is_valid: bool
    violations: list[Violation] = Field(default_factory=list)
    daily_totals: list[DailyTotalOut] = Field(default_factory=list)
    scored_items: list[ScoredItem] = Field(default_factory=list)


class ReviewSubmitRequest(BaseModel):
    """Quyết định duyệt của chuyên gia (approve / edit / reject)."""

    decision: Literal["approve", "edit", "reject"]
    reviewer_name: str = Field(default="BS. Dinh dưỡng", min_length=1, max_length=120)
    note: str = Field(default="", max_length=1000)
    edited_items: list[EditedItemInput] | None = None


class ReviewSubmitResponse(BaseModel):
    """Kết quả sau khi áp dụng quyết định chuyên gia."""

    meal_plan_id: int
    thread_id: str
    status: str
    decision: str
    note: str
    violations: list[Violation] = Field(default_factory=list)
    daily_totals: list[DailyTotalOut] = Field(default_factory=list)
    detail: MealPlanDetailResponse


class DashboardResponse(BaseModel):
    """Dữ liệu KPI, 4 biểu đồ và danh sách QueryLog cho màn Dashboard."""

    kpis: dict[str, Any]
    charts: dict[str, Any]
    logs: list[dict[str, Any]]
    is_synthetic_included: bool


class ChatMessageIn(BaseModel):
    """Một lượt tin nhắn trong lịch sử hội thoại."""

    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=6000)


class ChatRequest(BaseModel):
    """Yêu cầu gửi tin nhắn tới Chatbot Trợ lý Dinh dưỡng."""

    message: str = Field(..., min_length=1, max_length=800)
    meal_plan_id: int | None = Field(default=None, ge=1)
    session_id: str | None = Field(default=None, max_length=64)
    history: list[ChatMessageIn] = Field(default_factory=list, max_length=10)


class ChatCitationOut(BaseModel):
    """Trích dẫn hướng dẫn y khoa RAG gắn kèm phản hồi chat."""

    source: str
    page: str
    score: float
    excerpt: str


class ChatFoodSuggestionOut(BaseModel):
    """Món ăn gợi ý an toàn lấy từ Food DB."""

    food_id: int
    name_vi: str
    category: str
    kcal: float
    protein_g: float
    fat_g: float
    carb_g: float
    sodium_mg: float
    fiber_g: float
    purine_level: str


class ChatContextSummaryOut(BaseModel):
    """Tóm tắt ngữ cảnh thực đơn đang liên kết với phiên chat."""

    meal_plan_id: int | None = None
    status: str | None = None
    conditions: list[str] = Field(default_factory=list)
    kcal_target: float | None = None


class ChatResponse(BaseModel):
    """Phản hồi từ Chatbot Trợ lý Dinh dưỡng."""

    session_id: str
    reply_md: str
    guardrail_tier: Literal["hard_block", "soft_boundary", "normal"]
    flags: list[str] = Field(default_factory=list)
    citations: list[ChatCitationOut] = Field(default_factory=list)
    suggested_foods: list[ChatFoodSuggestionOut] = Field(default_factory=list)
    context_summary: ChatContextSummaryOut
    disclaimer_vi: str
    latency_ms: int
