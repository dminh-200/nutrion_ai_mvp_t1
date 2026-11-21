import * as React from "react";
import { cn } from "@/lib/utils";

export function Skeleton({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      aria-hidden="true"
      className={cn(
        "clinical-skeleton rounded-xl bg-[#E7EFEA]",
        className
      )}
      {...props}
    />
  );
}
