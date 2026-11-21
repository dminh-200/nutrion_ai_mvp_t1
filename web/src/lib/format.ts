import type {
  ActivityLevel,
  AllergenCode,
  ConditionCode,
  MealPlanDetailResponse,
  MealPlanRunResponse,
} from "@/types/api";

export const CONDITION_LABELS: Record<ConditionCode, string> = {
  t2d: "Đái tháo đường T2",
  htn: "Tăng huyết áp",
  gout: "Gout",
  obesity: "Béo phì",
};

export const CONDITION_DESCRIPTIONS: Record<ConditionCode, string> = {
  t2d: "Kiểm soát đường huyết, hạn chế đường đơn & tăng chất xơ",
  htn: "Giảm natri ≤ 2.000 mg/ngày, tránh đồ muối & chế biến sẵn",
  gout: "Hạn chế thực phẩm giàu purin, tránh nội tạng",
  obesity: "Kiểm soát thâm hụt năng lượng lành mạnh, tăng đạm nạc",
};

export const ALLERGEN_LABELS: Record<AllergenCode, string> = {
  seafood: "Hải sản",
  peanut: "Đậu phộng",
  milk: "Sữa",
  egg: "Trứng",
  gluten: "Gluten",
  soy: "Đậu nành",
};

export const ACTIVITY_LABELS: Record<ActivityLevel, string> = {
  sedentary: "Ít vận động (văn phòng, tĩnh tại)",
  light: "Vận động nhẹ (1–3 buổi/tuần)",
  moderate: "Vận động vừa phải (3–5 buổi/tuần)",
  active: "Vận động nhiều (6–7 buổi/tuần)",
  very_active: "Vận động rất nhiều (lao động nặng / thể thao)",
};

export const MEAL_LABELS: Record<string, string> = {
  breakfast: "Bữa sáng",
  lunch: "Bữa trưa",
  dinner: "Bữa tối",
  snack: "Bữa phụ",
};

export const STATUS_LABELS: Record<string, string> = {
  approved: "Đã duyệt",
  pending_review: "Chờ chuyên gia duyệt",
  needs_human_review: "Cần chuyên gia xem xét",
  blocked: "Bị chặn an toàn",
  rejected: "Đã từ chối",
  redirect_to_doctor: "Chuyển hướng bác sĩ",
  draft: "Bản nháp",
};

export const NEED_LABELS: Record<string, string> = {
  kiem_soat_duong_huyet: "Kiểm soát đường huyết",
  giam_natri: "Giảm natri",
  han_che_purin: "Hạn chế purin",
  giam_can: "Kiểm soát cân nặng",
  duy_tri_can_bang: "Duy trì cân bằng",
};

export const RISK_REASON_LABELS: Record<string, string> = {
  RISK_PREG: "Đang mang thai",
  RISK_LACT: "Đang cho con bú",
  RISK_MINOR: "Chưa đủ 18 tuổi",
  RISK_CKD: "Bệnh thận mạn giai đoạn muộn (≥ 4) hoặc đang lọc máu",
  RISK_ED: "Có tiền sử rối loạn ăn uống",
  RISK_BMI_LOW: "Chỉ số BMI dưới ngưỡng an toàn",
  RISK_TEXT: "Ghi chú sức khỏe cần bác sĩ đánh giá trực tiếp",
  RISK_EMERGENCY: "Dấu hiệu cấp cứu y khoa cần hỗ trợ ngay",
};

export const GUARDRAIL_TYPE_LABELS: Record<string, string> = {
  validation: "Dữ liệu không hợp lệ",
  high_risk: "Nguy cơ cao lâm sàng",
  injection: "Can thiệp chỉ dẫn (Injection)",
  medical_advice: "Yêu cầu kê đơn / chẩn đoán",
  off_topic: "Nội dung lạc đề",
  forbidden_output: "Từ ngữ y khoa bị cấm",
  missing_citation: "Thiếu trích dẫn nguồn",
  allergen: "Cảnh báo dị nguyên",
  energy_floor: "Dưới sàn năng lượng",
  boundary_case: "Ca biên cần lưu ý",
  risk_emergency: "Cảnh báo cấp cứu (Chat)",
  food_drug_interaction: "Tương tác thực phẩm - thuốc",
  soft_boundary_topic: "Ngoài phạm vi 4 bệnh nền",
  output_sanitized: "Lọc đầu ra Chatbot",
};

export function formatCondition(code: string): string {
  const key = code.trim().toLowerCase() as ConditionCode;
  return CONDITION_LABELS[key] ?? code;
}

export function formatAllergen(code: string): string {
  const key = code.trim().toLowerCase() as AllergenCode;
  return ALLERGEN_LABELS[key] ?? code;
}

export function formatActivity(code: string): string {
  const key = code.trim().toLowerCase() as ActivityLevel;
  return ACTIVITY_LABELS[key] ?? code;
}

export function formatMeal(code: string): string {
  return MEAL_LABELS[code.trim().toLowerCase()] ?? code;
}

export function formatStatus(code: string): string {
  return STATUS_LABELS[code.trim().toLowerCase()] ?? code;
}

export function formatNeed(code: string): string {
  const trimmed = code.trim();
  if (trimmed.startsWith("tranh_di_ung:")) {
    const alg = trimmed.split(":", 2)[1] ?? "";
    return `Tránh dị ứng: ${formatAllergen(alg)}`;
  }
  return NEED_LABELS[trimmed] ?? trimmed;
}

export function formatRiskReason(code: string): string {
  return RISK_REASON_LABELS[code.trim()] ?? "Tình trạng sức khỏe cần tư vấn trực tiếp";
}

export function formatGuardrailType(code: string): string {
  return GUARDRAIL_TYPE_LABELS[code.trim().toLowerCase()] ?? code;
}

export function formatGuardrailLayer(layer: string): string {
  const norm = layer.trim().toLowerCase();
  if (norm === "input") return "Kiểm duyệt đầu vào";
  if (norm === "output") return "Kiểm duyệt đầu ra";
  return layer;
}

export const VIOLATION_CODE_LABELS: Record<string, string> = {
  UNKNOWN_FOOD: "Món ăn không hợp lệ",
  GRAMS_OUT_OF_RANGE: "Khối lượng ngoài khoảng cho phép",
  KCAL_OUT_OF_RANGE: "Năng lượng lệch mục tiêu",
  MACRO_OUT_OF_RANGE: "Đa lượng lệch mục tiêu",
  ALLERGEN: "Chứa chất gây dị ứng",
  SODIUM_OVER: "Vượt giới hạn Natri",
  SUGAR_OVER: "Vượt giới hạn Đường",
  FIBER_LOW: "Thiếu chất xơ",
  PURINE_HIGH: "Purin vượt ngưỡng",
  AVOID_TAG: "Nhóm món cần tránh",
  BELOW_FLOOR: "Dưới sàn năng lượng an toàn",
  DAY_COUNT: "Thiếu ngày hoặc bữa chính",
  DATA_MISSING: "Thiếu dữ liệu dinh dưỡng",
  PORTION_UNREALISTIC: "Định lượng món chưa thực tế",
  MEAL_IMBALANCE: "Mất cân đối năng lượng giữa các bữa",
  DAY_DUPLICATE: "Thực đơn các ngày bị lặp",
};

export function formatViolationCode(code: string): string {
  return VIOLATION_CODE_LABELS[code.trim().toUpperCase()] ?? code;
}

export function formatNumber(val: number | undefined | null, decimals = 1): string {
  if (val === undefined || val === null || Number.isNaN(val)) return "0";
  return Number(val).toLocaleString("vi-VN", {
    minimumFractionDigits: decimals === 0 ? 0 : 0,
    maximumFractionDigits: decimals,
  });
}

export function formatInt(val: number | undefined | null): string {
  if (val === undefined || val === null || Number.isNaN(val)) return "0";
  return Math.round(Number(val)).toLocaleString("vi-VN");
}

export function classifyBmi(bmi: number): { label: string; tone: "neutral" | "good" | "warn" | "danger" } {
  if (bmi < 18.5) return { label: "Thiếu cân", tone: "warn" };
  if (bmi < 23.0) return { label: "Bình thường (Chuẩn châu Á)", tone: "good" };
  if (bmi < 25.0) return { label: "Thừa cân", tone: "warn" };
  return { label: "Béo phì", tone: "danger" };
}

export function cleanDisclaimer(raw: string): string {
  return raw.replace(/^\*+|\*+$/g, "").trim();
}

export function detailToRunResponse(detail: MealPlanDetailResponse): MealPlanRunResponse {
  const mp = detail.meal_plan;
  return {
    status: mp.status,
    meal_plan_id: mp.id,
    thread_id: mp.thread_id,
    session_id: "",
    trace_id: "",
    retry_count: mp.retry_count,
    input_flags: detail.guardrail_events
      .filter((e) => e.layer === "input")
      .map((e) => e.type),
    output_flags: detail.guardrail_events
      .filter((e) => e.layer === "output")
      .map((e) => e.type),
    patient: detail.patient
      ? {
          patient_code: detail.patient.code,
          display_name: detail.patient.display_name,
          age: detail.patient.age,
          sex: detail.patient.sex,
          height_cm: detail.patient.height_cm,
          weight_kg: detail.patient.weight_kg,
          conditions: detail.patient.conditions,
          allergens: detail.patient.allergens,
          days: detail.patient.days,
          preferences_text: detail.patient.preferences_text,
        }
      : null,
    risk: detail.risk ?? null,
    targets: detail.targets && Object.keys(detail.targets).length > 0
      ? (detail.targets as MealPlanRunResponse["targets"])
      : null,
    needs: detail.needs && Object.keys(detail.needs).length > 0
      ? (detail.needs as MealPlanRunResponse["needs"])
      : null,
    items: detail.items,
    daily_totals: detail.daily_totals,
    violations: detail.violations ?? [],
    snippets: detail.snippets ?? [],
    explanation_md: mp.explanation_md ?? "",
    metrics: {},
    execution: {},
    trace_notes: [],
  };
}
