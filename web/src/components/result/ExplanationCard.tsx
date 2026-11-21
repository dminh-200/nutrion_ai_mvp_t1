import { useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { BookOpen, ChevronDown, ChevronUp, FileText } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { GuidelineSnippet } from "@/types/api";

interface ExplanationCardProps {
  explanationMd: string;
  snippets: GuidelineSnippet[];
}

function stripTrailingDisclaimer(md: string): string {
  const lines = md.trim().split(/\r?\n/);
  while (lines.length > 0) {
    const last = lines[lines.length - 1].trim();
    if (
      !last ||
      last === "---" ||
      last.toLowerCase().includes("thực đơn chỉ mang tính tham khảo hỗ trợ dinh dưỡng")
    ) {
      lines.pop();
    } else {
      break;
    }
  }
  return lines.join("\n").trim();
}

function humanizeNeedTokens(md: string): string {
  const map: Record<string, string> = {
    kiem_soat_duong_huyet: "kiểm soát đường huyết",
    giam_natri: "giảm natri",
    han_che_purin: "hạn chế purin",
    giam_can: "kiểm soát cân nặng",
    duy_tri_can_bang: "duy trì cân bằng",
  };
  let out = md;
  for (const [k, v] of Object.entries(map)) {
    out = out.replaceAll(k, v);
  }
  return out;
}

/**
 * Đánh số chú thích `[1]`, `[2]` ngay tại từng câu khuyến nghị và liệt kê nguồn tương ứng
 * ở bên dưới để giữ nguyên liên kết câu ↔ tài liệu/trang.
 */
function parseCitationsAndCleanMd(md: string): {
  cleanedMd: string;
  citationTags: Array<{ index: number; label: string }>;
} {
  const tagMap = new Map<string, number>();
  const citationRegex = /\[([^\]\n]{6,140}(?:tr\.|trang|QĐ-BYT|BYT|WHO|ADA|KDIGO)[^\]\n]*)\]/gi;

  const cleanedLines = md.split(/\r?\n/).map((line) => {
    let cleanLine = line.replace(citationRegex, (_full, rawTag: string) => {
      const normalized = rawTag.trim();
      let idx = tagMap.get(normalized);
      if (idx === undefined) {
        idx = tagMap.size + 1;
        tagMap.set(normalized, idx);
      }
      return ` **[${idx}]**`;
    });
    cleanLine = cleanLine.replace(/\s{2,}/g, " ").trim();
    // Làm gọn bullet nếu có dạng "- đoạn bị cắt... điều trị. 6..."
    cleanLine = cleanLine.replace(/\s+\d+\.\.\.$/, "…");
    return cleanLine;
  });

  return {
    cleanedMd: cleanedLines
      .filter((l, idx, arr) => l !== "" || (idx > 0 && arr[idx - 1] !== ""))
      .join("\n")
      .trim(),
    citationTags: Array.from(tagMap.entries()).map(([label, index]) => ({ index, label })),
  };
}

function cleanSnippetExcerpt(raw: string): string {
  const trimmed = raw.replace(/\s+/g, " ").trim();
  if (!trimmed) return "";
  // Nếu đoạn đầu bị cắt giữa từ (bắt đầu bằng chữ thường không có dấu), bỏ từ dở đầu tiên
  const cleanedStart = /^[a-zàáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]/.test(
    trimmed
  )
    ? `…${trimmed.replace(/^\S+\s+/, "")}`
    : trimmed;
  return cleanedStart;
}

export function ExplanationCard({ explanationMd, snippets }: ExplanationCardProps) {
  const [showSnippets, setShowSnippets] = useState(false);

  const { cleanedMd, citationTags } = useMemo(() => {
    const base = humanizeNeedTokens(stripTrailingDisclaimer(explanationMd));
    return parseCitationsAndCleanMd(base);
  }, [explanationMd]);

  if (!cleanedMd && !snippets.length && !citationTags.length) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <BookOpen className="h-4.5 w-4.5 text-[#0D9488]" />
          Giải trình dinh dưỡng & Trích dẫn hướng dẫn lâm sàng
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {cleanedMd && (
          <div className="prose prose-sm max-w-none text-[#334155] [&_p]:leading-relaxed [&_ul]:my-2 [&_ul]:list-disc [&_ul]:pl-5 [&_li]:my-1.5 [&_strong]:text-[#0F172A]">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{cleanedMd}</ReactMarkdown>
          </div>
        )}

        {citationTags.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5 border-t border-[#F1F5F3] pt-3">
            <span className="mr-1 inline-flex items-center gap-1 text-[11px] font-bold uppercase tracking-wide text-[#64748B]">
              <FileText className="h-3.5 w-3.5 text-[#0D9488]" />
              Nguồn trích dẫn:
            </span>
            {citationTags.map((tag) => (
              <Badge key={tag.index} variant="default" className="text-[11px] font-medium">
                <span className="mr-1 font-mono font-bold">[{tag.index}]</span>
                {tag.label}
              </Badge>
            ))}
          </div>
        )}

        {snippets.length > 0 && (
          <div className="border-t border-[#F1F5F3] pt-3">
            <button
              type="button"
              onClick={() => setShowSnippets((prev) => !prev)}
              className="inline-flex items-center gap-1.5 text-xs font-bold text-[#0B4F4A] hover:underline cursor-pointer"
            >
              {showSnippets ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
              Xem {snippets.length} đoạn tài liệu hướng dẫn đã truy xuất (RAG)
            </button>

            {showSnippets && (
              <div className="mt-3 grid grid-cols-1 gap-2.5 sm:grid-cols-2">
                {snippets.map((s, idx) => (
                  <div
                    key={idx}
                    className="rounded-xl border border-[#E4ECE8] bg-[#F8FAF9] p-3 text-xs space-y-1.5"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-1">
                      <span className="font-bold text-[#0F172A]">
                        {s.source_name} ({s.year})
                      </span>
                      <Badge variant="secondary" className="font-mono text-[10px]">
                        Tr. {s.page} · Score {s.score.toFixed(2)}
                      </Badge>
                    </div>
                    <p className="text-[#475569] leading-relaxed italic">
                      “{cleanSnippetExcerpt(s.text)}”
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
