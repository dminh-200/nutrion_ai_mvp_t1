import { useCallback, useEffect, useState } from "react";
import { AnimatePresence, MotionConfig, motion } from "framer-motion";
import { Toaster, toast } from "sonner";
import { DisclaimerFooter } from "@/components/layout/DisclaimerFooter";
import { SystemStatusDialog } from "@/components/layout/SystemStatusDialog";
import { getAllowedTabs, type NavTab, TopNavbar } from "@/components/layout/TopNavbar";
import { TooltipProvider } from "@/components/ui/tooltip";
import { apiClient } from "@/lib/api";
import { detailToRunResponse, formatStatus } from "@/lib/format";
import { PAGE_TRANSITION } from "@/lib/motion";
import { ChatPage } from "@/pages/ChatPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { ProfilePage } from "@/pages/ProfilePage";
import { ResultPage } from "@/pages/ResultPage";
import { ReviewPage } from "@/pages/ReviewPage";
import type {
  DemoRole,
  MealPlanRunResponse,
  MealPlanSummary,
  PatientProfileInput,
  SamplePatient,
  SystemStatusResponse,
} from "@/types/api";

function AmbientBackdrop() {
  return (
    <div
      aria-hidden="true"
      className="pointer-events-none fixed inset-0 -z-10 overflow-hidden select-none"
    >
      <svg
        className="h-full w-full opacity-[0.55]"
        viewBox="0 0 1440 900"
        fill="none"
        preserveAspectRatio="xMidYMid slice"
      >
        <defs>
          <linearGradient id="waveStrokeA" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#14B8A6" stopOpacity="0.18" />
            <stop offset="50%" stopColor="#0D9488" stopOpacity="0.08" />
            <stop offset="100%" stopColor="#38BDF8" stopOpacity="0.16" />
          </linearGradient>
          <linearGradient id="waveFillSoft" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#CCFBF1" stopOpacity="0.22" />
            <stop offset="100%" stopColor="#E0F2FE" stopOpacity="0.06" />
          </linearGradient>
        </defs>
        <path
          d="M-60 170C210 60 480 280 780 185C1080 90 1290 210 1520 120V-40H-60V170Z"
          fill="url(#waveFillSoft)"
        />
        <path
          d="M-80 235C220 125 510 315 830 220C1120 132 1310 240 1520 160"
          stroke="url(#waveStrokeA)"
          strokeWidth="1.5"
        />
        <path
          d="M-80 760C240 670 530 840 880 745C1160 670 1320 770 1520 700"
          stroke="url(#waveStrokeA)"
          strokeWidth="1.25"
        />
      </svg>
    </div>
  );
}

export function App() {
  const [role, setRole] = useState<DemoRole>("patient");
  const [activeTab, setActiveTab] = useState<NavTab>("profile");
  const [systemStatus, setSystemStatus] = useState<SystemStatusResponse | null>(null);
  const [systemModalOpen, setSystemModalOpen] = useState(false);

  const [samples, setSamples] = useState<SamplePatient[]>([]);
  const [recentPlans, setRecentPlans] = useState<MealPlanSummary[]>([]);
  const [pendingCount, setPendingCount] = useState(0);

  const [currentResult, setCurrentResult] = useState<MealPlanRunResponse | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [reviewPlanId, setReviewPlanId] = useState<number | null>(null);
  const [chatPlanId, setChatPlanId] = useState<number | null>(null);

  const refreshQueueMeta = useCallback(async () => {
    try {
      const list = await apiClient.listMealPlans(undefined, 10);
      setRecentPlans(list.items);
      setPendingCount(list.counts.pending_review + list.counts.needs_human_review);
    } catch {
      // Im lặng nếu server đang khởi động
    }
  }, []);

  useEffect(() => {
    apiClient.getSystemStatus().then(setSystemStatus).catch(() => {});
    apiClient.getSamplePatients().then(setSamples).catch(() => {});
    refreshQueueMeta();
  }, [refreshQueueMeta]);

  // Phím tắt Alt+1..5 chuyển tab theo vai trò
  useEffect(() => {
    const onKeyDown = (e: globalThis.KeyboardEvent) => {
      if (!e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return;
      const num = Number(e.key);
      if (!Number.isInteger(num) || num < 1 || num > 5) return;
      const allowed = getAllowedTabs(role);
      const target = allowed[num - 1];
      if (target) {
        e.preventDefault();
        setActiveTab(target);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [role]);

  const handleRoleChange = (nextRole: DemoRole) => {
    setRole(nextRole);
    const allowed = getAllowedTabs(nextRole);
    if (!allowed.includes(activeTab)) {
      setActiveTab(allowed[0]);
    }
  };

  const handleSubmitProfile = async (profile: PatientProfileInput) => {
    setIsSubmitting(true);
    try {
      const res = await apiClient.runMealPlan(profile);
      setCurrentResult(res);
      await refreshQueueMeta();

      if (res.status === "redirect_to_doctor") {
        toast.warning("Hồ sơ thuộc nhóm nguy cơ cao — đã chuyển hướng khuyến nghị bác sĩ.");
      } else if (res.status === "blocked") {
        toast.error("Yêu cầu bị chặn bởi lớp bảo vệ an toàn.");
      } else {
        toast.success(`Hoàn tất phân tích (${formatStatus(res.status)}).`);
      }
      setActiveTab("result");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Đã xảy ra lỗi khi phân tích hồ sơ.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleOpenPlanById = async (id: number) => {
    try {
      const det = await apiClient.getMealPlanDetail(id);
      setCurrentResult(detailToRunResponse(det));
      setActiveTab("result");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Không thể tải thực đơn.");
    }
  };

  const handleOpenReviewForId = (id: number) => {
    setReviewPlanId(id);
    setActiveTab("review");
  };

  const handleOpenChatWithPlan = (id: number) => {
    setChatPlanId(id);
    setActiveTab("chat");
  };

  return (
    <MotionConfig reducedMotion="user">
      <TooltipProvider delayDuration={200}>
        <div className="relative min-h-screen flex flex-col overflow-x-hidden">
          <AmbientBackdrop />
          <Toaster position="bottom-right" richColors closeButton />

          <TopNavbar
            role={role}
            activeTab={activeTab}
            pendingCount={pendingCount}
            systemStatus={systemStatus}
            onRoleChange={handleRoleChange}
            onTabChange={setActiveTab}
            onOpenSystemModal={() => setSystemModalOpen(true)}
          />

          <main className="mx-auto mt-5 w-full max-w-6xl min-w-0 flex-1 px-4 sm:px-6">
            <AnimatePresence mode="wait">
              <motion.div
                key={activeTab}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={PAGE_TRANSITION}
              >
                {activeTab === "profile" && (
                  <ProfilePage
                    samples={samples}
                    isSubmitting={isSubmitting}
                    onSubmitProfile={handleSubmitProfile}
                  />
                )}

                {activeTab === "result" && (
                  <ResultPage
                    role={role}
                    result={currentResult}
                    recentPlans={recentPlans}
                    onGoToProfile={() => setActiveTab("profile")}
                    onOpenPlanById={handleOpenPlanById}
                    onOpenReviewForId={handleOpenReviewForId}
                    onOpenChatWithPlan={handleOpenChatWithPlan}
                  />
                )}

                {activeTab === "chat" && (
                  <ChatPage
                    currentResult={currentResult}
                    recentPlans={recentPlans}
                    initialLinkedPlanId={chatPlanId}
                    defaultDisclaimer={systemStatus?.disclaimer_vi}
                  />
                )}

                {activeTab === "review" && role !== "patient" && (
                  <ReviewPage
                    initialSelectedPlanId={reviewPlanId}
                    onQueueChanged={refreshQueueMeta}
                    onViewInResult={handleOpenPlanById}
                  />
                )}

                {activeTab === "dashboard" && role === "admin" && <DashboardPage />}
              </motion.div>
            </AnimatePresence>
          </main>

          <DisclaimerFooter disclaimerText={systemStatus?.disclaimer_vi} />

          <SystemStatusDialog
            open={systemModalOpen}
            onOpenChange={setSystemModalOpen}
            status={systemStatus}
          />
        </div>
      </TooltipProvider>
    </MotionConfig>
  );
}

export default App;
