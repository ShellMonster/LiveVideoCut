import { Check, Loader2, AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import { userFacingMessage } from "@/components/admin/format";

const STEPS = [
  { key: "UPLOADED", label: "上传完成" },
  { key: "EXTRACTING_FRAMES", label: "抽帧中" },
  { key: "SCENE_DETECTING", label: "场景检测" },
  { key: "VISUAL_SCREENING", label: "视觉预筛" },
  { key: "VLM_CONFIRMING", label: "VLM确认" },
  { key: "TRANSCRIBING", label: "语音转写" },
  { key: "PROCESSING", label: "视频处理" },
  { key: "COMPLETED", label: "完成" },
] as const;

interface ProgressBarProps {
  currentState: string;
  errorMessage?: string;
}

export function ProgressBar({ currentState, errorMessage }: ProgressBarProps) {
  const isError = currentState === "ERROR";
  const currentIndex = STEPS.findIndex((s) => s.key === currentState);

  return (
    <div className="w-full space-y-3">
      <div className="progress-bar h-2 w-full rounded-full bg-gray-200">
        <div
          className={cn(
            "h-2 rounded-full transition-all duration-500",
            isError ? "bg-red-500" : "bg-blue-500",
          )}
          style={{
            width: `${isError ? 100 : Math.max(((currentIndex + 1) / STEPS.length) * 100, 4)}%`,
          }}
        />
      </div>

      <div className="flex flex-wrap gap-x-4 gap-y-1">
        {STEPS.map((step, i) => {
          const done = !isError && i < currentIndex;
          const active = !isError && i === currentIndex;

          return (
            <span
              key={step.key}
              className={cn(
                "step-indicator flex items-center gap-1 text-xs",
                done && "text-green-600",
                active && "font-semibold text-blue-600",
                !done && !active && "text-gray-400",
                isError && i <= currentIndex && "text-red-500",
              )}
            >
              {done && <Check className="h-3 w-3" />}
              {active && <Loader2 className="h-3 w-3 animate-spin" />}
              {isError && i === currentIndex && <AlertCircle className="h-3 w-3" />}
              {step.label}
            </span>
          );
        })}
      </div>

      {isError && errorMessage && (
        <p className="text-sm text-red-600">{userFacingMessage(errorMessage) || "处理失败，请检查配置后重试"}</p>
      )}
    </div>
  );
}
