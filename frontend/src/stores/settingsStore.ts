import { create } from "zustand";

export type VlmProvider = "qwen" | "glm";
export type ExportMode = "smart" | "no_vlm" | "all_candidates" | "all_scenes";
export type StrictnessMode = "strict" | "standard" | "loose";
export type ReviewMode = "adjacent_frames" | "segment_multiframe";
export type SubtitleMode = "off" | "basic" | "styled" | "karaoke";
export type SubtitlePosition = "top" | "bottom" | "middle" | "custom";
export type SubtitleTemplate = "clean" | "ecommerce" | "bold" | "karaoke";
export type AsrProvider = "dashscope" | "volcengine" | "volcengine_vc";
export type FillerFilterMode = "off" | "subtitle" | "video";
export type SensitiveFilterMode = "video_segment" | "drop_clip";
export type SensitiveMatchMode = "contains" | "exact";
export type CoverStrategy = "content_first" | "person_first";
export type VideoSpeed = 0.5 | 0.75 | 1.0 | 1.25 | 1.5 | 1.75 | 2.0 | 3.0;
export type LlmType = "openai" | "gemini";
export type ExportResolution = "original" | "1080p" | "4k";
export type SegmentGranularity = "single_item" | "outfit";
export type ChangeDetectionFusionMode = "any_signal" | "weighted_vote";
export type ChangeDetectionSensitivity = "conservative" | "balanced" | "sensitive";
export type FFmpegPreset = "veryfast" | "fast" | "medium";
export type CommerceImageSize = "2K" | "1024x1024" | "1024x1536" | "1536x1024" | "2048x2048" | "2160x3840";
export type CommerceImageQuality = "auto" | "low" | "medium" | "high";

export interface Settings {
  enableVlm: boolean;
  exportMode: ExportMode;
  provider: VlmProvider;
  apiKey: string;
  apiBase: string;
  model: string;
  reviewStrictness: StrictnessMode;
  reviewMode: ReviewMode;
  sceneThreshold: number;
  frameSampleFps: number;
  recallCooldownSeconds: number;
  candidateLooseness: StrictnessMode;
  minSegmentDurationSeconds: number;
  dedupeWindowSeconds: number;
  mergeCount: number;
  allowReturnedProduct: boolean;
  maxCandidateCount: number;
  subtitleMode: SubtitleMode;
  subtitlePosition: SubtitlePosition;
  subtitleTemplate: SubtitleTemplate;
  subtitleFontSize: number;
  subtitleHighlightFontSize: number;
  fillerFilterMode: FillerFilterMode;
  sensitiveFilterEnabled: boolean;
  sensitiveWords: string[];
  sensitiveFilterMode: SensitiveFilterMode;
  sensitiveMatchMode: SensitiveMatchMode;
  coverStrategy: CoverStrategy;
  videoSpeed: VideoSpeed;
  boundarySnap: boolean;
  enableBoundaryRefinement: boolean;
  customPositionY: number | null;
  asrProvider: AsrProvider;
  asrApiKey: string;
  tosAk: string;
  tosSk: string;
  tosBucket: string;
  tosRegion: string;
  tosEndpoint: string;
  enableLlmAnalysis: boolean;
  llmApiKey: string;
  llmApiBase: string;
  llmModel: string;
  llmType: LlmType;
  exportResolution: ExportResolution;
  segmentGranularity: SegmentGranularity;
  changeDetectionFusionMode: ChangeDetectionFusionMode;
  changeDetectionSensitivity: ChangeDetectionSensitivity;
  clothingYoloConfidence: number;
  ffmpegPreset: FFmpegPreset;
  ffmpegCrf: number;
  bgmEnabled: boolean;
  bgmVolume: number;
  originalVolume: number;
  commerceGeminiApiKey: string;
  commerceGeminiApiBase: string;
  commerceGeminiModel: string;
  commerceGeminiTimeoutSeconds: number;
  commerceImageApiKey: string;
  commerceImageApiBase: string;
  commerceImageModel: string;
  commerceImageSize: CommerceImageSize;
  commerceImageQuality: CommerceImageQuality;
  commerceImageTimeoutSeconds: number;
}

export type SettingsPayload = {
  api_key?: string;
  enable_vlm?: boolean;
  export_mode?: ExportMode;
  vlm_provider?: VlmProvider;
  api_base?: string;
  model?: string;
  review_strictness?: StrictnessMode;
  review_mode?: ReviewMode;
  scene_threshold?: number;
  frame_sample_fps?: number;
  recall_cooldown_seconds?: number;
  candidate_looseness?: StrictnessMode;
  min_segment_duration_seconds?: number;
  dedupe_window_seconds?: number;
  merge_count?: number;
  allow_returned_product?: boolean;
  max_candidate_count?: number;
  subtitle_mode?: SubtitleMode;
  subtitle_position?: SubtitlePosition;
  subtitle_template?: SubtitleTemplate;
  subtitle_font_size?: number;
  subtitle_highlight_font_size?: number;
  filter_filler_mode?: FillerFilterMode;
  sensitive_filter_enabled?: boolean;
  sensitive_words?: string[];
  sensitive_filter_mode?: SensitiveFilterMode;
  sensitive_match_mode?: SensitiveMatchMode;
  cover_strategy?: CoverStrategy;
  video_speed?: VideoSpeed;
  boundary_snap?: boolean;
  enable_boundary_refinement?: boolean;
  custom_position_y?: number | null;
  asr_provider?: AsrProvider;
  asr_api_key?: string;
  tos_ak?: string;
  tos_sk?: string;
  tos_bucket?: string;
  tos_region?: string;
  tos_endpoint?: string;
  enable_llm_analysis?: boolean;
  llm_api_key?: string;
  llm_api_base?: string;
  llm_model?: string;
  llm_type?: LlmType;
  export_resolution?: ExportResolution;
  segment_granularity?: SegmentGranularity;
  change_detection_fusion_mode?: ChangeDetectionFusionMode;
  change_detection_sensitivity?: ChangeDetectionSensitivity;
  clothing_yolo_confidence?: number;
  ffmpeg_preset?: FFmpegPreset;
  ffmpeg_crf?: number;
  bgm_enabled?: boolean;
  bgm_volume?: number;
  original_volume?: number;
  commerce_gemini_api_key?: string;
  commerce_gemini_api_base?: string;
  commerce_gemini_model?: string;
  commerce_gemini_timeout_seconds?: number;
  commerce_image_api_key?: string;
  commerce_image_api_base?: string;
  commerce_image_model?: string;
  commerce_image_size?: CommerceImageSize;
  commerce_image_quality?: CommerceImageQuality;
  commerce_image_timeout_seconds?: number;
};

const STORAGE_KEY = "clipper-settings";

export const DEFAULT_API_BASES: Record<VlmProvider, string> = {
  qwen: "https://dashscope.aliyuncs.com/compatible-mode/v1",
  glm: "https://open.bigmodel.cn/api/paas/v4",
};

export const DEFAULT_MODELS: Record<VlmProvider, string> = {
  qwen: "qwen-vl-plus",
  glm: "glm-5v-turbo",
};

const defaultSettings: Settings = {
  enableVlm: true,
  exportMode: "smart",
  provider: "qwen",
  apiKey: "",
  apiBase: DEFAULT_API_BASES.qwen,
  model: DEFAULT_MODELS.qwen,
  reviewStrictness: "standard",
  reviewMode: "segment_multiframe",
  sceneThreshold: 27,
  frameSampleFps: 0.5,
  recallCooldownSeconds: 15,
  candidateLooseness: "standard",
  minSegmentDurationSeconds: 25,
  dedupeWindowSeconds: 90,
  mergeCount: 1,
  allowReturnedProduct: true,
  maxCandidateCount: 20,
  subtitleMode: "karaoke",
  subtitlePosition: "bottom",
  subtitleTemplate: "clean",
  subtitleFontSize: 45,
  subtitleHighlightFontSize: 55,
  fillerFilterMode: "off",
  sensitiveFilterEnabled: false,
  sensitiveWords: [],
  sensitiveFilterMode: "video_segment",
  sensitiveMatchMode: "contains",
  coverStrategy: "content_first" as CoverStrategy,
  videoSpeed: 1.25 as VideoSpeed,
  boundarySnap: true,
  enableBoundaryRefinement: false,
  customPositionY: null,
  asrProvider: "volcengine_vc",
  asrApiKey: "",
  tosAk: "",
  tosSk: "",
  tosBucket: "mp3-srt",
  tosRegion: "cn-beijing",
  tosEndpoint: "tos-cn-beijing.volces.com",
  enableLlmAnalysis: false,
  llmApiKey: "",
  llmApiBase: "",
  llmModel: "",
  llmType: "openai",
  exportResolution: "1080p" as ExportResolution,
  segmentGranularity: "single_item" as SegmentGranularity,
  changeDetectionFusionMode: "any_signal",
  changeDetectionSensitivity: "balanced",
  clothingYoloConfidence: 0.25,
  ffmpegPreset: "fast",
  ffmpegCrf: 23,
  bgmEnabled: true,
  bgmVolume: 0.25,
  originalVolume: 1.0,
  commerceGeminiApiKey: "",
  commerceGeminiApiBase: "https://generativelanguage.googleapis.com",
  commerceGeminiModel: "gemini-3-flash-preview",
  commerceGeminiTimeoutSeconds: 150,
  commerceImageApiKey: "",
  commerceImageApiBase: "https://api.openai.com/v1",
  commerceImageModel: "gpt-image-2",
  commerceImageSize: "2K",
  commerceImageQuality: "auto",
  commerceImageTimeoutSeconds: 500,
};

function loadSettings(): Settings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw) as Partial<Settings>;
        if (!parsed.exportMode && parsed.enableVlm === false) {
          parsed.exportMode = "no_vlm";
        }
        if (!parsed.commerceImageSize || parsed.commerceImageSize === "1024x1536") {
          parsed.commerceImageSize = "2K";
        }
        return { ...defaultSettings, ...parsed };
      }
  } catch {
    // ignore parse errors
  }
  return { ...defaultSettings };
}

function persistSettings(settings: Settings): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
  } catch {
    // ignore storage errors
  }
}

export function settingsToPayload(settings: Settings): SettingsPayload {
  return {
    api_key: settings.apiKey,
    enable_vlm: settings.enableVlm,
    export_mode: settings.exportMode,
    vlm_provider: settings.provider,
    api_base: settings.apiBase,
    model: settings.model,
    review_strictness: settings.reviewStrictness,
    review_mode: settings.reviewMode,
    scene_threshold: settings.sceneThreshold,
    frame_sample_fps: settings.frameSampleFps,
    recall_cooldown_seconds: settings.recallCooldownSeconds,
    candidate_looseness: settings.candidateLooseness,
    min_segment_duration_seconds: settings.minSegmentDurationSeconds,
    dedupe_window_seconds: settings.dedupeWindowSeconds,
    merge_count: settings.mergeCount,
    allow_returned_product: settings.allowReturnedProduct,
    max_candidate_count: settings.maxCandidateCount,
    subtitle_mode: settings.subtitleMode,
    subtitle_position: settings.subtitlePosition,
    subtitle_template: settings.subtitleTemplate,
    subtitle_font_size: settings.subtitleFontSize,
    subtitle_highlight_font_size: settings.subtitleHighlightFontSize,
    filter_filler_mode: settings.fillerFilterMode,
    sensitive_filter_enabled: settings.sensitiveFilterEnabled,
    sensitive_words: settings.sensitiveWords,
    sensitive_filter_mode: settings.sensitiveFilterMode,
    sensitive_match_mode: settings.sensitiveMatchMode,
    cover_strategy: settings.coverStrategy,
    video_speed: settings.videoSpeed,
    boundary_snap: settings.boundarySnap,
    enable_boundary_refinement: settings.enableBoundaryRefinement,
    custom_position_y: settings.customPositionY,
    asr_provider: settings.asrProvider,
    asr_api_key: settings.asrApiKey,
    tos_ak: settings.tosAk,
    tos_sk: settings.tosSk,
    tos_bucket: settings.tosBucket,
    tos_region: settings.tosRegion,
    tos_endpoint: settings.tosEndpoint,
    enable_llm_analysis: settings.enableLlmAnalysis,
    llm_api_key: settings.llmApiKey,
    llm_api_base: settings.llmApiBase,
    llm_model: settings.llmModel,
    llm_type: settings.llmType,
    export_resolution: settings.exportResolution,
    segment_granularity: settings.segmentGranularity,
    change_detection_fusion_mode: settings.changeDetectionFusionMode,
    change_detection_sensitivity: settings.changeDetectionSensitivity,
    clothing_yolo_confidence: settings.clothingYoloConfidence,
    ffmpeg_preset: settings.ffmpegPreset,
    ffmpeg_crf: settings.ffmpegCrf,
    bgm_enabled: settings.bgmEnabled,
    bgm_volume: settings.bgmVolume,
    original_volume: settings.originalVolume,
    commerce_gemini_api_key: settings.commerceGeminiApiKey,
    commerce_gemini_api_base: settings.commerceGeminiApiBase,
    commerce_gemini_model: settings.commerceGeminiModel,
    commerce_gemini_timeout_seconds: settings.commerceGeminiTimeoutSeconds,
    commerce_image_api_key: settings.commerceImageApiKey,
    commerce_image_api_base: settings.commerceImageApiBase,
    commerce_image_model: settings.commerceImageModel,
    commerce_image_size: settings.commerceImageSize,
    commerce_image_quality: settings.commerceImageQuality,
    commerce_image_timeout_seconds: settings.commerceImageTimeoutSeconds,
  };
}

function payloadValuesEqual(left: unknown, right: unknown): boolean {
  if (Array.isArray(left) || Array.isArray(right)) {
    return JSON.stringify(left ?? []) === JSON.stringify(right ?? []);
  }
  return left === right;
}

export function diffSettingsToPayload(base: Settings, draft: Settings): SettingsPayload {
  const basePayload = settingsToPayload(base);
  const draftPayload = settingsToPayload(draft);
  const diff: SettingsPayload = {};

  for (const key of Object.keys(draftPayload) as Array<keyof SettingsPayload>) {
    if (!payloadValuesEqual(basePayload[key], draftPayload[key])) {
      diff[key] = draftPayload[key] as never;
    }
  }

  return diff;
}

export function payloadToSettings(payload: SettingsPayload): Settings {
  return {
    ...defaultSettings,
    enableVlm: payload.enable_vlm ?? defaultSettings.enableVlm,
    exportMode: payload.export_mode ?? defaultSettings.exportMode,
    provider: payload.vlm_provider ?? defaultSettings.provider,
    apiKey: payload.api_key ?? defaultSettings.apiKey,
    apiBase: payload.api_base ?? defaultSettings.apiBase,
    model: payload.model ?? defaultSettings.model,
    reviewStrictness: payload.review_strictness ?? defaultSettings.reviewStrictness,
    reviewMode: payload.review_mode ?? defaultSettings.reviewMode,
    sceneThreshold: payload.scene_threshold ?? defaultSettings.sceneThreshold,
    frameSampleFps: payload.frame_sample_fps ?? defaultSettings.frameSampleFps,
    recallCooldownSeconds: payload.recall_cooldown_seconds ?? defaultSettings.recallCooldownSeconds,
    candidateLooseness: payload.candidate_looseness ?? defaultSettings.candidateLooseness,
    minSegmentDurationSeconds: payload.min_segment_duration_seconds ?? defaultSettings.minSegmentDurationSeconds,
    dedupeWindowSeconds: payload.dedupe_window_seconds ?? defaultSettings.dedupeWindowSeconds,
    mergeCount: payload.merge_count ?? defaultSettings.mergeCount,
    allowReturnedProduct: payload.allow_returned_product ?? defaultSettings.allowReturnedProduct,
    maxCandidateCount: payload.max_candidate_count ?? defaultSettings.maxCandidateCount,
    subtitleMode: payload.subtitle_mode ?? defaultSettings.subtitleMode,
    subtitlePosition: payload.subtitle_position ?? defaultSettings.subtitlePosition,
    subtitleTemplate: payload.subtitle_template ?? defaultSettings.subtitleTemplate,
    subtitleFontSize: payload.subtitle_font_size ?? defaultSettings.subtitleFontSize,
    subtitleHighlightFontSize: payload.subtitle_highlight_font_size ?? defaultSettings.subtitleHighlightFontSize,
    fillerFilterMode: payload.filter_filler_mode ?? defaultSettings.fillerFilterMode,
    sensitiveFilterEnabled: payload.sensitive_filter_enabled ?? defaultSettings.sensitiveFilterEnabled,
    sensitiveWords: payload.sensitive_words ?? defaultSettings.sensitiveWords,
    sensitiveFilterMode: payload.sensitive_filter_mode ?? defaultSettings.sensitiveFilterMode,
    sensitiveMatchMode: payload.sensitive_match_mode ?? defaultSettings.sensitiveMatchMode,
    coverStrategy: payload.cover_strategy ?? defaultSettings.coverStrategy,
    videoSpeed: payload.video_speed ?? defaultSettings.videoSpeed,
    boundarySnap: payload.boundary_snap ?? defaultSettings.boundarySnap,
    enableBoundaryRefinement: payload.enable_boundary_refinement ?? defaultSettings.enableBoundaryRefinement,
    customPositionY: payload.custom_position_y ?? defaultSettings.customPositionY,
    asrProvider: payload.asr_provider ?? defaultSettings.asrProvider,
    asrApiKey: payload.asr_api_key ?? defaultSettings.asrApiKey,
    tosAk: payload.tos_ak ?? defaultSettings.tosAk,
    tosSk: payload.tos_sk ?? defaultSettings.tosSk,
    tosBucket: payload.tos_bucket ?? defaultSettings.tosBucket,
    tosRegion: payload.tos_region ?? defaultSettings.tosRegion,
    tosEndpoint: payload.tos_endpoint ?? defaultSettings.tosEndpoint,
    enableLlmAnalysis: payload.enable_llm_analysis ?? defaultSettings.enableLlmAnalysis,
    llmApiKey: payload.llm_api_key ?? defaultSettings.llmApiKey,
    llmApiBase: payload.llm_api_base ?? defaultSettings.llmApiBase,
    llmModel: payload.llm_model ?? defaultSettings.llmModel,
    llmType: payload.llm_type ?? defaultSettings.llmType,
    exportResolution: payload.export_resolution ?? defaultSettings.exportResolution,
    segmentGranularity: payload.segment_granularity ?? defaultSettings.segmentGranularity,
    changeDetectionFusionMode: payload.change_detection_fusion_mode ?? defaultSettings.changeDetectionFusionMode,
    changeDetectionSensitivity: payload.change_detection_sensitivity ?? defaultSettings.changeDetectionSensitivity,
    clothingYoloConfidence: payload.clothing_yolo_confidence ?? defaultSettings.clothingYoloConfidence,
    ffmpegPreset: payload.ffmpeg_preset ?? defaultSettings.ffmpegPreset,
    ffmpegCrf: payload.ffmpeg_crf ?? defaultSettings.ffmpegCrf,
    bgmEnabled: payload.bgm_enabled ?? defaultSettings.bgmEnabled,
    bgmVolume: payload.bgm_volume ?? defaultSettings.bgmVolume,
    originalVolume: payload.original_volume ?? defaultSettings.originalVolume,
    commerceGeminiApiKey: payload.commerce_gemini_api_key ?? defaultSettings.commerceGeminiApiKey,
    commerceGeminiApiBase: payload.commerce_gemini_api_base ?? defaultSettings.commerceGeminiApiBase,
    commerceGeminiModel: payload.commerce_gemini_model ?? defaultSettings.commerceGeminiModel,
    commerceGeminiTimeoutSeconds: payload.commerce_gemini_timeout_seconds ?? defaultSettings.commerceGeminiTimeoutSeconds,
    commerceImageApiKey: payload.commerce_image_api_key ?? defaultSettings.commerceImageApiKey,
    commerceImageApiBase: payload.commerce_image_api_base ?? defaultSettings.commerceImageApiBase,
    commerceImageModel: payload.commerce_image_model ?? defaultSettings.commerceImageModel,
    commerceImageSize: payload.commerce_image_size ?? defaultSettings.commerceImageSize,
    commerceImageQuality: payload.commerce_image_quality ?? defaultSettings.commerceImageQuality,
    commerceImageTimeoutSeconds: payload.commerce_image_timeout_seconds ?? defaultSettings.commerceImageTimeoutSeconds,
  };
}

interface SettingsState extends Settings {
  setSettings: (partial: Partial<Settings>) => void;
  reset: () => void;
}

export const useSettingsStore = create<SettingsState>((set) => {
  const initial = loadSettings();

  return {
    ...initial,
    setSettings: (partial) =>
      set((state) => {
        const next = { ...state, ...partial };
        persistSettings(next);
        return next;
      }),
    reset: () => {
      persistSettings(defaultSettings);
      set(defaultSettings);
    },
  };
});
