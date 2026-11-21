import { useCallback, useEffect, useMemo, useState } from "react";
import {
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  type ColumnDef,
  type SortingState,
  useReactTable,
} from "@tanstack/react-table";
import { motion } from "framer-motion";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  Activity,
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  CheckCircle2,
  Clock,
  Coins,
  Cpu,
  Download,
  ExternalLink,
  Gauge,
  Search,
  ShieldCheck,
  Stethoscope,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/layout/PageHeader";
import { AnimatedNumber } from "@/components/ui/animated-number";
import { Badge, statusBadgeVariant } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ChartTooltip } from "@/components/ui/chart-tooltip";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input, Label } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { SpotlightCard } from "@/components/ui/spotlight-card";
import { Switch } from "@/components/ui/switch";
import { InfoTip } from "@/components/ui/tooltip";
import { apiClient } from "@/lib/api";
import {
  formatGuardrailType,
  formatInt,
  formatNumber,
  formatStatus,
} from "@/lib/format";
import { STAGGER_CONTAINER, STAGGER_ITEM } from "@/lib/motion";
import { cn } from "@/lib/utils";
import type { DashboardResponse, QueryLogRow } from "@/types/api";

function toIsoDate(d: Date): string {
  return d.toISOString().slice(0, 10);
}

const CONDITION_FILTERS = [
  { code: null, label: "Tất cả" },
  { code: "t2d", label: "Đái tháo đường T2" },
  { code: "htn", label: "Tăng huyết áp" },
  { code: "gout", label: "Gout" },
  { code: "obesity", label: "Béo phì" },
] as const;

export function DashboardPage() {
  const today = useMemo(() => new Date(), []);
  const defaultStart = useMemo(() => {
    const d = new Date(today);
    d.setDate(d.getDate() - 14);
    return toIsoDate(d);
  }, [today]);

  const [startDate, setStartDate] = useState(defaultStart);
  const [endDate, setEndDate] = useState(toIsoDate(today));
  const [condition, setCondition] = useState<string | null>(null);
  const [includeSynthetic, setIncludeSynthetic] = useState(true);

  const [data, setData] = useState<DashboardResponse | null>(null);
  const [loading, setLoading] = useState(false);

  const [globalFilter, setGlobalFilter] = useState("");
  const [sorting, setSorting] = useState<SortingState>([]);
  const [selectedLog, setSelectedLog] = useState<QueryLogRow | null>(null);

  const loadDashboard = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiClient.getDashboard({
        startDate,
        endDate,
        condition,
        includeSynthetic,
      });
      setData(res);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Không thể tải dữ liệu bảng điều khiển.");
    } finally {
      setLoading(false);
    }
  }, [startDate, endDate, condition, includeSynthetic]);

  useEffect(() => {
    loadDashboard();
  }, [loadDashboard]);

  // Tính histogram độ trễ từ mảng latencies thật của backend
  const latencyBins = useMemo(() => {
    const raw = data?.charts.latency_distribution.latencies ?? [];
    if (!raw.length) return [];
    const maxVal = Math.max(...raw);
    const step = maxVal <= 2000 ? 250 : maxVal <= 10000 ? 1000 : 5000;
    const binCount = Math.min(10, Math.max(4, Math.ceil(maxVal / step)));
    const bins = Array.from({ length: binCount }, (_, idx) => {
      const low = idx * step;
      const high = (idx + 1) * step;
      const label =
        high >= 1000
          ? idx === 0
            ? `<${(high / 1000).toFixed(0)}s`
            : `${(low / 1000).toFixed(0)}–${(high / 1000).toFixed(0)}s`
          : `${low}–${high}`;
      return {
        label,
        count: 0,
      };
    });
    for (const v of raw) {
      const idx = Math.min(binCount - 1, Math.floor(v / step));
      bins[idx].count += 1;
    }
    return bins;
  }, [data]);

  const conditionChartData = useMemo(() => {
    const c = data?.charts.condition_distribution;
    if (!c) return [];
    return c.labels.map((label, idx) => ({
      name: label,
      value: c.values[idx] ?? 0,
    }));
  }, [data]);

  const guardrailChartData = useMemo(() => {
    const g = data?.charts.guardrails_by_type;
    if (!g) return [];
    return g.labels.map((label, idx) => ({
      name: label === "Không có" ? "Không có" : formatGuardrailType(label),
      count: g.counts[idx] ?? 0,
    }));
  }, [data]);

  const latencyBarScale = useMemo(() => {
    const p95 = data?.kpis.p95_latency_ms ?? 0;
    return Math.max(p95, 2500);
  }, [data?.kpis.p95_latency_ms]);

  const columns = useMemo<ColumnDef<QueryLogRow>[]>(
    () => [
      {
        accessorKey: "created_at",
        header: "Thời gian",
        cell: (info) => (
          <span className="font-mono text-[11px] text-[#475569] whitespace-nowrap">
            {String(info.getValue())}
          </span>
        ),
      },
      {
        accessorKey: "patient_code",
        header: "Mã BN",
        cell: (info) => (
          <span className="font-mono text-xs font-bold text-[#0B4F4A]">
            {String(info.getValue())}
          </span>
        ),
      },
      {
        accessorKey: "status",
        header: "Trạng thái",
        cell: (info) => {
          const s = String(info.getValue());
          return <Badge variant={statusBadgeVariant(s)}>{formatStatus(s)}</Badge>;
        },
      },
      {
        accessorKey: "latency_ms",
        header: "Độ trễ (ms)",
        cell: (info) => {
          const ms = Number(info.getValue());
          const pct = Math.max(4, Math.min(100, (ms / latencyBarScale) * 100));
          const barColor =
            ms > 5000
              ? "bg-gradient-to-r from-[#E11D48] to-[#F43F5E]"
              : ms > 1500
                ? "bg-gradient-to-r from-[#D97706] to-[#F59E0B]"
                : "bg-gradient-to-r from-[#0D9488] to-[#14B8A6]";
          return (
            <div className="w-24 space-y-1">
              <span className="block font-mono text-xs font-semibold text-[#0F172A] tabular-nums">
                {formatInt(ms)}
              </span>
              <div className="h-1 w-full overflow-hidden rounded-full bg-[#E6F0EC]">
                <div className={cn("h-full rounded-full", barColor)} style={{ width: `${pct}%` }} />
              </div>
            </div>
          );
        },
      },
      {
        accessorKey: "llm_calls",
        header: "LLM",
        cell: (info) => (
          <span className="font-mono text-xs tabular-nums">{String(info.getValue())}</span>
        ),
      },
      {
        id: "tokens",
        header: "Tokens",
        accessorFn: (row) => row.tokens_in + row.tokens_out,
        cell: ({ row, getValue }) => {
          const total = Number(getValue());
          const isMockZero =
            total === 0 && row.original.llm_calls > 0 && !row.original.is_synthetic_log;
          return (
            <span className="font-mono text-xs tabular-nums">
              {formatInt(total)}
              {isMockZero && (
                <span className="ml-1 text-[10px] font-normal text-[#94A3B8]">(mock)</span>
              )}
            </span>
          );
        },
      },
      {
        accessorKey: "is_synthetic_log",
        header: "Nguồn",
        cell: (info) => (
          <Badge variant="secondary" className="text-[10px]">
            {info.getValue() ? "Giả lập" : "Thực tế"}
          </Badge>
        ),
      },
      {
        id: "trace",
        header: "Trace",
        cell: ({ row }) =>
          row.original.trace_url ? (
            <a
              href={row.original.trace_url}
              target="_blank"
              rel="noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="inline-flex items-center gap-1 text-xs font-semibold text-[#0D9488] hover:underline"
            >
              Langfuse <ExternalLink className="h-3 w-3" />
            </a>
          ) : (
            <span className="font-mono text-[11px] text-[#94A3B8]">
              {row.original.trace_id ? row.original.trace_id.slice(0, 8) : "—"}
            </span>
          ),
      },
    ],
    [latencyBarScale]
  );

  const table = useReactTable({
    data: data?.logs ?? [],
    columns,
    state: { globalFilter, sorting },
    onGlobalFilterChange: setGlobalFilter,
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: { pagination: { pageSize: 10 } },
  });

  const kpis = data?.kpis;
  const csvUrl = apiClient.getDashboardCsvUrl({
    startDate,
    endDate,
    condition,
    includeSynthetic,
  });

  const isInitialLoading = loading && !data;

  // Phân bổ 4 trạng thái cho Segmented Health Bar (Bonus 2)
  const statusSegments = useMemo(() => {
    const total = kpis?.total_requests ?? 0;
    if (total <= 0) return [];
    const approved = kpis?.approved_count ?? 0;
    const pending = kpis?.pending_count ?? 0;
    const redirect = kpis?.redirect_count ?? 0;
    const blocked = kpis?.blocked_count ?? 0;
    const other = Math.max(0, total - (approved + pending + redirect + blocked));
    return [
      {
        key: "approved",
        label: "Đã duyệt",
        count: approved,
        pct: (approved / total) * 100,
        bar: "bg-gradient-to-r from-[#059669] to-[#10B981]",
        dot: "bg-[#10B981]",
      },
      {
        key: "pending",
        label: "Chờ duyệt",
        count: pending,
        pct: (pending / total) * 100,
        bar: "bg-gradient-to-r from-[#D97706] to-[#FBBF24]",
        dot: "bg-[#F59E0B]",
      },
      {
        key: "redirect",
        label: "Chuyển bác sĩ",
        count: redirect,
        pct: (redirect / total) * 100,
        bar: "bg-gradient-to-r from-[#0284C7] to-[#38BDF8]",
        dot: "bg-[#0284C7]",
      },
      {
        key: "blocked",
        label: "Bị chặn",
        count: blocked,
        pct: (blocked / total) * 100,
        bar: "bg-gradient-to-r from-[#DC2626] to-[#F43F5E]",
        dot: "bg-[#E11D48]",
      },
      ...(other > 0
        ? [
            {
              key: "other",
              label: "Khác / Từ chối",
              count: other,
              pct: (other / total) * 100,
              bar: "bg-[#94A3B8]",
              dot: "bg-[#94A3B8]",
            },
          ]
        : []),
    ].filter((s) => s.count > 0);
  }, [kpis]);

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="GIÁM SÁT VẬN HÀNH & AN TOÀN"
        title="Bảng điều khiển lâm sàng"
        description="Theo dõi tỷ lệ an toàn, độ trễ xử lý, phân bố bệnh lý và nhật ký truy vấn theo thời gian thực."
        rightSlot={
          <div className="flex flex-wrap items-center gap-2">
            {includeSynthetic && (
              <Badge
                variant="pending"
                className="border-[#FBBF24]/50 bg-[#D97706]/28 text-[#FEF3C7] shadow-2xs"
              >
                Đang gồm dữ liệu log giả lập (seed)
              </Badge>
            )}
            <Button asChild variant="glassDark" size="sm">
              <a href={csvUrl} download="query_logs_export.csv">
                <Download className="h-3.5 w-3.5 text-[#5EEAD4]" />
                Xuất QueryLog (CSV)
              </a>
            </Button>
          </div>
        }
      />

      {/* Filter Toolbar */}
      <Card>
        <CardContent className="p-4 space-y-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3 lg:items-end">
            <div className="space-y-1.5">
              <Label htmlFor="dash-start">Từ ngày</Label>
              <Input
                id="dash-start"
                type="date"
                value={startDate}
                max={endDate}
                onChange={(e) => setStartDate(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="dash-end">Đến ngày</Label>
              <Input
                id="dash-end"
                type="date"
                value={endDate}
                min={startDate}
                onChange={(e) => setEndDate(e.target.value)}
              />
            </div>
            <div className="flex items-center justify-between rounded-xl border border-[#DCEAE4] bg-[#F7FCFA] px-3.5 py-2.5">
              <div>
                <p className="text-xs font-bold text-[#0F172A]">Gồm dữ liệu giả lập (seed)</p>
                <p className="text-[11px] text-[#64748B]">Bật để trình diễn biểu đồ vận hành</p>
              </div>
              <Switch
                checked={includeSynthetic}
                onCheckedChange={setIncludeSynthetic}
                aria-label="Bao gồm dữ liệu giả lập"
              />
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2 border-t border-[#E6F0EC] pt-3">
            <span className="mr-1 text-xs font-semibold text-[#64748B]">Lọc bệnh lý:</span>
            {CONDITION_FILTERS.map((cf) => {
              const active = condition === cf.code;
              return (
                <button
                  key={cf.label}
                  type="button"
                  onClick={() => setCondition(cf.code)}
                  className={cn(
                    "rounded-full border px-3.5 py-1 text-xs font-semibold transition-all cursor-pointer active:scale-[0.98]",
                    active
                      ? "border-transparent bg-gradient-to-r from-[#0D9488] via-[#0EA5A8] to-[#06B6D4] text-white shadow-[0_4px_14px_rgba(6,182,212,0.32)]"
                      : "border-[#CBE4DC] bg-white/85 text-[#334155] hover:border-[#06B6D4] hover:bg-[#ECFEFF]"
                  )}
                >
                  {cf.label}
                </button>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* KPI Group 1: Asymmetric Bento Grid (Dark-Emerald Verifier Ring + Glass KPI Cluster) */}
      <div className="space-y-3">
        <h2 className="text-sm font-bold uppercase tracking-wider text-[#0B4F4A]">
          Chỉ số lâm sàng & An toàn y tế
        </h2>
        {isInitialLoading ? (
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
            <Skeleton className="h-[246px] w-full rounded-2xl lg:col-span-5" />
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:col-span-7">
              <Skeleton className="h-[112px] w-full rounded-2xl sm:col-span-2" />
              <Skeleton className="h-[118px] w-full rounded-2xl" />
              <Skeleton className="h-[118px] w-full rounded-2xl" />
            </div>
          </div>
        ) : (
          <motion.div
            variants={STAGGER_CONTAINER}
            initial="hidden"
            animate="show"
            className="grid grid-cols-1 gap-4 lg:grid-cols-12"
          >
            {/* Left Large Dark-Emerald Signature Card with Large Glowing SVG Ring */}
            <motion.div variants={STAGGER_ITEM} className="lg:col-span-5">
              {(() => {
                const verifierPct = Math.max(
                  0,
                  Math.min(100, kpis?.first_pass_verifier_rate_pct ?? 0)
                );
                const ringR = 52;
                const ringC = 2 * Math.PI * ringR;
                const ringOffset = ringC * (1 - verifierPct / 100);
                return (
                  <SpotlightCard
                    tone="dark"
                    className="dark-emerald-card h-full rounded-2xl text-white"
                  >
                    <div className="h-[3px] w-full bg-gradient-to-r from-[#2DD4BF] via-[#22D3EE] to-[#34D399]" />
                    <div className="flex h-full flex-col justify-between p-5 sm:p-6">
                      <div className="flex flex-col items-start gap-1.5">
                        <span className="inline-flex items-center gap-1.5 rounded-full border border-[#5EEAD4]/35 bg-[#14B8A6]/18 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-[0.12em] text-[#CCFBF1]">
                          <ShieldCheck className="h-3 w-3 text-[#2DD4BF]" />
                          An toàn kiểm chứng
                        </span>
                        <h3 className="flex items-center gap-1.5 text-base font-extrabold text-white">
                          Đạt Verifier lần đầu
                          <InfoTip
                            text="Tỷ lệ thực đơn vượt qua toàn bộ 11 tiêu chí kiểm chứng ngay ở lần đầu tiên mà không cần AI sinh lại."
                            className="text-[#99F6E4]/85 hover:bg-white/15 hover:text-white"
                          />
                        </h3>
                      </div>

                      <div className="my-4 flex flex-col items-center gap-5 sm:flex-row">
                        <div className="relative flex h-[132px] w-[132px] shrink-0 items-center justify-center">
                          <svg viewBox="0 0 132 132" className="h-full w-full -rotate-90">
                            <defs>
                              <linearGradient id="dashVerifierRing" x1="0%" y1="0%" x2="100%" y2="100%">
                                <stop offset="0%" stopColor="#22D3EE" />
                                <stop offset="55%" stopColor="#2DD4BF" />
                                <stop offset="100%" stopColor="#34D399" />
                              </linearGradient>
                            </defs>
                            <circle
                              cx="66"
                              cy="66"
                              r={ringR}
                              fill="none"
                              stroke="rgba(255,255,255,0.14)"
                              strokeWidth="10"
                            />
                            <circle
                              cx="66"
                              cy="66"
                              r={ringR}
                              fill="none"
                              stroke="url(#dashVerifierRing)"
                              strokeWidth="10"
                              strokeLinecap="round"
                              strokeDasharray={ringC}
                              strokeDashoffset={ringOffset}
                              style={{
                                transition: "stroke-dashoffset 550ms cubic-bezier(0.22, 1, 0.36, 1)",
                                filter: "drop-shadow(0 0 10px rgba(34, 211, 238, 0.72))",
                              }}
                            />
                          </svg>
                          <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center text-center">
                            <span className="font-mono text-2xl font-extrabold text-white tabular-nums">
                              <AnimatedNumber
                                value={verifierPct}
                                formatter={(v) => `${formatNumber(v, 1)}%`}
                              />
                            </span>
                            <span className="mt-0.5 text-[10px] font-semibold uppercase tracking-wider text-[#99F6E4]">
                              1st-pass
                            </span>
                          </div>
                        </div>

                        <div className="flex-1 space-y-2.5 text-xs w-full">
                          <div className="rounded-xl border border-white/14 bg-white/[0.07] px-3 py-2">
                            <span className="text-[10.5px] text-[#99F6E4]/85">Vượt 11 tiêu chí ngay lần đầu</span>
                            <p className="mt-0.5 font-semibold text-white">Không cần vòng lặp retry AI</p>
                          </div>
                          <div className="grid grid-cols-2 gap-2">
                            <div className="rounded-xl border border-white/15 bg-white/[0.08] px-2.5 py-2">
                              <span className="block text-[10px] text-[#CCFBF1]/85">Đã duyệt</span>
                              <span className="font-mono text-sm font-extrabold text-[#6EE7B7] tabular-nums">
                                {formatInt(kpis?.approved_count)}
                              </span>
                            </div>
                            <div className="rounded-xl border border-white/15 bg-white/[0.08] px-2.5 py-2">
                              <span className="block text-[10px] text-[#CCFBF1]/85">Bị chặn</span>
                              <span className="font-mono text-sm font-extrabold text-[#FECDD3] tabular-nums">
                                {formatInt(kpis?.blocked_count)}
                              </span>
                            </div>
                          </div>
                        </div>
                      </div>

                      <p className="text-[11px] text-[#CCFBF1]/75">
                        Đo lường độ chính xác của lớp kiểm chứng định lượng &amp; an toàn lâm sàng.
                      </p>
                    </div>
                  </SpotlightCard>
                );
              })()}
            </motion.div>

            {/* Right Glass KPI Cluster (Bento 1-wide + 2-half) */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:col-span-7">
              <motion.div variants={STAGGER_ITEM} className="sm:col-span-2">
                <SpotlightCard className="h-full rounded-2xl border border-white/85 bg-white/78 backdrop-blur-2xl ring-1 ring-[#0D9488]/10 shadow-[inset_0_1px_0_rgba(255,255,255,0.95),0_12px_30px_-6px_rgba(11,79,74,0.1)] transition-all duration-200 hover:-translate-y-0.5 hover:ring-[#06B6D4]/35 hover:shadow-[0_14px_32px_rgba(6,182,212,0.15)]">
                  <div className="h-[3px] w-full bg-gradient-to-r from-[#0D9488] via-[#0EA5A8] to-[#06B6D4]" />
                  <div className="flex flex-col justify-between gap-3 p-5 sm:flex-row sm:items-center">
                    <div>
                      <span className="text-xs font-semibold text-[#475569]">Tổng ca tư vấn</span>
                      <p className="mt-1 font-mono text-3xl font-extrabold text-[#0F172A] tabular-nums">
                        <AnimatedNumber value={kpis?.total_requests ?? 0} formatter={formatInt} />
                      </p>
                      <p className="mt-0.5 text-xs text-[#64748B]">
                        Tổng hợp theo khoảng ngày &amp; bộ lọc bệnh lý hiện tại
                      </p>
                    </div>
                    <div className="flex items-center gap-2.5">
                      <div className="rounded-xl border border-[#D4E8E0] bg-white/80 px-3 py-2 text-right">
                        <span className="block text-[10px] font-semibold uppercase text-[#64748B]">
                          Chờ duyệt
                        </span>
                        <span className="font-mono text-sm font-extrabold text-[#D97706] tabular-nums">
                          {formatInt(kpis?.pending_count)}
                        </span>
                      </div>
                      <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-gradient-to-br from-[#0D9488] to-[#06B6D4] text-white shadow-[0_6px_16px_rgba(6,182,212,0.3)]">
                        <Activity className="h-5 w-5" />
                      </span>
                    </div>
                  </div>
                </SpotlightCard>
              </motion.div>

              <motion.div variants={STAGGER_ITEM}>
                <SpotlightCard className="h-full rounded-2xl border border-white/85 bg-white/78 backdrop-blur-2xl ring-1 ring-[#0D9488]/10 shadow-[inset_0_1px_0_rgba(255,255,255,0.95),0_12px_30px_-6px_rgba(11,79,74,0.1)] transition-all duration-200 hover:-translate-y-0.5 hover:ring-[#10B981]/40 hover:shadow-[0_14px_32px_rgba(16,185,129,0.15)]">
                  <div className="h-[3px] w-full bg-gradient-to-r from-[#047857] to-[#10B981]" />
                  <div className="flex h-full flex-col justify-between p-4 sm:p-5">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs font-semibold text-[#475569]">Tỷ lệ phê duyệt</span>
                      <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-br from-[#059669] to-[#10B981] text-white shadow-[0_4px_12px_rgba(16,185,129,0.26)]">
                        <CheckCircle2 className="h-4 w-4" />
                      </span>
                    </div>
                    <p className="mt-2 font-mono text-2xl font-extrabold text-[#059669] tabular-nums">
                      <AnimatedNumber
                        value={kpis?.approval_rate_pct ?? 0}
                        formatter={(v) => `${formatNumber(v, 1)}%`}
                      />
                    </p>
                    <div className="mt-2 space-y-1">
                      <div className="h-1.5 w-full overflow-hidden rounded-full bg-[#E2F0EA]">
                        <div
                          className="h-full rounded-full bg-gradient-to-r from-[#059669] to-[#34D399]"
                          style={{ width: `${Math.min(100, kpis?.approval_rate_pct ?? 0)}%` }}
                        />
                      </div>
                      <p className="text-[11px] text-[#64748B]">
                        {formatInt(kpis?.approved_count)} ca đã duyệt
                      </p>
                    </div>
                  </div>
                </SpotlightCard>
              </motion.div>

              <motion.div variants={STAGGER_ITEM}>
                <SpotlightCard className="h-full rounded-2xl border border-white/85 bg-white/78 backdrop-blur-2xl ring-1 ring-[#0D9488]/10 shadow-[inset_0_1px_0_rgba(255,255,255,0.95),0_12px_30px_-6px_rgba(11,79,74,0.1)] transition-all duration-200 hover:-translate-y-0.5 hover:ring-[#38BDF8]/45 hover:shadow-[0_14px_32px_rgba(2,132,199,0.15)]">
                  <div className="h-[3px] w-full bg-gradient-to-r from-[#0284C7] to-[#38BDF8]" />
                  <div className="flex h-full flex-col justify-between p-4 sm:p-5">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs font-semibold text-[#475569]">Chuyển hướng bác sĩ</span>
                      <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-br from-[#0284C7] to-[#38BDF8] text-white shadow-[0_4px_12px_rgba(2,132,199,0.26)]">
                        <Stethoscope className="h-4 w-4" />
                      </span>
                    </div>
                    <p className="mt-2 font-mono text-2xl font-extrabold text-[#0284C7] tabular-nums">
                      <AnimatedNumber
                        value={kpis?.redirect_rate_pct ?? 0}
                        formatter={(v) => `${formatNumber(v, 1)}%`}
                      />
                    </p>
                    <div className="mt-2 space-y-1">
                      <div className="h-1.5 w-full overflow-hidden rounded-full bg-[#E2EFF7]">
                        <div
                          className="h-full rounded-full bg-gradient-to-r from-[#0284C7] to-[#38BDF8]"
                          style={{ width: `${Math.min(100, kpis?.redirect_rate_pct ?? 0)}%` }}
                        />
                      </div>
                      <p className="text-[11px] text-[#64748B]">
                        {formatInt(kpis?.redirect_count)} ca nguy cơ cao
                      </p>
                    </div>
                  </div>
                </SpotlightCard>
              </motion.div>
            </div>
          </motion.div>
        )}
      </div>

      {/* KPI Group 2: Performance & Cost (Spotlight Glass Cards) */}
      <div className="space-y-3">
        <h2 className="text-sm font-bold uppercase tracking-wider text-[#475569]">
          Hiệu năng vận hành & Chi phí
        </h2>
        {isInitialLoading ? (
          <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
            {[1, 2, 3, 4].map((i) => (
              <Skeleton key={i} className="h-[108px] w-full rounded-2xl" />
            ))}
          </div>
        ) : (
          <motion.div
            variants={STAGGER_CONTAINER}
            initial="hidden"
            animate="show"
            className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4"
          >
            <motion.div variants={STAGGER_ITEM}>
              <SpotlightCard className="h-full rounded-2xl border border-white/85 bg-white/78 backdrop-blur-2xl ring-1 ring-[#0D9488]/10 shadow-[inset_0_1px_0_rgba(255,255,255,0.95),0_12px_28px_-6px_rgba(11,79,74,0.09)] transition-all duration-200 hover:-translate-y-0.5 hover:ring-[#64748B]/35">
                <div className="h-[3px] w-full bg-gradient-to-r from-[#334155] to-[#64748B]" />
                <div className="p-4">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-semibold text-[#475569]">Độ trễ trung bình</span>
                    <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-br from-[#334155] to-[#64748B] text-white shadow-2xs">
                      <Clock className="h-4 w-4" />
                    </span>
                  </div>
                  <p className="mt-1.5 font-mono text-2xl font-extrabold text-[#0F172A] tabular-nums">
                    <AnimatedNumber value={kpis?.avg_latency_ms ?? 0} formatter={formatInt} />{" "}
                    <span className="text-xs font-semibold text-[#64748B]">ms</span>
                  </p>
                  <p className="mt-1 text-[11px] text-[#64748B]">Trung bình toàn luồng xử lý</p>
                </div>
              </SpotlightCard>
            </motion.div>

            <motion.div variants={STAGGER_ITEM}>
              <SpotlightCard className="h-full rounded-2xl border border-white/85 bg-white/78 backdrop-blur-2xl ring-1 ring-[#0D9488]/10 shadow-[inset_0_1px_0_rgba(255,255,255,0.95),0_12px_28px_-6px_rgba(11,79,74,0.09)] transition-all duration-200 hover:-translate-y-0.5 hover:ring-[#F59E0B]/40">
                <div className="h-[3px] w-full bg-gradient-to-r from-[#D97706] to-[#FBBF24]" />
                <div className="p-4">
                  <div className="flex items-center justify-between gap-2">
                    <span className="inline-flex items-center gap-1 text-xs font-semibold text-[#475569]">
                      Độ trễ P95
                      <InfoTip text="Phân vị thứ 95: 95% số yêu cầu hoàn tất nhanh hơn hoặc bằng ngưỡng thời gian này." />
                    </span>
                    <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-br from-[#D97706] to-[#F59E0B] text-white shadow-[0_4px_10px_rgba(217,119,6,0.24)]">
                      <Gauge className="h-4 w-4" />
                    </span>
                  </div>
                  <p className="mt-1.5 font-mono text-2xl font-extrabold text-[#0F172A] tabular-nums">
                    <AnimatedNumber value={kpis?.p95_latency_ms ?? 0} formatter={formatInt} />{" "}
                    <span className="text-xs font-semibold text-[#64748B]">ms</span>
                  </p>
                  <p className="mt-1 text-[11px] text-[#64748B]">Ngưỡng 95% yêu cầu nhanh nhất</p>
                </div>
              </SpotlightCard>
            </motion.div>

            <motion.div variants={STAGGER_ITEM}>
              <SpotlightCard className="h-full rounded-2xl border border-white/85 bg-white/78 backdrop-blur-2xl ring-1 ring-[#0D9488]/10 shadow-[inset_0_1px_0_rgba(255,255,255,0.95),0_12px_28px_-6px_rgba(11,79,74,0.09)] transition-all duration-200 hover:-translate-y-0.5 hover:ring-[#06B6D4]/45">
                <div className="h-[3px] w-full bg-gradient-to-r from-[#0E7490] to-[#22D3EE]" />
                <div className="p-4">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-semibold text-[#475569]">Tổng token sử dụng</span>
                    <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-br from-[#0E7490] to-[#06B6D4] text-white shadow-[0_4px_10px_rgba(6,182,212,0.24)]">
                      <Cpu className="h-4 w-4" />
                    </span>
                  </div>
                  <p className="mt-1.5 font-mono text-2xl font-extrabold text-[#0F172A] tabular-nums">
                    <AnimatedNumber value={kpis?.total_tokens ?? 0} formatter={formatInt} />
                  </p>
                  <p className="mt-1 text-[11px] text-[#64748B]">Gồm prompt + completion tokens</p>
                </div>
              </SpotlightCard>
            </motion.div>

            <motion.div variants={STAGGER_ITEM}>
              <SpotlightCard className="h-full rounded-2xl border border-white/85 bg-white/78 backdrop-blur-2xl ring-1 ring-[#0D9488]/10 shadow-[inset_0_1px_0_rgba(255,255,255,0.95),0_12px_28px_-6px_rgba(11,79,74,0.09)] transition-all duration-200 hover:-translate-y-0.5 hover:ring-[#10B981]/40">
                <div className="h-[3px] w-full bg-gradient-to-r from-[#059669] to-[#34D399]" />
                <div className="p-4">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-semibold text-[#475569]">Chi phí ước tính</span>
                    <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-br from-[#059669] to-[#10B981] text-white shadow-[0_4px_10px_rgba(5,150,105,0.24)]">
                      <Coins className="h-4 w-4" />
                    </span>
                  </div>
                  <p className="mt-1.5 font-mono text-2xl font-extrabold text-[#0F172A] tabular-nums">
                    $
                    <AnimatedNumber
                      value={kpis?.est_cost_usd ?? 0}
                      formatter={(v) => v.toFixed(4)}
                    />
                  </p>
                  <p className="mt-1 text-[11px] text-[#64748B]">Quy đổi USD theo log mô hình</p>
                </div>
              </SpotlightCard>
            </motion.div>
          </motion.div>
        )}
      </div>

      {/* Bonus 2: Segmented Safety & Status Composition Strip */}
      {!isInitialLoading && statusSegments.length > 0 && (
        <Card>
          <CardContent className="p-4 space-y-2.5">
            <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
              <span className="font-bold text-[#0F172A]">
                Cơ cấu trạng thái an toàn ({formatInt(kpis?.total_requests)} ca)
              </span>
              <div className="flex flex-wrap items-center gap-3 text-[11px]">
                {statusSegments.map((seg) => (
                  <span key={seg.key} className="inline-flex items-center gap-1.5 font-medium text-[#475569]">
                    <span className={cn("h-2 w-2 rounded-full", seg.dot)} />
                    <span>{seg.label}:</span>
                    <span className="font-mono font-bold text-[#0F172A] tabular-nums">
                      {formatNumber(seg.pct, 1)}% ({formatInt(seg.count)})
                    </span>
                  </span>
                ))}
              </div>
            </div>
            <div className="flex h-2.5 w-full gap-0.5 overflow-hidden rounded-full bg-[#E8F0EC] p-0.5">
              {statusSegments.map((seg) => (
                <div
                  key={seg.key}
                  title={`${seg.label}: ${formatInt(seg.count)} ca (${formatNumber(seg.pct, 1)}%)`}
                  className={cn("h-full first:rounded-l-full last:rounded-r-full transition-all duration-300", seg.bar)}
                  style={{ width: `${Math.max(1.5, seg.pct)}%` }}
                />
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* 2x2 Charts Grid */}
      {isInitialLoading ? (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-[325px] w-full rounded-2xl" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          {/* Chart 1: Trend by Date */}
          <Card>
            <CardHeader>
              <CardTitle>Số ca tư vấn theo ngày & kết quả</CardTitle>
            </CardHeader>
            <CardContent className="h-[270px]">
              {data?.charts.trend_by_date.length ? (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={data.charts.trend_by_date}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E4ECE8" />
                    <XAxis
                      dataKey="date"
                      tick={{ fontSize: 11, fill: "#64748B" }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <YAxis
                      tick={{ fontSize: 11, fill: "#64748B" }}
                      width={36}
                      axisLine={false}
                      tickLine={false}
                    />
                    <Tooltip
                      cursor={{ fill: "rgba(20, 184, 166, 0.08)" }}
                      content={<ChartTooltip unit="ca" />}
                    />
                    <Legend wrapperStyle={{ fontSize: "11px" }} />
                    <Bar dataKey="approved" stackId="a" name="Đã duyệt" fill="#10B981" />
                    <Bar dataKey="pending" stackId="a" name="Chờ duyệt" fill="#F59E0B" />
                    <Bar dataKey="redirect" stackId="a" name="Chuyển bác sĩ" fill="#0EA5E9" />
                    <Bar
                      dataKey="blocked"
                      stackId="a"
                      name="Bị chặn"
                      fill="#F43F5E"
                      radius={[4, 4, 0, 0]}
                    />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex h-full items-center justify-center text-xs text-[#64748B]">
                  Chưa có dữ liệu xu hướng theo bộ lọc đã chọn.
                </div>
              )}
            </CardContent>
          </Card>

          {/* Chart 2: Condition Distribution */}
          <Card>
            <CardHeader>
              <CardTitle>Phân bố bệnh lý người bệnh</CardTitle>
            </CardHeader>
            <CardContent className="h-[270px]">
              {conditionChartData.some((d) => d.value > 0) ? (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={conditionChartData} layout="vertical" margin={{ left: 10, right: 16 }}>
                    <defs>
                      <linearGradient id="condGrad0" x1="0" y1="0" x2="1" y2="0">
                        <stop offset="0%" stopColor="#0B4F4A" />
                        <stop offset="100%" stopColor="#14B8A6" />
                      </linearGradient>
                      <linearGradient id="condGrad1" x1="0" y1="0" x2="1" y2="0">
                        <stop offset="0%" stopColor="#059669" />
                        <stop offset="100%" stopColor="#34D399" />
                      </linearGradient>
                      <linearGradient id="condGrad2" x1="0" y1="0" x2="1" y2="0">
                        <stop offset="0%" stopColor="#0284C7" />
                        <stop offset="100%" stopColor="#38BDF8" />
                      </linearGradient>
                      <linearGradient id="condGrad3" x1="0" y1="0" x2="1" y2="0">
                        <stop offset="0%" stopColor="#D97706" />
                        <stop offset="100%" stopColor="#FBBF24" />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#E4ECE8" />
                    <XAxis
                      type="number"
                      tick={{ fontSize: 11, fill: "#64748B" }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <YAxis
                      type="category"
                      dataKey="name"
                      width={132}
                      tick={{ fontSize: 11, fill: "#334155" }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <Tooltip
                      cursor={{ fill: "rgba(20, 184, 166, 0.08)" }}
                      content={<ChartTooltip unit="lượt" />}
                    />
                    <Bar dataKey="value" name="Số lượt" radius={[0, 7, 7, 0]} maxBarSize={28}>
                      {conditionChartData.map((entry, idx) => (
                        <Cell key={entry.name} fill={`url(#condGrad${idx % 4})`} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex h-full items-center justify-center text-xs text-[#64748B]">
                  Chưa có dữ liệu phân bố bệnh lý.
                </div>
              )}
            </CardContent>
          </Card>

          {/* Chart 3: Guardrails by Type */}
          <Card>
            <CardHeader>
              <CardTitle>Sự kiện Guardrails theo loại</CardTitle>
            </CardHeader>
            <CardContent className="h-[270px]">
              {guardrailChartData.some((d) => d.count > 0) ? (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={guardrailChartData} layout="vertical" margin={{ left: 8, right: 16 }}>
                    <defs>
                      <linearGradient id="guardrailBarGrad" x1="0" y1="0" x2="1" y2="0">
                        <stop offset="0%" stopColor="#0B4F4A" />
                        <stop offset="100%" stopColor="#14B8A6" />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#E4ECE8" />
                    <XAxis
                      type="number"
                      tick={{ fontSize: 11, fill: "#64748B" }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <YAxis
                      type="category"
                      dataKey="name"
                      width={176}
                      interval={0}
                      tick={{ fontSize: 11, fill: "#334155" }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <Tooltip
                      cursor={{ fill: "rgba(20, 184, 166, 0.08)" }}
                      content={<ChartTooltip unit="sự kiện" />}
                    />
                    <Bar
                      dataKey="count"
                      name="Số sự kiện"
                      fill="url(#guardrailBarGrad)"
                      radius={[0, 7, 7, 0]}
                      maxBarSize={22}
                    />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex h-full items-center justify-center text-xs text-[#64748B]">
                  Chưa ghi nhận sự kiện guardrail trong khoảng thời gian này.
                </div>
              )}
            </CardContent>
          </Card>

          {/* Chart 4: Latency Distribution */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle>Phân bố độ trễ xử lý</CardTitle>
              <span className="font-mono text-[11px] text-[#64748B]">
                Avg {formatInt(data?.charts.latency_distribution.avg)}ms · P95{" "}
                {formatInt(data?.charts.latency_distribution.p95)}ms
              </span>
            </CardHeader>
            <CardContent className="h-[270px]">
              {latencyBins.length ? (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={latencyBins}>
                    <defs>
                      <linearGradient id="latencyBarGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#38BDF8" />
                        <stop offset="100%" stopColor="#0284C7" />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E4ECE8" />
                    <XAxis
                      dataKey="label"
                      interval={0}
                      tick={{ fontSize: 10, fill: "#64748B" }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <YAxis
                      tick={{ fontSize: 11, fill: "#64748B" }}
                      width={36}
                      axisLine={false}
                      tickLine={false}
                    />
                    <Tooltip
                      cursor={{ fill: "rgba(2, 132, 199, 0.08)" }}
                      content={<ChartTooltip unit="request" />}
                    />
                    <ReferenceLine y={0} stroke="#CBD5E1" />
                    <Bar
                      dataKey="count"
                      name="Số request"
                      fill="url(#latencyBarGrad)"
                      radius={[7, 7, 0, 0]}
                    />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex h-full items-center justify-center text-xs text-[#64748B]">
                  Chưa có dữ liệu độ trễ.
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* QueryLog Table with Inline Mini Latency Bar */}
      <Card className="min-w-0 overflow-hidden">
        <CardHeader className="flex flex-col gap-3 border-b border-[#E6F0EC] pb-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <CardTitle>Nhật ký truy vấn (QueryLog)</CardTitle>
            <p className="text-xs text-[#64748B]">
              Hiển thị {table.getFilteredRowModel().rows.length} bản ghi khớp bộ lọc. Nhấp vào một dòng để xem chi tiết.
            </p>
          </div>
          <div className="relative w-full sm:w-64">
            <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-[#94A3B8]" />
            <Input
              value={globalFilter}
              onChange={(e) => setGlobalFilter(e.target.value)}
              placeholder="Tìm mã BN, trạng thái..."
              className="h-9 bg-white/90 pl-9 pr-8 text-xs"
            />
            {globalFilter && (
              <button
                type="button"
                aria-label="Xóa từ khóa tìm kiếm"
                onClick={() => setGlobalFilter("")}
                className="absolute right-2.5 top-2.5 rounded p-0.5 text-[#94A3B8] hover:text-[#0F172A] cursor-pointer"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}
          </div>
        </CardHeader>
        <CardContent className="p-4">
          {isInitialLoading ? (
            <div className="space-y-2.5">
              {[1, 2, 3, 4, 5].map((i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    {table.getHeaderGroups().map((hg) => (
                      <tr
                        key={hg.id}
                        className="border-b border-[#DCEAE4] text-[11px] uppercase text-[#64748B]"
                      >
                        {hg.headers.map((header) => {
                          const sorted = header.column.getIsSorted();
                          return (
                            <th key={header.id} className="py-2 pr-3">
                              <button
                                type="button"
                                onClick={header.column.getToggleSortingHandler()}
                                className="inline-flex items-center gap-1 font-semibold hover:text-[#0F172A] cursor-pointer"
                              >
                                {flexRender(header.column.columnDef.header, header.getContext())}
                                {sorted === "asc" ? (
                                  <ArrowUp className="h-3 w-3 text-[#0D9488]" />
                                ) : sorted === "desc" ? (
                                  <ArrowDown className="h-3 w-3 text-[#0D9488]" />
                                ) : (
                                  <ArrowUpDown className="h-3 w-3 opacity-45" />
                                )}
                              </button>
                            </th>
                          );
                        })}
                      </tr>
                    ))}
                  </thead>
                  <tbody className="divide-y divide-[#EDF4F0]">
                    {table.getRowModel().rows.length ? (
                      table.getRowModel().rows.map((row) => (
                        <tr
                          key={row.id}
                          onClick={() => setSelectedLog(row.original)}
                          className="transition-colors hover:bg-[#F0FDFA]/75 cursor-pointer"
                        >
                          {row.getVisibleCells().map((cell) => (
                            <td key={cell.id} className="py-2.5 pr-3">
                              {flexRender(cell.column.columnDef.cell, cell.getContext())}
                            </td>
                          ))}
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={columns.length} className="py-6 text-center text-[#64748B]">
                          Không có bản ghi phù hợp.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>

              <div className="mt-4 flex items-center justify-between border-t border-[#E6F0EC] pt-3 text-xs text-[#64748B]">
                <span className="font-mono">
                  Trang {table.getState().pagination.pageIndex + 1} /{" "}
                  {Math.max(1, table.getPageCount())}
                </span>
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={!table.getCanPreviousPage()}
                    onClick={() => table.previousPage()}
                  >
                    Trước
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={!table.getCanNextPage()}
                    onClick={() => table.nextPage()}
                  >
                    Sau
                  </Button>
                </div>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* Quick Preview Dialog for QueryLog Row */}
      <Dialog open={selectedLog !== null} onOpenChange={(o) => !o && setSelectedLog(null)}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Chi tiết truy vấn #{selectedLog?.id}</DialogTitle>
            <DialogDescription>
              Bản ghi thực thi cho mã bệnh nhân {selectedLog?.patient_code}.
            </DialogDescription>
          </DialogHeader>
          {selectedLog && (
            <div className="space-y-4 text-xs">
              <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-[#DCEAE4] bg-[#F7FCFA] p-3">
                <div>
                  <span className="text-[11px] font-semibold uppercase text-[#64748B]">Trạng thái</span>
                  <div className="mt-1">
                    <Badge variant={statusBadgeVariant(selectedLog.status)}>
                      {formatStatus(selectedLog.status)}
                    </Badge>
                  </div>
                </div>
                <div className="text-right">
                  <span className="text-[11px] font-semibold uppercase text-[#64748B]">Thời gian</span>
                  <p className="mt-1 font-mono font-semibold text-[#0F172A]">
                    {selectedLog.created_at}
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                <div className="rounded-xl border border-[#DCEAE4] p-3">
                  <span className="text-[11px] font-semibold uppercase text-[#64748B]">Độ trễ</span>
                  <p className="mt-1 font-mono text-sm font-bold text-[#0F172A]">
                    {formatInt(selectedLog.latency_ms)} ms
                  </p>
                </div>
                <div className="rounded-xl border border-[#DCEAE4] p-3">
                  <span className="text-[11px] font-semibold uppercase text-[#64748B]">LLM Calls</span>
                  <p className="mt-1 font-mono text-sm font-bold text-[#0F172A]">
                    {selectedLog.llm_calls} (Retry {selectedLog.retry_count})
                  </p>
                </div>
                <div className="col-span-2 sm:col-span-1 rounded-xl border border-[#DCEAE4] p-3">
                  <span className="text-[11px] font-semibold uppercase text-[#64748B]">Chi phí</span>
                  <p className="mt-1 font-mono text-sm font-bold text-[#0B4F4A]">
                    ${selectedLog.est_cost_usd.toFixed(5)}
                  </p>
                </div>
              </div>

              <div className="rounded-xl border border-[#DCEAE4] p-3 space-y-1.5">
                <div className="flex justify-between font-mono">
                  <span className="text-[#64748B]">Tokens vào (Prompt):</span>
                  <span className="font-bold text-[#0F172A]">{formatInt(selectedLog.tokens_in)}</span>
                </div>
                <div className="flex justify-between font-mono">
                  <span className="text-[#64748B]">Tokens ra (Completion):</span>
                  <span className="font-bold text-[#0F172A]">{formatInt(selectedLog.tokens_out)}</span>
                </div>
                {selectedLog.tokens_in + selectedLog.tokens_out === 0 &&
                  selectedLog.llm_calls > 0 &&
                  !selectedLog.is_synthetic_log && (
                    <p className="pt-1 text-[11px] text-[#64748B] italic">
                      Bản ghi chạy ở chế độ mock nên bộ đếm token thực tế bằng 0.
                    </p>
                  )}
              </div>

              {selectedLog.violation_codes && (
                <div className="rounded-xl border border-[#FDE68A] bg-[#FFFBEB] p-3">
                  <span className="font-bold uppercase text-[#92400E]">Mã vi phạm ghi nhận:</span>
                  <p className="mt-1 font-mono text-[#78350F]">{selectedLog.violation_codes}</p>
                </div>
              )}

              <div className="flex items-center justify-between border-t border-[#E6F0EC] pt-3">
                <span className="font-mono text-[11px] text-[#64748B]">
                  Session: {selectedLog.session_id}
                </span>
                {selectedLog.trace_url && (
                  <Button asChild size="sm" variant="outline">
                    <a href={selectedLog.trace_url} target="_blank" rel="noreferrer">
                      Mở Langfuse <ExternalLink className="h-3.5 w-3.5" />
                    </a>
                  </Button>
                )}
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
