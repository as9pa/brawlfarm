/**
 * A dialog that will not fire until the name is typed out.
 *
 * Removing an instance and deleting a data folder cannot be undone, so the confirm button
 * stays disabled, and says what to type, until the trimmed value equals `word` exactly.
 * Case sensitive: on a case-sensitive disk Pie64 and pie64 are two different folders.
 *
 * The bad tone is one custom property on a wrapper rather than a new Button variant.
 * theme.css declares its colours with `@theme inline`, so `bg-accent` compiles to
 * `background-color: var(--accent)`: pointing --accent at --bad for this one subtree turns
 * the fill, and the focus ring with it, red in both themes, and Button's props stay exactly
 * as phase 4 left them.
 */
import { type ReactNode, useEffect, useId, useState } from "react";

import { Button } from "./Button";
import { Dialog } from "./Dialog";
import { Field } from "./Field";

export interface ConfirmDialogProps {
  open: boolean;
  onClose: () => void;
  title: string;
  body: ReactNode;
  word: string;
  confirmLabel: string;
  tone: "bad";
  onConfirm: () => void | Promise<void>;
}

const TONE_ACCENT: Record<ConfirmDialogProps["tone"], string> = {
  bad: "[--accent:var(--bad)]",
};

export function ConfirmDialog({
  open,
  onClose,
  title,
  body,
  word,
  confirmLabel,
  tone,
  onConfirm,
}: ConfirmDialogProps) {
  const [typed, setTyped] = useState("");
  const boxId = useId();
  const matches = typed.trim() === word;

  // The next thing this dialog confirms is a different instance, so a closed dialog cannot
  // keep the last name: reopening it would find the button already armed.
  useEffect(() => {
    if (!open) setTyped("");
  }, [open]);

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={title}
      actions={
        <>
          <Button variant="quiet" onClick={onClose}>
            Cancel
          </Button>
          <span className={TONE_ACCENT[tone]}>
            <Button
              variant="primary"
              disabled={!matches}
              disabledReason={`Type ${word} to confirm`}
              onClick={() => {
                // The caller owns the failure: it is the one that knows whether a refusal
                // belongs in a toast, in a row, or under the section title.
                void onConfirm();
              }}
            >
              {confirmLabel}
            </Button>
          </span>
        </>
      }
    >
      <div className="space-y-3">
        <div>{body}</div>
        <Field
          label="Type to confirm"
          id={boxId}
          value={typed}
          onChange={setTyped}
          width="full"
          placeholder={word}
        />
      </div>
    </Dialog>
  );
}
