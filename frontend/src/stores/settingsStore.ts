import { create } from "zustand";

export type VlmProvider = "qwen" | "glm";
export type ExportMode = "smart" | "no_vlm" | "all_candidates" | "all_scenes";
export type StrictnessMode = "strict" | "standard" | "loose";
export type ReviewMode = "adjacent_frames" | "segment_multiframe";
export type SubtitleMode = "off" | "basic" | "styled" | "karaoke";
export type SubtitlePosition = "bottom" | "middle" | "custom";
export type SubtitleTemplate = "clean" | "ecommerce" | "bold" | "karaoke";
export type AsrProvider = "dashscope" | "volcengine" | "volcengine_vc";
export type FillerFilterMode = "off" | "subtitle" | "video";
export type CoverStrategy = "content_first" | "person_first";
export type VideoSpeed = 0.5 | 0.75 | 1.0 | 1.25 | 1.5 | 1.75 | 2.0 | 3.0;
export type LlmType = "openai" | "gemini";
export type ExportResolution = "original" | "1080p" | "4k";

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
  fillerFilterMode: FillerFilterMode;
  coverStrategy: CoverStrategy;
  videoSpeed: VideoSpeed;
  funasrMode: "local" | "remote";
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
}

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
  subtitleMode: "basic",
  subtitlePosition: "bottom",
  subtitleTemplate: "clean",
  fillerFilterMode: "off",
  coverStrategy: "content_first" as CoverStrategy,
  videoSpeed: 1.25 as VideoSpeed,
  funasrMode: "local",
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
};

function loadSettings(): Settings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as Partial<Settings>;
      if (!parsed.exportMode && parsed.enableVlm === false) {
        parsed.exportMode = "no_vlm";
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
