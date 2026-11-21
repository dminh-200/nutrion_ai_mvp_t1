import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Loader2, ShieldCheck } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

const WORKFLOW_STEPS = [
  "Kiểm tra an toàn đầu vào & sàng lọc nguy cơ cao",
  "Phân loại nhu cầu dinh dưỡng & truy xuất tài liệu hướng dẫn lâm sàng (RAG)",
  "Lựa chọn món ăn Việt Nam phù hợp & cân chỉnh khẩu phần bằng mã nguồn",
  "Kiểm chứng các tiêu chí an toàn & tổng hợp giải trình có trích nguồn",
];

export function AnalyzingCard({ patientCode }: { patientCode: string }) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const id = window.setInterval(() => {
      setElapsed((prev) => prev + 1);
    }, 1000);
    return () => window.clearInterval(id);
  }, []);

  return (
    <Card className="ambient-teal-card overflow-hidden border-[#BDE3D8] bg-gradient-to-br from-white to-[#F0FDFA]">
      {/* Thanh chờ xử lý không định trước (tránh mô phỏng % giả) */}
      <div className="relative h-1.5 w-full overflow-hidden bg-[#E6F2EE]">
        <motion.div
          className="absolute inset-y-0 w-1/3 rounded-full bg-gradient-to-r from-[#0B4F4A] via-[#0D9488] to-[#0B4F4A]"
          animate={{ x: ["-100%", "320%"] }}
          transition={{ duration: 1.8, repeat: Number.POSITIVE_INFINITY, ease: "easeInOut" }}
        />
      </div>

      <CardContent className="p-6 sm:p-8">
        <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3.5">
            <div className="relative flex h-12 w-12 items-center justify-center rounded-2xl bg-[#0B4F4A] text-white shadow-sm">
              <span className="absolute inset-0 animate-ping rounded-2xl bg-[#0D9488]/25 [animation-duration:2.2s]" />
              <Loader2 className="relative h-6 w-6 animate-spin" />
            </div>
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-[#0D9488]">
                Đang xử lý hồ sơ {patientCode}
              </p>
              <h3 className="text-lg font-bold text-[#0F172A]">
                Hệ thống đang xây dựng & kiểm chứng thực đơn
              </h3>
            </div>
          </div>

          <div className="inline-flex items-center gap-2 rounded-xl border border-[#CCE4DC] bg-white px-3.5 py-2 font-mono text-sm font-bold text-[#0B4F4A] tabular-nums self-start sm:self-auto shadow-2xs">
            <span className="h-2 w-2 rounded-full bg-[#0D9488] animate-pulse" />
            <span>
              {String(Math.floor(elapsed / 60)).padStart(2, "0")}:
              {String(elapsed % 60).padStart(2, "0")}
            </span>
          </div>
        </div>

        <div className="mt-6 space-y-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-[#64748B]">
            Quy trình máy chủ đang xử lý đồng bộ:
          </p>
          <div className="space-y-2">
            {WORKFLOW_STEPS.map((label, idx) => (
              <div
                key={label}
                className="flex items-center gap-3 rounded-xl border border-[#E4ECE8] bg-white/80 px-3.5 py-2.5 text-sm text-[#334155]"
              >
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[#E6F4F1] text-xs font-bold text-[#0B4F4A]">
                  {idx + 1}
                </span>
                <span>{label}</span>
              </div>
            ))}
          </div>
        </div>

        <p className="mt-5 flex items-center gap-2 text-xs text-[#64748B]">
          <ShieldCheck className="h-4 w-4 shrink-0 text-[#0D9488]" />
          Nút gửi đã được khóa tạm thời để tránh tạo trùng yêu cầu. Máy chủ sẽ trả kết quả ngay sau khi toàn bộ quy trình hoàn tất.
        </p>
      </CardContent>
    </Card>
  );
}
