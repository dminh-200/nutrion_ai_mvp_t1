import * as React from "react";
import { cn } from "@/lib/utils";

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, type, ...props }, ref) => (
    <input
      type={type}
      className={cn(
        "flex h-10 w-full rounded-xl border border-[#D5E2DC] bg-white px-3.5 py-2 text-sm text-[#0F172A] shadow-2xs transition-colors placeholder:text-[#94A3B8] focus-visible:outline-none focus-visible:border-[#0D9488] focus-visible:ring-2 focus-visible:ring-[#0D9488]/20 disabled:cursor-not-allowed disabled:bg-[#F8FAFC] disabled:opacity-60",
        className
      )}
      ref={ref}
      {...props}
    />
  )
);
Input.displayName = "Input";

export const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement>
>(({ className, ...props }, ref) => (
  <textarea
    className={cn(
      "flex min-h-[96px] w-full rounded-xl border border-[#D5E2DC] bg-white px-3.5 py-2.5 text-sm text-[#0F172A] shadow-2xs transition-colors placeholder:text-[#94A3B8] focus-visible:outline-none focus-visible:border-[#0D9488] focus-visible:ring-2 focus-visible:ring-[#0D9488]/20 disabled:cursor-not-allowed disabled:opacity-60",
      className
    )}
    ref={ref}
    {...props}
  />
));
Textarea.displayName = "Textarea";

export const Label = React.forwardRef<
  HTMLLabelElement,
  React.LabelHTMLAttributes<HTMLLabelElement>
>(({ className, ...props }, ref) => (
  <label
    ref={ref}
    className={cn("text-xs font-semibold uppercase tracking-wide text-[#475569]", className)}
    {...props}
  />
));
Label.displayName = "Label";
