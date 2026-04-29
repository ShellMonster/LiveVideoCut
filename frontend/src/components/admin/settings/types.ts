import type { Settings } from "@/stores/settingsStore";

export type SettingsDraft = Settings;
export type UpdateSettingsDraft = (partial: Partial<SettingsDraft>) => void;
