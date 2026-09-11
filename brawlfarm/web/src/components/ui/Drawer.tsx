/**
 * A right-side modal panel.
 *
 * Focus moves into the panel on open, Tab cycles inside it, Escape closes it, and focus
 * returns to whatever opened it. Written by hand rather than pulled from a library: this
 * is the only modal in the panel and it owes nothing to a dependency.
 */
import { type ReactNode, useEffect, useRef } from "react";

import { Button } from "./Button";

const FOCUSABLE =
  'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export interface DrawerProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  actions?: ReactNode;
}

export function Drawer({ open, onClose, title, children, actions }: DrawerProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  // Held in a ref so the effect below depends on `open` alone. A caller that builds onClose
  // inline hands over a new function on every render, and re-running the effect would fire
  // its cleanup, which returns focus to the opener and so takes it out of the open panel.
  const onCloseRef = useRef(onClose);

  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    if (!open) return;
    const panel = panelRef.current;
    if (panel === null) return;
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    panel.focus();

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onCloseRef.current();
        return;
      }
      if (event.key !== "Tab") return;
      const focusable = [...panel.querySelectorAll<HTMLElement>(FOCUSABLE)];
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      opener?.focus();
    };
  }, [open]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-40">
      <div aria-hidden="true" className="absolute inset-0 bg-scrim" onClick={onClose} />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
        className="absolute right-0 top-0 flex h-full w-[360px] flex-col border-l border-line bg-panel outline-none"
      >
        <header className="flex h-[52px] shrink-0 items-center justify-between border-b border-line px-4">
          <h2 className="text-[15px] font-semibold">{title}</h2>
          <div className="flex items-center gap-2">
            {actions}
            <Button variant="text" size="sm" onClick={onClose}>
              Close
            </Button>
          </div>
        </header>
        <div className="min-h-0 flex-1 overflow-y-auto">{children}</div>
      </div>
    </div>
  );
}
