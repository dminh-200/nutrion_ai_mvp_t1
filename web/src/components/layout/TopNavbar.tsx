import { useState } from "react";
import { motion } from "framer-motion";
import {
  Activity,
  ClipboardList,
  Leaf,
  Menu,
  MessageSquareHeart,
  ShieldAlert,
  Stethoscope,
  UserCheck,
  UserCog,
  UtensilsCrossed,
  X,
} from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { TAB_SPRING } from "@/lib/motion";
import { cn } from "@/lib/utils";
import type { DemoRole, SystemStatusResponse } from "@/types/api";

export type NavTab = "profile" | "result" | "chat" | "review" | "dashboard";

interface TopNavbarProps {
  role: DemoRole;
  activeTab: NavTab;
  pendingCount: number;
  systemStatus: SystemStatusResponse | null;
  onRoleChange: (role: DemoRole) => void;
  onTabChange: (tab: NavTab) => void;
  onOpenSystemModal: () => void;
}

const ROLE_META: Record<DemoRole, { label: string; dot: string; icon: typeof UserCheck }> = {
  patient: { label: "Bệnh nhân", dot: "bg-[#14B8A6]", icon: UserCheck },
  expert: { label: "Chuyên gia", dot: "bg-[#0284C7]", icon: Stethoscope },
  admin: { label: "Quản trị", dot: "bg-[#D97706]", icon: UserCog },
};

export function getAllowedTabs(role: DemoRole): NavTab[] {
  if (role === "admin") return ["profile", "result", "chat", "review", "dashboard"];
  if (role === "expert") return ["review", "result", "chat", "profile"];
  return ["profile", "result", "chat"];
}

const TAB_META: Record<NavTab, { label: string; icon: typeof ClipboardList }> = {
  profile: { label: "Hồ sơ", icon: ClipboardList },
  result: { label: "Thực đơn", icon: UtensilsCrossed },
  chat: { label: "Trợ lý AI", icon: MessageSquareHeart },
  review: { label: "Chuyên gia duyệt", icon: Stethoscope },
  dashboard: { label: "Bảng điều khiển", icon: Activity },
};

export function TopNavbar({
  role,
  activeTab,
  pendingCount,
  systemStatus,
  onRoleChange,
  onTabChange,
  onOpenSystemModal,
}: TopNavbarProps) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const allowedTabs = getAllowedTabs(role);
  const showSystemInfo = role !== "patient";
  const warnCount = systemStatus?.warnings?.warnings?.length ?? 0;
  const activeRoleMeta = ROLE_META[role];

  return (
    <header className="sticky top-3 z-40 mx-auto w-full max-w-6xl px-4 sm:px-6">
      <div className="glass-navbar relative overflow-hidden rounded-2xl px-3.5 py-2.5">
        <div className="flex items-center justify-between gap-3">
          {/* Brand */}
          <button
            type="button"
            onClick={() => onTabChange(allowedTabs[0])}
            className="group flex items-center gap-2.5 rounded-xl px-1 py-0.5 text-left cursor-pointer shrink-0 transition-transform active:scale-[0.985]"
          >
            <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-[#0D9488] via-[#0EA5A8] to-[#06B6D4] text-white shadow-[0_4px_16px_rgba(6,182,212,0.34),inset_0_1px_0_rgba(255,255,255,0.34)] transition-transform duration-200 group-hover:scale-[1.04]">
              <Leaf className="h-4.5 w-4.5" />
            </span>
            <div className="leading-tight">
              <span className="block text-sm font-extrabold tracking-tight text-[#0F172A]">
                NutriAI <span className="bg-gradient-to-r from-[#0D9488] to-[#06B6D4] bg-clip-text text-transparent">Clinical</span>
              </span>
              <span className="hidden sm:block text-[11px] font-medium text-[#64748B]">
                Dinh dưỡng bệnh lý
              </span>
            </div>
          </button>

          {/* Desktop Nav Pills with Luminous Gradient Sliding Indicator */}
          <nav
            aria-label="Điều hướng chính"
            className="hidden md:flex items-center gap-1 rounded-xl border border-[#DCEAE4] bg-[#EFF7F4]/85 p-1 shadow-[inset_0_1px_2px_rgba(11,79,74,0.04)]"
          >
            {allowedTabs.map((tab, idx) => {
              const meta = TAB_META[tab];
              const Icon = meta.icon;
              const isActive = activeTab === tab;
              return (
                <Tooltip key={tab} delayDuration={350}>
                  <TooltipTrigger asChild>
                    <button
                      type="button"
                      onClick={() => onTabChange(tab)}
                      className={cn(
                        "relative inline-flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-xs font-semibold transition-colors duration-150 cursor-pointer whitespace-nowrap select-none",
                        isActive
                          ? "text-white"
                          : "text-[#475569] hover:text-[#0B4F4A]"
                      )}
                    >
                      {isActive && (
                        <motion.span
                          layoutId="nav-active-pill"
                          transition={TAB_SPRING}
                          className="absolute inset-0 rounded-lg bg-gradient-to-r from-[#0D9488] via-[#0EA5A8] to-[#06B6D4] shadow-[0_4px_16px_rgba(6,182,212,0.36),inset_0_1px_0_rgba(255,255,255,0.28)]"
                        />
                      )}
                      <span className="relative z-10 inline-flex items-center gap-1.5">
                        <Icon className="h-3.5 w-3.5 shrink-0" />
                        <span>{meta.label}</span>
                        {tab === "review" && pendingCount > 0 && (
                          <span
                            className={cn(
                              "ml-0.5 rounded-full px-1.5 py-0.2 text-[10px] font-bold tabular-nums transition-colors",
                              isActive
                                ? "bg-white/25 text-white"
                                : "bg-[#FEF3C7] text-[#92400E]"
                            )}
                          >
                            {pendingCount}
                          </span>
                        )}
                      </span>
                    </button>
                  </TooltipTrigger>
                  <TooltipContent>
                    {meta.label} · Phím tắt <span className="font-mono">Alt+{idx + 1}</span>
                  </TooltipContent>
                </Tooltip>
              );
            })}
          </nav>

          {/* Right Actions */}
          <div className="flex items-center gap-2 shrink-0">
            {showSystemInfo && (
              <Tooltip delayDuration={250}>
                <TooltipTrigger asChild>
                  <button
                    type="button"
                    onClick={onOpenSystemModal}
                    className="hidden sm:inline-flex items-center gap-1.5 rounded-xl border border-[#D4E6DF] bg-white/85 px-2.5 py-1.5 text-xs font-semibold text-[#334155] shadow-2xs transition-all hover:border-[#0D9488]/60 hover:bg-[#F0FDFA] cursor-pointer active:scale-[0.985]"
                  >
                    <ShieldAlert
                      className={cn(
                        "h-3.5 w-3.5",
                        warnCount > 0 ? "text-[#D97706]" : "text-[#0D9488]"
                      )}
                    />
                    <span className="hidden lg:inline">Hệ thống</span>
                    {warnCount > 0 && (
                      <span className="rounded-full bg-[#FEF3C7] px-1.5 text-[10px] font-bold text-[#92400E] tabular-nums">
                        {warnCount}
                      </span>
                    )}
                  </button>
                </TooltipTrigger>
                <TooltipContent>Trạng thái mô hình, cảnh báo & luồng LangGraph</TooltipContent>
              </Tooltip>
            )}

            <div className="w-[136px] sm:w-[148px]">
              <Select value={role} onValueChange={(v) => onRoleChange(v as DemoRole)}>
                <SelectTrigger
                  aria-label="Chọn vai trò demo"
                  className="h-9 bg-white/90 text-xs font-semibold border-[#D2E4DC]"
                >
                  <SelectValue>
                    <span className="inline-flex items-center gap-1.5">
                      <span className={cn("h-2 w-2 rounded-full shrink-0", activeRoleMeta.dot)} />
                      <span>{activeRoleMeta.label}</span>
                    </span>
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  {(["patient", "expert", "admin"] as const).map((r) => {
                    const rm = ROLE_META[r];
                    const RIcon = rm.icon;
                    return (
                      <SelectItem key={r} value={r}>
                        <span className="inline-flex items-center gap-2">
                          <RIcon className="h-3.5 w-3.5 text-[#0D9488]" />
                          <span>{rm.label}</span>
                        </span>
                      </SelectItem>
                    );
                  })}
                </SelectContent>
              </Select>
            </div>

            <button
              type="button"
              aria-label={mobileOpen ? "Đóng menu" : "Mở menu"}
              onClick={() => setMobileOpen((prev) => !prev)}
              className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-[#DCEAE4] bg-white/90 text-[#334155] md:hidden cursor-pointer"
            >
              {mobileOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
            </button>
          </div>
        </div>

        {/* Hairline bottom luminous accent */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-x-4 bottom-0 h-[1px] bg-gradient-to-r from-transparent via-[#14B8A6]/40 to-transparent"
        />
      </div>

      {/* Mobile Drawer */}
      {mobileOpen && (
        <div className="glass-surface mt-2 rounded-2xl p-3 md:hidden">
          <div className="flex flex-col gap-1">
            {allowedTabs.map((tab) => {
              const meta = TAB_META[tab];
              const Icon = meta.icon;
              const isActive = activeTab === tab;
              return (
                <button
                  key={tab}
                  type="button"
                  onClick={() => {
                    onTabChange(tab);
                    setMobileOpen(false);
                  }}
                  className={cn(
                    "flex items-center justify-between rounded-xl px-3.5 py-2.5 text-sm font-semibold transition-colors cursor-pointer",
                    isActive
                      ? "bg-gradient-to-r from-[#0D9488] to-[#06B6D4] text-white shadow-[0_4px_14px_rgba(6,182,212,0.28)]"
                      : "text-[#334155] hover:bg-[#E6F6F2]"
                  )}
                >
                  <span className="flex items-center gap-2.5">
                    <Icon className="h-4 w-4" />
                    {meta.label}
                  </span>
                  {tab === "review" && pendingCount > 0 && (
                    <span className="rounded-full bg-[#FEF3C7] px-2 py-0.5 text-xs font-bold text-[#92400E] tabular-nums">
                      {pendingCount}
                    </span>
                  )}
                </button>
              );
            })}
            {showSystemInfo && (
              <button
                type="button"
                onClick={() => {
                  setMobileOpen(false);
                  onOpenSystemModal();
                }}
                className="mt-1 flex items-center justify-between rounded-xl border border-[#DCEAE4] bg-[#F8FAF9] px-3.5 py-2.5 text-sm font-semibold text-[#334155] cursor-pointer"
              >
                <span className="flex items-center gap-2.5">
                  <ShieldAlert className="h-4 w-4 text-[#D97706]" />
                  Thông số & Cảnh báo hệ thống
                </span>
                {warnCount > 0 && (
                  <span className="rounded-full bg-[#FEF3C7] px-2 py-0.5 text-xs font-bold text-[#92400E]">
                    {warnCount}
                  </span>
                )}
              </button>
            )}
          </div>
        </div>
      )}
    </header>
  );
}
