import { useEffect, useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Code2,
  Cpu,
  GitBranch,
  Wrench,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { apiClient } from "@/lib/api";
import type { SystemStatusResponse } from "@/types/api";

interface SystemStatusDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  status: SystemStatusResponse | null;
}

const PIPELINE_STAGES = [
  {
    stage: "1. Tiếp nhận & Bảo vệ đầu vào",
    tone: "border-[#BAE6FD] bg-[#F0F9FF]/70 text-[#0369A1]",
    nodes: [
      { id: "intake", label: "Intake", desc: "Chuẩn hóa hồ sơ & BMI/TDEE" },
      { id: "input_guardrail", label: "Input Guardrail", desc: "Chặn injection & ca nguy cơ cao" },
    ],
  },
  {
    stage: "2. Phân loại & Truy xuất RAG",
    tone: "border-[#CCE4DC] bg-[#F0FDFA]/80 text-[#0B4F4A]",
    nodes: [
      { id: "classify", label: "Classify", desc: "Phân loại nhu cầu & lọc dị nguyên" },
      { id: "retrieve", label: "Retrieve", desc: "Truy xuất hướng dẫn QĐ-BYT" },
    ],
  },
  {
    stage: "3. Lập khẩu phần & Kiểm chứng 11 tiêu chí",
    tone: "border-[#A7F3D0] bg-[#ECFDF5]/80 text-[#065F46]",
    nodes: [
      { id: "plan", label: "Plan (LLM)", desc: "Chọn món Việt Nam an toàn" },
      { id: "portion_adjust", label: "Portion Adjust", desc: "Cân chỉnh gram theo toán học" },
      { id: "verify", label: "Verify (11 Rules)", desc: "Kiểm tra sàn kcal, macro, Na, purin" },
    ],
  },
  {
    stage: "4. Giải trình, An toàn đầu ra & HITL",
    tone: "border-[#FDE68A] bg-[#FFFBEB]/80 text-[#92400E]",
    nodes: [
      { id: "explain", label: "Explain", desc: "Tổng hợp giải trình có trích dẫn" },
      { id: "output_guardrail", label: "Output Guardrail", desc: "Lọc từ cấm & chẩn đoán" },
      { id: "await_review", label: "Await Review", desc: "Chờ chuyên gia duyệt HITL" },
      { id: "finalize", label: "Finalize", desc: "Lưu SQLite & QueryLog" },
    ],
  },
];

export function SystemStatusDialog({ open, onOpenChange, status }: SystemStatusDialogProps) {
  const [mermaid, setMermaid] = useState<string>("");
  const [loadingGraph, setLoadingGraph] = useState(false);
  const [showRawMermaid, setShowRawMermaid] = useState(false);

  useEffect(() => {
    if (!open || mermaid) return;
    setLoadingGraph(true);
    apiClient
      .getGraphMermaid()
      .then((res) => setMermaid(res.mermaid))
      .catch(() => setMermaid("Không thể tải sơ đồ luồng tác tử."))
      .finally(() => setLoadingGraph(false));
  }, [open, mermaid]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>Trạng thái vận hành & Cảnh báo hệ thống</DialogTitle>
          <DialogDescription>
            Thông số cấu hình hiện tại dành cho Chuyên gia dinh dưỡng & Quản trị viên.
          </DialogDescription>
        </DialogHeader>

        {status ? (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              <div className="rounded-xl border border-[#E4ECE8] bg-[#F8FAF9] p-3">
                <span className="flex items-center gap-1.5 text-[11px] font-semibold uppercase text-[#64748B]">
                  <Cpu className="h-3.5 w-3.5 text-[#0D9488]" /> Chế độ LLM
                </span>
                <p className="mt-1 font-mono text-sm font-bold text-[#0F172A]">
                  {status.llm_mode} ({status.llm_provider})
                </p>
              </div>
              <div className="rounded-xl border border-[#E4ECE8] bg-[#F8FAF9] p-3">
                <span className="flex items-center gap-1.5 text-[11px] font-semibold uppercase text-[#64748B]">
                  <Wrench className="h-3.5 w-3.5 text-[#0D9488]" /> Tools Mode
                </span>
                <p className="mt-1 font-mono text-sm font-bold text-[#0F172A]">
                  {status.tools_mode}
                </p>
              </div>
              <div className="col-span-2 sm:col-span-1 rounded-xl border border-[#E4ECE8] bg-[#F8FAF9] p-3">
                <span className="text-[11px] font-semibold uppercase text-[#64748B]">
                  Model đang chọn
                </span>
                <p className="mt-1 font-mono text-xs font-bold text-[#0F172A] break-all">
                  {status.active_model}
                </p>
              </div>
            </div>

            <div className="flex flex-wrap gap-2">
              <Badge variant="secondary">SAFETY_LLM: {status.safety_llm}</Badge>
              {status.chat_model && (
                <Badge variant="secondary">
                  Chat model: {status.chat_model}
                  {status.chat_uses_dedicated_key ? " (key riêng)" : " (fallback)"}
                </Badge>
              )}
              <Badge variant={status.langfuse_enabled ? "approved" : "secondary"}>
                Langfuse: {status.langfuse_enabled ? "Đang bật" : "Tắt (no-op)"}
              </Badge>
            </div>

            {status.warnings.has_warnings ? (
              <div className="space-y-2 rounded-xl border border-[#FDE68A] bg-[#FFFBEB] p-3.5">
                <p className="flex items-center gap-2 text-xs font-bold uppercase tracking-wide text-[#92400E]">
                  <AlertTriangle className="h-4 w-4" />
                  Cảnh báo cấu hình ({status.warnings.warnings.length})
                </p>
                <ul className="space-y-1 text-xs text-[#78350F]">
                  {status.warnings.warnings.map((w, idx) => (
                    <li key={idx}>• {w}</li>
                  ))}
                </ul>
                {status.warnings.todo_verify_items.length > 0 && (
                  <pre className="mt-2 max-h-28 overflow-y-auto rounded-lg bg-white/80 p-2 font-mono text-[11px] text-[#78350F]">
                    {status.warnings.todo_verify_items.slice(0, 6).join("\n")}
                  </pre>
                )}
              </div>
            ) : (
              <div className="flex items-center gap-2 rounded-xl border border-[#A7F3D0] bg-[#ECFDF5] p-3 text-xs font-semibold text-[#065F46]">
                <CheckCircle2 className="h-4 w-4" />
                Toàn bộ quy tắc dinh dưỡng và dữ liệu thực phẩm đã sẵn sàng.
              </div>
            )}

            {/* Visual Pipeline Architecture */}
            <div className="rounded-xl border border-[#E4ECE8] bg-[#F8FAF9] p-3.5 space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="flex items-center gap-1.5 text-xs font-bold text-[#0F172A]">
                  <GitBranch className="h-4 w-4 text-[#0D9488]" />
                  Kiến trúc luồng xử lý LangGraph (11 Nodes)
                </p>
                <button
                  type="button"
                  onClick={() => setShowRawMermaid((prev) => !prev)}
                  className="inline-flex items-center gap-1 rounded-lg border border-[#D5E2DC] bg-white px-2.5 py-1 text-[11px] font-semibold text-[#334155] hover:bg-[#EEF5F2] cursor-pointer"
                >
                  <Code2 className="h-3.5 w-3.5 text-[#0D9488]" />
                  {showRawMermaid ? "Ẩn mã Mermaid" : "Xem mã Mermaid gốc"}
                </button>
              </div>

              <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
                {PIPELINE_STAGES.map((group) => (
                  <div
                    key={group.stage}
                    className={`rounded-xl border p-2.5 space-y-2 ${group.tone}`}
                  >
                    <p className="text-[11px] font-bold uppercase tracking-wide">{group.stage}</p>
                    <div className="flex flex-wrap items-center gap-1.5">
                      {group.nodes.map((node, nIdx) => (
                        <div key={node.id} className="flex items-center gap-1.5">
                          <div className="rounded-lg border border-black/5 bg-white px-2 py-1.5 shadow-2xs">
                            <p className="font-mono text-[11px] font-bold text-[#0F172A]">
                              {node.label}
                            </p>
                            <p className="text-[10px] text-[#64748B] leading-tight">{node.desc}</p>
                          </div>
                          {nIdx < group.nodes.length - 1 && (
                            <ArrowRight className="h-3 w-3 shrink-0 opacity-60" />
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>

              {showRawMermaid && (
                <pre className="max-h-44 overflow-auto rounded-lg border border-[#E4ECE8] bg-white p-2.5 font-mono text-[11px] text-[#334155]">
                  {loadingGraph ? "Đang tải sơ đồ Mermaid..." : mermaid}
                </pre>
              )}
            </div>
          </div>
        ) : (
          <p className="text-sm text-[#64748B]">Đang tải trạng thái hệ thống...</p>
        )}
      </DialogContent>
    </Dialog>
  );
}
