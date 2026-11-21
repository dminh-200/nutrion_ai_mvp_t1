import { useState } from "react";
import { motion } from "framer-motion";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Sector,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ChartTooltip } from "@/components/ui/chart-tooltip";
import { formatInt, formatNumber } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { DailyTotal, NutritionTargets } from "@/types/api";

interface MacroDonutCardProps {
  avgKcal: number;
  avgProtein: number;
  avgFat: number;
  avgCarb: number;
}

const MACRO_COLORS = {
  protein: { solid: "#0D9488", gradId: "macroProteinGrad" },
  carb: { solid: "#0284C7", gradId: "macroCarbGrad" },
  fat: { solid: "#D97706", gradId: "macroFatGrad" },
};

interface ActiveSectorProps {
  cx: number;
  cy: number;
  innerRadius: number;
  outerRadius: number;
  startAngle: number;
  endAngle: number;
  fill: string;
}

function renderActiveSlice(props: unknown) {
  const { cx, cy, innerRadius, outerRadius, startAngle, endAngle, fill } =
    props as ActiveSectorProps;
  return (
    <g>
      <Sector
        cx={cx}
        cy={cy}
        innerRadius={innerRadius - 2}
        outerRadius={outerRadius + 7}
        startAngle={startAngle}
        endAngle={endAngle}
        fill={fill}
        stroke="#FFFFFF"
        strokeWidth={2.5}
      />
    </g>
  );
}

export function MacroDonutCard({
  avgKcal,
  avgProtein,
  avgFat,
  avgCarb,
}: MacroDonutCardProps) {
  const [activeIndex, setActiveIndex] = useState<number | undefined>(undefined);

  const pKcal = Math.round(avgProtein * 4);
  const fKcal = Math.round(avgFat * 9);
  const cKcal = Math.round(avgCarb * 4);
  const totalMacroKcal = Math.max(pKcal + fKcal + cKcal, 1);

  const data = [
    {
      name: "Đạm (Protein)",
      value: pKcal,
      grams: avgProtein,
      color: MACRO_COLORS.protein.solid,
      fill: `url(#${MACRO_COLORS.protein.gradId})`,
    },
    {
      name: "Tinh bột (Carb)",
      value: cKcal,
      grams: avgCarb,
      color: MACRO_COLORS.carb.solid,
      fill: `url(#${MACRO_COLORS.carb.gradId})`,
    },
    {
      name: "Chất béo (Fat)",
      value: fKcal,
      grams: avgFat,
      color: MACRO_COLORS.fat.solid,
      fill: `url(#${MACRO_COLORS.fat.gradId})`,
    },
  ];

  const activeItem = activeIndex !== undefined ? data[activeIndex] : null;
  const activePct = activeItem ? Math.round((activeItem.value / totalMacroKcal) * 100) : null;

  return (
    <Card className="flex flex-col h-full">
      <CardHeader>
        <CardTitle>Tỷ lệ năng lượng đa lượng (trung bình/ngày)</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col justify-between gap-4 pb-6">
        <div className="relative mx-auto h-[232px] w-full max-w-[270px]">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <defs>
                <linearGradient id={MACRO_COLORS.protein.gradId} x1="0" y1="0" x2="1" y2="1">
                  <stop offset="0%" stopColor="#0B4F4A" />
                  <stop offset="100%" stopColor="#14B8A6" />
                </linearGradient>
                <linearGradient id={MACRO_COLORS.carb.gradId} x1="0" y1="0" x2="1" y2="1">
                  <stop offset="0%" stopColor="#0369A1" />
                  <stop offset="100%" stopColor="#38BDF8" />
                </linearGradient>
                <linearGradient id={MACRO_COLORS.fat.gradId} x1="0" y1="0" x2="1" y2="1">
                  <stop offset="0%" stopColor="#D97706" />
                  <stop offset="100%" stopColor="#FBBF24" />
                </linearGradient>
              </defs>
              <Pie
                data={data}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                startAngle={90}
                endAngle={-270}
                innerRadius={64}
                outerRadius={90}
                paddingAngle={2}
                stroke="#FFFFFF"
                strokeWidth={2}
                animationDuration={450}
                animationEasing="ease-out"
                activeIndex={activeIndex}
                activeShape={renderActiveSlice}
                onMouseEnter={(_, idx) => setActiveIndex(idx)}
                onMouseLeave={() => setActiveIndex(undefined)}
              >
                {data.map((entry, idx) => (
                  <Cell
                    key={entry.name}
                    fill={entry.fill}
                    fillOpacity={activeIndex === undefined || activeIndex === idx ? 1 : 0.4}
                    className="transition-opacity duration-150 cursor-pointer"
                  />
                ))}
              </Pie>
            </PieChart>
          </ResponsiveContainer>
          <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center text-center px-4">
            {activeItem && activePct !== null ? (
              <>
                <span
                  className="text-[11px] font-bold uppercase tracking-wide"
                  style={{ color: activeItem.color }}
                >
                  {activeItem.name.replace(/\s*\([^)]*\)$/, "")}
                </span>
                <span className="font-mono text-2xl font-extrabold text-[#0F172A] tabular-nums">
                  {activePct}%
                </span>
                <span className="font-mono text-[10px] font-semibold text-[#64748B] tabular-nums">
                  {formatNumber(activeItem.grams, 1)}g · {formatInt(activeItem.value)} kcal
                </span>
              </>
            ) : (
              <>
                <span className="font-mono text-2xl font-extrabold text-[#0F172A] tabular-nums">
                  {formatInt(avgKcal)}
                </span>
                <span className="text-[11px] font-semibold text-[#64748B]">kcal / ngày</span>
              </>
            )}
          </div>
        </div>

        {/* Synchronized Interactive Legend */}
        <div className="grid grid-cols-3 gap-2 border-t border-[#E6F0EC] pt-3">
          {data.map((item, idx) => {
            const pct = Math.round((item.value / totalMacroKcal) * 100);
            const isHighlighted = activeIndex === idx;
            return (
              <div
                key={item.name}
                onMouseEnter={() => setActiveIndex(idx)}
                onMouseLeave={() => setActiveIndex(undefined)}
                className={cn(
                  "rounded-xl border px-2.5 py-2 transition-all duration-150 cursor-pointer",
                  isHighlighted
                    ? "border-[#14B8A6] bg-[#F0FDFA] shadow-[0_4px_14px_rgba(20,184,166,0.16)] -translate-y-0.5"
                    : "border-[#E6F0EC] bg-white/75 hover:border-[#99D5C6]"
                )}
              >
                <div className="flex items-center gap-1.5">
                  <span
                    className="h-2.5 w-2.5 rounded-full shrink-0"
                    style={{ backgroundColor: item.color }}
                  />
                  <span className="truncate text-[11px] font-semibold text-[#475569]">
                    {item.name.replace(/\s*\([^)]*\)$/, "")}
                  </span>
                </div>
                <p className="mt-1 font-mono text-xs font-bold text-[#0F172A] tabular-nums">
                  {formatNumber(item.grams, 1)}g · {pct}%
                </p>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}

interface ThresholdBarsProps {
  avgKcal: number;
  avgProtein: number;
  avgFat: number;
  avgCarb: number;
  avgSodium: number;
  avgFiber: number;
  targets: Partial<NutritionTargets>;
}

interface BarSpec {
  label: string;
  actualText: string;
  targetText: string;
  pct: number;
  tone: "good" | "warn" | "danger";
  statusLabel: string;
  goodGradient: string;
  goodGlow: string;
  hint?: string;
}

export function ThresholdBars({
  avgKcal,
  avgProtein,
  avgFat,
  avgCarb,
  avgSodium,
  avgFiber,
  targets,
}: ThresholdBarsProps) {
  const targetKcal = Number(targets.target_kcal ?? 0);
  const kcalFloor = Number(targets.kcal_floor ?? 0);
  const targetP = Number(targets.protein_g ?? 0);
  const targetC = Number(targets.carb_g ?? 0);
  const targetF = Number(targets.fat_g ?? 0);
  const sodiumMax = Number(targets.sodium_max_mg ?? 2300);
  const fiberMin = Number(targets.fiber_min_g ?? 20);

  const macroTone = (actual: number, target: number): "good" | "warn" | "danger" => {
    if (target <= 0) return "good";
    const diff = Math.abs(actual - target) / target;
    if (diff > 0.15) return "danger";
    if (diff > 0.1) return "warn";
    return "good";
  };

  const kcalTone = (): "good" | "warn" | "danger" => {
    if (kcalFloor > 0 && avgKcal < kcalFloor) return "danger";
    if (targetKcal <= 0) return "good";
    const diff = Math.abs(avgKcal - targetKcal) / targetKcal;
    if (diff > 0.1) return "danger";
    if (diff > 0.06) return "warn";
    return "good";
  };

  const sodiumTone = (): "good" | "warn" | "danger" => {
    if (avgSodium > sodiumMax) return "danger";
    if (avgSodium > sodiumMax * 0.85) return "warn";
    return "good";
  };

  const fiberTone = (): "good" | "warn" | "danger" => {
    if (fiberMin <= 0) return "good";
    if (avgFiber < fiberMin * 0.85) return "danger";
    if (avgFiber < fiberMin) return "warn";
    return "good";
  };

  const toneLabel = (tone: "good" | "warn" | "danger", kind: "range" | "max" | "min") => {
    if (tone === "good") return "Đạt chuẩn";
    if (tone === "warn") return kind === "max" ? "Sát trần" : "Cận ngưỡng";
    return kind === "max" ? "Vượt ngưỡng" : "Lệch mục tiêu";
  };

  const bars: BarSpec[] = [
    {
      label: "Năng lượng",
      actualText: `${formatInt(avgKcal)}`,
      targetText: `${formatInt(targetKcal)} kcal`,
      pct: targetKcal > 0 ? Math.min(100, (avgKcal / targetKcal) * 100) : 0,
      tone: kcalTone(),
      statusLabel: toneLabel(kcalTone(), "range"),
      goodGradient: "bg-gradient-to-r from-[#0B4F4A] via-[#0D9488] to-[#14B8A6]",
      goodGlow: "shadow-[0_0_10px_rgba(20,184,166,0.35)]",
      hint: kcalFloor > 0 ? `Sàn an toàn ≥ ${formatInt(kcalFloor)} kcal` : undefined,
    },
    {
      label: "Chất đạm (Protein)",
      actualText: `${formatNumber(avgProtein, 1)}`,
      targetText: `${formatNumber(targetP, 1)} g`,
      pct: targetP > 0 ? Math.min(100, (avgProtein / targetP) * 100) : 0,
      tone: macroTone(avgProtein, targetP),
      statusLabel: toneLabel(macroTone(avgProtein, targetP), "range"),
      goodGradient: "bg-gradient-to-r from-[#047857] to-[#10B981]",
      goodGlow: "shadow-[0_0_10px_rgba(16,185,129,0.3)]",
    },
    {
      label: "Tinh bột (Carb)",
      actualText: `${formatNumber(avgCarb, 1)}`,
      targetText: `${formatNumber(targetC, 1)} g`,
      pct: targetC > 0 ? Math.min(100, (avgCarb / targetC) * 100) : 0,
      tone: macroTone(avgCarb, targetC),
      statusLabel: toneLabel(macroTone(avgCarb, targetC), "range"),
      goodGradient: "bg-gradient-to-r from-[#0369A1] to-[#38BDF8]",
      goodGlow: "shadow-[0_0_10px_rgba(56,189,248,0.32)]",
    },
    {
      label: "Chất béo (Fat)",
      actualText: `${formatNumber(avgFat, 1)}`,
      targetText: `${formatNumber(targetF, 1)} g`,
      pct: targetF > 0 ? Math.min(100, (avgFat / targetF) * 100) : 0,
      tone: macroTone(avgFat, targetF),
      statusLabel: toneLabel(macroTone(avgFat, targetF), "range"),
      goodGradient: "bg-gradient-to-r from-[#D97706] to-[#FBBF24]",
      goodGlow: "shadow-[0_0_10px_rgba(245,158,11,0.28)]",
    },
    {
      label: "Natri (Giới hạn tối đa)",
      actualText: `${formatInt(avgSodium)}`,
      targetText: `≤ ${formatInt(sodiumMax)} mg`,
      pct: sodiumMax > 0 ? Math.min(100, (avgSodium / sodiumMax) * 100) : 0,
      tone: sodiumTone(),
      statusLabel: toneLabel(sodiumTone(), "max"),
      goodGradient: "bg-gradient-to-r from-[#0E7490] to-[#22D3EE]",
      goodGlow: "shadow-[0_0_10px_rgba(34,211,238,0.32)]",
    },
    {
      label: "Chất xơ (Tối thiểu)",
      actualText: `${formatNumber(avgFiber, 1)}`,
      targetText: `≥ ${formatNumber(fiberMin, 0)} g`,
      pct: fiberMin > 0 ? Math.min(100, (avgFiber / fiberMin) * 100) : 0,
      tone: fiberTone(),
      statusLabel: toneLabel(fiberTone(), "min"),
      goodGradient: "bg-gradient-to-r from-[#0D9488] to-[#34D399]",
      goodGlow: "shadow-[0_0_10px_rgba(52,211,153,0.32)]",
    },
  ];

  const tonePillClass = {
    good: "bg-[#ECFDF5] text-[#065F46] border-[#A7F3D0]",
    warn: "bg-[#FFFBEB] text-[#92400E] border-[#FDE68A]",
    danger: "bg-[#FFF1F2] text-[#BE123C] border-[#FECDD3]",
  };

  return (
    <Card className="flex flex-col h-full">
      <CardHeader>
        <CardTitle>Đối chiếu ngưỡng dinh dưỡng & an toàn</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col justify-between space-y-3 pb-6">
        {bars.map((bar, idx) => {
          const widthPct = Math.max(4, Math.min(100, bar.pct));
          const barVisual =
            bar.tone === "danger"
              ? "bg-gradient-to-r from-[#BE123C] to-[#F43F5E] shadow-[0_0_10px_rgba(244,63,94,0.32)]"
              : bar.tone === "warn"
                ? "bg-gradient-to-r from-[#D97706] to-[#F59E0B] shadow-[0_0_10px_rgba(245,158,11,0.3)]"
                : `${bar.goodGradient} ${bar.goodGlow}`;
          return (
            <div key={bar.label} className="space-y-1.5">
              <div className="flex items-center justify-between gap-2 text-xs">
                <div className="flex items-center gap-2 min-w-0">
                  <span className="truncate font-semibold text-[#334155]">{bar.label}</span>
                  <span
                    className={cn(
                      "hidden sm:inline-flex shrink-0 rounded-full border px-1.5 py-0 text-[10px] font-semibold",
                      tonePillClass[bar.tone]
                    )}
                  >
                    {bar.statusLabel}
                  </span>
                </div>
                <span className="shrink-0 font-mono font-bold text-[#0F172A] tabular-nums">
                  {bar.actualText}{" "}
                  <span className="font-normal text-[#64748B]">/ {bar.targetText}</span>
                </span>
              </div>
              <div className="h-2.5 w-full overflow-hidden rounded-full bg-[#E9F2EE]">
                <motion.div
                  className={cn("h-full rounded-full", barVisual)}
                  initial={{ width: 0 }}
                  animate={{ width: `${widthPct}%` }}
                  transition={{ duration: 0.45, delay: idx * 0.04, ease: [0.22, 1, 0.36, 1] }}
                />
              </div>
              {bar.hint && <p className="text-[11px] text-[#64748B]">{bar.hint}</p>}
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}

interface DailyEnergyChartProps {
  dailyTotals: DailyTotal[];
  targetKcal: number;
}

export function DailyEnergyChart({ dailyTotals, targetKcal }: DailyEnergyChartProps) {
  if (dailyTotals.length < 2) return null;

  const lowBound = Math.round(targetKcal * 0.9);
  const highBound = Math.round(targetKcal * 1.1);
  const maxDayKcal = Math.max(...dailyTotals.map((d) => d.kcal), targetKcal);
  const yMax = Math.ceil((maxDayKcal * 1.18) / 100) * 100;

  const chartData = dailyTotals.map((d) => {
    const within = targetKcal > 0 ? Math.abs(d.kcal - targetKcal) / targetKcal <= 0.1 : true;
    return {
      name: `Ngày ${d.day}`,
      kcal: Math.round(d.kcal),
      within,
    };
  });

  return (
    <Card>
      <CardHeader className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <CardTitle>Năng lượng theo từng ngày (so với mục tiêu ±10%)</CardTitle>
          <p className="text-xs text-[#64748B]">
            Vùng xanh ngọc biểu thị khoảng đạt chuẩn từ {formatInt(lowBound)} đến {formatInt(highBound)} kcal.
          </p>
        </div>
        <span className="font-mono text-xs font-bold text-[#0B4F4A] tabular-nums">
          Mục tiêu: {formatInt(targetKcal)} kcal/ngày
        </span>
      </CardHeader>
      <CardContent className="h-[235px] pt-2">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData} margin={{ top: 10, right: 16, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="dailyKcalGood" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#14B8A6" />
                <stop offset="100%" stopColor="#0B4F4A" />
              </linearGradient>
              <linearGradient id="dailyKcalWarn" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#FBBF24" />
                <stop offset="100%" stopColor="#D97706" />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E4ECE8" />
            <XAxis
              dataKey="name"
              tick={{ fontSize: 12, fill: "#475569" }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              domain={[0, yMax]}
              tick={{ fontSize: 11, fill: "#64748B" }}
              axisLine={false}
              tickLine={false}
              width={48}
            />
            <Tooltip
              cursor={{ fill: "rgba(20, 184, 166, 0.08)" }}
              content={
                <ChartTooltip
                  unit="kcal"
                  valueFormatter={(val) => `${formatInt(val)} kcal`}
                />
              }
            />
            {targetKcal > 0 && (
              <>
                <ReferenceArea y1={lowBound} y2={highBound} fill="#14B8A6" fillOpacity={0.1} />
                <ReferenceLine
                  y={targetKcal}
                  stroke="#0B4F4A"
                  strokeDasharray="5 4"
                  label={{
                    value: `Mục tiêu ${formatInt(targetKcal)}`,
                    position: "insideTopRight",
                    fill: "#0B4F4A",
                    fontSize: 11,
                  }}
                />
              </>
            )}
            <Bar
              dataKey="kcal"
              name="Năng lượng"
              radius={[8, 8, 0, 0]}
              maxBarSize={52}
              animationDuration={450}
            >
              {chartData.map((entry) => (
                <Cell
                  key={entry.name}
                  fill={entry.within ? "url(#dailyKcalGood)" : "url(#dailyKcalWarn)"}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
