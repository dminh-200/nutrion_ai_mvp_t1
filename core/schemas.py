"""Schema Pydantic dùng chung giữa các module trong nutrition-ai-mvp."""

from typing import Literal

from pydantic import BaseModel, Field

ConditionCode = Literal["t2d", "htn", "gout", "obesity"]
AllergenCode = Literal["seafood", "peanut", "milk", "egg", "gluten", "soy"]
ActivityLevel = Literal["sedentary", "light", "moderate", "active", "very_active"]
SexType = Literal["male", "female"]
MealType = Literal["breakfast", "lunch", "dinner", "snack"]


class PatientProfile(BaseModel):
    """Hồ sơ sức khỏe đầu vào của người bệnh."""

    patient_code: str = Field(..., min_length=1)
    age: int = Field(..., ge=1, le=120)
    sex: SexType
    height_cm: float = Field(..., ge=50.0, le=250.0)
    weight_kg: float = Field(..., ge=2.0, le=400.0)
    activity_level: ActivityLevel
    conditions: list[ConditionCode]
    allergens: list[AllergenCode] = Field(default_factory=list)
    pregnancy: bool = False
    lactating: bool = False
    ckd_stage: int = Field(default=0, ge=0, le=5)
    dialysis: bool = False
    eating_disorder: bool = False
    preferences_text: str = Field(default="", max_length=500)
    days: int = Field(default=3, ge=1, le=7)


class NutritionTargets(BaseModel):
    """Mục tiêu dinh dưỡng hàng ngày được tính bằng công thức."""

    bmi: float = Field(..., gt=0)
    bmr: float = Field(..., gt=0)
    tdee: float = Field(..., gt=0)
    target_kcal: float = Field(..., gt=0)
    protein_g: float = Field(..., ge=0)
    fat_g: float = Field(..., ge=0)
    carb_g: float = Field(..., ge=0)
    fiber_min_g: float = Field(..., ge=0)
    sodium_max_mg: float = Field(..., ge=0)
    sugar_max_g: float = Field(..., ge=0)
    kcal_floor: float = Field(..., gt=0)
    rationale: list[str] = Field(default_factory=list)


class NeedsResult(BaseModel):
    """Kết quả phân loại nhu cầu dinh dưỡng."""

    needs: list[str] = Field(default_factory=list)
    rule_refs: list[str] = Field(default_factory=list)


class RiskResult(BaseModel):
    """Kết quả sàng lọc nguy cơ cao."""

    high_risk: bool
    reasons: list[str] = Field(default_factory=list)
    message_vi: str = ""


class PlannedItem(BaseModel):
    """Một món ăn được LLM chọn trong bữa."""

    food_id: int = Field(..., gt=0)
    grams: float = Field(..., ge=10.0, le=400.0)


class Meal(BaseModel):
    """Một bữa ăn trong ngày."""

    meal: MealType
    items: list[PlannedItem] = Field(default_factory=list)


class DayPlan(BaseModel):
    """Thực đơn một ngày."""

    day: int = Field(..., ge=1, le=7)
    meals: list[Meal] = Field(default_factory=list)


class MealPlanLLM(BaseModel):
    """Cấu trúc JSON thực đơn do LLM trả về."""

    days: list[DayPlan] = Field(default_factory=list)
    cannot_plan: bool = False
    reason: str = ""


class ScoredItem(PlannedItem):
    """Món ăn đã được code tính toán lại giá trị dinh dưỡng từ DB."""

    name_vi: str
    kcal: float = Field(..., ge=0)
    protein_g: float = Field(..., ge=0)
    fat_g: float = Field(..., ge=0)
    carb_g: float = Field(..., ge=0)
    sodium_mg: float = Field(..., ge=0)
    fiber_g: float = Field(default=0.0, ge=0)
    sugar_g: float = Field(default=0.0, ge=0)


class Violation(BaseModel):
    """Vi phạm phát hiện bởi bộ kiểm chứng hoặc bộ lọc dị ứng."""

    code: str
    message_vi: str
    day: int | None = None
    meal: str | None = None
    food_id: int | None = None


class GuidelineSnippet(BaseModel):
    """Đoạn trích hướng dẫn dinh dưỡng truy xuất từ RAG."""

    text: str
    source_name: str
    year: int | str
    page: int | str
    disease: str
    score: float
