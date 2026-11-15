"""Định nghĩa AgentState cho LangGraph theo SPEC mục 5.3."""

from typing import Any, TypedDict

from core.schemas import (
    GuidelineSnippet,
    MealPlanLLM,
    NeedsResult,
    NutritionTargets,
    PatientProfile,
    RiskResult,
    Violation,
)


class AgentState(TypedDict, total=False):
    """State dùng chung giữa các node trong LangGraph (SPEC 5.3)."""

    session_id: str
    thread_id: str
    trace_id: str
    profile: PatientProfile
    risk: RiskResult | None
    input_flags: list[str]
    targets: NutritionTargets | None
    needs: NeedsResult | None
    snippets: list[GuidelineSnippet]
    allowed_foods: list[dict[str, Any]]
    plan_llm: MealPlanLLM | None
    plan_scored: list[dict[str, Any]] | None
    violations: list[Violation]
    retry_count: int
    explanation_md: str
    output_flags: list[str]
    review: dict[str, Any] | None  # {decision, note, edited_items}
    status: str
    meal_plan_id: int | None
    metrics: dict[str, Any]  # latency, llm_calls, tokens
    trace_notes: list[str]
    # Cờ kiểm thử cho mock LLM: False | True ("once") | "always"
    mock_force_violation: bool | str
