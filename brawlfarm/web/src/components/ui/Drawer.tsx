/**
 * A right-side modal panel.
 *
 * Focus moves into the panel on open, Tab cycles inside it, Escape closes it, and focus
 * returns to whatever opened it: useFocusTrap owns all four, and Dialog shares the same
 * hook, so the two modals cannot drift apart.
 *
 * The page behind it does not scroll either: the body keeps its own overflow while the
 * panel is open and gets the captured value back on close, never a hard-coded "", so a
 * confirm opening over the drawer cannot unlock the page when it closes.
 */
import { type ReactNode, useEffect, useRef } from "react";

import { Button } from "./Button";
import { useFocusTrap } from "./useFocusTrap";

export interface DrawerProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  actions?: ReactNode;
}

export function Drawer({ open, onClose, title, children, actions }: DrawerProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  useFocusTrap(open, panelRef, onClose);

  useEffect(() => {
    if (!open) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous;
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
            <Button variant="quiet" size="sm" onClick={onClose}>
              Close
            </Button>
          </div>
        </header>
        <div className="min-h-0 flex-1 overflow-y-auto">{children}</div>
      </div>
    </div>
  );
}
