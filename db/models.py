"""Mô hình SQLAlchemy 2.x cho 14 bảng SQLite theo SPEC mục 5.1."""

from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utc_now() -> datetime:
    """Trả về thời gian hiện tại múi giờ UTC."""
    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Lớp cơ sở cho tất cả các bảng ORM."""


class Patient(Base):
    """Bảng bệnh nhân giả lập."""

    __tablename__ = "patient"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)


class HealthProfile(Base):
    """Hồ sơ sức khỏe gắn với bệnh nhân."""

    __tablename__ = "health_profile"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("patient.id", ondelete="CASCADE"), nullable=False
    )
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    sex: Mapped[str] = mapped_column(String(10), nullable=False)
    height_cm: Mapped[float] = mapped_column(Float, nullable=False)
    weight_kg: Mapped[float] = mapped_column(Float, nullable=False)
    activity_level: Mapped[str] = mapped_column(String(20), nullable=False)
    pregnancy: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    lactating: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ckd_stage: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    dialysis: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    eating_disorder: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    preferences_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    days: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)


class Condition(Base):
    """Danh mục 4 nhóm bệnh hỗ trợ."""

    __tablename__ = "condition"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    name_vi: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)


class ProfileCondition(Base):
    """Bảng nối hồ sơ sức khỏe và bệnh lý."""

    __tablename__ = "profile_condition"

    profile_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("health_profile.id", ondelete="CASCADE"), primary_key=True
    )
    condition_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("condition.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)


class Allergen(Base):
    """Danh mục dị nguyên."""

    __tablename__ = "allergen"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    name_vi: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)


class ProfileAllergen(Base):
    """Bảng nối hồ sơ sức khỏe và dị nguyên."""

    __tablename__ = "profile_allergen"

    profile_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("health_profile.id", ondelete="CASCADE"), primary_key=True
    )
    allergen_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("allergen.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)


class Food(Base):
    """Danh mục thực phẩm."""

    __tablename__ = "food"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    name_vi: Mapped[str] = mapped_column(String(200), nullable=False)
    name_ascii: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    food_group: Mapped[str] = mapped_column(String(80), nullable=False)
    unit_default_g: Mapped[float] = mapped_column(Float, default=100.0, nullable=False)
    purine_level: Mapped[str] = mapped_column(String(20), default="unknown", nullable=False)
    allergen_tags: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    tags: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    source: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)


class FoodNutrient(Base):
    """Giá trị dinh dưỡng trên 100g ăn được."""

    __tablename__ = "food_nutrient"

    food_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("food.id", ondelete="CASCADE"), primary_key=True
    )
    kcal: Mapped[float] = mapped_column(Float, nullable=False)
    protein_g: Mapped[float] = mapped_column(Float, nullable=False)
    fat_g: Mapped[float] = mapped_column(Float, nullable=False)
    carb_g: Mapped[float] = mapped_column(Float, nullable=False)
    fiber_g: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    sugar_g: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    sodium_mg: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    sat_fat_g: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)


class MealPlan(Base):
    """Kế hoạch bữa ăn và trạng thái HITL."""

    __tablename__ = "meal_plan"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("health_profile.id", ondelete="CASCADE"), nullable=False
    )
    thread_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), default="draft", nullable=False)
    targets_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    needs_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    explanation_md: Mapped[str] = mapped_column(Text, default="", nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    verifier_passed_first_try: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)


class MealPlanItem(Base):
    """Chi tiết từng món ăn trong kế hoạch."""

    __tablename__ = "meal_plan_item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    meal_plan_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("meal_plan.id", ondelete="CASCADE"), nullable=False
    )
    day: Mapped[int] = mapped_column(Integer, nullable=False)
    meal: Mapped[str] = mapped_column(String(20), nullable=False)
    food_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("food.id", ondelete="RESTRICT"), nullable=False
    )
    grams: Mapped[float] = mapped_column(Float, nullable=False)
    kcal: Mapped[float] = mapped_column(Float, nullable=False)
    protein_g: Mapped[float] = mapped_column(Float, nullable=False)
    fat_g: Mapped[float] = mapped_column(Float, nullable=False)
    carb_g: Mapped[float] = mapped_column(Float, nullable=False)
    sodium_mg: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)


class GuidelineDoc(Base):
    """Tài liệu hướng dẫn dinh dưỡng dùng cho RAG."""

    __tablename__ = "guideline_doc"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_name: Mapped[str] = mapped_column(String(200), nullable=False)
    organization: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    year: Mapped[int] = mapped_column(Integer, default=2024, nullable=False)
    url: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    diseases: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    license_note: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)


class Review(Base):
    """Quyết định duyệt của chuyên gia dinh dưỡng."""

    __tablename__ = "review"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    meal_plan_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("meal_plan.id", ondelete="CASCADE"), nullable=False
    )
    reviewer_name: Mapped[str] = mapped_column(String(120), nullable=False)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    edited_items_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)


class QueryLog(Base):
    """Nhật ký truy vấn phục vụ dashboard và đánh giá."""

    __tablename__ = "query_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    meal_plan_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("meal_plan.id", ondelete="SET NULL"), nullable=True
    )
    session_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    patient_code: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    llm_calls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    est_cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    violation_codes: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    trace_id: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    is_synthetic_log: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)


class GuardrailEvent(Base):
    """Nhật ký các sự kiện chặn hoặc cảnh báo từ guardrails."""

    __tablename__ = "guardrail_event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    layer: Mapped[str] = mapped_column(String(20), nullable=False)
    type: Mapped[str] = mapped_column(String(40), nullable=False)
    reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
