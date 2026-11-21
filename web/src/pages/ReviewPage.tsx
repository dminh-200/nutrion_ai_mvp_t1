import { useCallback, useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import {
  AlertTriangle,
  CheckCircle2,
  Eye,
  FlaskConical,
  Minus,
  Plus,
  RotateCcw,
  Search,
  ShieldAlert,
  Stethoscope,
  X,
  XCircle,
} from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge, statusBadgeVariant } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, Textarea } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { apiClient } from "@/lib/api";
import {
  formatAllergen,
  formatCondition,
  formatInt,
  formatMeal,
  formatNumber,
  formatStatus,
} from "@/lib/format";
import { TAB_SPRING } from "@/lib/motion";
import { cn } from "@/lib/utils";
import type {
  EditedItemInput,
  MealPlanDetailResponse,
  MealPlanListResponse,
  MealType,
  PreviewEditResponse,
} from "@/types/api";

interface ReviewPageProps {
  initialSelectedPlanId: number | null;
  onQueueChanged: () => void;
  onViewInResult: (id: number) => void;
}

type QueueFilterKey =
  | "pending_review,needs_human_review"
  | "pending_review"
  | "needs_human_review"
  | "all";

interface EditableRow {
  day: number;
  meal: MealType;
  food_id: number;
  name_vi: string;
  original_grams: number;
  grams: number;
}

export function ReviewPage({
  initialSelectedPlanId,
  onQueueChanged,
  onViewInResult,
}: ReviewPageProps) {
  const [filter, setFilter] = useState<QueueFilterKey>("pending_review,needs_human_review");
  const [queueData, setQueueData] = useState<MealPlanListResponse | null>(null);
  const [loadingQueue, setLoadingQueue] = useState(false);
  const [queueSearch, setQueueSearch] = useState("");

  const [selectedId, setSelectedId] = useState<number | null>(initialSelectedPlanId);
  const [detail, setDetail] = useState<MealPlanDetailResponse | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  const [editableRows, setEditableRows] = useState<EditableRow[]>([]);
  const [dryRunResult, setDryRunResult] = useState<PreviewEditResponse | null>(null);
  const [dryRunFingerprint, setDryRunFingerprint] = useState<string>("");
  const [runningDryRun, setRunningDryRun] = useState(false);

  const [reviewerName, setReviewerName] = useState("BS. Dinh dưỡng");
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const fetchQueue = useCallback(async (f: QueueFilterKey) => {
    setLoadingQueue(true);
    try {
      const res = await apiClient.listMealPlans(f === "all" ? undefined : f, 80);
      setQueueData(res);
      return res;
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Không thể tải hàng đợi duyệt.");
      return null;
    } finally {
      setLoadingQueue(false);
    }
  }, []);

  const fetchDetail = useCallback(async (id: number) => {
    setLoadingDetail(true);
    setDryRunResult(null);
    setDryRunFingerprint("");
    try {
      const d = await apiClient.getMealPlanDetail(id);
      setDetail(d);
      setEditableRows(
        d.items.map((it) => ({
          day: it.day,
          meal: (it.meal as MealType) || "breakfast",
          food_id: it.food_id,
          name_vi: it.name_vi,
          original_grams: it.grams,
          grams: it.grams,
        }))
      );
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Không thể tải chi tiết thực đơn.");
    } finally {
      setLoadingDetail(false);
    }
  }, []);

  useEffect(() => {
    if (initialSelectedPlanId !== null) {
      setSelectedId(initialSelectedPlanId);
    }
  }, [initialSelectedPlanId]);

  useEffect(() => {
    fetchQueue(filter).then((res) => {
      if (!res) return;
      if (selectedId && res.items.some((x) => x.id === selectedId)) {
        return;
      }
      if (initialSelectedPlanId && res.items.some((x) => x.id === initialSelectedPlanId)) {
        setSelectedId(initialSelectedPlanId);
        return;
      }
      if (res.items.length > 0) {
        setSelectedId(res.items[0].id);
      } else {
        setSelectedId(null);
        setDetail(null);
      }
    });
  }, [filter, fetchQueue]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (selectedId !== null) {
      fetchDetail(selectedId);
    }
  }, [selectedId, fetchDetail]);

  const filteredQueueItems = useMemo(() => {
    const items = queueData?.items ?? [];
    const q = queueSearch.trim().toLowerCase();
    if (!q) return items;
    return items.filter(
      (it) =>
        String(it.id).includes(q) ||
        it.patient_code.toLowerCase().includes(q) ||
        it.display_name.toLowerCase().includes(q)
    );
  }, [queueData?.items, queueSearch]);

  const currentFingerprint = useMemo(
    () =>
      JSON.stringify(
        editableRows.map((r) => ({
          day: r.day,
          meal: r.meal,
          food_id: r.food_id,
          grams: r.grams,
        }))
      ),
    [editableRows]
  );

  const isDryRunFresh = dryRunResult !== null && dryRunFingerprint === currentFingerprint;
  const hasMenuItems = editableRows.length > 0;
  const currentStatus = detail?.meal_plan.status ?? "";
  const canReviewAction =
    currentStatus === "pending_review" || currentStatus === "needs_human_review";

  const handleGramsChange = (index: number, rawVal: string | number) => {
    const parsed = rawVal === "" ? 0 : Number(rawVal);
    const clamped = Number.isNaN(parsed) ? 0 : Math.max(0, Math.min(1000, parsed));
    setEditableRows((prev) =>
      prev.map((row, idx) => (idx === index ? { ...row, grams: clamped } : row))
    );
  };

  const handleResetRows = () => {
    setEditableRows((prev) => prev.map((r) => ({ ...r, grams: r.original_grams })));
    setDryRunResult(null);
    setDryRunFingerprint("");
  };

  const buildEditedPayload = useCallback(
    (): EditedItemInput[] =>
      editableRows.map((r) => ({
        day: r.day,
        meal: r.meal,
        food_id: r.food_id,
        grams: r.grams,
      })),
    [editableRows]
  );

  const handleDryRun = useCallback(async () => {
    if (selectedId === null) return;
    setRunningDryRun(true);
    try {
      const res = await apiClient.previewEdit(selectedId, buildEditedPayload());
      setDryRunResult(res);
      setDryRunFingerprint(currentFingerprint);
      if (res.is_valid) {
        toast.success("Bản sửa đạt toàn bộ 11 tiêu chí kiểm chứng.");
      } else {
        toast.warning(`Bản sửa còn ${res.violations.length} cảnh báo cần điều chỉnh.`);
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Lỗi kiểm chứng bản sửa.");
    } finally {
      setRunningDryRun(false);
    }
  }, [selectedId, buildEditedPayload, currentFingerprint]);

  // Phím tắt J/K (hoặc mũi tên) chuyển nhanh ca, Ctrl+Enter để kiểm chứng lại bản sửa
  useEffect(() => {
    const onKey = (e: globalThis.KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      const isEditingText =
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.isContentEditable);

      if ((e.ctrlKey || e.metaKey) && e.key === "Enter" && hasMenuItems && !runningDryRun) {
        e.preventDefault();
        handleDryRun();
        return;
      }

      if (isEditingText || !filteredQueueItems.length) return;
      if (e.key === "j" || e.key === "ArrowDown") {
        e.preventDefault();
        const curIdx = filteredQueueItems.findIndex((x) => x.id === selectedId);
        const nextIdx = curIdx < 0 ? 0 : Math.min(filteredQueueItems.length - 1, curIdx + 1);
        setSelectedId(filteredQueueItems[nextIdx].id);
      } else if (e.key === "k" || e.key === "ArrowUp") {
        e.preventDefault();
        const curIdx = filteredQueueItems.findIndex((x) => x.id === selectedId);
        const prevIdx = curIdx <= 0 ? 0 : curIdx - 1;
        setSelectedId(filteredQueueItems[prevIdx].id);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [filteredQueueItems, selectedId, hasMenuItems, runningDryRun, handleDryRun]);

  const handleSubmitDecision = async (decision: "approve" | "edit" | "reject") => {
    if (selectedId === null) return;
    if (decision === "reject" && !note.trim()) {
      toast.error("Từ chối thực đơn bắt buộc phải nhập lý do trong ô ghi chú.");
      return;
    }

    setSubmitting(true);
    try {
      const res = await apiClient.submitReview(selectedId, {
        decision,
        reviewer_name: reviewerName.trim() || "BS. Dinh dưỡng",
        note: note.trim(),
        edited_items: decision === "edit" ? buildEditedPayload() : undefined,
      });

      setDetail(res.detail);
      setDryRunResult(null);
      setNote("");
      onQueueChanged();

      if (res.status === "approved") {
        toast.success(`Đã phê duyệt thực đơn #${res.meal_plan_id}.`);
      } else if (res.status === "rejected") {
        toast.info(`Đã từ chối thực đơn #${res.meal_plan_id}.`);
      } else {
        toast.warning(`Thực đơn #${res.meal_plan_id} chuyển trạng thái: ${formatStatus(res.status)}`);
      }
      await fetchQueue(filter);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Không thể lưu quyết định duyệt.");
    } finally {
      setSubmitting(false);
    }
  };

  const counts = queueData?.counts;
  const actionableCount = (counts?.pending_review ?? 0) + (counts?.needs_human_review ?? 0);
  const totalForCurrentFilter =
    filter === "pending_review,needs_human_review"
      ? actionableCount
      : filter === "pending_review"
        ? (counts?.pending_review ?? 0)
        : filter === "needs_human_review"
          ? (counts?.needs_human_review ?? 0)
          : (counts?.total ?? 0);
  const loadedCount = queueData?.items.length ?? 0;

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="CỔNG PHÊ DUYỆT LÂM SÀNG (HITL)"
        title="Thẩm định & điều chỉnh thực đơn"
        description="Kiểm duyệt các ca đang chờ, điều chỉnh định lượng từng món, chạy kiểm chứng 11 tiêu chí trước khi phê duyệt."
        rightSlot={
          <span className="hidden lg:inline-flex items-center gap-1.5 rounded-xl border border-[#CDE6DF] bg-white/85 px-3 py-1.5 text-[11px] text-[#475569] shadow-2xs">
            Phím tắt: <kbd className="rounded border border-[#D5E2DC] bg-[#F8FAF9] px-1 font-mono text-[10px]">J</kbd>/
            <kbd className="rounded border border-[#D5E2DC] bg-[#F8FAF9] px-1 font-mono text-[10px]">K</kbd> đổi ca ·{" "}
            <kbd className="rounded border border-[#D5E2DC] bg-[#F8FAF9] px-1 font-mono text-[10px]">Ctrl+Enter</kbd> kiểm chứng
          </span>
        }
      />

      {/* Filter Segmented Bar with Luminous Sliding Pill */}
      <div className="inline-flex flex-wrap gap-1 rounded-xl border border-[#DCEAE4] bg-[#EFF7F4]/90 p-1 shadow-[inset_0_1px_2px_rgba(11,79,74,0.04)]">
        {(
          [
            {
              key: "pending_review,needs_human_review" as const,
              label: `Cần xử lý (${actionableCount})`,
            },
            {
              key: "pending_review" as const,
              label: `Chờ duyệt (${counts?.pending_review ?? 0})`,
            },
            {
              key: "needs_human_review" as const,
              label: `Cần can thiệp (${counts?.needs_human_review ?? 0})`,
            },
            {
              key: "all" as const,
              label: `Tất cả (${counts?.total ?? 0})`,
            },
          ] as const
        ).map((tab) => {
          const active = filter === tab.key;
          return (
            <button
              key={tab.key}
              type="button"
              onClick={() => setFilter(tab.key)}
              className={cn(
                "relative rounded-lg px-3.5 py-2 text-xs font-semibold transition-colors cursor-pointer tabular-nums",
                active ? "text-white" : "text-[#475569] hover:text-[#0B4F4A]"
              )}
            >
              {active && (
                <motion.span
                  layoutId="review-filter-pill"
                  transition={TAB_SPRING}
                  className="absolute inset-0 rounded-lg bg-gradient-to-r from-[#0B4F4A] via-[#0D9488] to-[#14B8A6] shadow-[0_4px_14px_rgba(13,148,136,0.28)]"
                />
              )}
              <span className="relative z-10">{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* Master-Detail Grid */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        {/* Left: Queue List with Vertical Accent Indicators */}
        <div className="lg:col-span-4">
          <Card className="flex flex-col lg:sticky lg:top-20 lg:max-h-[calc(100vh-140px)]">
            <CardHeader className="border-b border-[#E6F0EC] pb-3 space-y-2.5 shrink-0">
              <CardTitle className="flex items-center justify-between text-sm">
                <span>Hàng đợi hồ sơ</span>
                <span className="font-mono text-[11px] font-semibold text-[#64748B] tabular-nums">
                  {totalForCurrentFilter > loadedCount
                    ? `${loadedCount} / ${totalForCurrentFilter} mới nhất`
                    : `${filteredQueueItems.length} ca`}
                </span>
              </CardTitle>
              <div className="relative">
                <Search className="pointer-events-none absolute left-2.5 top-2.5 h-3.5 w-3.5 text-[#94A3B8]" />
                <Input
                  value={queueSearch}
                  onChange={(e) => setQueueSearch(e.target.value)}
                  placeholder="Tìm mã BN hoặc #ID..."
                  className="h-8.5 bg-white/90 pl-8 pr-7 text-xs"
                />
                {queueSearch && (
                  <button
                    type="button"
                    aria-label="Xóa tìm kiếm"
                    onClick={() => setQueueSearch("")}
                    className="absolute right-2 top-2 rounded p-0.5 text-[#94A3B8] hover:text-[#0F172A] cursor-pointer"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                )}
              </div>
            </CardHeader>
            <CardContent className="flex-1 overflow-y-auto p-2.5 space-y-1.5 min-h-[240px]">
              {loadingQueue && !queueData ? (
                <div className="space-y-2 p-1">
                  {[1, 2, 3, 4, 5].map((i) => (
                    <Skeleton key={i} className="h-[74px] w-full rounded-xl" />
                  ))}
                </div>
              ) : !filteredQueueItems.length ? (
                <div className="p-6 text-center space-y-1">
                  <CheckCircle2 className="mx-auto h-7 w-7 text-[#0D9488]" />
                  <p className="text-sm font-semibold text-[#0F172A]">Không có ca phù hợp</p>
                  <p className="text-xs text-[#64748B]">
                    Các hồ sơ mới tạo hoặc khớp từ khóa sẽ xuất hiện tại đây.
                  </p>
                </div>
              ) : (
                filteredQueueItems.map((item) => {
                  const isSelected = selectedId === item.id;
                  const needsIntervention = item.status === "needs_human_review";
                  return (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => setSelectedId(item.id)}
                      className={cn(
                        "relative w-full overflow-hidden rounded-xl border p-3 pl-3.5 text-left transition-all cursor-pointer space-y-1.5",
                        isSelected
                          ? "border-[#14B8A6] bg-gradient-to-r from-[#F0FDFA] to-white shadow-[0_4px_14px_rgba(13,148,136,0.12)]"
                          : "border-[#E4ECE8] bg-white/85 hover:border-[#99D5C6] hover:bg-white"
                      )}
                    >
                      {/* Vertical 3px Accent Bar */}
                      <span
                        aria-hidden="true"
                        className={cn(
                          "absolute inset-y-1.5 left-1 w-[3px] rounded-full transition-opacity",
                          isSelected
                            ? "bg-gradient-to-b from-[#0B4F4A] to-[#14B8A6] opacity-100"
                            : needsIntervention
                              ? "bg-[#F59E0B]/70 opacity-100"
                              : "opacity-0"
                        )}
                      />

                      <div className="flex items-center justify-between gap-2">
                        <span className="font-mono text-xs font-bold text-[#0B4F4A]">
                          #{item.id} · {item.patient_code}
                        </span>
                        <Badge variant={statusBadgeVariant(item.status)} className="text-[10px]">
                          {formatStatus(item.status)}
                        </Badge>
                      </div>
                      <p className="truncate text-xs font-semibold text-[#0F172A]">
                        {item.display_name}
                      </p>
                      <div className="flex items-center justify-between text-[11px] text-[#64748B]">
                        <span className="truncate">
                          {item.conditions.length
                            ? item.conditions.map(formatCondition).join(", ")
                            : "Không bệnh nền"}
                        </span>
                        <span className="shrink-0 font-mono">Retry: {item.retry_count}</span>
                      </div>
                    </button>
                  );
                })
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right: Workbench */}
        <div className="lg:col-span-8 space-y-5">
          {loadingDetail ? (
            <div className="space-y-4">
              <Card>
                <CardContent className="p-5 space-y-4">
                  <div className="flex items-center justify-between">
                    <Skeleton className="h-6 w-64" />
                    <Skeleton className="h-8 w-36" />
                  </div>
                  <div className="grid grid-cols-3 gap-4">
                    <Skeleton className="h-14 w-full" />
                    <Skeleton className="h-14 w-full" />
                    <Skeleton className="h-14 w-full" />
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-5 space-y-3">
                  <Skeleton className="h-6 w-56" />
                  {[1, 2, 3, 4].map((i) => (
                    <Skeleton key={i} className="h-10 w-full" />
                  ))}
                </CardContent>
              </Card>
            </div>
          ) : !detail ? (
            <Card>
              <CardContent className="p-8 text-center text-sm text-[#64748B]">
                Chọn một hồ sơ từ hàng đợi bên trái để bắt đầu thẩm định.
              </CardContent>
            </Card>
          ) : (
            <>
              {/* Patient Header Card */}
              <Card className="overflow-hidden">
                <div className="h-[3px] w-full bg-gradient-to-r from-[#0B4F4A] via-[#0D9488] to-[#38BDF8]" />
                <CardHeader className="flex flex-col gap-2 border-b border-[#E6F0EC] pb-3 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <CardTitle className="text-base">
                        Hồ sơ #{detail.meal_plan.id} · {detail.patient.display_name} (
                        {detail.patient.code})
                      </CardTitle>
                      <Badge variant={statusBadgeVariant(currentStatus)}>
                        {formatStatus(currentStatus)}
                      </Badge>
                    </div>
                    <p className="mt-1 text-xs text-[#64748B]">
                      {detail.patient.age} tuổi · {detail.patient.sex === "male" ? "Nam" : "Nữ"} ·{" "}
                      {detail.patient.height_cm} cm · {detail.patient.weight_kg} kg
                    </p>
                  </div>
                  <Button
                    size="sm"
                    variant="outline"
                    className="shrink-0"
                    onClick={() => onViewInResult(detail.meal_plan.id)}
                  >
                    <Eye className="h-3.5 w-3.5" />
                    Xem giao diện Kết quả
                  </Button>
                </CardHeader>
                <CardContent className="grid grid-cols-1 gap-4 pt-4 sm:grid-cols-3 text-xs">
                  <div>
                    <span className="font-semibold uppercase text-[#64748B]">Bệnh lý & Dị ứng</span>
                    <p className="mt-1 font-semibold text-[#0F172A]">
                      {detail.patient.conditions.length
                        ? detail.patient.conditions.map(formatCondition).join(", ")
                        : "Không khai báo"}
                    </p>
                    <p
                      className={cn(
                        "mt-0.5 font-medium",
                        detail.patient.allergens.length > 0 ? "text-[#DC2626]" : "text-[#64748B]"
                      )}
                    >
                      Dị ứng:{" "}
                      {detail.patient.allergens.length
                        ? detail.patient.allergens.map(formatAllergen).join(", ")
                        : "Không có"}
                    </p>
                  </div>
                  <div>
                    <span className="font-semibold uppercase text-[#64748B]">Mục tiêu ngày</span>
                    <p className="mt-1 font-mono font-bold text-[#0B4F4A] text-sm">
                      {formatInt(detail.targets.target_kcal)} kcal
                    </p>
                    <p className="mt-0.5 flex flex-wrap gap-x-1.5 font-mono text-[#64748B]">
                      <span>P {formatNumber(detail.targets.protein_g, 0)}g</span>
                      <span>· F {formatNumber(detail.targets.fat_g, 0)}g</span>
                      <span>· C {formatNumber(detail.targets.carb_g, 0)}g</span>
                      <span className="whitespace-nowrap">
                        · Na ≤ {formatInt(detail.targets.sodium_max_mg)}mg
                      </span>
                    </p>
                  </div>
                  <div>
                    <span className="font-semibold uppercase text-[#64748B]">Sở thích ghi nhận</span>
                    <p className="mt-1 text-[#334155] italic">
                      {detail.patient.preferences_text || "Không có ghi chú"}
                    </p>
                  </div>
                </CardContent>
              </Card>

              {/* Guardrails / Review Note Alert */}
              {(detail.guardrail_events.length > 0 || currentStatus === "needs_human_review") && (
                <Card className="border-[#FDE68A] bg-gradient-to-r from-[#FFFBEB]/95 to-[#FEF3C7]/45">
                  <CardContent className="p-4 space-y-2 text-xs">
                    <p className="flex items-center gap-1.5 font-bold text-[#92400E]">
                      <ShieldAlert className="h-4 w-4" />
                      Lý do cần chuyên gia xem xét
                    </p>
                    {detail.guardrail_events.length > 0 ? (
                      <ul className="space-y-1 text-[#78350F]">
                        {detail.guardrail_events.map((ge) => (
                          <li key={ge.id}>
                            • [{ge.layer.toUpperCase()} / {ge.type}] {ge.reason}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="text-[#78350F]">
                        Thực đơn chưa đạt hết ngưỡng kiểm chứng tự động. Cần chuyên gia kiểm tra kỹ định lượng trước khi phê duyệt.
                      </p>
                    )}
                  </CardContent>
                </Card>
              )}

              {/* Portion Editor Table */}
              <Card>
                <CardHeader className="flex flex-col gap-3 border-b border-[#E6F0EC] pb-3 sm:flex-row sm:items-center sm:justify-between">
                  <div className="min-w-0">
                    <CardTitle className="text-base">Điều chỉnh định lượng khẩu phần</CardTitle>
                    <p className="text-xs text-[#64748B]">
                      Sửa số gram từng món (bước 5g; nhập 0 để bỏ món), sau đó chạy kiểm chứng lại.
                    </p>
                  </div>
                  {hasMenuItems && (
                    <div className="flex items-center gap-2 shrink-0">
                      <Button
                        size="sm"
                        variant="outline"
                        className="whitespace-nowrap"
                        onClick={handleResetRows}
                        disabled={submitting || runningDryRun}
                      >
                        <RotateCcw className="h-3.5 w-3.5" />
                        Đặt lại gốc
                      </Button>
                      <Button
                        size="sm"
                        variant="secondary"
                        className="whitespace-nowrap"
                        onClick={handleDryRun}
                        disabled={runningDryRun || submitting}
                      >
                        <FlaskConical className="h-3.5 w-3.5" />
                        {runningDryRun ? "Đang kiểm chứng..." : "Kiểm chứng lại"}
                      </Button>
                    </div>
                  )}
                </CardHeader>
                <CardContent className="p-4">
                  {!hasMenuItems ? (
                    <p className="rounded-xl bg-[#FEF2F2] p-4 text-xs font-medium text-[#991B1B]">
                      Ca này chưa có món ăn để duyệt (do chưa lập được thực đơn hợp lệ hoặc đã bị chặn/chuyển hướng). Chuyên gia chỉ có thể từ chối và ghi rõ lý do.
                    </p>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs">
                        <thead>
                          <tr className="border-b border-[#DCEAE4] text-[11px] uppercase text-[#64748B]">
                            <th className="py-2 pr-3">Ngày</th>
                            <th className="py-2 pr-3">Bữa</th>
                            <th className="py-2 pr-3">Tên món ăn</th>
                            <th className="py-2 pr-3 text-right">Gốc (g)</th>
                            <th className="py-2 text-right w-40">Điều chỉnh (g)</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-[#EDF4F0]">
                          {editableRows.map((row, idx) => {
                            const markedDelete = row.grams <= 0;
                            const diff = row.grams - row.original_grams;
                            const modified = diff !== 0;
                            return (
                              <tr
                                key={`${row.day}-${row.meal}-${row.food_id}-${idx}`}
                                className={cn(
                                  "transition-colors hover:bg-[#F0FDFA]/55",
                                  markedDelete && "bg-[#FEF2F2]/60"
                                )}
                              >
                                <td className="py-2.5 pr-3 font-mono font-semibold whitespace-nowrap">
                                  Ngày {row.day}
                                </td>
                                <td className="py-2.5 pr-3 text-[#475569] whitespace-nowrap">
                                  {formatMeal(row.meal)}
                                </td>
                                <td className="py-2.5 pr-3">
                                  <span
                                    className={cn(
                                      "font-semibold text-[#0F172A]",
                                      markedDelete && "line-through text-[#B91C1C]"
                                    )}
                                  >
                                    {row.name_vi}
                                  </span>
                                  {markedDelete && (
                                    <Badge variant="danger" className="ml-2 text-[10px]">
                                      Sẽ xóa
                                    </Badge>
                                  )}
                                  {!markedDelete && modified && (
                                    <Badge variant="pending" className="ml-2 font-mono text-[10px]">
                                      {diff > 0 ? `+${diff}g` : `${diff}g`}
                                    </Badge>
                                  )}
                                </td>
                                <td className="py-2.5 pr-3 text-right font-mono text-[#64748B] tabular-nums">
                                  {formatNumber(row.original_grams, 0)}
                                </td>
                                <td className="py-2.5 text-right">
                                  <div className="inline-flex items-center justify-end gap-1">
                                    <button
                                      type="button"
                                      aria-label={`Giảm 5g ${row.name_vi}`}
                                      disabled={!canReviewAction || row.grams <= 0}
                                      onClick={() => handleGramsChange(idx, row.grams - 5)}
                                      className="flex h-8 w-7 items-center justify-center rounded-lg border border-[#D2E4DC] bg-white/90 text-[#475569] transition-colors hover:border-[#14B8A6] hover:bg-[#F0FDFA] hover:text-[#0B4F4A] disabled:opacity-40 cursor-pointer"
                                    >
                                      <Minus className="h-3 w-3" />
                                    </button>
                                    <Input
                                      type="number"
                                      min={0}
                                      max={1000}
                                      step={5}
                                      disabled={!canReviewAction}
                                      value={row.grams}
                                      onChange={(e) => handleGramsChange(idx, e.target.value)}
                                      className="h-8 w-16 px-2 text-right font-mono text-xs tabular-nums"
                                    />
                                    <button
                                      type="button"
                                      aria-label={`Tăng 5g ${row.name_vi}`}
                                      disabled={!canReviewAction || row.grams >= 1000}
                                      onClick={() => handleGramsChange(idx, row.grams + 5)}
                                      className="flex h-8 w-7 items-center justify-center rounded-lg border border-[#D2E4DC] bg-white/90 text-[#475569] transition-colors hover:border-[#14B8A6] hover:bg-[#F0FDFA] hover:text-[#0B4F4A] disabled:opacity-40 cursor-pointer"
                                    >
                                      <Plus className="h-3 w-3" />
                                    </button>
                                  </div>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Dry-run Result & Before/After Comparison */}
              {dryRunResult && (
                <Card
                  className={cn(
                    dryRunResult.is_valid
                      ? "border-[#A7F3D0] bg-[#ECFDF5]/75"
                      : "border-[#FECACA] bg-[#FEF2F2]/75"
                  )}
                >
                  <CardContent className="p-4 space-y-3">
                    <div className="flex items-center justify-between gap-2">
                      <p
                        className={cn(
                          "flex items-center gap-2 text-sm font-bold",
                          dryRunResult.is_valid ? "text-[#065F46]" : "text-[#991B1B]"
                        )}
                      >
                        {dryRunResult.is_valid ? (
                          <>
                            <CheckCircle2 className="h-4.5 w-4.5" />
                            Bản sửa đạt toàn bộ 11 tiêu chí kiểm chứng lâm sàng
                          </>
                        ) : (
                          <>
                            <AlertTriangle className="h-4.5 w-4.5" />
                            Bản sửa còn {dryRunResult.violations.length} vi phạm chưa đạt
                          </>
                        )}
                      </p>
                      {!isDryRunFresh && (
                        <Badge variant="pending">Bạn vừa sửa thêm — hãy kiểm chứng lại</Badge>
                      )}
                    </div>

                    {dryRunResult.violations.length > 0 && (
                      <ul className="space-y-1 text-xs text-[#991B1B]">
                        {dryRunResult.violations.map((v, idx) => (
                          <li key={idx}>
                            • <span className="font-mono font-bold">[{v.code}]</span> {v.message_vi}
                          </li>
                        ))}
                      </ul>
                    )}

                    {/* Before / After Daily Totals */}
                    <div className="overflow-x-auto rounded-xl border border-[#DCEAE4] bg-white/95 p-3">
                      <p className="mb-2 text-[11px] font-bold uppercase text-[#64748B]">
                        Đối chiếu tổng ngày (Trước sửa → Sau sửa)
                      </p>
                      <table className="w-full text-left font-mono text-xs tabular-nums">
                        <thead>
                          <tr className="border-b border-[#EDF4F0] text-[11px] text-[#64748B]">
                            <th className="py-1.5 pr-3">Ngày</th>
                            <th className="py-1.5 pr-3">Kcal</th>
                            <th className="py-1.5 pr-3">Đạm (g)</th>
                            <th className="py-1.5 pr-3">Béo (g)</th>
                            <th className="py-1.5 pr-3">Carb (g)</th>
                            <th className="py-1.5">Natri (mg)</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-[#EDF4F0]">
                          {dryRunResult.daily_totals.map((after) => {
                            const before = detail.daily_totals.find((b) => b.day === after.day);
                            return (
                              <tr key={after.day}>
                                <td className="py-1.5 pr-3 font-bold">Ngày {after.day}</td>
                                <td className="py-1.5 pr-3">
                                  {before ? `${formatInt(before.kcal)} → ` : ""}
                                  <span className="font-bold text-[#0B4F4A]">
                                    {formatInt(after.kcal)}
                                  </span>
                                </td>
                                <td className="py-1.5 pr-3">
                                  {before ? `${formatNumber(before.protein_g, 1)} → ` : ""}
                                  {formatNumber(after.protein_g, 1)}
                                </td>
                                <td className="py-1.5 pr-3">
                                  {before ? `${formatNumber(before.fat_g, 1)} → ` : ""}
                                  {formatNumber(after.fat_g, 1)}
                                </td>
                                <td className="py-1.5 pr-3">
                                  {before ? `${formatNumber(before.carb_g, 1)} → ` : ""}
                                  {formatNumber(after.carb_g, 1)}
                                </td>
                                <td className="py-1.5">
                                  {before ? `${formatInt(before.sodium_mg)} → ` : ""}
                                  {formatInt(after.sodium_mg)}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Decision Panel */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-[#0B4F4A] to-[#14B8A6] text-white shadow-2xs">
                      <Stethoscope className="h-4 w-4" />
                    </span>
                    Quyết định của chuyên gia dinh dưỡng
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                    <div className="space-y-1.5">
                      <Label htmlFor="reviewer_name">Họ tên chuyên gia</Label>
                      <Input
                        id="reviewer_name"
                        value={reviewerName}
                        disabled={!canReviewAction || submitting}
                        onChange={(e) => setReviewerName(e.target.value)}
                      />
                    </div>
                    <div className="space-y-1.5 sm:col-span-2">
                      <Label htmlFor="review_note">Ghi chú chuyên môn (bắt buộc nếu từ chối)</Label>
                      <Textarea
                        id="review_note"
                        className="min-h-[72px]"
                        disabled={!canReviewAction || submitting}
                        value={note}
                        onChange={(e) => setNote(e.target.value)}
                        placeholder="Nhập lời dặn cho người bệnh hoặc lý do từ chối..."
                      />
                    </div>
                  </div>

                  {canReviewAction ? (
                    <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-3 pt-1">
                      <Button
                        type="button"
                        disabled={!hasMenuItems || currentStatus !== "pending_review" || submitting}
                        onClick={() => handleSubmitDecision("approve")}
                      >
                        <CheckCircle2 className="h-4 w-4" />
                        Phê duyệt nguyên bản
                      </Button>

                      <Tooltip delayDuration={150}>
                        <TooltipTrigger asChild>
                          <span className="inline-flex w-full">
                            <Button
                              type="button"
                              variant="secondary"
                              className="w-full"
                              disabled={
                                !hasMenuItems ||
                                !isDryRunFresh ||
                                !dryRunResult?.is_valid ||
                                submitting
                              }
                              onClick={() => handleSubmitDecision("edit")}
                            >
                              <FlaskConical className="h-4 w-4" />
                              Lưu chỉnh sửa & Duyệt
                            </Button>
                          </span>
                        </TooltipTrigger>
                        {(!isDryRunFresh || !dryRunResult?.is_valid) && (
                          <TooltipContent>
                            Hãy bấm &ldquo;Kiểm chứng lại&rdquo; và đảm bảo đạt 11 tiêu chí trước khi lưu bản sửa.
                          </TooltipContent>
                        )}
                      </Tooltip>

                      <Button
                        type="button"
                        variant="destructiveOutline"
                        disabled={submitting}
                        onClick={() => handleSubmitDecision("reject")}
                      >
                        <XCircle className="h-4 w-4" />
                        Từ chối thực đơn
                      </Button>
                    </div>
                  ) : (
                    <p className="rounded-xl bg-[#F8FAF9] p-3 text-xs text-[#64748B]">
                      Hồ sơ này đang ở trạng thái <strong>{formatStatus(currentStatus)}</strong> và đã kết thúc quy trình duyệt.
                    </p>
                  )}

                  {detail.reviews.length > 0 && (
                    <div className="border-t border-[#E6F0EC] pt-3 space-y-2">
                      <p className="text-xs font-bold uppercase text-[#64748B]">
                        Lịch sử thẩm định
                      </p>
                      {detail.reviews.map((r) => (
                        <div
                          key={r.id}
                          className="rounded-xl border border-[#DCEAE4] bg-[#F8FAF9]/90 px-3 py-2 text-xs"
                        >
                          <span className="font-bold text-[#0F172A]">{r.reviewer_name}</span> ·{" "}
                          <span className="font-semibold text-[#0D9488]">{r.decision}</span>
                          {r.note && <p className="mt-0.5 text-[#475569]">{r.note}</p>}
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
