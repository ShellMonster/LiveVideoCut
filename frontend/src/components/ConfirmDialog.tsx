import { AlertTriangle, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { useConfirmStore } from "@/stores/confirmStore";

export function ConfirmDialog() {
  const { visible, title, description, confirmLabel, cancelLabel, danger, resolve } = useConfirmStore();

  if (!visible) return null;

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-slate-950/35 px-4" role="presentation">
      <div className="w-full max-w-md rounded-xl border border-slate-200 bg-white shadow-xl" role="dialog" aria-modal="true" aria-labelledby="confirm-dialog-title">
        <div className="flex items-start gap-3 border-b border-slate-100 p-5">
          <div className={cn("mt-0.5 rounded-lg p-2", danger ? "bg-red-50 text-red-600" : "bg-blue-50 text-blue-600")}>
            <AlertTriangle size={18} />
          </div>
          <div className="min-w-0 flex-1">
            <h2 id="confirm-dialog-title" className="text-base font-semibold text-slate-950">
              {title}
            </h2>
            <p className="mt-1 text-sm leading-6 text-slate-500">{description}</p>
          </div>
          <button
            type="button"
            onClick={() => resolve(false)}
            className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
            aria-label="关闭确认弹窗"
          >
            <X size={16} />
          </button>
        </div>
        <div className="flex justify-end gap-2 p-4">
          <button
            type="button"
            onClick={() => resolve(false)}
            className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={() => resolve(true)}
            className={cn(
              "rounded-lg px-3 py-2 text-sm font-medium text-white",
              danger ? "bg-red-600 hover:bg-red-700" : "bg-blue-600 hover:bg-blue-700",
            )}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
