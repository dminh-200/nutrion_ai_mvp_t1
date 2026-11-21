import { type KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";
import { motion } from "framer-motion";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { toast } from "sonner";
import {
  ArrowRight,
  BookOpen,
  Bot,
  Check,
  ChevronDown,
  ChevronUp,
  Copy,
  Info,
  Link2,
  MessageSquareHeart,
  RotateCcw,
  SendHorizontal,
  ShieldAlert,
  Sparkles,
  User,
  Utensils,
} from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { SpotlightCard } from "@/components/ui/spotlight-card";
import { apiClient } from "@/lib/api";
import { formatCondition, formatInt, formatNumber, formatStatus } from "@/lib/format";
import { STAGGER_CONTAINER, STAGGER_ITEM } from "@/lib/motion";
import { cn } from "@/lib/utils";
import type {
  ChatCitation,
  ChatFoodSuggestion,
  ChatMessageItem,
  GuardrailTier,
  MealPlanRunResponse,
  MealPlanSummary,
} from "@/types/api";

interface ChatTurn {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt?: string;
  tier?: GuardrailTier;
  flags?: string[];
  citations?: ChatCitation[];
  suggestedFoods?: ChatFoodSuggestion[];
}

interface ChatPageProps {
  currentResult: MealPlanRunResponse | null;
  recentPlans: MealPlanSummary[];
  initialLinkedPlanId: number | null;
  defaultDisclaimer?: string;
}

const STORAGE_TURNS_KEY = "nutriai_chat_turns_v1";
const STORAGE_SESSION_KEY = "nutriai_chat_session_v1";

const STARTER_PROMPTS_WITH_PLAN = [
  "Giải thích chỉ số BMI và mục tiêu kcal của thực đơn này",
  "Gợi ý đổi 1 món trưa ít muối hơn nhưng vẫn đủ đạm",
  "Cách chế biến các món trong thực đơn để giữ trọn dinh dưỡng",
  "Tôi đang uống thuốc huyết áp thì ăn bưởi được không?",
];

const STARTER_PROMPTS_GENERAL = [
  "Người tiểu đường type 2 nên chọn trái cây thế nào?",
  "Nguyên tắc giảm natri cho người tăng huyết áp",
  "Bị gan nhiễm mỡ nhẹ nên ăn uống thế nào?",
  "Người bệnh gout cần kiêng thực phẩm giàu purin nào?",
];

const THINKING_PHRASES = [
  "Đang đối chiếu hồ sơ thực đơn & mục tiêu dinh dưỡng...",
  "Đang tra cứu tài liệu hướng dẫn y khoa & cơ sở dữ liệu món...",
  "Đang kiểm tra an toàn câu trả lời...",
];

function nowTimeLabel(): string {
  const d = new Date();
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

function CitationChips({ citations }: { citations: ChatCitation[] }) {
  const [open, setOpen] = useState(false);
  if (!citations.length) return null;

  return (
    <div className="mt-2.5 border-t border-[#E4ECE8] pt-2">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className="inline-flex items-center gap-1.5 text-[11px] font-semibold text-[#0B4F4A] hover:underline cursor-pointer"
      >
        <BookOpen className="h-3.5 w-3.5" />
        <span>Nguồn tham khảo y khoa ({citations.length})</span>
        {open ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
      </button>

      {open && (
        <div className="mt-2 space-y-1.5">
          {citations.map((c, idx) => (
            <div
              key={`${c.source}-${c.page}-${idx}`}
              className="rounded-lg border border-[#E4ECE8] bg-[#F8FAF9] px-2.5 py-2 text-[11px] text-[#334155]"
            >
              <div className="flex items-center justify-between gap-2 font-semibold text-[#0B4F4A]">
                <span>
                  [{c.source}, tr. {c.page}]
                </span>
                <span className="font-mono text-[10px] text-[#64748B]">
                  {Math.round(c.score * 100)}%
                </span>
              </div>
              <p className="mt-0.5 leading-relaxed text-[#475569]">{c.excerpt}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function FoodSuggestionCards({ foods }: { foods: ChatFoodSuggestion[] }) {
  if (!foods.length) return null;

  return (
    <div className="mt-2.5 border-t border-[#E4ECE8] pt-2.5">
      <p className="mb-1.5 flex items-center gap-1.5 text-[11px] font-semibold text-[#0B4F4A]">
        <Utensils className="h-3.5 w-3.5" />
        Món thay thế an toàn từ cơ sở dữ liệu (trên 100g)
      </p>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        {foods.map((f) => (
          <div
            key={f.food_id}
            className="rounded-xl border border-[#DCE7E2] bg-[#F8FAF9] p-2.5 text-xs"
          >
            <div className="flex items-start justify-between gap-2">
              <span className="font-semibold text-[#0F172A]">{f.name_vi}</span>
              <span className="shrink-0 rounded-md bg-[#E6F4F1] px-1.5 py-0.5 font-mono text-[11px] font-bold text-[#0B4F4A] tabular-nums">
                {formatInt(f.kcal)} kcal
              </span>
            </div>
            <div className="mt-1.5 flex flex-wrap gap-x-2.5 gap-y-0.5 font-mono text-[11px] text-[#475569] tabular-nums">
              <span>Đạm {formatNumber(f.protein_g)}g</span>
              <span>Carb {formatNumber(f.carb_g)}g</span>
              <span>Natri {formatInt(f.sodium_mg)}mg</span>
              <span>Xơ {formatNumber(f.fiber_g)}g</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function ChatPage({
  currentResult,
  recentPlans,
  initialLinkedPlanId,
}: ChatPageProps) {
  const [turns, setTurns] = useState<ChatTurn[]>(() => {
    try {
      const saved = sessionStorage.getItem(STORAGE_TURNS_KEY);
      return saved ? (JSON.parse(saved) as ChatTurn[]) : [];
    } catch {
      return [];
    }
  });
  const [sessionId, setSessionId] = useState<string | null>(() => {
    try {
      return sessionStorage.getItem(STORAGE_SESSION_KEY);
    } catch {
      return null;
    }
  });
  const [linkedPlanId, setLinkedPlanId] = useState<number | null>(
    initialLinkedPlanId ?? currentResult?.meal_plan_id ?? null
  );
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [thinkingIdx, setThinkingIdx] = useState(0);

  const scrollContainerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (initialLinkedPlanId !== null) {
      setLinkedPlanId(initialLinkedPlanId);
    } else if (currentResult?.meal_plan_id && linkedPlanId === null) {
      setLinkedPlanId(currentResult.meal_plan_id);
    }
  }, [initialLinkedPlanId, currentResult?.meal_plan_id, linkedPlanId]);

  useEffect(() => {
    try {
      sessionStorage.setItem(STORAGE_TURNS_KEY, JSON.stringify(turns.slice(-20)));
      if (sessionId) {
        sessionStorage.setItem(STORAGE_SESSION_KEY, sessionId);
      } else {
        sessionStorage.removeItem(STORAGE_SESSION_KEY);
      }
    } catch {
      // Bỏ qua nếu sessionStorage bị khóa
    }
  }, [turns, sessionId]);

  useEffect(() => {
    const el = scrollContainerRef.current;
    if (el) {
      el.scrollTop = el.scrollHeight;
    }
  }, [turns, sending]);

  useEffect(() => {
    if (!sending) {
      setThinkingIdx(0);
      return;
    }
    const id = window.setInterval(() => {
      setThinkingIdx((prev) => (prev + 1) % THINKING_PHRASES.length);
    }, 2400);
    return () => window.clearInterval(id);
  }, [sending]);

  const activePlanSummary = useMemo(() => {
    if (!linkedPlanId) return null;
    const fromRecent = recentPlans.find((p) => p.id === linkedPlanId);
    if (currentResult?.meal_plan_id === linkedPlanId) {
      return {
        id: linkedPlanId,
        status: currentResult.status,
        conditions: fromRecent?.conditions ?? [],
        kcalTarget: currentResult.targets?.target_kcal ?? null,
      };
    }
    if (!fromRecent) return { id: linkedPlanId, status: null, conditions: [] as string[], kcalTarget: null };
    return {
      id: fromRecent.id,
      status: fromRecent.status,
      conditions: fromRecent.conditions,
      kcalTarget: null,
    };
  }, [linkedPlanId, currentResult, recentPlans]);

  const planSelectOptions = useMemo(() => {
    const map = new Map<number, MealPlanSummary>();
    for (const p of recentPlans) {
      map.set(p.id, p);
    }
    if (currentResult?.meal_plan_id && !map.has(currentResult.meal_plan_id)) {
      map.set(currentResult.meal_plan_id, {
        id: currentResult.meal_plan_id,
        thread_id: currentResult.thread_id,
        status: currentResult.status,
        patient_code: "Hiện tại",
        display_name: "",
        conditions: [],
        retry_count: currentResult.retry_count,
        verifier_passed_first_try: currentResult.violations.length === 0,
        created_at: "",
      });
    }
    return Array.from(map.values());
  }, [recentPlans, currentResult]);

  const starterPrompts = linkedPlanId ? STARTER_PROMPTS_WITH_PLAN : STARTER_PROMPTS_GENERAL;

  const handleResetChat = () => {
    setTurns([]);
    setSessionId(null);
    try {
      sessionStorage.removeItem(STORAGE_TURNS_KEY);
      sessionStorage.removeItem(STORAGE_SESSION_KEY);
    } catch {
      // ignore
    }
    toast.success("Đã bắt đầu cuộc trò chuyện mới.");
  };

  const handleCopyTurn = async (turn: ChatTurn) => {
    try {
      await navigator.clipboard.writeText(turn.content);
      setCopiedId(turn.id);
      toast.success("Đã sao chép câu trả lời.");
      window.setTimeout(() => {
        setCopiedId((prev) => (prev === turn.id ? null : prev));
      }, 1800);
    } catch {
      toast.error("Không thể sao chép vào clipboard.");
    }
  };

  const handleSend = async (overrideText?: string) => {
    const text = (overrideText ?? input).trim();
    if (!text || sending) return;

    const historyPayload: ChatMessageItem[] = turns.slice(-10).map((t) => ({
      role: t.role,
      content: t.content.slice(0, 1500),
    }));

    const userTurn: ChatTurn = {
      id: `u-${Date.now()}`,
      role: "user",
      content: text,
      createdAt: nowTimeLabel(),
    };

    setTurns((prev) => [...prev, userTurn]);
    if (!overrideText) setInput("");
    setSending(true);

    try {
      const resp = await apiClient.sendChat({
        message: text,
        meal_plan_id: linkedPlanId,
        session_id: sessionId,
        history: historyPayload,
      });
      setSessionId(resp.session_id);

      const botTurn: ChatTurn = {
        id: `a-${Date.now()}`,
        role: "assistant",
        content: resp.reply_md,
        createdAt: nowTimeLabel(),
        tier: resp.guardrail_tier,
        flags: resp.flags,
        citations: resp.citations,
        suggestedFoods: resp.suggested_foods,
      };
      setTurns((prev) => [...prev, botTurn]);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Không thể kết nối Trợ lý AI.");
      setTurns((prev) => prev.filter((t) => t.id !== userTurn.id));
      if (!overrideText) setInput(text);
    } finally {
      setSending(false);
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const charPct = Math.min(100, (input.length / 800) * 100);

  return (
    <div className="space-y-4">
      <PageHeader
        eyebrow="TRỢ LÝ DINH DƯỠNG AI"
        title="Hỏi đáp thực đơn, đổi món & kiến thức dinh dưỡng"
        description="Giải đáp dựa trên hồ sơ thực đơn đang mở, cơ sở dữ liệu món ăn và tài liệu hướng dẫn y khoa."
        rightSlot={
          <Button variant="glassDark" size="sm" onClick={handleResetChat} disabled={sending}>
            <RotateCcw className="h-3.5 w-3.5 text-[#5EEAD4]" />
            Cuộc trò chuyện mới
          </Button>
        }
      />

      {/* Context Selector Bar */}
      <Card>
        <CardContent className="flex flex-col gap-3 p-3.5 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span className="inline-flex items-center gap-1.5 font-semibold text-[#0B4F4A]">
              <Link2 className="h-3.5 w-3.5 text-[#0D9488]" />
              Ngữ cảnh thực đơn:
            </span>
            {activePlanSummary ? (
              <div className="flex flex-wrap items-center gap-1.5">
                <Badge variant="approved" className="font-mono">
                  #{activePlanSummary.id}
                </Badge>
                {activePlanSummary.kcalTarget && (
                  <Badge variant="secondary" className="font-mono">
                    {formatInt(activePlanSummary.kcalTarget)} kcal
                  </Badge>
                )}
                {activePlanSummary.conditions.map((c) => (
                  <Badge key={c} variant="secondary">
                    {formatCondition(c)}
                  </Badge>
                ))}
                {activePlanSummary.status && (
                  <Badge
                    variant={
                      activePlanSummary.status === "redirect_to_doctor" ||
                      activePlanSummary.status === "blocked"
                        ? "danger"
                        : "secondary"
                    }
                  >
                    {formatStatus(activePlanSummary.status)}
                  </Badge>
                )}
              </div>
            ) : (
              <span className="text-[#64748B]">Chế độ hỏi đáp dinh dưỡng chung (chưa gắn thực đơn)</span>
            )}
          </div>

          <div className="w-full sm:w-[300px] shrink-0">
            <Select
              value={linkedPlanId ? String(linkedPlanId) : "none"}
              onValueChange={(val) => setLinkedPlanId(val === "none" ? null : Number(val))}
            >
              <SelectTrigger
                aria-label="Chọn thực đơn liên kết"
                className="h-9 bg-white/90 text-xs [&>span]:truncate"
              >
                <SelectValue placeholder="Chọn thực đơn liên kết" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">Không gắn thực đơn (Hỏi đáp chung)</SelectItem>
                {planSelectOptions.map((p) => (
                  <SelectItem key={p.id} value={String(p.id)}>
                    Thực đơn #{p.id} · {p.patient_code} ({formatStatus(p.status)})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Main Luminous Glass Studio Chat Window */}
      <Card className="glass-surface flex h-[calc(100vh-355px)] min-h-[380px] max-h-[530px] flex-col overflow-hidden">
        <div
          ref={scrollContainerRef}
          className="flex-1 space-y-4 overflow-y-auto p-4 sm:p-5 bg-gradient-to-b from-[#ECFAF6]/55 via-white/45 to-white/35"
        >
          {turns.length === 0 ? (
            <div className="flex h-full min-h-[240px] flex-col items-center justify-center text-center px-2">
              <div className="relative flex items-center justify-center">
                {/* Soft Aurora Halo */}
                <div
                  aria-hidden="true"
                  className="pointer-events-none absolute -inset-7 rounded-full opacity-70 blur-2xl"
                  style={{
                    background:
                      "radial-gradient(circle, rgba(34, 211, 238, 0.45) 0%, rgba(52, 211, 153, 0.34) 50%, transparent 72%)",
                  }}
                />
                <div className="relative flex h-13 w-13 items-center justify-center rounded-2xl border border-white/60 bg-gradient-to-br from-[#042F2E] via-[#0D9488] to-[#06B6D4] text-white shadow-[0_10px_28px_rgba(6,182,212,0.34),inset_0_1px_0_rgba(255,255,255,0.35)]">
                  <MessageSquareHeart className="h-6 w-6" />
                </div>
              </div>
              <h3 className="mt-3.5 text-base font-extrabold tracking-tight text-[#0F172A]">
                Xin chào! Tôi có thể hỗ trợ gì cho bữa ăn của bạn?
              </h3>
              <p className="mt-1 max-w-md text-xs leading-relaxed text-[#475569]">
                Bạn có thể hỏi về chỉ số BMI/TDEE, cách chế biến món ăn, gợi ý đổi món phù hợp
                dị ứng hoặc kiến thức dinh dưỡng bệnh lý.
              </p>

              <motion.div
                variants={STAGGER_CONTAINER}
                initial="hidden"
                animate="show"
                className="mt-4 grid w-full max-w-2xl grid-cols-1 gap-2.5 sm:grid-cols-2"
              >
                {starterPrompts.map((prompt) => (
                  <motion.div key={prompt} variants={STAGGER_ITEM}>
                    <SpotlightCard className="h-full rounded-xl border border-white/90 bg-white/82 backdrop-blur-xl ring-1 ring-[#0D9488]/12 shadow-[inset_0_1px_0_rgba(255,255,255,0.95),0_4px_14px_rgba(11,79,74,0.06)] transition-all duration-150 hover:-translate-y-0.5 hover:ring-[#06B6D4]/45 hover:shadow-[0_10px_24px_rgba(6,182,212,0.14)]">
                      <button
                        type="button"
                        onClick={() => handleSend(prompt)}
                        disabled={sending}
                        className="group flex h-full w-full items-start justify-between gap-2 p-3 text-left text-xs font-medium text-[#1E293B] active:scale-[0.99] cursor-pointer"
                      >
                        <span className="flex items-start gap-2">
                          <Sparkles className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[#0D9488] transition-transform group-hover:scale-110 group-hover:text-[#06B6D4]" />
                          <span>{prompt}</span>
                        </span>
                        <ArrowRight className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[#06B6D4] opacity-0 -translate-x-1 transition-all group-hover:opacity-100 group-hover:translate-x-0" />
                      </button>
                    </SpotlightCard>
                  </motion.div>
                ))}
              </motion.div>
            </div>
          ) : (
            turns.map((turn) => {
              const isUser = turn.role === "user";
              const isCopied = copiedId === turn.id;
              return (
                <motion.div
                  key={turn.id}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.16 }}
                  className={cn("flex items-start gap-2.5", isUser ? "justify-end" : "justify-start")}
                >
                  {!isUser && (
                    <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-[#0B4F4A] to-[#14B8A6] text-white shadow-[0_4px_10px_rgba(13,148,136,0.24)]">
                      <Bot className="h-4 w-4" />
                    </div>
                  )}

                  <div
                    className={cn(
                      "group relative max-w-[88%] sm:max-w-[78%] rounded-2xl px-4 py-3 text-sm leading-relaxed",
                      isUser
                        ? "bg-gradient-to-r from-[#0D9488] via-[#0EA5A8] to-[#06B6D4] text-white rounded-tr-sm shadow-[0_6px_18px_rgba(6,182,212,0.28)]"
                        : cn(
                            "border bg-white/95 backdrop-blur-sm text-[#1E293B] rounded-tl-sm shadow-[inset_0_1px_0_rgba(255,255,255,0.95),0_4px_14px_rgba(11,79,74,0.06)]",
                            turn.tier === "hard_block"
                              ? "border-[#FECACA] bg-[#FEF2F2]/85"
                              : turn.tier === "soft_boundary"
                                ? "border-[#BAE6FD] bg-[#F0F9FF]/80"
                                : "border-[#DCEAE4]"
                          )
                    )}
                  >
                    {!isUser && (
                      <div className="mb-1.5 flex items-center justify-between gap-2">
                        <div className="flex flex-wrap items-center gap-1.5">
                          <span className="text-[11px] font-bold text-[#0B4F4A]">Trợ lý NutriAI</span>
                          {turn.createdAt && (
                            <span className="font-mono text-[10px] text-[#94A3B8]">
                              {turn.createdAt}
                            </span>
                          )}
                          {turn.tier === "hard_block" && (
                            <span className="inline-flex items-center gap-1 rounded-full bg-[#FEE2E2] px-2 py-0.5 text-[10px] font-semibold text-[#991B1B]">
                              <ShieldAlert className="h-3 w-3" />
                              Bảo vệ an toàn y khoa
                            </span>
                          )}
                          {turn.tier === "soft_boundary" && (
                            <span className="inline-flex items-center gap-1 rounded-full bg-[#E0F2FE] px-2 py-0.5 text-[10px] font-semibold text-[#075985]">
                              <Info className="h-3 w-3" />
                              Tham khảo mở rộng
                            </span>
                          )}
                        </div>

                        <button
                          type="button"
                          onClick={() => handleCopyTurn(turn)}
                          title="Sao chép câu trả lời"
                          aria-label="Sao chép câu trả lời"
                          className="inline-flex items-center gap-1 rounded-lg border border-[#DCEAE4] bg-[#F8FAF9] px-2 py-0.5 text-[11px] font-semibold text-[#475569] transition-colors hover:border-[#14B8A6] hover:text-[#0B4F4A] cursor-pointer"
                        >
                          {isCopied ? (
                            <>
                              <Check className="h-3 w-3 text-[#059669]" />
                              <span className="text-[#059669]">Đã chép</span>
                            </>
                          ) : (
                            <>
                              <Copy className="h-3 w-3" />
                              <span className="hidden sm:inline">Sao chép</span>
                            </>
                          )}
                        </button>
                      </div>
                    )}

                    {isUser ? (
                      <p className="whitespace-pre-wrap break-words">{turn.content}</p>
                    ) : (
                      <div className="prose prose-sm max-w-none prose-headings:text-[#0F172A] prose-strong:text-[#0F172A] prose-p:my-1.5 prose-ul:my-1.5 prose-li:my-0.5 break-words">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{turn.content}</ReactMarkdown>
                      </div>
                    )}

                    {!isUser && turn.suggestedFoods && turn.suggestedFoods.length > 0 && (
                      <FoodSuggestionCards foods={turn.suggestedFoods} />
                    )}
                    {!isUser && turn.citations && turn.citations.length > 0 && (
                      <CitationChips citations={turn.citations} />
                    )}
                  </div>

                  {isUser && (
                    <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl border border-[#CDE6DF] bg-white/90 text-[#0B4F4A] shadow-2xs">
                      <User className="h-4 w-4" />
                    </div>
                  )}
                </motion.div>
              );
            })
          )}

          {sending && (
            <motion.div
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex items-start gap-2.5"
            >
              <div className="relative mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-[#0B4F4A] to-[#14B8A6] text-white">
                <span className="absolute inset-0 animate-ping rounded-xl bg-[#14B8A6]/35 [animation-duration:1.8s]" />
                <Bot className="relative h-4 w-4" />
              </div>
              <div className="rounded-2xl rounded-tl-sm border border-[#D4E7E0] bg-white/95 px-4 py-2.5 shadow-2xs">
                <div className="flex items-center gap-2.5">
                  <div className="flex items-center gap-1">
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-[#14B8A6] [animation-delay:-0.3s]" />
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-[#0D9488] [animation-delay:-0.15s]" />
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-[#0B4F4A]" />
                  </div>
                  <span className="text-xs font-medium text-[#475569]">
                    {THINKING_PHRASES[thinkingIdx]}
                  </span>
                </div>
              </div>
            </motion.div>
          )}
        </div>

        {/* Luminous Floating Dock Composer */}
        <div className="border-t border-white/75 bg-white/55 backdrop-blur-xl px-3.5 py-3 sm:px-4">
          <div className="rounded-2xl bg-gradient-to-r from-[#CBE4DC] via-[#CBE4DC] to-[#CBE4DC] p-[1.5px] shadow-[0_8px_24px_-6px_rgba(11,79,74,0.12)] transition-all duration-200 focus-within:from-[#0D9488] focus-within:via-[#0EA5A8] focus-within:to-[#06B6D4] focus-within:shadow-[0_0_26px_rgba(6,182,212,0.26)]">
            <div className="flex items-end gap-2 rounded-[14.5px] bg-white/95 p-2 backdrop-blur-md">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                rows={2}
                maxLength={800}
                disabled={sending}
                placeholder="Nhập câu hỏi về thực đơn, đổi món, cách chế biến hoặc dinh dưỡng..."
                aria-label="Nhập câu hỏi cho Trợ lý Dinh dưỡng"
                className="flex-1 resize-none bg-transparent px-2.5 py-1.5 text-sm text-[#0F172A] placeholder:text-[#94A3B8] focus:outline-none"
              />
              <Button
                type="button"
                onClick={() => handleSend()}
                disabled={sending || !input.trim()}
                className="h-10 px-4 shrink-0"
              >
                <SendHorizontal className="h-4 w-4" />
                <span className="hidden sm:inline">Gửi</span>
              </Button>
            </div>
          </div>
          <div className="mt-2 flex items-center justify-between gap-3 px-1">
            <span className="text-[11px] text-[#475569]">
              Nhấn <kbd className="rounded border border-[#CBE4DC] bg-white/90 px-1 py-0.2 font-mono text-[10px]">Enter</kbd> để gửi ·{" "}
              <kbd className="rounded border border-[#CBE4DC] bg-white/90 px-1 py-0.2 font-mono text-[10px]">Shift+Enter</kbd> xuống dòng
            </span>
            <div className="flex items-center gap-2 shrink-0">
              <div className="h-1 w-16 overflow-hidden rounded-full bg-[#DCECE6]">
                <div
                  className={cn(
                    "h-full rounded-full transition-all duration-150",
                    charPct >= 95 ? "bg-[#DC2626]" : charPct >= 80 ? "bg-[#D97706]" : "bg-gradient-to-r from-[#0D9488] to-[#06B6D4]"
                  )}
                  style={{ width: `${charPct}%` }}
                />
              </div>
              <span
                className={cn(
                  "font-mono text-[10px] tabular-nums",
                  charPct >= 95
                    ? "font-bold text-[#DC2626]"
                    : charPct >= 80
                      ? "font-semibold text-[#D97706]"
                      : "text-[#64748B]"
                )}
              >
                {input.length}/800
              </span>
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
}
