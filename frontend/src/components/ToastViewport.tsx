import { AlertCircle, CheckCircle2, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { useToastStore } from "@/stores/toastStore";

const toastStyles = {
  success: {
    container: "border-emerald-200 bg-emerald-50 text-emerald-900",
    icon: "text-emerald-600",
    button: "text-emerald-500 hover:bg-emerald-100 hover:text-emerald-700",
    Icon: CheckCircle2,
  },
  error: {
    container: "border-red-200 bg-red-50 text-red-900",
    icon: "text-red-600",
    button: "text-red-500 hover:bg-red-100 hover:text-red-700",
    Icon: AlertCircle,
  },
} as const;

export function ToastViewport() {
  const { message, variant, visible, hideToast } = useToastStore();

  if (!visible || !message) {
    return null;
  }

  const { container, icon, button, Icon } = toastStyles[variant];

  return (
    <div className="pointer-events-none fixed right-4 top-16 z-[60] w-[calc(100vw-2rem)] max-w-sm">
      <div
        className={cn(
          "pointer-events-auto flex items-start gap-3 rounded-xl border px-4 py-3 shadow-lg transition-opacity",
          container,
        )}
        role={variant === "error" ? "alert" : "status"}
        aria-live="polite"
      >
        <Icon className={cn("mt-0.5 h-5 w-5 shrink-0", icon)} />
        <p className="min-w-0 flex-1 text-sm font-medium break-words">{message}</p>
        <button
          type="button"
          onClick={hideToast}
          className={cn("shrink-0 rounded p-1 transition-colors", button)}
          aria-label="关闭提示"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
