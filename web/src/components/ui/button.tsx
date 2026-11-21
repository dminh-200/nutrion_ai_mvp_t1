import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-xl text-sm font-semibold transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0D9488]/35 focus-visible:ring-offset-1 disabled:pointer-events-none disabled:opacity-50 active:scale-[0.985] cursor-pointer",
  {
    variants: {
      variant: {
        default:
          "btn-sheen bg-gradient-to-r from-[#0D9488] via-[#0EA5A8] to-[#06B6D4] text-white shadow-[0_6px_18px_rgba(6,182,212,0.28),inset_0_1px_0_rgba(255,255,255,0.28)] hover:brightness-[1.04] hover:-translate-y-[0.5px] hover:shadow-[0_10px_26px_rgba(6,182,212,0.38)]",
        secondary:
          "border border-[#BDE6DC] bg-[#E8F8F4]/90 text-[#0B4F4A] hover:bg-[#D5F2EB] hover:border-[#5EEAD4]",
        outline:
          "border border-[#C8E0D8] bg-white/82 backdrop-blur-md text-[#0F172A] shadow-2xs hover:border-[#0D9488]/70 hover:bg-[#ECFEFF]/85",
        glassDark:
          "border border-white/25 bg-white/12 text-white backdrop-blur-md shadow-[inset_0_1px_0_rgba(255,255,255,0.2)] hover:border-[#5EEAD4]/60 hover:bg-white/20",
        ghost: "text-[#334155] hover:bg-[#E6F6F2] hover:text-[#0B4F4A]",
        destructive:
          "bg-gradient-to-r from-[#DC2626] to-[#EF4444] text-white shadow-sm hover:brightness-[1.03] hover:shadow-[0_6px_18px_rgba(220,38,38,0.25)]",
        destructiveOutline:
          "border border-[#FECACA] bg-[#FEF2F2]/90 text-[#B91C1C] hover:bg-[#FEE2E2]",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-8.5 rounded-lg px-3 text-xs",
        lg: "h-11 rounded-xl px-6 text-sm",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";
