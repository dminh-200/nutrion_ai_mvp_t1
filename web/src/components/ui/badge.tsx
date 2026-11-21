import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors",
  {
    variants: {
      variant: {
        default: "border-[#CCE4DC] bg-[#ECFDF5] text-[#0B4F4A]",
        secondary: "border-[#E2E8F0] bg-[#F8FAFC] text-[#475569]",
        approved: "border-[#A7F3D0] bg-[#ECFDF5] text-[#065F46]",
        pending: "border-[#FDE68A] bg-[#FFFBEB] text-[#92400E]",
        redirect: "border-[#BAE6FD] bg-[#F0F9FF] text-[#0369A1]",
        danger: "border-[#FECACA] bg-[#FEF2F2] text-[#B91C1C]",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export function statusBadgeVariant(status: string): BadgeProps["variant"] {
  const s = status.trim().toLowerCase();
  if (s === "approved") return "approved";
  if (s === "pending_review" || s === "needs_human_review") return "pending";
  if (s === "redirect_to_doctor") return "redirect";
  if (s === "blocked" || s === "rejected") return "danger";
  return "secondary";
}
