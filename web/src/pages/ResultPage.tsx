import { motion } from "framer-motion";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  Activity,
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  ClipboardList,
  Clock,
  Flame,
  MessageSquareHeart,
  Scale,
  ShieldBan,
  ShieldCheck,
  Sparkles,
  Stethoscope,
  Target,
} from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { ExplanationCard } from "@/components/result/ExplanationCard";
import { MealDayTabs } from "@/components/result/MealDayTabs";
import {
  DailyEnergyChart,
  MacroDonutCard,
  ThresholdBars,
} from "@/components/result/NutritionCharts";
import { AnimatedNumber } from "@/components/ui/animated-number";
import { Badge, statusBadgeVariant } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { SpotlightCard } from "@/components/ui/spotlight-card";
import { InfoTip } from "@/components/ui/tooltip";
import {
  classifyBmi,
  formatCondition,
  formatInt,
  formatNeed,
  formatNumber,
  formatRiskReason,
  formatStatus,
} from "@/lib/format";
import { STAGGER_CONTAINER, STAGGER_ITEM } from "@/lib/motion";
import type { DemoRole, MealPlanRunResponse, MealPlanSummary } from "@/types/api";

interface ResultPageProps {
  role: DemoRole;
  result: MealPlanRunResponse | null;
  recentPlans: MealPlanSummary[];
  onGoToProfile: () => void;
  onOpenPlanById: (id: number) => void;
  onOpenReviewForId: (id: number) => void;
  onOpenChatWithPlan?: (id: number) => void;
}

export function ResultPage({
  role,
  result,
  recentPlans,
  onGoToProfile,
  onOpenPlanById,
  onOpenReviewForId,
  onOpenChatWithPlan,
}: ResultPageProps) {
  if (!result) {
    return (
      <div className="space-y-6">
        <PageHeader
          eyebrow="KẾT QUẢ THỰC ĐƠN"
          title="Chưa có kết quả phân tích trong phiên làm việc"
          description="Hãy nhập hồ sơ sức khỏe tại trang Hồ sơ để hệ thống tính toán mục tiêu dinh dưỡng và xây dựng thực đơn."
        />
        <Card className="ambient-teal-card border-[#BDE3D8]">
          <CardContent className="flex flex-col items-start justify-between gap-4 p-6 sm:flex-row sm:items-center">
            <div className="flex items-start gap-3.5">
              <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-[#0B4F4A] to-[#14B8A6] text-white shadow-[0_4px_14px_rgba(13,148,136,0.28)]">
                <Sparkles className="h-5 w-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-[#0F172A]">Bắt đầu khảo sát hồ sơ mới</h3>
                <p className="mt-1 text-sm text-[#64748B]">
                  Bạn có thể tự nhập hoặc nạp nhanh từ 30 hồ sơ bệnh nhân mẫu.
                </p>
              </div>
            </div>
            <Button onClick={onGoToProfile}>
              <ClipboardList className="h-4 w-4" />
              Đi đến Hồ sơ bệnh nhân
            </Button>
          </CardContent>
        </Card>

        {recentPlans.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Hoặc mở lại các ca đã xử lý gần đây</CardTitle>
            </CardHeader>
            <CardContent className="divide-y divide-[#EDF4F0]">
              {recentPlans.slice(0, 5).map((p) => (
                <div
                  key={p.id}
                  className="group flex flex-col gap-2 py-3 transition-colors hover:bg-[#F0FDFA]/70 -mx-2 px-2 rounded-xl sm:flex-row sm:items-center sm:justify-between"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-xs font-bold text-[#0B4F4A]">#{p.id}</span>
                    <span className="text-sm font-semibold text-[#0F172A]">
                      {p.patient_code}
                    </span>
                    <span className="text-xs text-[#64748B]">
                      {p.conditions.map(formatCondition).join(", ") || "Không bệnh nền"}
                    </span>
                    <Badge variant={statusBadgeVariant(p.status)}>{formatStatus(p.status)}</Badge>
                  </div>
                  <Button size="sm" variant="outline" onClick={() => onOpenPlanById(p.id)}>
                    <span>Xem kết quả</span>
                    <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />
                  </Button>
                </div>
              ))}
            </CardContent>
          </Card>
        )}
      </div>
    );
  }

  const status = result.status;

  // QUY TẮC AN TOÀN Y TẾ BẤT BIẾN: redirect_to_doctor & blocked tuyệt đối không hiện thực đơn
  if (status === "redirect_to_doctor") {
    const reasons =
      result.risk?.reasons && result.risk.reasons.length > 0
        ? result.risk.reasons
        : result.input_flags;

    return (
      <div>
        <PageHeader
          eyebrow="SÀNG LỌC AN TOÀN Y TẾ"
          title="Khuyến nghị thăm khám bác sĩ trực tiếp"
          description="Hệ thống từ chối sinh thực đơn tự động để bảo đảm an toàn lâm sàng cho người bệnh."
          rightSlot={<Badge variant="redirect">{formatStatus(status)}</Badge>}
        />

        <Card className="border-[#BAE6FD] bg-gradient-to-br from-[#F0F9FF] to-white">
          <CardContent className="space-y-5 p-6 sm:p-8">
            <div className="flex items-start gap-4">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-[#0284C7] to-[#38BDF8] text-white shadow-sm">
                <Stethoscope className="h-6 w-6" />
              </div>
              <div className="space-y-1.5">
                <h2 className="text-lg font-bold text-[#0F172A]">
                  Hồ sơ thuộc nhóm đối tượng cần bác sĩ chỉ định trực tiếp
                </h2>
                <p className="text-sm text-[#334155] leading-relaxed">
                  {result.risk?.message_vi ||
                    "Tình trạng sức khỏe hiện tại cần được bác sĩ hoặc chuyên gia dinh dưỡng lâm sàng đánh giá trực tiếp trước khi xây dựng khẩu phần."}
                </p>
              </div>
            </div>

            {reasons.length > 0 && (
              <div className="rounded-xl border border-[#BAE6FD] bg-white/90 p-4">
                <p className="mb-2 text-xs font-bold uppercase tracking-wide text-[#0369A1]">
                  Yếu tố nguy cơ được phát hiện:
                </p>
                <ul className="space-y-1.5 text-sm text-[#0F172A]">
                  {reasons.map((r) => (
                    <li key={r} className="flex items-center gap-2">
                      <AlertTriangle className="h-4 w-4 shrink-0 text-[#D97706]" />
                      <span>{formatRiskReason(r)}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
              <p className="text-xs font-medium text-[#0369A1]">
                Vui lòng liên hệ cơ sở y tế hoặc đặt lịch khám chuyên khoa dinh dưỡng.
              </p>
              <Button variant="outline" onClick={onGoToProfile}>
                <ArrowLeft className="h-4 w-4" />
                Quay lại chỉnh sửa hồ sơ
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (status === "blocked") {
    return (
      <div>
        <PageHeader
          eyebrow="BẢO VỆ ĐẦU VÀO"
          title="Yêu cầu đã bị chặn an toàn"
          description="Nội dung nhập vào không hợp lệ hoặc vi phạm quy tắc bảo vệ hệ thống."
          rightSlot={<Badge variant="danger">{formatStatus(status)}</Badge>}
        />

        <Card className="border-[#FECACA] bg-gradient-to-br from-[#FEF2F2] to-white">
          <CardContent className="space-y-5 p-6 sm:p-8">
            <div className="flex items-start gap-4">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-[#DC2626] to-[#F43F5E] text-white shadow-sm">
                <ShieldBan className="h-6 w-6" />
              </div>
              <div className="space-y-2">
                <h2 className="text-lg font-bold text-[#991B1B]">
                  Không thể tiếp tục xử lý yêu cầu này
                </h2>
                <div className="prose prose-sm max-w-none text-[#7F1D1D]">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {result.explanation_md ||
                      "Phát hiện nội dung cố tình thay đổi chỉ dẫn hoặc dữ liệu ngoài phạm vi cho phép."}
                  </ReactMarkdown>
                </div>
              </div>
            </div>

            <div className="flex justify-end">
              <Button variant="outline" onClick={onGoToProfile}>
                <ArrowLeft className="h-4 w-4" />
                Quay lại nhập hồ sơ hợp lệ
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Trường hợp có phân tích chỉ số (pending_review / approved / needs_human_review / rejected)
  const targets = result.targets ?? {
    bmi: 0,
    bmr: 0,
    tdee: 0,
    target_kcal: 0,
    protein_g: 0,
    fat_g: 0,
    carb_g: 0,
    fiber_min_g: 25,
    sodium_max_mg: 2000,
    sugar_max_g: 25,
    kcal_floor: 1200,
    rationale: [],
  };
  const bmi = Number(targets.bmi ?? 0);
  const bmiInfo = classifyBmi(bmi);

  // Theo SPEC 3.2: ca needs_human_review chưa đạt kiểm chứng tự động nên không hiển thị
  // thực đơn chưa kiểm chứng trên trang Kết quả; bản nháp được mở tại Bàn duyệt chuyên gia.
  const hasMenu =
    result.items.length > 0 &&
    result.daily_totals.length > 0 &&
    status !== "needs_human_review";
  const nDays = result.daily_totals.length || 1;
  const avgKcal = hasMenu
    ? result.daily_totals.reduce((s, d) => s + d.kcal, 0) / nDays
    : 0;
  const avgProtein = hasMenu
    ? result.daily_totals.reduce((s, d) => s + d.protein_g, 0) / nDays
    : 0;
  const avgFat = hasMenu
    ? result.daily_totals.reduce((s, d) => s + d.fat_g, 0) / nDays
    : 0;
  const avgCarb = hasMenu
    ? result.daily_totals.reduce((s, d) => s + d.carb_g, 0) / nDays
    : 0;
  const avgSodium = hasMenu
    ? result.daily_totals.reduce((s, d) => s + d.sodium_mg, 0) / nDays
    : 0;
  const avgFiber = hasMenu
    ? result.daily_totals.reduce((s, d) => s + d.fiber_g, 0) / nDays
    : 0;

  const needsList = result.needs?.needs ?? [];

  // Quy tắc an toàn chặt (Bonus 1): chỉ gắn nhãn xanh "Đạt 11/11 tiêu chí an toàn"
  // khi có thực đơn, violations rỗng VÀ status là approved hoặc pending_review
  const passedAll11 =
    hasMenu &&
    result.violations.length === 0 &&
    (status === "approved" || status === "pending_review");
  const isRejected = status === "rejected";
  const kcalPct =
    targets.target_kcal && targets.target_kcal > 0
      ? Math.round((avgKcal / targets.target_kcal) * 100)
      : null;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="KẾT QUẢ PHÂN TÍCH LÂM SÀNG"
        title="Mục tiêu dinh dưỡng & Thực đơn cá nhân hóa"
        description="Số liệu dinh dưỡng được kiểm chứng bằng mã nguồn từ cơ sở dữ liệu thực phẩm Việt Nam."
        rightSlot={
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={statusBadgeVariant(status)} className="px-3 py-1 text-xs shadow-2xs">
              {formatStatus(status)}
            </Badge>
            {result.meal_plan_id && onOpenChatWithPlan && (
              <Button
                size="sm"
                variant="glassDark"
                onClick={() => onOpenChatWithPlan(result.meal_plan_id!)}
              >
                <MessageSquareHeart className="h-3.5 w-3.5 text-[#5EEAD4]" />
                Hỏi Trợ lý về thực đơn này
              </Button>
            )}
            {role !== "patient" &&
              result.meal_plan_id &&
              (status === "pending_review" || status === "needs_human_review") && (
                <Button size="sm" onClick={() => onOpenReviewForId(result.meal_plan_id!)}>
                  <Stethoscope className="h-3.5 w-3.5" />
                  Mở bàn duyệt
                </Button>
              )}
          </div>
        }
        bottomSlot={
          <div className="flex flex-wrap items-center justify-between gap-2.5 text-xs">
            <div className="flex flex-wrap items-center gap-2">
              {passedAll11 ? (
                <Badge
                  variant="approved"
                  className="gap-1.5 border-[#34D399]/50 bg-[#059669]/28 py-0.5 text-[#D1FAE5] shadow-[0_0_16px_rgba(52,211,153,0.22)]"
                >
                  <ShieldCheck className="h-3.5 w-3.5 text-[#34D399]" />
                  Đạt 11/11 tiêu chí an toàn
                </Badge>
              ) : isRejected ? (
                <Badge
                  variant="danger"
                  className="gap-1.5 border-[#FB7185]/50 bg-[#E11D48]/28 py-0.5 text-[#FFE4E6] shadow-2xs"
                >
                  <AlertTriangle className="h-3.5 w-3.5 text-[#FDA4AF]" />
                  Cần chuyên gia rà soát (Đã từ chối)
                </Badge>
              ) : (
                <Badge
                  variant="pending"
                  className="gap-1.5 border-[#FBBF24]/50 bg-[#D97706]/28 py-0.5 text-[#FEF3C7] shadow-2xs"
                >
                  <AlertTriangle className="h-3.5 w-3.5 text-[#FCD34D]" />
                  Cần chuyên gia rà soát
                </Badge>
              )}

              {hasMenu && (
                <span className="inline-flex items-center gap-1.5 rounded-full border border-white/22 bg-white/12 px-2.5 py-0.5 font-mono text-[11px] font-semibold text-white tabular-nums backdrop-blur-xs">
                  {nDays} ngày · TB {formatInt(avgKcal)} / {formatInt(targets.target_kcal)} kcal
                  {kcalPct !== null ? ` (${kcalPct}%)` : ""}
                </span>
              )}

              {needsList.map((n) => (
                <span
                  key={n}
                  className="inline-flex items-center rounded-full border border-[#5EEAD4]/35 bg-[#14B8A6]/18 px-2.5 py-0.5 text-[11px] font-semibold text-[#CCFBF1]"
                >
                  {formatNeed(n)}
                </span>
              ))}
            </div>

            <span className="font-mono text-[11px] font-semibold text-[#CCFBF1]/85">
              {result.retry_count === 0
                ? "Đạt kiểm chứng lần đầu"
                : `Số lần tinh chỉnh: ${result.retry_count}`}
            </span>
          </div>
        }
      />

      {/* Status Guidance Strip */}
      <Card>
        <CardContent className="flex items-center gap-2.5 p-3.5 sm:px-5 text-sm font-medium text-[#0F172A]">
          {status === "approved" ? (
            <CheckCircle2 className="h-5 w-5 shrink-0 text-[#059669]" />
          ) : status === "rejected" ? (
            <AlertTriangle className="h-5 w-5 shrink-0 text-[#DC2626]" />
          ) : (
            <Clock className="h-5 w-5 shrink-0 text-[#D97706]" />
          )}
          <span>
            {status === "approved" &&
              "Thực đơn đã được chuyên gia dinh dưỡng phê duyệt và sẵn sàng tham khảo."}
            {status === "pending_review" &&
              "Thực đơn đã vượt qua kiểm chứng tự động và đang chờ chuyên gia dinh dưỡng phê duyệt."}
            {status === "needs_human_review" &&
              "Hồ sơ cần chuyên gia dinh dưỡng rà soát và tinh chỉnh trước khi áp dụng."}
            {status === "rejected" &&
              "Thực đơn này đã bị từ chối trong quá trình thẩm định chuyên môn. Vui lòng tạo thực đơn mới."}
          </span>
        </CardContent>
      </Card>

      {/* 4 Luminous Elevated Clinical KPI Cards (3 Spotlight Glass + 1 Dark-Emerald Signature Ring) */}
      <motion.div
        variants={STAGGER_CONTAINER}
        initial="hidden"
        animate="show"
        className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4"
      >
        <motion.div variants={STAGGER_ITEM}>
          <SpotlightCard className="h-full rounded-2xl border border-white/85 bg-white/78 backdrop-blur-2xl ring-1 ring-[#0D9488]/10 shadow-[inset_0_1px_0_rgba(255,255,255,0.95),0_12px_30px_-6px_rgba(11,79,74,0.1)] transition-all duration-200 hover:-translate-y-0.5 hover:ring-[#14B8A6]/35 hover:shadow-[0_14px_32px_rgba(13,148,136,0.16)]">
            <div className="h-[3px] w-full bg-gradient-to-r from-[#0D9488] to-[#06B6D4]" />
            <div className="p-4 sm:p-5">
              <div className="flex items-center justify-between gap-2">
                <span className="inline-flex items-center gap-1 text-xs font-semibold text-[#475569]">
                  Chỉ số BMI
                  <InfoTip text="Chỉ số khối cơ thể (kg/m²), phân loại theo ngưỡng IDI & WPRO dành cho người châu Á." />
                </span>
                <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-br from-[#0D9488] to-[#06B6D4] text-white shadow-[0_4px_12px_rgba(6,182,212,0.3)]">
                  <Scale className="h-4 w-4" />
                </span>
              </div>
              <p className="mt-2 font-mono text-2xl font-extrabold text-[#0F172A] tabular-nums">
                <AnimatedNumber value={bmi} formatter={(v) => formatNumber(v, 1)} />
              </p>
              <p className="mt-1 text-xs font-semibold text-[#0D9488]">{bmiInfo.label}</p>
            </div>
          </SpotlightCard>
        </motion.div>

        <motion.div variants={STAGGER_ITEM}>
          <SpotlightCard className="h-full rounded-2xl border border-white/85 bg-white/78 backdrop-blur-2xl ring-1 ring-[#0D9488]/10 shadow-[inset_0_1px_0_rgba(255,255,255,0.95),0_12px_30px_-6px_rgba(11,79,74,0.1)] transition-all duration-200 hover:-translate-y-0.5 hover:ring-[#38BDF8]/45 hover:shadow-[0_14px_32px_rgba(2,132,199,0.16)]">
            <div className="h-[3px] w-full bg-gradient-to-r from-[#0284C7] to-[#38BDF8]" />
            <div className="p-4 sm:p-5">
              <div className="flex items-center justify-between gap-2">
                <span className="inline-flex items-center gap-1 text-xs font-semibold text-[#475569]">
                  BMR (Cơ bản)
                  <InfoTip text="Tỷ lệ trao đổi chất cơ bản (Mifflin-St Jeor): năng lượng tối thiểu duy trì sự sống khi nghỉ ngơi hoàn toàn." />
                </span>
                <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-br from-[#0284C7] to-[#38BDF8] text-white shadow-[0_4px_12px_rgba(2,132,199,0.28)]">
                  <Flame className="h-4 w-4" />
                </span>
              </div>
              <p className="mt-2 font-mono text-2xl font-extrabold text-[#0F172A] tabular-nums">
                <AnimatedNumber value={Number(targets.bmr ?? 0)} formatter={formatInt} />{" "}
                <span className="text-sm font-semibold text-[#64748B]">kcal</span>
              </p>
              <p className="mt-1 text-xs text-[#64748B]">Công thức Mifflin-St Jeor</p>
            </div>
          </SpotlightCard>
        </motion.div>

        <motion.div variants={STAGGER_ITEM}>
          <SpotlightCard className="h-full rounded-2xl border border-white/85 bg-white/78 backdrop-blur-2xl ring-1 ring-[#0D9488]/10 shadow-[inset_0_1px_0_rgba(255,255,255,0.95),0_12px_30px_-6px_rgba(11,79,74,0.1)] transition-all duration-200 hover:-translate-y-0.5 hover:ring-[#F59E0B]/40 hover:shadow-[0_14px_32px_rgba(217,119,6,0.16)]">
            <div className="h-[3px] w-full bg-gradient-to-r from-[#D97706] to-[#FBBF24]" />
            <div className="p-4 sm:p-5">
              <div className="flex items-center justify-between gap-2">
                <span className="inline-flex items-center gap-1 text-xs font-semibold text-[#475569]">
                  TDEE (Tiêu hao)
                  <InfoTip text="Tổng năng lượng tiêu hao hằng ngày = BMR × hệ số mức độ vận động thể lực." />
                </span>
                <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-br from-[#D97706] to-[#F59E0B] text-white shadow-[0_4px_12px_rgba(217,119,6,0.28)]">
                  <Activity className="h-4 w-4" />
                </span>
              </div>
              <p className="mt-2 font-mono text-2xl font-extrabold text-[#0F172A] tabular-nums">
                <AnimatedNumber value={Number(targets.tdee ?? 0)} formatter={formatInt} />{" "}
                <span className="text-sm font-semibold text-[#64748B]">kcal</span>
              </p>
              <p className="mt-1 text-xs text-[#64748B]">Theo mức độ vận động</p>
            </div>
          </SpotlightCard>
        </motion.div>

        <motion.div variants={STAGGER_ITEM}>
          <SpotlightCard
            tone="dark"
            className="dark-emerald-card h-full rounded-2xl text-white transition-transform duration-200 hover:-translate-y-0.5"
          >
            <div className="h-[3px] w-full bg-gradient-to-r from-[#2DD4BF] via-[#22D3EE] to-[#34D399]" />
            <div className="flex h-full items-center justify-between gap-3 p-4 sm:p-5">
              <div className="min-w-0">
                <span className="inline-flex items-center gap-1 text-xs font-semibold text-[#99F6E4]">
                  Mục tiêu khẩu phần
                  <InfoTip
                    text="Mức năng lượng đích mỗi ngày đã điều chỉnh theo bệnh lý nền và sàn an toàn tối thiểu."
                    className="text-[#99F6E4]/85 hover:bg-white/15 hover:text-white"
                  />
                </span>
                <p className="mt-1.5 font-mono text-2xl font-extrabold text-white tabular-nums leading-tight">
                  <AnimatedNumber value={Number(targets.target_kcal ?? 0)} formatter={formatInt} />{" "}
                  <span className="text-xs font-semibold text-[#CCFBF1]/80">kcal</span>
                </p>
                <p className="mt-1 text-[11px] font-medium text-[#CCFBF1]/80">
                  Sàn ≥ {formatInt(targets.kcal_floor)} kcal/ngày
                </p>
              </div>

              {hasMenu && kcalPct !== null ? (
                <div
                  className="relative flex h-16 w-16 shrink-0 items-center justify-center"
                  title={`Thực đơn đạt ${kcalPct}% mục tiêu năng lượng`}
                >
                  <svg viewBox="0 0 64 64" className="h-16 w-16 -rotate-90">
                    <defs>
                      <linearGradient id="kcalRingGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" stopColor="#22D3EE" />
                        <stop offset="100%" stopColor="#34D399" />
                      </linearGradient>
                    </defs>
                    <circle
                      cx="32"
                      cy="32"
                      r="25"
                      fill="none"
                      stroke="rgba(255,255,255,0.16)"
                      strokeWidth="5.5"
                    />
                    <circle
                      cx="32"
                      cy="32"
                      r="25"
                      fill="none"
                      stroke="url(#kcalRingGrad)"
                      strokeWidth="5.5"
                      strokeLinecap="round"
                      strokeDasharray={2 * Math.PI * 25}
                      strokeDashoffset={
                        2 * Math.PI * 25 * (1 - Math.min(100, Math.max(0, kcalPct)) / 100)
                      }
                      style={{
                        filter: "drop-shadow(0 0 6px rgba(34, 211, 238, 0.7))",
                      }}
                    />
                  </svg>
                  <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center text-center">
                    <span className="font-mono text-xs font-extrabold text-white tabular-nums leading-none">
                      {kcalPct}%
                    </span>
                    <span className="text-[8.5px] font-semibold uppercase tracking-wide text-[#99F6E4]">
                      đạt đích
                    </span>
                  </div>
                </div>
              ) : (
                <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-[#5EEAD4]/40 bg-white/12 text-[#5EEAD4]">
                  <Target className="h-5 w-5" />
                </span>
              )}
            </div>
          </SpotlightCard>
        </motion.div>
      </motion.div>

      {/* Macro Donut + Threshold Progress Bars */}
      {hasMenu ? (
        <>
          <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
            <MacroDonutCard
              avgKcal={avgKcal}
              avgProtein={avgProtein}
              avgFat={avgFat}
              avgCarb={avgCarb}
            />
            <ThresholdBars
              avgKcal={avgKcal}
              avgProtein={avgProtein}
              avgFat={avgFat}
              avgCarb={avgCarb}
              avgSodium={avgSodium}
              avgFiber={avgFiber}
              targets={targets}
            />
          </div>

          <DailyEnergyChart
            dailyTotals={result.daily_totals}
            targetKcal={Number(targets.target_kcal ?? 0)}
          />

          <MealDayTabs items={result.items} dailyTotals={result.daily_totals} />
        </>
      ) : (
        <Card className="border-[#FDE68A] bg-[#FFFBEB]/90">
          <CardContent className="p-5 text-sm text-[#92400E]">
            Chưa có danh sách món ăn đạt kiểm chứng tự động cho hồ sơ này. Hồ sơ đã được chuyển cho chuyên gia dinh dưỡng xem xét trực tiếp.
          </CardContent>
        </Card>
      )}

      <ExplanationCard explanationMd={result.explanation_md} snippets={result.snippets} />
    </div>
  );
}
