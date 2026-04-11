import { create } from "zustand";

export interface Settings {
  apiKey: string;
  apiBase: string;
  model: string;
  funasrMode: "local" | "remote";
}

const STORAGE_KEY = "clipper-settings";

const defaultSettings: Settings = {
  apiKey: "",
  apiBase: "https://dashscope.aliyuncs.com/compatible-mode/v1",
  model: "qwen-vl-plus",
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
