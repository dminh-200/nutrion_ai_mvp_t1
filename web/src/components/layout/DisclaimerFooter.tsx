import { ShieldCheck } from "lucide-react";
import { cleanDisclaimer } from "@/lib/format";

interface DisclaimerFooterProps {
  disclaimerText?: string;
}

const DEFAULT_DISCLAIMER =
  "Lưu ý: Thực đơn chỉ mang tính tham khảo hỗ trợ dinh dưỡng, không thay thế chẩn đoán hoặc chỉ định điều trị của bác sĩ.";

export function DisclaimerFooter({ disclaimerText }: DisclaimerFooterProps) {
  const clean = disclaimerText ? cleanDisclaimer(disclaimerText) : DEFAULT_DISCLAIMER;
  return (
    <footer className="mx-auto mt-10 w-full max-w-6xl px-4 pb-8 sm:px-6">
      <div className="glass-surface flex items-start gap-3 rounded-2xl px-4 py-3 text-xs sm:text-[13px] text-[#475569] leading-relaxed">
        <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-[#0D9488]" />
        <p>{clean}</p>
      </div>
    </footer>
  );
}
