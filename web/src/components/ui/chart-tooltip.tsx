import { formatInt } from "@/lib/format";

interface TooltipPayloadEntry {
  name?: string;
  value?: number | string;
  color?: string;
  dataKey?: string;
  payload?: {
    color?: string;
    grams?: number;
    pct?: number;
    fill?: string;
  };
}

interface ChartTooltipProps {
  active?: boolean;
  payload?: TooltipPayloadEntry[];
  label?: string;
  unit?: string;
  valueFormatter?: (val: number, entry: TooltipPayloadEntry) => string;
}

export function ChartTooltip({
  active,
  payload,
  label,
  unit = "",
  valueFormatter,
}: ChartTooltipProps) {
  if (!active || !payload || !payload.length) return null;

  return (
    <div className="min-w-[148px] rounded-xl border border-[#D4E4DD] bg-white/95 px-3 py-2.5 shadow-[0_10px_28px_rgba(11,79,74,0.12)] backdrop-blur-md">
      {label && (
        <p className="mb-1.5 border-b border-[#F1F5F3] pb-1 text-[11px] font-bold text-[#0F172A]">
          {label}
        </p>
      )}
      <div className="space-y-1">
        {payload.map((entry, idx) => {
          const rawNum = typeof entry.value === "number" ? entry.value : Number(entry.value ?? 0);
          const dotColor = entry.color || entry.payload?.color || entry.payload?.fill || "#0B4F4A";
          const formatted = valueFormatter
            ? valueFormatter(rawNum, entry)
            : `${formatInt(rawNum)}${unit ? ` ${unit}` : ""}`;

          return (
            <div key={`${entry.name ?? idx}`} className="flex items-center justify-between gap-4 text-xs">
              <span className="flex items-center gap-1.5 font-medium text-[#475569]">
                <span
                  className="h-2 w-2 shrink-0 rounded-full"
                  style={{ backgroundColor: dotColor }}
                />
                {entry.name}
              </span>
              <span className="font-mono font-bold text-[#0F172A] tabular-nums">
                {formatted}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
