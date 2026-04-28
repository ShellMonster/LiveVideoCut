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

export function userFacingMessage(message?: string | null): string {
  if (!message) return "";
  const text = message.trim();
  const lower = text.toLowerCase();

  const replacements: Array<[RegExp, string]> = [
    [/openai image api key is not configured/i, "OpenAI Image API Key 未配置，请先在系统设置的 AI 商品素材中填写生图 Key"],
    [/gemini api key is not configured/i, "Gemini API Key 未配置，请先在系统设置的 AI 商品素材中填写识图 Key"],
    [/api key is not configured/i, "API Key 未配置，请先检查系统设置"],
    [/clip cover not found/i, "片段封面不存在，请先重新生成片段封面"],
    [/clip not found/i, "未找到该片段"],
    [/no valid commerce actions/i, "没有可执行的商品素材生成动作"],
    [/invalid image item key/i, "图片类型无效"],
    [/invalid task_id or segment_id format/i, "任务或片段 ID 格式无效"],
    [/invalid task_id or clip_name format/i, "任务或片段 ID 格式无效"],
    [/queue failed/i, "任务排队失败"],
    [/retry failed/i, "任务重试失败"],
    [/reprocess failed/i, "单片段重导出失败"],
    [/patch failed/i, "复核状态更新失败"],
    [/upload failed/i, "上传失败"],
    [/delete failed/i, "删除失败"],
    [/save failed/i, "保存失败"],
    [/network error/i, "网络错误，请检查连接"],
  ];

  for (const [pattern, replacement] of replacements) {
    if (pattern.test(text)) return replacement;
  }

  if (lower.includes("ai 商品素材生成失败")) {
    const detail = text.replace(/^AI 商品素材生成失败[:：]\s*/i, "");
    const translated = userFacingMessage(detail);
    return translated ? `AI 商品素材生成失败：${translated}` : "AI 商品素材生成失败，请检查配置后重试";
  }

  if ([...text].every((char) => char.charCodeAt(0) <= 0x7f)) {
    return "操作失败，请检查配置或稍后重试";
  }

  return text;
}
