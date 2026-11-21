import { useEffect, useState } from "react";
import { animate, useReducedMotion } from "framer-motion";

interface AnimatedNumberProps {
  value: number;
  duration?: number;
  formatter?: (val: number) => string;
  className?: string;
}

export function AnimatedNumber({
  value,
  duration = 0.45,
  formatter = (v) => Math.round(v).toLocaleString("vi-VN"),
  className,
}: AnimatedNumberProps) {
  const prefersReduced = useReducedMotion();
  const safeTarget = Number.isFinite(value) ? value : 0;
  const [display, setDisplay] = useState<number>(prefersReduced ? safeTarget : 0);

  useEffect(() => {
    if (prefersReduced) {
      setDisplay(safeTarget);
      return;
    }
    const controls = animate(0, safeTarget, {
      duration,
      ease: [0.22, 1, 0.36, 1],
      onUpdate: (latest) => setDisplay(latest),
    });
    return () => controls.stop();
  }, [safeTarget, duration, prefersReduced]);

  return <span className={className}>{formatter(display)}</span>;
}
