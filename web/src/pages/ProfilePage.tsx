import { useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  Activity,
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  CalendarDays,
  Check,
  Flame,
  HeartPulse,
  ShieldAlert,
  Sparkles,
  UserCheck,
} from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/layout/PageHeader";
import { AnalyzingCard } from "@/components/profile/AnalyzingCard";
import { AnimatedNumber } from "@/components/ui/animated-number";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, Textarea } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { SpotlightCard } from "@/components/ui/spotlight-card";
import { InfoTip } from "@/components/ui/tooltip";
import {
  ACTIVITY_LABELS,
  ALLERGEN_LABELS,
  CONDITION_DESCRIPTIONS,
  CONDITION_LABELS,
  classifyBmi,
  formatActivity,
  formatAllergen,
  formatCondition,
  formatInt,
  formatNumber,
} from "@/lib/format";
import { PAGE_TRANSITION } from "@/lib/motion";
import { cn } from "@/lib/utils";
import type {
  ActivityLevel,
  AllergenCode,
  ConditionCode,
  PatientProfileInput,
  SamplePatient,
} from "@/types/api";

interface ProfilePageProps {
  samples: SamplePatient[];
  isSubmitting: boolean;
  onSubmitProfile: (profile: PatientProfileInput) => Promise<void>;
}

const DEFAULT_PROFILE: PatientProfileInput = {
  patient_code: "BN-001",
  age: 48,
  sex: "female",
  height_cm: 160,
  weight_kg: 62,
  activity_level: "moderate",
  conditions: ["t2d"],
  allergens: [],
  pregnancy: false,
  lactating: false,
  ckd_stage: 0,
  dialysis: false,
  eating_disorder: false,
  preferences_text: "",
  days: 3,
};

const CONDITION_KEYS: ConditionCode[] = ["t2d", "htn", "gout", "obesity"];
const ALLERGEN_KEYS: AllergenCode[] = ["seafood", "peanut", "milk", "egg", "gluten", "soy"];
const ACTIVITY_KEYS: ActivityLevel[] = ["sedentary", "light", "moderate", "active", "very_active"];

const ACTIVITY_FACTORS: Record<ActivityLevel, number> = {
  sedentary: 1.2,
  light: 1.375,
  moderate: 1.55,
  active: 1.725,
  very_active: 1.9,
};

function BmiArcGauge({
  bmi,
  label,
}: {
  bmi: number;
  label: string;
}) {
  // Quy đổi BMI từ dải [14..34] sang góc 0..180 độ (bán nguyệt trên)
  const clamped = Math.max(14, Math.min(34, bmi));
  const ratio = (clamped - 14) / (34 - 14);
  const cx = 110;
  const cy = 104;
  const r = 80;
  const arcLen = Math.PI * r; // ~251.33
  const dashOffset = arcLen * (1 - ratio);

  // Tọa độ đầu kim trên cung tròn từ 180° (trái) -> 0° (phải)
  const angleRad = Math.PI * (1 - ratio);
  const dotX = cx + r * Math.cos(angleRad);
  const dotY = cy - r * Math.sin(angleRad);

  const zone =
    bmi < 18.5
      ? { stroke: "#38BDF8", glow: "rgba(56,189,248,0.65)", pill: "border-[#38BDF8]/40 bg-[#38BDF8]/18 text-[#E0F2FE]" }
      : bmi < 23
        ? { stroke: "#34D399", glow: "rgba(52,211,153,0.7)", pill: "border-[#34D399]/40 bg-[#34D399]/18 text-[#D1FAE5]" }
        : bmi < 25
          ? { stroke: "#FBBF24", glow: "rgba(251,191,36,0.65)", pill: "border-[#FBBF24]/40 bg-[#FBBF24]/18 text-[#FEF3C7]" }
          : { stroke: "#FB7185", glow: "rgba(251,113,133,0.7)", pill: "border-[#FB7185]/45 bg-[#FB7185]/20 text-[#FFE4E6]" };

  const arcPath = `M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`;

  return (
    <div className="flex flex-col items-center">
      <div className="relative w-full max-w-[228px]">
        <svg viewBox="0 0 220 120" className="w-full overflow-visible" role="img" aria-label={`Biểu đồ bán nguyệt BMI ${formatNumber(bmi, 1)}`}>
          <defs>
            <linearGradient id="bmiZonesTrack" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#38BDF8" stopOpacity="0.38" />
              <stop offset="28%" stopColor="#34D399" stopOpacity="0.45" />
              <stop offset="56%" stopColor="#FBBF24" stopOpacity="0.45" />
              <stop offset="100%" stopColor="#FB7185" stopOpacity="0.48" />
            </linearGradient>
          </defs>
          {/* Base zone track */}
          <path
            d={arcPath}
            fill="none"
            stroke="url(#bmiZonesTrack)"
            strokeWidth="12"
            strokeLinecap="round"
          />
          {/* Active progress arc */}
          <path
            d={arcPath}
            fill="none"
            stroke={zone.stroke}
            strokeWidth="12"
            strokeLinecap="round"
            strokeDasharray={arcLen}
            strokeDashoffset={dashOffset}
            style={{
              transition: "stroke-dashoffset 320ms cubic-bezier(0.22, 1, 0.36, 1), stroke 240ms ease",
              filter: `drop-shadow(0 0 8px ${zone.glow})`,
            }}
          />
          {/* Glowing indicator dot */}
          <circle
            cx={dotX}
            cy={dotY}
            r="7"
            fill="#FFFFFF"
            stroke={zone.stroke}
            strokeWidth="3.5"
            style={{
              transition: "cx 320ms cubic-bezier(0.22, 1, 0.36, 1), cy 320ms cubic-bezier(0.22, 1, 0.36, 1), stroke 240ms ease",
              filter: `drop-shadow(0 0 10px ${zone.glow})`,
            }}
          />
        </svg>

        {/* Center Readout */}
        <div className="pointer-events-none absolute inset-x-0 bottom-1 flex flex-col items-center text-center">
          <span className="text-[10px] font-bold uppercase tracking-[0.14em] text-[#99F6E4]/80">
            BMI ước tính
          </span>
          <span className="mt-0.5 font-mono text-3xl font-extrabold leading-none text-white tabular-nums">
            <AnimatedNumber value={bmi} formatter={(v) => formatNumber(v, 1)} />
          </span>
        </div>
      </div>

      <span
        className={cn(
          "mt-1.5 inline-flex items-center rounded-full border px-2.5 py-0.5 text-[11px] font-semibold transition-colors",
          zone.pill
        )}
      >
        {label}
      </span>

      <div className="mt-2 flex w-full justify-between px-1 font-mono text-[10px] text-[#99F6E4]/70">
        <span>&lt;18.5</span>
        <span>18.5–22.9</span>
        <span>23–24.9</span>
        <span>≥25</span>
      </div>
    </div>
  );
}

export function ProfilePage({ samples, isSubmitting, onSubmitProfile }: ProfilePageProps) {
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [stepDir, setStepDir] = useState<1 | -1>(1);
  const [selectedSampleCode, setSelectedSampleCode] = useState<string>("custom");
  const [form, setForm] = useState<PatientProfileInput>(DEFAULT_PROFILE);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const goStep = (next: 1 | 2 | 3) => {
    setStepDir(next >= step ? 1 : -1);
    setStep(next);
  };

  // Chọn 4 hồ sơ mẫu đại diện từ dữ liệu thật kèm icon & màu ngữ nghĩa
  const quickSamples = useMemo(() => {
    if (!samples.length) return [];
    const pickT2d = samples.find(
      (s) =>
        s.conditions.includes("t2d") &&
        s.conditions.length === 1 &&
        !s.pregnancy &&
        !s.lactating &&
        s.ckd_stage < 4 &&
        s.age >= 18
    );
    const pickMulti = samples.find(
      (s) =>
        s.conditions.length >= 2 &&
        s.allergens.length >= 1 &&
        !s.pregnancy &&
        s.ckd_stage < 4 &&
        s.age >= 18
    );
    const pickGout = samples.find(
      (s) => s.conditions.includes("gout") && !s.pregnancy && s.ckd_stage < 4 && s.age >= 18
    );
    const pickHighRisk = samples.find(
      (s) => s.ckd_stage >= 4 || s.pregnancy || s.dialysis || s.eating_disorder
    );

    const out: Array<{
      tag: string;
      sample: SamplePatient;
      icon: typeof Activity;
      tone: string;
    }> = [];
    if (pickT2d)
      out.push({ tag: "Đái tháo đường T2", sample: pickT2d, icon: Activity, tone: "text-[#0D9488]" });
    if (pickMulti)
      out.push({
        tag: "Đa bệnh + Dị ứng",
        sample: pickMulti,
        icon: HeartPulse,
        tone: "text-[#0284C7]",
      });
    if (pickGout)
      out.push({ tag: "Bệnh Gout", sample: pickGout, icon: Flame, tone: "text-[#D97706]" });
    if (pickHighRisk)
      out.push({
        tag: "Ca nguy cơ cao",
        sample: pickHighRisk,
        icon: ShieldAlert,
        tone: "text-[#E11D48]",
      });
    return out;
  }, [samples]);

  const applySample = (patientCode: string) => {
    setSelectedSampleCode(patientCode);
    if (patientCode === "custom") {
      setForm(DEFAULT_PROFILE);
      setErrors({});
      goStep(1);
      return;
    }
    const found = samples.find((s) => s.patient_code === patientCode);
    if (!found) return;
    setForm({
      patient_code: found.patient_code,
      age: found.age,
      sex: found.sex,
      height_cm: found.height_cm,
      weight_kg: found.weight_kg,
      activity_level: found.activity_level,
      conditions: [...found.conditions],
      allergens: [...found.allergens],
      pregnancy: found.sex === "male" ? false : found.pregnancy,
      lactating: found.sex === "male" ? false : found.lactating,
      ckd_stage: found.ckd_stage,
      dialysis: found.dialysis,
      eating_disorder: found.eating_disorder,
      preferences_text: found.preferences_text ?? "",
      days: found.days ?? 3,
    });
    setErrors({});
    goStep(1);
    toast.success(`Đã nạp hồ sơ mẫu ${found.patient_code}`);
  };

  const validateStep1 = (): boolean => {
    const nextErr: Record<string, string> = {};
    if (!form.patient_code.trim()) {
      nextErr.patient_code = "Vui lòng nhập mã hồ sơ.";
    }
    if (!Number.isFinite(form.age) || form.age < 1 || form.age > 120) {
      nextErr.age = "Tuổi phải nằm trong khoảng 1–120.";
    }
    if (!Number.isFinite(form.height_cm) || form.height_cm < 50 || form.height_cm > 250) {
      nextErr.height_cm = "Chiều cao phải nằm trong khoảng 50–250 cm.";
    }
    if (!Number.isFinite(form.weight_kg) || form.weight_kg < 2 || form.weight_kg > 400) {
      nextErr.weight_kg = "Cân nặng phải nằm trong khoảng 2–400 kg.";
    }
    setErrors(nextErr);
    return Object.keys(nextErr).length === 0;
  };

  const toggleCondition = (code: ConditionCode) => {
    setForm((prev) => ({
      ...prev,
      conditions: prev.conditions.includes(code)
        ? prev.conditions.filter((c) => c !== code)
        : [...prev.conditions, code],
    }));
  };

  const toggleAllergen = (code: AllergenCode) => {
    setForm((prev) => ({
      ...prev,
      allergens: prev.allergens.includes(code)
        ? prev.allergens.filter((a) => a !== code)
        : [...prev.allergens, code],
    }));
  };

  const handleFinalSubmit = async () => {
    if (!validateStep1()) {
      goStep(1);
      toast.error("Vui lòng kiểm tra lại các chỉ số thể trạng ở Bước 1.");
      return;
    }
    await onSubmitProfile({
      ...form,
      patient_code: form.patient_code.trim() || "BN-001",
      preferences_text: form.preferences_text.trim(),
    });
  };

  const riskSummaryList = useMemo(() => {
    const list: string[] = [];
    if (form.pregnancy) list.push("Đang mang thai");
    if (form.lactating) list.push("Đang cho con bú");
    if (form.ckd_stage > 0) list.push(`Bệnh thận mạn giai đoạn ${form.ckd_stage}`);
    if (form.dialysis) list.push("Đang lọc máu");
    if (form.eating_disorder) list.push("Rối loạn ăn uống");
    return list;
  }, [form]);

  // Ước tính nhanh BMI, BMR & TDEE (Mifflin-St Jeor) trực quan khi gõ — máy chủ sẽ tính chuẩn khi phân tích
  const liveMetrics = useMemo(() => {
    if (
      !Number.isFinite(form.height_cm) ||
      !Number.isFinite(form.weight_kg) ||
      form.height_cm < 50 ||
      form.weight_kg < 2
    ) {
      return null;
    }
    const m = form.height_cm / 100;
    const bmi = form.weight_kg / (m * m);
    if (!Number.isFinite(bmi)) return null;
    const info = classifyBmi(bmi);

    const validAge = Number.isFinite(form.age) && form.age >= 1 && form.age <= 120;
    const baseBmr = validAge
      ? 10 * form.weight_kg + 6.25 * form.height_cm - 5 * form.age + (form.sex === "male" ? 5 : -161)
      : null;
    const bmr = baseBmr !== null && baseBmr > 0 ? Math.round(baseBmr) : null;
    const factor = ACTIVITY_FACTORS[form.activity_level] ?? 1.2;
    const tdee = bmr !== null ? Math.round(bmr * factor) : null;

    return { bmi, info, bmr, tdee };
  }, [form.height_cm, form.weight_kg, form.age, form.sex, form.activity_level]);

  return (
    <div>
      <PageHeader
        eyebrow="HỒ SƠ SỨC KHỎE · BƯỚC 1–3"
        title="Khảo sát hồ sơ dinh dưỡng lâm sàng"
        description="Nhập thông tin thể trạng, bệnh lý nền và dị ứng thực phẩm để hệ thống tính toán mục tiêu và xây dựng thực đơn an toàn."
      />

      {/* Quick Sample Bar with Luminous Chips */}
      <Card className="mb-5">
        <CardContent className="p-4">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide text-[#0B4F4A] mr-1">
                <Sparkles className="h-3.5 w-3.5 text-[#14B8A6]" />
                Thử nhanh hồ sơ mẫu:
              </span>
              {quickSamples.map(({ tag, sample, icon: SIcon, tone }) => {
                const active = selectedSampleCode === sample.patient_code;
                return (
                  <button
                    key={sample.patient_code}
                    type="button"
                    disabled={isSubmitting}
                    onClick={() => applySample(sample.patient_code)}
                    className={cn(
                      "inline-flex items-center gap-1.5 rounded-xl border px-3 py-1.5 text-xs font-semibold transition-all duration-150 cursor-pointer active:scale-[0.98] disabled:opacity-50",
                      active
                        ? "border-transparent bg-gradient-to-r from-[#0D9488] via-[#0EA5A8] to-[#06B6D4] text-white shadow-[0_6px_16px_rgba(6,182,212,0.3)]"
                        : "border-[#CBE4DC] bg-white/85 text-[#334155] hover:-translate-y-[1px] hover:border-[#06B6D4] hover:bg-[#ECFEFF] hover:text-[#0B4F4A] hover:shadow-[0_4px_14px_rgba(6,182,212,0.14)]"
                    )}
                  >
                    <SIcon className={cn("h-3.5 w-3.5 shrink-0", active ? "text-white" : tone)} />
                    <span>{tag}</span>
                    <span
                      className={cn(
                        "font-mono text-[10px]",
                        active ? "text-white/85" : "text-[#64748B]"
                      )}
                    >
                      {sample.patient_code}
                    </span>
                  </button>
                );
              })}
            </div>

            <div className="w-full lg:w-[310px] shrink-0">
              <Select
                value={selectedSampleCode}
                onValueChange={applySample}
                disabled={isSubmitting}
              >
                <SelectTrigger aria-label="Chọn từ 30 hồ sơ bệnh nhân mẫu" className="bg-white/90">
                  <SelectValue placeholder="Chọn từ 30 hồ sơ mẫu..." />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="custom">-- Tự nhập hồ sơ mới --</SelectItem>
                  {samples.map((p) => {
                    const condLabel =
                      p.conditions.length > 0
                        ? p.conditions.map(formatCondition).join(", ")
                        : "Không bệnh nền";
                    return (
                      <SelectItem key={p.patient_code} value={p.patient_code}>
                        {p.patient_code} · {p.display_name} ({condLabel})
                      </SelectItem>
                    );
                  })}
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>

      {isSubmitting ? (
        <AnalyzingCard patientCode={form.patient_code || "BN-001"} />
      ) : (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
          {/* Left: 3-Step Form */}
          <div className="lg:col-span-8 space-y-5">
            {/* Connected Stepper Header */}
            <div className="space-y-2.5">
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-[#D7ECE6]">
                <motion.div
                  className="h-full rounded-full bg-gradient-to-r from-[#0D9488] via-[#0EA5A8] to-[#06B6D4] shadow-[0_0_12px_rgba(6,182,212,0.5)]"
                  initial={false}
                  animate={{ width: `${(step / 3) * 100}%` }}
                  transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
                />
              </div>

              <div className="grid grid-cols-3 gap-2 sm:gap-3">
                {[
                  { id: 1 as const, label: "Thể trạng" },
                  { id: 2 as const, label: "Bệnh lý & Dị ứng" },
                  { id: 3 as const, label: "Kế hoạch & Xác nhận" },
                ].map((item) => {
                  const isDone = step > item.id;
                  const isCurrent = step === item.id;
                  return (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => {
                        if (item.id > 1 && !validateStep1()) return;
                        goStep(item.id);
                      }}
                      className={cn(
                        "flex items-center gap-2.5 rounded-xl border px-3 py-2.5 text-left transition-all cursor-pointer active:scale-[0.99]",
                        isCurrent
                          ? "border-transparent bg-gradient-to-r from-[#0D9488] via-[#0EA5A8] to-[#06B6D4] text-white shadow-[0_6px_18px_rgba(6,182,212,0.3)]"
                          : isDone
                            ? "border-[#A7F3D0] bg-[#ECFDF5]/90 text-[#065F46] hover:border-[#34D399]"
                            : "border-white/80 bg-white/75 backdrop-blur-md text-[#64748B] hover:border-[#5EEAD4] hover:text-[#0B4F4A]"
                      )}
                    >
                      <span
                        className={cn(
                          "flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold transition-colors",
                          isCurrent
                            ? "bg-white text-[#0B4F4A]"
                            : isDone
                              ? "bg-[#059669] text-white"
                              : "bg-[#EFF6F3] text-[#64748B]"
                        )}
                      >
                        {isDone ? <Check className="h-3.5 w-3.5" /> : item.id}
                      </span>
                      <span className="truncate text-xs sm:text-sm font-semibold">{item.label}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            <AnimatePresence mode="wait" initial={false}>
              {step === 1 && (
                <motion.div
                  key="step-1"
                  initial={{ opacity: 0, x: stepDir * 12 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: stepDir * -12 }}
                  transition={PAGE_TRANSITION}
                >
                  <Card>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2">
                        <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-[#0D9488] to-[#14B8A6] text-white shadow-2xs">
                          <UserCheck className="h-4 w-4" />
                        </span>
                        Bước 1 · Thông tin cá nhân & Chỉ số thể trạng
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-5">
                      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                        <div className="space-y-1.5">
                          <Label htmlFor="patient_code">Mã hồ sơ (ẩn danh)</Label>
                          <Input
                            id="patient_code"
                            value={form.patient_code}
                            onChange={(e) => setForm({ ...form, patient_code: e.target.value })}
                            placeholder="Ví dụ: BN-001"
                          />
                          {errors.patient_code && (
                            <p className="text-xs font-medium text-[#DC2626]">{errors.patient_code}</p>
                          )}
                        </div>

                        <div className="space-y-1.5">
                          <Label>Giới tính sinh học</Label>
                          <div className="grid grid-cols-2 gap-2">
                            {(
                              [
                                { value: "male", label: "Nam" },
                                { value: "female", label: "Nữ" },
                              ] as const
                            ).map((opt) => (
                              <button
                                key={opt.value}
                                type="button"
                                onClick={() =>
                                  setForm((prev) => ({
                                    ...prev,
                                    sex: opt.value,
                                    pregnancy: opt.value === "male" ? false : prev.pregnancy,
                                    lactating: opt.value === "male" ? false : prev.lactating,
                                  }))
                                }
                                className={cn(
                                  "h-10 rounded-xl border text-sm font-semibold transition-all cursor-pointer active:scale-[0.985]",
                                  form.sex === opt.value
                                    ? "border-transparent bg-gradient-to-r from-[#0D9488] to-[#06B6D4] text-white shadow-[0_4px_14px_rgba(6,182,212,0.28)]"
                                    : "border-[#CFE3DC] bg-white/85 text-[#334155] hover:border-[#0D9488]/60 hover:bg-[#ECFEFF]"
                                )}
                              >
                                {opt.label}
                              </button>
                            ))}
                          </div>
                        </div>
                      </div>

                      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                        <div className="space-y-1.5">
                          <Label htmlFor="age">Tuổi (1–120)</Label>
                          <Input
                            id="age"
                            type="number"
                            min={1}
                            max={120}
                            value={Number.isNaN(form.age) ? "" : form.age}
                            onChange={(e) => setForm({ ...form, age: Number(e.target.value) })}
                            className="font-mono tabular-nums"
                          />
                          {errors.age && (
                            <p className="text-xs font-medium text-[#DC2626]">{errors.age}</p>
                          )}
                        </div>

                        <div className="space-y-1.5">
                          <Label htmlFor="height_cm">Chiều cao (cm)</Label>
                          <Input
                            id="height_cm"
                            type="number"
                            min={50}
                            max={250}
                            step={0.5}
                            value={Number.isNaN(form.height_cm) ? "" : form.height_cm}
                            onChange={(e) => setForm({ ...form, height_cm: Number(e.target.value) })}
                            className="font-mono tabular-nums"
                          />
                          {errors.height_cm && (
                            <p className="text-xs font-medium text-[#DC2626]">{errors.height_cm}</p>
                          )}
                        </div>

                        <div className="space-y-1.5">
                          <Label htmlFor="weight_kg">Cân nặng (kg)</Label>
                          <Input
                            id="weight_kg"
                            type="number"
                            min={2}
                            max={400}
                            step={0.5}
                            value={Number.isNaN(form.weight_kg) ? "" : form.weight_kg}
                            onChange={(e) => setForm({ ...form, weight_kg: Number(e.target.value) })}
                            className="font-mono tabular-nums"
                          />
                          {errors.weight_kg && (
                            <p className="text-xs font-medium text-[#DC2626]">{errors.weight_kg}</p>
                          )}
                        </div>
                      </div>

                      <div className="space-y-2">
                        <Label>Mức độ vận động hàng ngày</Label>
                        <Select
                          value={form.activity_level}
                          onValueChange={(v) =>
                            setForm({ ...form, activity_level: v as ActivityLevel })
                          }
                        >
                          <SelectTrigger aria-label="Mức độ vận động">
                            <SelectValue>{ACTIVITY_LABELS[form.activity_level]}</SelectValue>
                          </SelectTrigger>
                          <SelectContent>
                            {ACTIVITY_KEYS.map((lvl) => (
                              <SelectItem key={lvl} value={lvl}>
                                {ACTIVITY_LABELS[lvl]}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>

                      <div className="flex justify-end pt-2">
                        <Button
                          type="button"
                          size="lg"
                          onClick={() => {
                            if (validateStep1()) goStep(2);
                          }}
                        >
                          Tiếp tục: Bệnh lý & Dị ứng
                          <ArrowRight className="h-4 w-4" />
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                </motion.div>
              )}

              {step === 2 && (
                <motion.div
                  key="step-2"
                  initial={{ opacity: 0, x: stepDir * 12 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: stepDir * -12 }}
                  transition={PAGE_TRANSITION}
                  className="space-y-5"
                >
                  <Card>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2">
                        <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-[#0D9488] to-[#14B8A6] text-white shadow-2xs">
                          <HeartPulse className="h-4 w-4" />
                        </span>
                        Bước 2 · Bệnh lý nền & Dị ứng thực phẩm
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-5">
                      <div>
                        <Label className="mb-2.5 block">
                          Nhóm bệnh lý cần hỗ trợ dinh dưỡng (có thể chọn nhiều)
                        </Label>
                        <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
                          {CONDITION_KEYS.map((code) => {
                            const selected = form.conditions.includes(code);
                            return (
                              <SpotlightCard
                                key={code}
                                className={cn(
                                  "rounded-xl border transition-all",
                                  selected
                                    ? "border-[#0D9488] bg-gradient-to-br from-[#F0FDFA] to-[#CCFBF1]/60 shadow-[0_6px_18px_rgba(13,148,136,0.16)]"
                                    : "border-[#CFE3DC] bg-white/85 hover:border-[#5EEAD4]"
                                )}
                              >
                                <button
                                  type="button"
                                  onClick={() => toggleCondition(code)}
                                  className="flex h-full w-full items-start justify-between gap-3 p-3.5 text-left cursor-pointer active:scale-[0.99]"
                                >
                                  <div>
                                    <p className="text-sm font-bold text-[#0F172A]">
                                      {CONDITION_LABELS[code]}
                                    </p>
                                    <p className="mt-0.5 text-xs text-[#475569]">
                                      {CONDITION_DESCRIPTIONS[code]}
                                    </p>
                                  </div>
                                  <span
                                    className={cn(
                                      "mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-md border transition-colors",
                                      selected
                                        ? "border-transparent bg-gradient-to-br from-[#0D9488] to-[#06B6D4] text-white shadow-[0_2px_8px_rgba(6,182,212,0.35)]"
                                        : "border-[#CBD5E1] bg-white"
                                    )}
                                  >
                                    {selected && <Check className="h-3.5 w-3.5" />}
                                  </span>
                                </button>
                              </SpotlightCard>
                            );
                          })}
                        </div>
                      </div>

                      <div>
                        <Label className="mb-2.5 block">
                          Dị ứng thực phẩm (loại trừ tuyệt đối khỏi thực đơn)
                        </Label>
                        <div className="flex flex-wrap gap-2">
                          {ALLERGEN_KEYS.map((alg) => {
                            const selected = form.allergens.includes(alg);
                            return (
                              <button
                                key={alg}
                                type="button"
                                onClick={() => toggleAllergen(alg)}
                                className={cn(
                                  "inline-flex items-center gap-1.5 rounded-full border px-3.5 py-1.5 text-xs font-semibold transition-all cursor-pointer active:scale-[0.98]",
                                  selected
                                    ? "border-[#E11D48] bg-[#FFF1F2] text-[#BE123C] shadow-2xs"
                                    : "border-[#D5E2DC] bg-white/90 text-[#334155] hover:border-[#0D9488] hover:bg-[#F0FDFA]"
                                )}
                              >
                                {selected && <Check className="h-3.5 w-3.5" />}
                                {ALLERGEN_LABELS[alg]}
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    </CardContent>
                  </Card>

                  {/* High Risk Screening Card */}
                  <Card className="border-[#FDE68A] bg-gradient-to-br from-[#FFFDF7]/95 to-[#FEF3C7]/45">
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2 text-[#92400E]">
                        <AlertTriangle className="h-4.5 w-4.5 text-[#D97706]" />
                        Sàng lọc tình trạng nguy cơ cao
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <p className="text-xs text-[#78350F]">
                        Vì an toàn y tế, các trường hợp mang thai, cho con bú, dưới 18 tuổi, suy thận giai đoạn muộn (≥ 4) hoặc rối loạn ăn uống sẽ được khuyến nghị thăm khám trực tiếp bác sĩ thay vì tự động sinh thực đơn.
                      </p>

                      <div className="flex flex-wrap gap-2.5">
                        {form.sex === "female" && (
                          <>
                            <button
                              type="button"
                              onClick={() => setForm({ ...form, pregnancy: !form.pregnancy })}
                              className={cn(
                                "inline-flex items-center gap-2 rounded-xl border px-3.5 py-2 text-xs font-semibold transition-all cursor-pointer active:scale-[0.98]",
                                form.pregnancy
                                  ? "border-[#D97706] bg-[#FEF3C7] text-[#92400E]"
                                  : "border-[#E4ECE8] bg-white/90 text-[#334155] hover:border-[#D97706]/50"
                              )}
                            >
                              {form.pregnancy && <Check className="h-3.5 w-3.5" />}
                              Đang mang thai
                            </button>
                            <button
                              type="button"
                              onClick={() => setForm({ ...form, lactating: !form.lactating })}
                              className={cn(
                                "inline-flex items-center gap-2 rounded-xl border px-3.5 py-2 text-xs font-semibold transition-all cursor-pointer active:scale-[0.98]",
                                form.lactating
                                  ? "border-[#D97706] bg-[#FEF3C7] text-[#92400E]"
                                  : "border-[#E4ECE8] bg-white/90 text-[#334155] hover:border-[#D97706]/50"
                              )}
                            >
                              {form.lactating && <Check className="h-3.5 w-3.5" />}
                              Đang cho con bú
                            </button>
                          </>
                        )}

                        <button
                          type="button"
                          onClick={() => setForm({ ...form, dialysis: !form.dialysis })}
                          className={cn(
                            "inline-flex items-center gap-2 rounded-xl border px-3.5 py-2 text-xs font-semibold transition-all cursor-pointer active:scale-[0.98]",
                            form.dialysis
                              ? "border-[#D97706] bg-[#FEF3C7] text-[#92400E]"
                              : "border-[#E4ECE8] bg-white/90 text-[#334155] hover:border-[#D97706]/50"
                          )}
                        >
                          {form.dialysis && <Check className="h-3.5 w-3.5" />}
                          Đang chạy thận nhân tạo
                        </button>

                        <button
                          type="button"
                          onClick={() =>
                            setForm({ ...form, eating_disorder: !form.eating_disorder })
                          }
                          className={cn(
                            "inline-flex items-center gap-2 rounded-xl border px-3.5 py-2 text-xs font-semibold transition-all cursor-pointer active:scale-[0.98]",
                            form.eating_disorder
                              ? "border-[#D97706] bg-[#FEF3C7] text-[#92400E]"
                              : "border-[#E4ECE8] bg-white/90 text-[#334155] hover:border-[#D97706]/50"
                          )}
                        >
                          {form.eating_disorder && <Check className="h-3.5 w-3.5" />}
                          Tiền sử rối loạn ăn uống
                        </button>
                      </div>

                      <div className="space-y-1.5">
                        <Label>Giai đoạn bệnh thận mạn (CKD 0–5)</Label>
                        <div className="flex flex-wrap gap-2">
                          {[0, 1, 2, 3, 4, 5].map((stage) => (
                            <button
                              key={stage}
                              type="button"
                              onClick={() => setForm({ ...form, ckd_stage: stage })}
                              className={cn(
                                "h-9 min-w-[52px] rounded-xl border px-3 font-mono text-xs font-bold transition-all cursor-pointer active:scale-[0.98]",
                                form.ckd_stage === stage
                                  ? stage >= 4
                                    ? "border-[#DC2626] bg-[#FEE2E2] text-[#991B1B]"
                                    : "border-transparent bg-gradient-to-r from-[#0B4F4A] to-[#0D9488] text-white"
                                  : "border-[#E4ECE8] bg-white/90 text-[#475569] hover:bg-[#F8FAF9]"
                              )}
                            >
                              {stage === 0 ? "Không" : `Độ ${stage}`}
                            </button>
                          ))}
                        </div>
                      </div>
                    </CardContent>
                  </Card>

                  <div className="flex items-center justify-between gap-3">
                    <Button type="button" variant="outline" onClick={() => goStep(1)}>
                      <ArrowLeft className="h-4 w-4" />
                      Quay lại
                    </Button>
                    <Button type="button" size="lg" onClick={() => goStep(3)}>
                      Tiếp tục: Kế hoạch & Xác nhận
                      <ArrowRight className="h-4 w-4" />
                    </Button>
                  </div>
                </motion.div>
              )}

              {step === 3 && (
                <motion.div
                  key="step-3"
                  initial={{ opacity: 0, x: stepDir * 12 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: stepDir * -12 }}
                  transition={PAGE_TRANSITION}
                >
                  <Card>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2">
                        <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-[#0D9488] to-[#14B8A6] text-white shadow-2xs">
                          <CalendarDays className="h-4 w-4" />
                        </span>
                        Bước 3 · Số ngày thực đơn & Sở thích ăn uống
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-5">
                      <div className="space-y-2">
                        <Label>Số ngày thực đơn cần lập (1–7 ngày)</Label>
                        <div className="grid grid-cols-7 gap-2">
                          {[1, 2, 3, 4, 5, 6, 7].map((d) => (
                            <button
                              key={d}
                              type="button"
                              onClick={() => setForm({ ...form, days: d })}
                              className={cn(
                                "h-10 rounded-xl border font-mono text-sm font-bold transition-all cursor-pointer active:scale-[0.97]",
                                form.days === d
                                  ? "border-transparent bg-gradient-to-r from-[#0D9488] to-[#06B6D4] text-white shadow-[0_4px_14px_rgba(6,182,212,0.3)]"
                                  : "border-[#CFE3DC] bg-white/85 text-[#334155] hover:border-[#06B6D4] hover:bg-[#ECFEFF]"
                              )}
                            >
                              {d}
                            </button>
                          ))}
                        </div>
                      </div>

                      <div className="space-y-1.5">
                        <div className="flex items-center justify-between">
                          <Label htmlFor="preferences_text">Sở thích / Thói quen ăn uống (tùy chọn)</Label>
                          <span
                            className={cn(
                              "font-mono text-xs tabular-nums",
                              form.preferences_text.length > 420
                                ? "font-bold text-[#D97706]"
                                : "text-[#64748B]"
                            )}
                          >
                            {form.preferences_text.length} / 500
                          </span>
                        </div>
                        <Textarea
                          id="preferences_text"
                          maxLength={500}
                          value={form.preferences_text}
                          onChange={(e) => setForm({ ...form, preferences_text: e.target.value })}
                          placeholder="Ví dụ: Thích ăn cá hấp, rau luộc, ăn nhạt, không ăn món chiên rán..."
                        />
                        <div className="h-1 w-full overflow-hidden rounded-full bg-[#EDF2EF]">
                          <div
                            className={cn(
                              "h-full rounded-full transition-all duration-200",
                              form.preferences_text.length > 420 ? "bg-[#D97706]" : "bg-[#14B8A6]"
                            )}
                            style={{ width: `${Math.min(100, (form.preferences_text.length / 500) * 100)}%` }}
                          />
                        </div>
                      </div>

                      <div className="flex items-center justify-between gap-3 pt-2">
                        <Button type="button" variant="outline" onClick={() => goStep(2)}>
                          <ArrowLeft className="h-4 w-4" />
                          Quay lại
                        </Button>
                        <Button
                          type="button"
                          size="lg"
                          disabled={isSubmitting}
                          onClick={handleFinalSubmit}
                        >
                          Tạo thực đơn
                          <ArrowRight className="h-4 w-4" />
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* Right: Live Biometric Dark-Emerald Signature Card */}
          <div className="lg:col-span-4">
            <SpotlightCard
              tone="dark"
              className="dark-emerald-card sticky top-24 rounded-2xl text-white"
            >
              {/* Top 3px Aurora Accent */}
              <div className="h-[3px] w-full bg-gradient-to-r from-[#2DD4BF] via-[#22D3EE] to-[#34D399]" />

              <div className="flex items-center justify-between border-b border-white/14 px-5 py-3.5">
                <div>
                  <span className="block text-[10px] font-bold uppercase tracking-[0.14em] text-[#5EEAD4]">
                    Live Biometrics
                  </span>
                  <h3 className="text-sm font-extrabold text-white">Hồ sơ gửi phân tích</h3>
                </div>
                <span className="rounded-full border border-[#5EEAD4]/40 bg-white/12 px-2.5 py-0.5 font-mono text-xs font-bold text-[#CCFBF1] shadow-2xs">
                  {form.patient_code || "BN-001"}
                </span>
              </div>

              <div className="space-y-3.5 p-4 sm:p-5 text-sm">
                {/* Semicircular BMI Arc Gauge + Live BMR/TDEE */}
                {liveMetrics && (
                  <div className="rounded-2xl border border-white/14 bg-[#031F1E]/55 p-3.5 backdrop-blur-md space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="inline-flex items-center gap-1 text-[10.5px] font-bold uppercase tracking-wider text-[#99F6E4]/85">
                        Chỉ số khối cơ thể
                        <InfoTip
                          text="Chỉ số khối cơ thể = cân nặng / (chiều cao m)². Phân loại theo ngưỡng chuẩn châu Á (IDI & WPRO)."
                          className="text-[#99F6E4]/80 hover:bg-white/15 hover:text-white"
                        />
                      </span>
                      <span className="font-mono text-[11px] font-semibold text-[#CCFBF1]/85 tabular-nums">
                        {form.height_cm} cm · {form.weight_kg} kg
                      </span>
                    </div>

                    <BmiArcGauge bmi={liveMetrics.bmi} label={liveMetrics.info.label} />

                    {liveMetrics.bmr !== null && liveMetrics.tdee !== null && (
                      <div className="grid grid-cols-2 gap-2 pt-1">
                        <div className="rounded-xl border border-white/12 bg-white/[0.07] px-3 py-2">
                          <span className="block text-[10px] font-semibold uppercase tracking-wide text-[#99F6E4]/80">
                            BMR sơ bộ
                          </span>
                          <p className="mt-0.5 font-mono text-base font-extrabold text-white tabular-nums">
                            <AnimatedNumber value={liveMetrics.bmr} formatter={formatInt} />{" "}
                            <span className="text-[10.5px] font-medium text-[#CCFBF1]/75">kcal</span>
                          </p>
                        </div>
                        <div className="rounded-xl border border-white/12 bg-white/[0.07] px-3 py-2">
                          <span className="block text-[10px] font-semibold uppercase tracking-wide text-[#99F6E4]/80">
                            TDEE sơ bộ
                          </span>
                          <p className="mt-0.5 font-mono text-base font-extrabold text-[#5EEAD4] tabular-nums">
                            <AnimatedNumber value={liveMetrics.tdee} formatter={formatInt} />{" "}
                            <span className="text-[10.5px] font-medium text-[#CCFBF1]/75">kcal</span>
                          </p>
                        </div>
                      </div>
                    )}

                    <p className="text-[10.5px] leading-snug text-[#CCFBF1]/70">
                      * Ước tính nhanh (Mifflin-St Jeor), máy chủ tính chuẩn theo quy tắc lâm sàng khi phân tích.
                    </p>
                  </div>
                )}

                {/* Compact Demographics Strip */}
                <div className="grid grid-cols-2 gap-2 rounded-xl border border-white/12 bg-white/[0.06] p-3 text-xs">
                  <div>
                    <span className="text-[10px] font-semibold uppercase text-[#99F6E4]/75">
                      Tuổi / Giới
                    </span>
                    <p className="mt-0.5 font-semibold text-white tabular-nums">
                      {form.age} tuổi · {form.sex === "male" ? "Nam" : "Nữ"}
                    </p>
                  </div>
                  <div>
                    <span className="text-[10px] font-semibold uppercase text-[#99F6E4]/75">
                      Số ngày lập
                    </span>
                    <p className="mt-0.5 font-mono font-bold text-[#5EEAD4] tabular-nums">
                      {form.days} ngày
                    </p>
                  </div>
                  <div className="col-span-2 border-t border-white/10 pt-2">
                    <span className="text-[10px] font-semibold uppercase text-[#99F6E4]/75">
                      Mức vận động
                    </span>
                    <p className="mt-0.5 text-[11.5px] font-medium text-[#E2FAF5]">
                      {formatActivity(form.activity_level)}
                    </p>
                  </div>
                </div>

                {/* Conditions / Allergens / Risks */}
                <div className="space-y-2.5 text-xs">
                  <div>
                    <span className="text-[10px] font-semibold uppercase tracking-wide text-[#99F6E4]/75">
                      Bệnh lý nền
                    </span>
                    <div className="mt-1 flex flex-wrap gap-1.5">
                      {form.conditions.length > 0 ? (
                        form.conditions.map((c) => (
                          <span
                            key={c}
                            className="inline-flex items-center rounded-full border border-[#5EEAD4]/35 bg-[#14B8A6]/20 px-2.5 py-0.5 text-[11px] font-semibold text-[#CCFBF1]"
                          >
                            {formatCondition(c)}
                          </span>
                        ))
                      ) : (
                        <span className="text-xs text-[#CCFBF1]/60">Không khai báo</span>
                      )}
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <span className="text-[10px] font-semibold uppercase tracking-wide text-[#99F6E4]/75">
                        Dị ứng loại trừ
                      </span>
                      <div className="mt-1 flex flex-wrap gap-1">
                        {form.allergens.length > 0 ? (
                          form.allergens.map((a) => (
                            <span
                              key={a}
                              className="inline-flex items-center rounded-full border border-[#FB7185]/45 bg-[#FB7185]/20 px-2 py-0.5 text-[10.5px] font-semibold text-[#FFE4E6]"
                            >
                              {formatAllergen(a)}
                            </span>
                          ))
                        ) : (
                          <span className="text-[11px] text-[#CCFBF1]/60">Không có</span>
                        )}
                      </div>
                    </div>

                    <div>
                      <span className="text-[10px] font-semibold uppercase tracking-wide text-[#99F6E4]/75">
                        Lưu ý nguy cơ
                      </span>
                      <div className="mt-1 flex flex-wrap gap-1">
                        {riskSummaryList.length > 0 ? (
                          riskSummaryList.map((r) => (
                            <span
                              key={r}
                              className="inline-flex items-center rounded-full border border-[#FBBF24]/45 bg-[#FBBF24]/20 px-2 py-0.5 text-[10.5px] font-semibold text-[#FEF3C7]"
                            >
                              {r}
                            </span>
                          ))
                        ) : (
                          <span className="text-[11px] text-[#CCFBF1]/60">Chưa ghi nhận</span>
                        )}
                      </div>
                    </div>
                  </div>

                  {form.preferences_text.trim() && (
                    <div className="border-t border-white/12 pt-2">
                      <span className="text-[10px] font-semibold uppercase tracking-wide text-[#99F6E4]/75">
                        Sở thích ăn uống
                      </span>
                      <p className="mt-0.5 line-clamp-2 text-[11.5px] italic text-[#E2FAF5]/90">
                        “{form.preferences_text.trim()}”
                      </p>
                    </div>
                  )}
                </div>
              </div>
            </SpotlightCard>
          </div>
        </div>
      )}
    </div>
  );
}
