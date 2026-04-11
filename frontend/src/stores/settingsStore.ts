import { create } from "zustand";

export type VlmProvider = "qwen" | "glm";
export type StrictnessMode = "strict" | "standard" | "loose";
export type ReviewMode = "adjacent_frames" | "segment_multiframe";
export type SubtitleMode = "off" | "basic" | "styled" | "karaoke";
export type SubtitlePosition = "bottom" | "middle" | "custom";
export type SubtitleTemplate = "clean" | "ecommerce" | "bold" | "karaoke";

export interface Settings {
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
  allowReturnedProduct: boolean;
  maxCandidateCount: number;
  subtitleMode: SubtitleMode;
  subtitlePosition: SubtitlePosition;
  subtitleTemplate: SubtitleTemplate;
  funasrMode: "local" | "remote";
}

const STORAGE_KEY = "clipper-settings";

const defaultSettings: Settings = {
  provider: "qwen",
  apiKey: "",
  apiBase: "https://dashscope.aliyuncs.com/compatible-mode/v1",
  model: "qwen-vl-plus",
  reviewStrictness: "standard",
  reviewMode: "segment_multiframe",
  sceneThreshold: 27,
  frameSampleFps: 2,
  recallCooldownSeconds: 15,
  candidateLooseness: "standard",
  minSegmentDurationSeconds: 25,
  dedupeWindowSeconds: 90,
  allowReturnedProduct: true,
  maxCandidateCount: 20,
  subtitleMode: "off",
  subtitlePosition: "bottom",
  subtitleTemplate: "clean",
  funasrMode: "local",
};

function loadSettings(): Settings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      return { ...defaultSettings, ...JSON.parse(raw) };
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
