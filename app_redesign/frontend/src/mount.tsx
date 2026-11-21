import type { ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";

export type ComponentArgs<Data> = {
  data: Data;
  parentElement: ShadowRoot | HTMLElement;
  setTriggerValue: (name: string, value: unknown) => void;
};

const mounted = new WeakMap<Element, Root>();

export function mount(parent: ShadowRoot | HTMLElement, selector: string, content: ReactNode) {
  const container = parent.querySelector(selector);
  if (!container) return;
  let root = mounted.get(container);
  if (!root) {
    root = createRoot(container);
    mounted.set(container, root);
  }
  root.render(content);
  return () => {
    // A data update can invoke cleanup without removing the host.
    window.setTimeout(() => {
      if (container.isConnected) return;
      mounted.get(container)?.unmount();
      mounted.delete(container);
    }, 0);
  };
}
