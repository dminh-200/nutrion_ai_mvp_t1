import * as React from "react";
import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import { Info } from "lucide-react";
import { cn } from "@/lib/utils";

export const TooltipProvider = TooltipPrimitive.Provider;
export const Tooltip = TooltipPrimitive.Root;
export const TooltipTrigger = TooltipPrimitive.Trigger;

export const TooltipContent = React.forwardRef<
  React.ElementRef<typeof TooltipPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof TooltipPrimitive.Content>
>(({ className, sideOffset = 6, ...props }, ref) => (
  <TooltipPrimitive.Portal>
    <TooltipPrimitive.Content
      ref={ref}
      sideOffset={sideOffset}
      className={cn(
        "z-50 max-w-xs rounded-xl border border-[#D4E4DD] bg-[#0F172A]/95 px-3 py-2 text-[11px] font-medium leading-relaxed text-white shadow-[0_10px_28px_rgba(11,79,74,0.22)] backdrop-blur-xs animate-in fade-in-0 zoom-in-95",
        className
      )}
      {...props}
    />
  </TooltipPrimitive.Portal>
));
TooltipContent.displayName = TooltipPrimitive.Content.displayName;

interface InfoTipProps {
  text: string;
  className?: string;
}

export function InfoTip({ text, className }: InfoTipProps) {
  return (
    <Tooltip delayDuration={180}>
      <TooltipTrigger asChild>
        <button
          type="button"
          aria-label="Thông tin giải thích"
          className={cn(
            "inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-[#64748B] transition-colors hover:bg-[#E6F4F1] hover:text-[#0B4F4A] cursor-help",
            className
          )}
        >
          <Info className="h-3 w-3" />
        </button>
      </TooltipTrigger>
      <TooltipContent>{text}</TooltipContent>
    </Tooltip>
  );
}
