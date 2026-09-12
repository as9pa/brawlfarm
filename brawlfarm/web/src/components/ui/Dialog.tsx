/**
 * A centred modal.
 *
 * The same focus contract as Drawer, because it is literally the same hook. A click on the
 * backdrop closes it and a click on the panel does not, which is why the backdrop is the
 * panel's sibling rather than its parent: no click has to be stopped from propagating.
 */
import { type ReactNode, useId, useRef } from "react";

import { useFocusTrap } from "./useFocusTrap";

export interface DialogProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  actions?: ReactNode;
}

export function Dialog({ open, onClose, title, children, actions }: DialogProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const titleId = useId();
  useFocusTrap(open, panelRef, onClose);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div aria-hidden="true" className="absolute inset-0 bg-scrim" onClick={onClose} />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        className="relative w-[480px] max-w-full rounded-[10px] border border-line bg-panel outline-none"
      >
        <h2 id={titleId} className="border-b border-line px-4 py-3 text-[15px] font-semibold">
          {title}
        </h2>
        <div className="px-4 py-3 text-[13px]">{children}</div>
        {actions !== undefined && (
          <div className="flex items-center justify-end gap-2 border-t border-line px-4 py-3">
            {actions}
          </div>
        )}
      </div>
    </div>
  );
}
