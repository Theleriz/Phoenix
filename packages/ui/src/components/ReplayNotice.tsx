import type { ReactNode } from "react";

/** The "synthetic/demo" banner both apps render, structurally identical. */
export function ReplayNotice({ label, detail }: { label: ReactNode; detail: string }) {
  return (
    <div className="replay-notice">
      <i />
      <span>{label}</span>
      <button aria-label="Information" title={detail}>
        i
      </button>
    </div>
  );
}
