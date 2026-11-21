import type { ReactNode } from "react";

interface PageHeaderProps {
  eyebrow: string;
  title: string;
  description: string;
  rightSlot?: ReactNode;
  bottomSlot?: ReactNode;
}

export function PageHeader({
  eyebrow,
  title,
  description,
  rightSlot,
  bottomSlot,
}: PageHeaderProps) {
  return (
    <section className="hero-luminous relative mb-5 overflow-hidden rounded-2xl px-5 py-4 sm:px-6 sm:py-5">
      {/* Decorative soft ambient orb */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -right-14 -top-14 h-44 w-44 rounded-full bg-gradient-to-br from-[#14B8A6]/18 to-[#38BDF8]/12 blur-2xl"
      />

      <div className="relative flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="max-w-2xl">
          <div className="mb-2 inline-flex items-center gap-1.5 rounded-full border border-[#BFE3DA] bg-white/85 px-2.5 py-0.5 text-[10.5px] font-bold uppercase tracking-[0.12em] text-[#0B4F4A] shadow-2xs">
            <span className="h-1.5 w-1.5 rounded-full bg-[#14B8A6] shadow-[0_0_6px_rgba(20,184,166,0.75)]" />
            <span>{eyebrow}</span>
          </div>
          <h1 className="text-xl sm:text-[26px] font-extrabold tracking-tight text-[#0F172A] leading-tight">
            {title}
          </h1>
          <p className="mt-1 text-xs sm:text-sm text-[#475569] leading-relaxed">
            {description}
          </p>
        </div>
        {rightSlot && <div className="relative z-10 shrink-0">{rightSlot}</div>}
      </div>

      {bottomSlot && (
        <div className="relative z-10 mt-3.5 border-t border-[#CDE6DF]/80 pt-3">
          {bottomSlot}
        </div>
      )}
    </section>
  );
}
