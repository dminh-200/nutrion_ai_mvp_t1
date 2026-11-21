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
    <section className="hero-aurora-dark relative mb-5 overflow-hidden rounded-2xl px-5 py-4 text-white sm:px-6 sm:py-4.5">
      {/* Decorative soft aurora orb top-right */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -right-12 -top-14 h-48 w-48 rounded-full bg-gradient-to-br from-[#22D3EE]/35 via-[#34D399]/22 to-transparent blur-2xl"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -left-16 -bottom-16 h-36 w-36 rounded-full bg-gradient-to-tr from-[#06B6D4]/22 to-transparent blur-2xl"
      />

      <div className="relative flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="max-w-2xl">
          <div className="mb-1.5 inline-flex items-center gap-1.5 rounded-full border border-[#5EEAD4]/35 bg-[#14B8A6]/18 px-2.5 py-0.5 text-[10.5px] font-bold uppercase tracking-[0.12em] text-[#CCFBF1] shadow-[0_0_16px_rgba(45,212,191,0.22)]">
            <span className="h-1.5 w-1.5 rounded-full bg-[#2DD4BF] shadow-[0_0_8px_rgba(45,212,191,0.95)]" />
            <span>{eyebrow}</span>
          </div>
          <h1 className="text-xl sm:text-[25px] font-extrabold tracking-tight text-white leading-tight">
            {title}
          </h1>
          <p className="mt-1 text-xs sm:text-sm text-[#CCFBF1]/85 leading-relaxed">
            {description}
          </p>
        </div>
        {rightSlot && <div className="relative z-10 shrink-0">{rightSlot}</div>}
      </div>

      {bottomSlot && (
        <div className="relative z-10 mt-3.5 border-t border-white/15 pt-3">
          {bottomSlot}
        </div>
      )}
    </section>
  );
}
