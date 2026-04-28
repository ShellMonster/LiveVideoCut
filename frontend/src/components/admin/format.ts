import { asrProviderLabels, statusMap } from "./constants";
import type { ClipReprocessJob, ReviewSegment, TaskItem } from "./types";

export function classifyStatus(raw: string): keyof typeof statusMap {
  if (raw === "COMPLETED") return "completed";
  if (raw === "ERROR") return "failed";
  if (raw === "UPLOADED") return "uploaded";
  return "processing";
}

export function statusLabel(raw: string): string {
  return statusMap[classifyStatus(raw)].label;
}

export function statusBadgeClass(raw: string): string {
  return statusMap[classifyStatus(raw)].className;
}

export function formatDuration(seconds?: number): string {
  if (!seconds || seconds <= 0) return "—";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.round(seconds % 60);
  if (h > 0) return `${h}h ${m}m`;
  return `${m}:${String(s).padStart(2, "0")}`;
}

export function formatDate(dateStr?: string | null): string {
  if (!dateStr) return "—";
  const d = new Date(dateStr);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatBytes(bytes?: number): string {
  if (!bytes || bytes <= 0) return "0MB";
  const mb = bytes / (1024 * 1024);
  if (mb < 1024) return `${mb.toFixed(mb >= 10 ? 0 : 1)}MB`;
  return `${(mb / 1024).toFixed(1)}GB`;
}

export function formatElapsed(seconds?: number | null): string {
  if (seconds == null || seconds < 0) return "—";
  if (seconds < 60) return `${seconds.toFixed(seconds < 10 ? 1 : 0)}s`;
  const minutes = Math.floor(seconds / 60);
  const rest = Math.round(seconds % 60);
  if (minutes < 60) return `${minutes}m ${rest}s`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ${minutes % 60}m`;
}

export function formatConfidence(confidence?: number | null): string {
  if (confidence == null || Number.isNaN(confidence)) return "—";
  return confidence.toFixed(2);
}

export function displayTaskName(task: TaskItem): string {
  return task.display_name || task.original_filename || "未命名直播项目";
}

export function displayAsrProvider(provider?: string): string {
  if (!provider) return "—";
  return asrProviderLabels[provider] ?? provider;
}

export function progressByStatus(task: TaskItem): number {
  const order = [
    "UPLOADED",
    "EXTRACTING_FRAMES",
    "SCENE_DETECTING",
    "VISUAL_SCREENING",
    "VLM_CONFIRMING",
    "TRANSCRIBING",
    "LLM_ANALYZING",
    "PROCESSING",
    "COMPLETED",
  ];
  if (task.status === "COMPLETED") return 100;
  if (task.status === "ERROR") return 100;
  const idx = order.indexOf(task.status);
  if (idx < 0) return 18;
  return Math.max(10, Math.round(((idx + 1) / order.length) * 100));
}

export function resourcePercent(value?: number, max?: number): number | undefined {
  if (!value || !max || max <= 0) return undefined;
  return Math.min(100, Math.max(4, Math.round((value / max) * 100)));
}

export function reviewStatusLabel(status: ReviewSegment["review_status"]): string {
  const labels: Record<ReviewSegment["review_status"], string> = {
    pending: "待复核",
    approved: "已通过",
    skipped: "已跳过",
    needs_adjustment: "需调整",
  };
  return labels[status] ?? "待复核";
}

export function clipJobStatusLabel(status: NonNullable<ClipReprocessJob["status"]>): string {
  const labels: Record<NonNullable<ClipReprocessJob["status"]>, string> = {
    queued: "排队中",
    running: "处理中",
    completed: "已完成",
    failed: "失败",
  };
  return labels[status] ?? status;
}
