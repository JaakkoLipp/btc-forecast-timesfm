import { useEffect } from "react";
import { AlertTriangle, CheckCircle2, Info, X } from "lucide-react";

export type ToastTone = "error" | "info" | "success";

export interface ToastItem {
  id: string;
  tone: ToastTone;
  message: string;
}

interface ToastStackProps {
  toasts: ToastItem[];
  onDismiss: (id: string) => void;
}

const toneStyle: Record<ToastTone, string> = {
  error: "border-negative/40 bg-negative/10 text-orange-100",
  info: "border-line bg-mutedPanel text-muted",
  success: "border-positive/40 bg-positive/10 text-positive",
};

const toneIcon = {
  error: AlertTriangle,
  info: Info,
  success: CheckCircle2,
} as const;

const TIMEOUT_MS: Record<ToastTone, number> = {
  error: 8000,
  info: 4000,
  success: 4000,
};

export function ToastStack({ toasts, onDismiss }: ToastStackProps) {
  useEffect(() => {
    if (!toasts.length) return;
    const timers = toasts.map((toast) =>
      window.setTimeout(() => onDismiss(toast.id), TIMEOUT_MS[toast.tone]),
    );
    return () => {
      timers.forEach((id) => window.clearTimeout(id));
    };
  }, [toasts, onDismiss]);

  if (!toasts.length) return null;

  return (
    <div className="pointer-events-none fixed right-5 top-5 z-50 flex w-80 max-w-[calc(100vw-40px)] flex-col gap-2">
      {toasts.map((toast) => {
        const Icon = toneIcon[toast.tone];
        return (
          <div
            key={toast.id}
            role="status"
            className={`pointer-events-auto flex items-start gap-2 rounded-lg border px-3 py-2 text-sm shadow-glow ${toneStyle[toast.tone]}`}
          >
            <Icon size={16} className="mt-0.5 shrink-0" />
            <div className="flex-1 leading-5">{toast.message}</div>
            <button
              type="button"
              className="text-muted hover:text-text"
              onClick={() => onDismiss(toast.id)}
              aria-label="Dismiss"
            >
              <X size={14} />
            </button>
          </div>
        );
      })}
    </div>
  );
}
