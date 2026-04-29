import type { AsrProvider, ExportMode, SubtitleMode, SubtitlePosition, SubtitleTemplate } from "@/stores/settingsStore";

export const sectionTabs = ["处理预设", "AI 服务", "转写服务", "字幕设置", "敏感词过滤", "切分策略", "导出与音频", "高级参数"];

export const exportModeLabels: Record<ExportMode, string> = {
  smart: "智能模式",
  no_vlm: "跳过 VLM",
  all_candidates: "候选全切",
  all_scenes: "场景全切",
};

export const asrLabels: Record<AsrProvider, string> = {
  volcengine_vc: "火山 VC",
  volcengine: "火山标准",
  dashscope: "DashScope",
};

export const subtitleLabels: Record<SubtitleMode, string> = {
  off: "关闭",
  basic: "基础字幕",
  styled: "样式字幕",
  karaoke: "卡拉 OK 字幕",
};

export const subtitlePositionLabels: Record<SubtitlePosition, string> = {
  top: "顶部",
  middle: "中部",
  bottom: "底部",
  custom: "自定义",
};

export const subtitleTemplateLabels: Record<SubtitleTemplate, string> = {
  clean: "简洁",
  ecommerce: "电商",
  bold: "加粗",
  karaoke: "卡拉 OK",
};
