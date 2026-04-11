import { AlertCircle, RefreshCw, X } from "lucide-react";
import { cn } from "@/lib/utils";

const ERROR_LABELS: Record<string, string> = {
  UPLOAD_FAILED: "上传失败",
  VISUAL_FAILED: "视觉分析失败",
  VLM_FAILED: "VLM确认失败",
  ASR_FAILED: "语音转写失败",
  EXPORT_FAILED: "视频导出失败",
};

interface ErrorCardProps {
  errorType: string;
  errorMessage: string;
  onRetry?: () => void;
  onDismiss?: () => void;
  className?: string;
}

export function ErrorCard({
  errorType,
  errorMessage,
  onRetry,
  onDismiss,
  className,
}: ErrorCardProps) {
  const label = ERROR_LABELS[errorType] ?? errorType;

  return (
    <div
      className={cn(
        "rounded-lg border border-red-200 bg-red-50 p-4",
        className,
      )}
    >
      <div className="flex items-start gap-3">
        <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-red-500" />

        <div className="min-w-0 flex-1">
          <h3 className="text-sm font-semibold text-red-800">{label}</h3>
          <p className="mt-1 text-sm text-red-600 break-words">{errorMessage}</p>
        </div>

        {onDismiss && (
          <button
            type="button"
            onClick={onDismiss}
            className="shrink-0 rounded p-1 text-red-400 hover:bg-red-100 hover:text-red-600"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {onRetry && (
        <div className="mt-3 flex justify-end">
          <button
            type="button"
            onClick={onRetry}
            className="inline-flex items-center gap-1.5 rounded-md bg-red-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-red-700"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            重试
          </button>
        </div>
      )}
    </div>
  );
}
