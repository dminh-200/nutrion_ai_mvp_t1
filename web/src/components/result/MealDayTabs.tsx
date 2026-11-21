import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Coffee, Moon, Sun, Utensils } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
  { icon: typeof Sun; headerBg: string; iconBg: string; titleText: string; badgeClass: string }
> = {
  breakfast: {
    icon: Coffee,
    headerBg: "bg-gradient-to-r from-[#FFFBEB]/95 via-[#FEF3C7]/45 to-white/80",
    iconBg: "bg-gradient-to-br from-[#F59E0B] to-[#D97706] text-white",
    titleText: "text-[#92400E]",
    badgeClass: "border-[#FDE68A] bg-white/90 text-[#92400E]",
  },
  lunch: {
    icon: Sun,
    headerBg: "bg-gradient-to-r from-[#F0FDFA]/95 via-[#CCFBF1]/50 to-white/80",
    iconBg: "bg-gradient-to-br from-[#0D9488] to-[#14B8A6] text-white",
    titleText: "text-[#0B4F4A]",
    badgeClass: "border-[#99F6E4] bg-white/90 text-[#0B4F4A]",
  },
  dinner: {
    icon: Moon,
    headerBg: "bg-gradient-to-r from-[#EFF6FF]/95 via-[#E0E7FF]/45 to-white/80",
    iconBg: "bg-gradient-to-br from-[#0284C7] to-[#4F46E5] text-white",
    titleText: "text-[#1E3A8A]",
    badgeClass: "border-[#BFDBFE] bg-white/90 text-[#1E40AF]",
  },
  snack: {
    icon: Utensils,
    headerBg: "bg-gradient-to-r from-[#ECFDF5]/95 via-[#D1FAE5]/50 to-white/80",
    iconBg: "bg-gradient-to-br from-[#059669] to-[#10B981] text-white",
    titleText: "text-[#065F46]",
    badgeClass: "border-[#A7F3D0] bg-white/90 text-[#065F46]",
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
          <p className="text-xs text-[#64748B]">
            Toàn bộ định lượng và chỉ số dinh dưỡng được tính trực tiếp từ cơ sở dữ liệu thực phẩm.
          </p>
        </div>

        {/* Day Selector Pills with Luminous Sliding Indicator */}
        <div className="flex flex-wrap gap-1 rounded-xl border border-[#DCEAE4] bg-[#EFF7F4]/90 p-1">
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
                    className="absolute inset-0 rounded-lg bg-gradient-to-r from-[#0B4F4A] via-[#0D9488] to-[#14B8A6] shadow-[0_4px_12px_rgba(13,148,136,0.28)]"
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

      {/* Meal Cards with Time-of-Day Header Tints */}
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
              <Card
                key={mealCode}
                className="flex flex-col overflow-hidden hover:-translate-y-0.5 hover:border-[#99D5C6] hover:shadow-[0_12px_30px_rgba(11,79,74,0.09)]"
              >
                <CardHeader
                  className={cn(
                    "flex flex-row items-center justify-between border-b border-[#E6F0EC] pb-3",
                    style.headerBg
                  )}
                >
                  <CardTitle className={cn("flex items-center gap-2 text-sm font-bold", style.titleText)}>
                    <span
                      className={cn(
                        "flex h-7 w-7 items-center justify-center rounded-lg shadow-2xs",
                        style.iconBg
                      )}
                    >
                      <Icon className="h-4 w-4" />
                    </span>
                    {formatMeal(mealCode)}
                  </CardTitle>
                  <Badge className={cn("font-mono tabular-nums", style.badgeClass)}>
                    {formatInt(mealKcal)} kcal
                  </Badge>
                </CardHeader>
                <CardContent className="divide-y divide-[#EDF4F0] pt-1">
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
                          <span className="shrink-0 rounded-lg border border-[#CDE6DF] bg-[#F0FDFA] px-2.5 py-0.5 font-mono text-xs font-bold text-[#0B4F4A] tabular-nums">
                            {formatNumber(it.grams, 0)} g
                          </span>
                        </div>

                        {/* Macro proportion micro-strip */}
                        <div
                          className="flex h-1.5 w-full overflow-hidden rounded-full bg-[#EDF2EF]"
                          title={`Đạm ${Math.round((pCal / totCal) * 100)}% · Carb ${Math.round((cCal / totCal) * 100)}% · Béo ${Math.round((fCal / totCal) * 100)}%`}
                        >
                          <div className="bg-[#0D9488]" style={{ width: `${(pCal / totCal) * 100}%` }} />
                          <div className="bg-[#0284C7]" style={{ width: `${(cCal / totCal) * 100}%` }} />
                          <div className="bg-[#F59E0B]" style={{ width: `${(fCal / totCal) * 100}%` }} />
                        </div>

                        <div className="flex flex-wrap items-center gap-1.5 font-mono text-[11px] tabular-nums">
                          <span className="rounded-md border border-[#CCFBF1] bg-[#F0FDFA] px-1.5 py-0.5 font-bold text-[#0B4F4A]">
                            {formatNumber(it.kcal, 1)} kcal
                          </span>
                          <span className="rounded-md border border-[#D1FAE5] bg-[#ECFDF5]/80 px-1.5 py-0.5 text-[#065F46]">
                            Đạm {formatNumber(it.protein_g, 1)}g
                          </span>
                          <span className="rounded-md border border-[#E0F2FE] bg-[#F0F9FF]/80 px-1.5 py-0.5 text-[#0369A1]">
                            Carb {formatNumber(it.carb_g, 1)}g
                          </span>
                          <span className="rounded-md border border-[#FEF3C7] bg-[#FFFBEB]/80 px-1.5 py-0.5 text-[#92400E]">
                            Béo {formatNumber(it.fat_g, 1)}g
                          </span>
                          <span className="text-[#64748B] px-0.5">
                            Xơ {formatNumber(it.fiber_g, 1)}g · Na {formatInt(it.sodium_mg)}mg
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </CardContent>
              </Card>
            );
          })}
        </motion.div>
      </AnimatePresence>

      {/* Bonus 4: Glass Summary Dock */}
      {dayTotal && (
        <div className="glass-surface rounded-2xl border-[#BDE3D8] bg-gradient-to-r from-[#F0FDFA]/92 via-white/88 to-[#E0F2FE]/70 px-4 py-3.5">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex items-center gap-2 shrink-0">
              <span className="h-2.5 w-2.5 rounded-full bg-gradient-to-r from-[#0B4F4A] to-[#14B8A6] shadow-[0_0_8px_rgba(20,184,166,0.6)]" />
              <span className="text-xs font-extrabold uppercase tracking-wide text-[#0B4F4A]">
                Tổng dinh dưỡng Ngày {selectedDay}
              </span>
            </div>
            <div className="grid grid-cols-3 gap-2 sm:grid-cols-7">
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
                  className="rounded-xl border border-[#DCEAE4] bg-white/85 px-2.5 py-1.5 text-center shadow-2xs"
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
