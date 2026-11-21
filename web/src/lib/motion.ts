import type { Transition, Variants } from "framer-motion";

export const PAGE_TRANSITION: Transition = {
  duration: 0.16,
  ease: [0.22, 1, 0.36, 1],
};

export const TAB_SPRING: Transition = {
  type: "spring",
  stiffness: 440,
  damping: 34,
  mass: 0.85,
};

export const STAGGER_CONTAINER: Variants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: {
      staggerChildren: 0.04,
      delayChildren: 0.02,
    },
  },
};

export const STAGGER_ITEM: Variants = {
  hidden: { opacity: 0, y: 8 },
  show: {
    opacity: 1,
    y: 0,
    transition: {
      duration: 0.2,
      ease: [0.22, 1, 0.36, 1],
    },
  },
};
