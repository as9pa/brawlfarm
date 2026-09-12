/**
 * The modal focus contract, in one place.
 *
 * Focus moves into the panel on open, Tab cycles inside it, Escape closes it, and focus
 * returns to whatever opened it. Written by hand rather than pulled from a library: the
 * panel has two modals and neither owes anything to a dependency.
 *
 * onClose is held in a ref so the effect depends on `open` alone. A caller that builds
 * onClose inline hands over a new function on every render, and re-running the effect
 * would fire its cleanup, which returns focus to the opener and so takes focus straight
 * back out of the panel that just opened.
 */
import { type RefObject, useEffect, useRef } from "react";

const FOCUSABLE =
  'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function useFocusTrap(
  open: boolean,
  ref: RefObject<HTMLElement | null>,
  onClose: () => void,
): void {
  const onCloseRef = useRef(onClose);

  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    if (!open) return;
    const panel = ref.current;
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
    // ref is the stable object useRef returns, so only `open` ever re-runs the trap.
  }, [open, ref]);
}
