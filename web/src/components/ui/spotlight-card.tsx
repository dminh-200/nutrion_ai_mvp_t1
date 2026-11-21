import * as React from "react";
import { cn } from "@/lib/utils";

export interface SpotlightCardProps extends React.HTMLAttributes<HTMLDivElement> {
  tone?: "light" | "dark";
}

export const SpotlightCard = React.forwardRef<HTMLDivElement, SpotlightCardProps>(
  ({ className, tone = "light", children, onMouseMove, ...props }, ref) => {
    const innerRef = React.useRef<HTMLDivElement | null>(null);

    const setRefs = React.useCallback(
      (node: HTMLDivElement | null) => {
        innerRef.current = node;
        if (typeof ref === "function") {
          ref(node);
        } else if (ref) {
          (ref as React.MutableRefObject<HTMLDivElement | null>).current = node;
        }
      },
      [ref]
    );

    const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
      const el = innerRef.current;
      if (el) {
        const rect = el.getBoundingClientRect();
        el.style.setProperty("--spot-x", `${e.clientX - rect.left}px`);
        el.style.setProperty("--spot-y", `${e.clientY - rect.top}px`);
      }
      onMouseMove?.(e);
    };

    return (
      <div
        ref={setRefs}
        onMouseMove={handleMouseMove}
        className={cn("group/spot relative overflow-hidden", className)}
        {...props}
      >
        <div
          aria-hidden="true"
          className={cn(
            "pointer-events-none absolute inset-0 z-0 opacity-0 transition-opacity duration-300 group-hover/spot:opacity-100",
            tone === "dark" ? "spotlight-overlay-dark" : "spotlight-overlay"
          )}
        />
        <div className="relative z-10 h-full">{children}</div>
      </div>
    );
  }
);
SpotlightCard.displayName = "SpotlightCard";
