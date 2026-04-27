import type React from "react";
import {
  Activity,
  FileVideo,
  LayoutDashboard,
  ListChecks,
  Music,
  Scissors,
  Settings,
} from "lucide-react";
import type { PageKey } from "./types";

export const navItems: { key: PageKey; label: string; icon: React.ElementType }[] = [
  { key: "projects", label: "项目总览", icon: LayoutDashboard },
  { key: "queue", label: "任务队列", icon: ListChecks },
  { key: "review", label: "剪辑复核", icon: Scissors },
  { key: "assets", label: "片段资产", icon: FileVideo },
  { key: "music", label: "音乐库", icon: Music },
  { key: "diagnostics", label: "数据诊断", icon: Activity },
  { key: "settings", label: "系统设置", icon: Settings },
];

export const statusMap = {
  completed: { label: "已完成", className: "bg-emerald-50 text-emerald-700 ring-emerald-100" },
  failed: { label: "失败", className: "bg-red-50 text-red-700 ring-red-100" },
  uploaded: { label: "已上传", className: "bg-slate-100 text-slate-600 ring-slate-200" },
  processing: { label: "处理中", className: "bg-blue-50 text-blue-700 ring-blue-100" },
} as const;

export const stageLabels: Record<string, string> = {
  UPLOADED: "上传完成",
  EXTRACTING_FRAMES: "抽帧中",
  SCENE_DETECTING: "换衣检测",
  VISUAL_SCREENING: "视觉预筛",
  VLM_CONFIRMING: "VLM确认",
  TRANSCRIBING: "ASR转写",
  LLM_ANALYZING: "LLM融合",
  PROCESSING: "导出中",
  COMPLETED: "完成",
  ERROR: "失败",
};

export const asrProviderLabels: Record<string, string> = {
  volcengine_vc: "火山 VC",
  volcengine_flash: "火山极速",
  volcengine: "火山标准",
  dashscope: "DashScope",
};

export const editableMoodOptions = ["bright", "casual", "warm", "luxury", "energetic", "soft", "clean", "elegant"];
export const editableCategoryOptions = ["default", "dress", "coat", "pants", "skirt", "shoes", "bag", "accessory", "beauty", "home"];
