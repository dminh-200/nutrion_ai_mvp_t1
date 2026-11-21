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
import { Badge } from "@/components/ui/badge";
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

  // Ước tính BMI trực quan để người dùng thấy dữ liệu sống theo chiều cao/cân nặng đang gõ
  const liveBmi = useMemo(() => {
    if (
      !Number.isFinite(form.height_cm) ||
      !Number.isFinite(form.weight_kg) ||
      form.height_cm < 50 ||
      form.weight_kg < 2
    ) {
      return null;
    }
    const m = form.height_cm / 100;
    const val = form.weight_kg / (m * m);
    if (!Number.isFinite(val)) return null;
    const info = classifyBmi(val);
    const markerPct = Math.max(4, Math.min(96, ((val - 14) / (34 - 14)) * 100));
    return { val, info, markerPct };
  }, [form.height_cm, form.weight_kg]);

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
                        ? "border-transparent bg-gradient-to-r from-[#0B4F4A] via-[#0D9488] to-[#14B8A6] text-white shadow-[0_4px_14px_rgba(13,148,136,0.28)]"
                        : "border-[#D5E6DF] bg-white/85 text-[#334155] hover:-translate-y-[1px] hover:border-[#14B8A6] hover:bg-[#F0FDFA] hover:text-[#0B4F4A] hover:shadow-[0_4px_14px_rgba(13,148,136,0.12)]"
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
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-[#E2EFEA]">
                <motion.div
                  className="h-full rounded-full bg-gradient-to-r from-[#0B4F4A] via-[#0D9488] to-[#14B8A6] shadow-[0_0_10px_rgba(20,184,166,0.45)]"
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
                          ? "border-transparent bg-gradient-to-r from-[#0B4F4A] via-[#0D9488] to-[#14B8A6] text-white shadow-[0_6px_18px_rgba(13,148,136,0.28)]"
                          : isDone
                            ? "border-[#A7F3D0] bg-[#ECFDF5]/90 text-[#065F46] hover:border-[#34D399]"
                            : "border-[#DCEAE4] bg-white/80 text-[#64748B] hover:border-[#99D5C6] hover:text-[#0B4F4A]"
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
                                    ? "border-transparent bg-gradient-to-r from-[#0B4F4A] to-[#0D9488] text-white shadow-[0_4px_12px_rgba(13,148,136,0.25)]"
                                    : "border-[#D5E2DC] bg-white/90 text-[#334155] hover:border-[#0D9488]/60 hover:bg-[#F0FDFA]"
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
                              <button
                                key={code}
                                type="button"
                                onClick={() => toggleCondition(code)}
                                className={cn(
                                  "flex items-start justify-between gap-3 rounded-xl border p-3.5 text-left transition-all cursor-pointer active:scale-[0.99]",
                                  selected
                                    ? "border-[#0D9488] bg-gradient-to-br from-[#F0FDFA] to-[#CCFBF1]/45 shadow-[0_4px_14px_rgba(13,148,136,0.12)]"
                                    : "border-[#DCEAE4] bg-white/90 hover:border-[#99D5C6]"
                                )}
                              >
                                <div>
                                  <p className="text-sm font-bold text-[#0F172A]">
                                    {CONDITION_LABELS[code]}
                                  </p>
                                  <p className="mt-0.5 text-xs text-[#64748B]">
                                    {CONDITION_DESCRIPTIONS[code]}
                                  </p>
                                </div>
                                <span
                                  className={cn(
                                    "mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-md border transition-colors",
                                    selected
                                      ? "border-transparent bg-gradient-to-br from-[#0B4F4A] to-[#14B8A6] text-white"
                                      : "border-[#CBD5E1] bg-white"
                                  )}
                                >
                                  {selected && <Check className="h-3.5 w-3.5" />}
                                </span>
                              </button>
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
                                  ? "border-transparent bg-gradient-to-r from-[#0B4F4A] to-[#14B8A6] text-white shadow-[0_4px_12px_rgba(13,148,136,0.28)]"
                                  : "border-[#D5E2DC] bg-white/90 text-[#334155] hover:border-[#0D9488] hover:bg-[#F0FDFA]"
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

          {/* Right: Luminous Clinical Profile Card */}
          <div className="lg:col-span-4">
            <Card className="sticky top-24 overflow-hidden border-[#C7E3DA]">
              {/* Top 3px Luminous Accent */}
              <div className="h-[3px] w-full bg-gradient-to-r from-[#0B4F4A] via-[#0D9488] to-[#38BDF8]" />
              <CardHeader className="border-b border-[#DCEAE4] bg-gradient-to-r from-[#F0FDFA]/90 via-[#E6F8F5]/75 to-[#E0F2FE]/60 pb-3.5">
                <CardTitle className="flex items-center justify-between text-base">
                  <span className="text-[#0B4F4A]">Hồ sơ gửi phân tích</span>
                  <Badge variant="default" className="border-[#99D5C6] bg-white/90 font-mono shadow-2xs">
                    {form.patient_code || "BN-001"}
                  </Badge>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3.5 pt-4 text-sm">
                <div className="grid grid-cols-2 gap-2.5 rounded-xl border border-[#DCEAE4] bg-[#F7FCFA] p-3">
                  <div>
                    <span className="text-[11px] font-semibold uppercase text-[#64748B]">
                      Tuổi / Giới
                    </span>
                    <p className="mt-0.5 font-semibold text-[#0F172A] tabular-nums">
                      {form.age} tuổi · {form.sex === "male" ? "Nam" : "Nữ"}
                    </p>
                  </div>
                  <div>
                    <span className="text-[11px] font-semibold uppercase text-[#64748B]">
                      Chiều cao / Cân nặng
                    </span>
                    <p className="mt-0.5 font-semibold text-[#0F172A] tabular-nums">
                      {form.height_cm} cm · {form.weight_kg} kg
                    </p>
                  </div>
                  <div className="col-span-2">
                    <span className="text-[11px] font-semibold uppercase text-[#64748B]">
                      Mức vận động
                    </span>
                    <p className="mt-0.5 text-xs font-medium text-[#334155]">
                      {formatActivity(form.activity_level)}
                    </p>
                  </div>
                </div>

                {/* Live BMI Reference Scale */}
                {liveBmi && (
                  <div className="rounded-xl border border-[#D4E7E0] bg-white/90 p-3 space-y-2 shadow-2xs">
                    <div className="flex items-center justify-between gap-2">
                      <span className="inline-flex items-center gap-1 text-[11px] font-semibold uppercase text-[#64748B]">
                        BMI ước tính
                        <InfoTip text="Chỉ số khối cơ thể = cân nặng / (chiều cao m)². Phân loại theo ngưỡng chuẩn châu Á (IDI & WPRO)." />
                      </span>
                      <span className="font-mono text-xs font-bold text-[#0B4F4A] tabular-nums">
                        {formatNumber(liveBmi.val, 1)} · {liveBmi.info.label}
                      </span>
                    </div>
                    <div className="relative h-2.5 w-full rounded-full bg-gradient-to-r from-[#38BDF8] via-[#10B981] via-55% to-[#F43F5E]">
                      <div
                        className="absolute top-1/2 h-4 w-4 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white bg-[#0B4F4A] shadow-[0_0_0_3px_rgba(20,184,166,0.28)] transition-all duration-200"
                        style={{ left: `${liveBmi.markerPct}%` }}
                      />
                    </div>
                    <div className="flex justify-between font-mono text-[10px] text-[#64748B]">
                      <span>&lt;18.5</span>
                      <span>18.5–22.9</span>
                      <span>23–24.9</span>
                      <span>≥25</span>
                    </div>
                  </div>
                )}

                <div>
                  <span className="text-[11px] font-semibold uppercase text-[#64748B]">
                    Bệnh lý nền
                  </span>
                  <div className="mt-1.5 flex flex-wrap gap-1.5">
                    {form.conditions.length > 0 ? (
                      form.conditions.map((c) => (
                        <Badge key={c} variant="default">
                          {formatCondition(c)}
                        </Badge>
                      ))
                    ) : (
                      <span className="text-xs text-[#64748B]">Không khai báo</span>
                    )}
                  </div>
                </div>

                <div>
                  <span className="text-[11px] font-semibold uppercase text-[#64748B]">
                    Dị ứng loại trừ
                  </span>
                  <div className="mt-1.5 flex flex-wrap gap-1.5">
                    {form.allergens.length > 0 ? (
                      form.allergens.map((a) => (
                        <Badge key={a} variant="danger">
                          {formatAllergen(a)}
                        </Badge>
                      ))
                    ) : (
                      <span className="text-xs text-[#64748B]">Không có</span>
                    )}
                  </div>
                </div>

                <div>
                  <span className="text-[11px] font-semibold uppercase text-[#64748B]">
                    Lưu ý nguy cơ
                  </span>
                  <div className="mt-1.5 flex flex-wrap gap-1.5">
                    {riskSummaryList.length > 0 ? (
                      riskSummaryList.map((r) => (
                        <Badge key={r} variant="pending">
                          {r}
                        </Badge>
                      ))
                    ) : (
                      <span className="text-xs text-[#64748B]">Chưa ghi nhận</span>
                    )}
                  </div>
                </div>

                <div className="border-t border-[#E6F0EC] pt-3 space-y-1.5">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-[#64748B] font-medium">Số ngày lập thực đơn</span>
                    <span className="font-mono font-bold text-[#0F172A]">{form.days} ngày</span>
                  </div>
                  <div>
                    <span className="text-xs text-[#64748B] font-medium">Sở thích ăn uống</span>
                    <p className="mt-0.5 text-xs text-[#334155] italic">
                      {form.preferences_text.trim() || "Không có ghi chú thêm"}
                    </p>
                  </div>
                </div>

                <p className="rounded-xl border border-[#CDE6DF] bg-[#F0FDFA]/90 px-3 py-2 text-[11px] text-[#0B4F4A]">
                  BMI, BMR, TDEE và nhu cầu dinh dưỡng sẽ được máy chủ tính toán chuẩn xác theo quy tắc y khoa khi phân tích.
                </p>
              </CardContent>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}
