import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Clock, Coffee, Moon, Sun, Utensils } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { SpotlightCard } from "@/components/ui/spotlight-card";
import { formatInt, formatMeal, formatNumber } from "@/lib/format";
import { PAGE_TRANSITION, TAB_SPRING } from "@/lib/motion";
import { cn } from "@/lib/utils";
import type { DailyTotal, MealItem } from "@/types/api";

interface MealDayTabsProps {
  items: MealItem[];
  dailyTotals: DailyTotal[];
}

const MEAL_ORDER = ["breakfast", "lunch", "dinner", "snack"] as const;

const MEAL_STYLES: Record<
  string,
  {
    icon: typeof Sun;
    suggestedTime: string;
    topBar: string;
    headerBg: string;
    iconBg: string;
    titleText: string;
    timeBadge: string;
    badgeClass: string;
  }
> = {
  breakfast: {
    icon: Coffee,
    suggestedTime: "07:00",
    topBar: "bg-gradient-to-r from-[#F59E0B] via-[#FBBF24] to-[#FB923C]",
    headerBg: "bg-gradient-to-r from-[#FEF3C7]/85 via-[#FFFBEB]/75 to-white/60",
    iconBg: "bg-gradient-to-br from-[#F59E0B] to-[#D97706] text-white shadow-[0_4px_12px_rgba(217,119,6,0.28)]",
    titleText: "text-[#92400E]",
    timeBadge: "border-[#FCD34D] bg-white/85 text-[#B45309]",
    badgeClass: "border-[#FDE68A] bg-white/95 text-[#92400E]",
  },
  lunch: {
    icon: Sun,
    suggestedTime: "12:00",
    topBar: "bg-gradient-to-r from-[#0D9488] via-[#14B8A6] to-[#06B6D4]",
    headerBg: "bg-gradient-to-r from-[#CCFBF1]/85 via-[#ECFEFF]/75 to-white/60",
    iconBg: "bg-gradient-to-br from-[#0D9488] to-[#06B6D4] text-white shadow-[0_4px_12px_rgba(6,182,212,0.28)]",
    titleText: "text-[#0B4F4A]",
    timeBadge: "border-[#5EEAD4] bg-white/85 text-[#0F766E]",
    badgeClass: "border-[#99F6E4] bg-white/95 text-[#0B4F4A]",
  },
  dinner: {
    icon: Moon,
    suggestedTime: "18:30",
    topBar: "bg-gradient-to-r from-[#0284C7] via-[#3B82F6] to-[#6366F1]",
    headerBg: "bg-gradient-to-r from-[#DBEAFE]/85 via-[#E0E7FF]/70 to-white/60",
    iconBg: "bg-gradient-to-br from-[#0284C7] to-[#4F46E5] text-white shadow-[0_4px_12px_rgba(59,130,246,0.28)]",
    titleText: "text-[#1E3A8A]",
    timeBadge: "border-[#93C5FD] bg-white/85 text-[#1D4ED8]",
    badgeClass: "border-[#BFDBFE] bg-white/95 text-[#1E40AF]",
  },
  snack: {
    icon: Utensils,
    suggestedTime: "15:30",
    topBar: "bg-gradient-to-r from-[#059669] via-[#10B981] to-[#34D399]",
    headerBg: "bg-gradient-to-r from-[#D1FAE5]/85 via-[#ECFDF5]/75 to-white/60",
    iconBg: "bg-gradient-to-br from-[#059669] to-[#10B981] text-white shadow-[0_4px_12px_rgba(16,185,129,0.28)]",
    titleText: "text-[#065F46]",
    timeBadge: "border-[#6EE7B7] bg-white/85 text-[#047857]",
    badgeClass: "border-[#A7F3D0] bg-white/95 text-[#065F46]",
  },
};

export function MealDayTabs({ items, dailyTotals }: MealDayTabsProps) {
  const days = Array.from(new Set(items.map((it) => it.day))).sort((a, b) => a - b);
  const [selectedDay, setSelectedDay] = useState<number>(days[0] ?? 1);

  useEffect(() => {
    if (days.length > 0 && !days.includes(selectedDay)) {
      setSelectedDay(days[0]);
    }
  }, [days, selectedDay]);

  if (!items.length) return null;

  const dayItems = items.filter((it) => it.day === selectedDay);
  const dayTotal = dailyTotals.find((d) => d.day === selectedDay);

  const mealGroups = MEAL_ORDER.map((mealCode) => ({
    mealCode,
    mealItems: dayItems.filter((it) => it.meal === mealCode),
  })).filter((g) => g.mealItems.length > 0);

  const gridColsClass =
    mealGroups.length === 1
      ? "grid-cols-1"
      : mealGroups.length === 3
        ? "grid-cols-1 lg:grid-cols-3"
        : "grid-cols-1 lg:grid-cols-2";

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-lg font-bold text-[#0F172A]">Chi tiết thực đơn từng ngày</h2>
          <p className="text-xs text-[#475569]">
            Toàn bộ định lượng và chỉ số dinh dưỡng được tính trực tiếp từ cơ sở dữ liệu thực phẩm.
          </p>
        </div>

        {/* Day Selector Pills with Luminous Sliding Indicator */}
        <div className="flex flex-wrap gap-1 rounded-xl border border-white/85 bg-white/75 backdrop-blur-xl p-1 ring-1 ring-[#0D9488]/12 shadow-2xs">
          {days.map((d) => {
            const dt = dailyTotals.find((x) => x.day === d);
            const active = selectedDay === d;
            return (
              <button
                key={d}
                type="button"
                onClick={() => setSelectedDay(d)}
                className={cn(
                  "relative rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors cursor-pointer tabular-nums",
                  active ? "text-white" : "text-[#475569] hover:text-[#0B4F4A]"
                )}
              >
                {active && (
                  <motion.span
                    layoutId="meal-day-pill"
                    transition={TAB_SPRING}
                    className="absolute inset-0 rounded-lg bg-gradient-to-r from-[#0D9488] via-[#0EA5A8] to-[#06B6D4] shadow-[0_4px_14px_rgba(6,182,212,0.34)]"
                  />
                )}
                <span className="relative z-10">
                  Ngày {d}
                  {dt ? ` · ${formatInt(dt.kcal)} kcal` : ""}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Meal Cards with Time-of-Day Strips, Suggested Hours & Spotlight */}
      <AnimatePresence mode="wait">
        <motion.div
          key={selectedDay}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -4 }}
          transition={PAGE_TRANSITION}
          className={cn("grid gap-4", gridColsClass)}
        >
          {mealGroups.map(({ mealCode, mealItems }) => {
            const style = MEAL_STYLES[mealCode] ?? MEAL_STYLES.snack;
            const Icon = style.icon;
            const mealKcal = mealItems.reduce((acc, it) => acc + it.kcal, 0);

            return (
              <SpotlightCard
                key={mealCode}
                className="flex flex-col rounded-2xl border border-white/85 bg-white/78 backdrop-blur-2xl ring-1 ring-[#0D9488]/10 shadow-[inset_0_1px_0_rgba(255,255,255,0.95),0_12px_32px_-4px_rgba(11,79,74,0.1)] transition-all duration-200 hover:-translate-y-0.5 hover:ring-[#14B8A6]/35 hover:shadow-[0_16px_34px_rgba(11,79,74,0.14)]"
              >
                <div className={cn("h-[3.5px] w-full", style.topBar)} />
                <CardHeader
                  className={cn(
                    "flex flex-row items-center justify-between gap-2 border-b border-[#DCECE6] py-3.5",
                    style.headerBg
                  )}
                >
                  <CardTitle className={cn("flex items-center gap-2 text-sm font-bold", style.titleText)}>
                    <span
                      className={cn(
                        "flex h-7.5 w-7.5 items-center justify-center rounded-lg",
                        style.iconBg
                      )}
                    >
                      <Icon className="h-4 w-4" />
                    </span>
                    <div className="flex flex-wrap items-center gap-1.5">
                      <span>{formatMeal(mealCode)}</span>
                      <span
                        className={cn(
                          "inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 font-mono text-[10.5px] font-bold tabular-nums",
                          style.timeBadge
                        )}
                      >
                        <Clock className="h-2.5 w-2.5" />
                        {style.suggestedTime}
                      </span>
                    </div>
                  </CardTitle>
                  <Badge className={cn("font-mono tabular-nums shadow-2xs", style.badgeClass)}>
                    {formatInt(mealKcal)} kcal
                  </Badge>
                </CardHeader>
                <CardContent className="divide-y divide-[#E4F0EC] pt-1">
                  {mealItems.map((it, idx) => {
                    const pCal = Math.max(0, it.protein_g * 4);
                    const cCal = Math.max(0, it.carb_g * 4);
                    const fCal = Math.max(0, it.fat_g * 9);
                    const totCal = Math.max(pCal + cCal + fCal, 1);

                    return (
                      <div
                        key={`${it.food_id}-${idx}`}
                        className="flex flex-col gap-2 py-3 first:pt-2.5 last:pb-1"
                      >
                        <div className="flex items-start justify-between gap-2.5">
                          <span className="text-sm font-semibold text-[#0F172A] leading-snug">
                            {it.name_vi}
                          </span>
                          <span className="shrink-0 rounded-lg border border-[#BCE5DA] bg-[#ECFEFF]/90 px-2.5 py-0.5 font-mono text-xs font-bold text-[#0B4F4A] tabular-nums">
                            {formatNumber(it.grams, 0)} g
                          </span>
                        </div>

                        {/* Macro proportion micro-strip */}
                        <div
                          className="flex h-1.5 w-full overflow-hidden rounded-full bg-[#E4EFEA]"
                          title={`Đạm ${Math.round((pCal / totCal) * 100)}% · Carb ${Math.round((cCal / totCal) * 100)}% · Béo ${Math.round((fCal / totCal) * 100)}%`}
                        >
                          <div className="bg-[#0D9488]" style={{ width: `${(pCal / totCal) * 100}%` }} />
                          <div className="bg-[#0284C7]" style={{ width: `${(cCal / totCal) * 100}%` }} />
                          <div className="bg-[#F59E0B]" style={{ width: `${(fCal / totCal) * 100}%` }} />
                        </div>

                        <div className="flex flex-wrap items-center gap-1.5 font-mono text-[11px] tabular-nums">
                          <span className="rounded-md border border-[#99F6E4] bg-[#F0FDFA] px-1.5 py-0.5 font-bold text-[#0B4F4A]">
                            {formatNumber(it.kcal, 1)} kcal
                          </span>
                          <span className="rounded-md border border-[#D1FAE5] bg-[#ECFDF5]/85 px-1.5 py-0.5 text-[#065F46]">
                            Đạm {formatNumber(it.protein_g, 1)}g
                          </span>
                          <span className="rounded-md border border-[#E0F2FE] bg-[#F0F9FF]/85 px-1.5 py-0.5 text-[#0369A1]">
                            Carb {formatNumber(it.carb_g, 1)}g
                          </span>
                          <span className="rounded-md border border-[#FEF3C7] bg-[#FFFBEB]/85 px-1.5 py-0.5 text-[#92400E]">
                            Béo {formatNumber(it.fat_g, 1)}g
                          </span>
                          <span className="text-[#475569] px-0.5">
                            Xơ {formatNumber(it.fiber_g, 1)}g · Na {formatInt(it.sodium_mg)}mg
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </CardContent>
              </SpotlightCard>
            );
          })}
        </motion.div>
      </AnimatePresence>

      {/* Luminous Glass Summary Dock */}
      {dayTotal && (
        <div className="glass-surface overflow-hidden rounded-2xl px-4 py-3.5">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div className="inline-flex items-center gap-2 self-start rounded-xl bg-gradient-to-r from-[#042F2E] to-[#0F766E] px-3 py-1.5 text-white shadow-[0_4px_14px_rgba(4,47,46,0.2)] lg:self-auto shrink-0">
              <span className="h-2 w-2 rounded-full bg-[#2DD4BF] shadow-[0_0_8px_rgba(45,212,191,0.9)]" />
              <span className="text-xs font-extrabold uppercase tracking-wide">
                Tổng Ngày {selectedDay}
              </span>
            </div>
            <div className="grid grid-cols-3 gap-2 sm:grid-cols-7 flex-1 lg:max-w-4xl">
              {[
                { label: "Năng lượng", val: `${formatInt(dayTotal.kcal)} kcal`, tone: "text-[#0B4F4A]" },
                { label: "Đạm", val: `${formatNumber(dayTotal.protein_g, 1)}g`, tone: "text-[#047857]" },
                { label: "Tinh bột", val: `${formatNumber(dayTotal.carb_g, 1)}g`, tone: "text-[#0369A1]" },
                { label: "Chất béo", val: `${formatNumber(dayTotal.fat_g, 1)}g`, tone: "text-[#B45309]" },
                { label: "Chất xơ", val: `${formatNumber(dayTotal.fiber_g, 1)}g`, tone: "text-[#0D9488]" },
                { label: "Đường", val: `${formatNumber(dayTotal.sugar_g, 1)}g`, tone: "text-[#475569]" },
                { label: "Natri", val: `${formatInt(dayTotal.sodium_mg)}mg`, tone: "text-[#0E7490]" },
              ].map((m) => (
                <div
                  key={m.label}
                  className="rounded-xl border border-white/90 bg-white/82 px-2.5 py-1.5 text-center ring-1 ring-[#0D9488]/10 shadow-2xs"
                >
                  <span className="block text-[10px] font-semibold uppercase text-[#64748B]">
                    {m.label}
                  </span>
                  <span className={cn("font-mono text-xs font-extrabold tabular-nums", m.tone)}>
                    {m.val}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
