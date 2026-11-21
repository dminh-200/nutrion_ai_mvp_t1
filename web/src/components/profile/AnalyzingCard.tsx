import { useEffect, useState } from "react";
import {
  BookOpen,
  CheckCircle2,
  Cpu,
  ShieldCheck,
  Sparkles,
  UtensilsCrossed,
} from "lucide-react";
import { SpotlightCard } from "@/components/ui/spotlight-card";
import { cn } from "@/lib/utils";

const PIPELINE_STATIONS = [
  {
    id: 1,
    short: "Trạm 1",
    title: "Sàng lọc an toàn",
    desc: "Kiểm tra nguy cơ cao & bảo vệ đầu vào",
    icon: ShieldCheck,
  },
  {
    id: 2,
    short: "Trạm 2",
    title: "Phân loại & RAG",
    desc: "Tính mục tiêu & tra cứu hướng dẫn BYT/WHO",
    icon: BookOpen,
  },
  {
    id: 3,
    short: "Trạm 3",
    title: "Tối ưu thực đơn",
    desc: "Chọn món Việt & cân chỉnh định lượng bằng code",
    icon: UtensilsCrossed,
  },
  {
    id: 4,
    short: "Trạm 4",
    title: "Kiểm chứng 11 tiêu chí",
    desc: "Xác thực an toàn & tổng hợp giải trình trích nguồn",
    icon: CheckCircle2,
  },
] as const;

export function AnalyzingCard({ patientCode }: { patientCode: string }) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const id = window.setInterval(() => {
      setElapsed((prev) => prev + 1);
    }, 1000);
    return () => window.clearInterval(id);
  }, []);

  // Luân phiên nhịp sáng nhẹ qua 4 trạm để trực quan hóa pipeline đồng bộ (không giả mạo % tiến độ)
  const pulseIdx = Math.floor(elapsed / 2) % PIPELINE_STATIONS.length;

  return (
    <SpotlightCard
      tone="dark"
      className="dark-emerald-card rounded-2xl text-white"
    >
      {/* Top luminous energy rail */}
      <div className="relative h-1 w-full overflow-hidden bg-white/10">
        <div className="energy-beam absolute inset-y-0 w-1/3 rounded-full bg-gradient-to-r from-transparent via-[#22D3EE] to-[#34D399] shadow-[0_0_16px_rgba(34,211,238,0.85)]" />
      </div>

      <div className="p-6 sm:p-8">
        {/* Header + Digital Mono Clock */}
        <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-4">
            <div className="relative flex h-13 w-13 shrink-0 items-center justify-center rounded-2xl border border-[#5EEAD4]/40 bg-gradient-to-br from-[#0D9488] to-[#06B6D4] text-white shadow-[0_0_26px_rgba(6,182,212,0.45)]">
              <span className="absolute inset-0 animate-ping rounded-2xl bg-[#22D3EE]/30 [animation-duration:2.2s]" />
              <Cpu className="relative h-6 w-6" />
            </div>
            <div>
              <div className="inline-flex items-center gap-1.5 rounded-full border border-[#5EEAD4]/35 bg-[#14B8A6]/18 px-2.5 py-0.5 text-[10.5px] font-bold uppercase tracking-[0.12em] text-[#CCFBF1]">
                <Sparkles className="h-3 w-3 text-[#2DD4BF]" />
                <span>AI Clinical Engine · Hồ sơ {patientCode}</span>
              </div>
              <h3 className="mt-1.5 text-lg sm:text-xl font-extrabold tracking-tight text-white">
                Đang vận hành quy trình xây dựng &amp; kiểm chứng thực đơn
              </h3>
            </div>
          </div>

          {/* Luminous Digital Mono Clock */}
          <div className="inline-flex items-center gap-3 self-start rounded-2xl border border-[#5EEAD4]/35 bg-[#031F1E]/75 px-4 py-2.5 backdrop-blur-md shadow-[inset_0_1px_0_rgba(255,255,255,0.12),0_0_24px_rgba(34,211,238,0.2)] sm:self-auto">
            <span className="relative flex h-2.5 w-2.5">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[#34D399] opacity-75" />
              <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-[#2DD4BF]" />
            </span>
            <div className="leading-none">
              <span className="block text-[9.5px] font-bold uppercase tracking-widest text-[#99F6E4]/75">
                Thời gian xử lý
              </span>
              <span className="mt-0.5 block font-mono text-xl font-extrabold tracking-wider text-white tabular-nums">
                {String(Math.floor(elapsed / 60)).padStart(2, "0")}:
                {String(elapsed % 60).padStart(2, "0")}
              </span>
            </div>
          </div>
        </div>

        {/* 4-Station Pipeline Visualizer with Energy Beam */}
        <div className="relative mt-7">
          {/* Desktop horizontal beam track connecting the 4 stations */}
          <div
            aria-hidden="true"
            className="pointer-events-none absolute left-[12%] right-[12%] top-7 hidden h-[3px] overflow-hidden rounded-full bg-white/15 md:block"
          >
            <div className="energy-beam h-full w-2/5 rounded-full bg-gradient-to-r from-transparent via-[#22D3EE] to-[#34D399] shadow-[0_0_14px_rgba(34,211,238,0.9)]" />
          </div>

          <div className="relative grid grid-cols-1 gap-3 md:grid-cols-4 md:gap-4">
            {PIPELINE_STATIONS.map((st, idx) => {
              const Icon = st.icon;
              const isPulsing = idx === pulseIdx;
              return (
                <div
                  key={st.id}
                  className={cn(
                    "relative flex flex-row items-center gap-3.5 rounded-2xl border p-4 backdrop-blur-md transition-all duration-300 md:flex-col md:items-center md:text-center",
                    isPulsing
                      ? "border-[#5EEAD4]/65 bg-white/14 shadow-[0_0_28px_rgba(34,211,238,0.22),inset_0_1px_0_rgba(255,255,255,0.22)]"
                      : "border-white/14 bg-white/[0.06]"
                  )}
                >
                  <div className="relative flex h-12 w-12 shrink-0 items-center justify-center">
                    {isPulsing && (
                      <span className="absolute inset-0 animate-ping rounded-2xl bg-[#22D3EE]/35 [animation-duration:1.8s]" />
                    )}
                    <div
                      className={cn(
                        "relative flex h-11 w-11 items-center justify-center rounded-xl border transition-all duration-300",
                        isPulsing
                          ? "border-[#99F6E4]/70 bg-gradient-to-br from-[#0D9488] to-[#06B6D4] text-white shadow-[0_0_18px_rgba(6,182,212,0.55)]"
                          : "border-white/20 bg-[#042F2E]/85 text-[#99F6E4]"
                      )}
                    >
                      <Icon className="h-5 w-5" />
                    </div>
                  </div>

                  <div className="min-w-0">
                    <span className="block font-mono text-[10px] font-bold uppercase tracking-widest text-[#5EEAD4]">
                      {st.short}
                    </span>
                    <p className="mt-0.5 text-sm font-bold text-white">{st.title}</p>
                    <p className="mt-1 text-xs leading-relaxed text-[#CCFBF1]/75">{st.desc}</p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="mt-6 flex items-center gap-2.5 rounded-xl border border-white/14 bg-white/[0.06] px-4 py-2.5 text-xs text-[#CCFBF1]/85">
          <ShieldCheck className="h-4 w-4 shrink-0 text-[#2DD4BF]" />
          <span>
            Quy trình máy chủ đang xử lý đồng bộ (LangGraph). Nút gửi đã tạm khóa để tránh tạo trùng yêu cầu và sẽ tự mở kết quả ngay khi hoàn tất.
          </span>
        </div>
      </div>
    </SpotlightCard>
  );
}
