import { create } from "zustand";

export interface ClipData {
  clip_id: string;
  product_name: string;
  duration: number;
  start_time: number;
  end_time: number;
  confidence: number;
  video_url: string;
  thumbnail_url: string;
  has_video: boolean;
  has_thumbnail: boolean;
}

interface TaskState {
  taskId: string | null;
  metadata: Record<string, unknown> | null;
  currentState: string;
  status: "idle" | "uploading" | "processing" | "done" | "error";
  error: string | null;
  progress: number;
  clips: ClipData[] | null;
  clipsLoading: boolean;
  selectedClips: Set<string>;
  setTask: (taskId: string, metadata: Record<string, unknown>) => void;
  setCurrentState: (state: string) => void;
  setStatus: (status: TaskState["status"]) => void;
  setError: (error: string) => void;
  setProgress: (progress: number) => void;
  reset: () => void;
  fetchClips: (taskId: string) => Promise<void>;
  toggleClipSelection: (clipId: string) => void;
  selectAllClips: () => void;
  clearSelection: () => void;
}

const initialState = {
  taskId: null,
  metadata: null,
  currentState: "UPLOADED",
  status: "idle" as const,
  error: null,
  progress: 0,
  clips: null,
  clipsLoading: false,
  selectedClips: new Set<string>(),
};

export const useTaskStore = create<TaskState>((set, get) => ({
  ...initialState,
  setTask: (taskId, metadata) =>
    set({ taskId, metadata, currentState: "UPLOADED", status: "processing", clips: null }),
  setCurrentState: (currentState) =>
    set((state) => (state.currentState === currentState ? state : { currentState })),
  setStatus: (status) =>
    set((state) => (state.status === status ? state : { status })),
  setError: (error) =>
    set((state) =>
      state.error === error && state.status === "error" ? state : { error, status: "error" },
    ),
  setProgress: (progress) =>
    set((state) => (state.progress === progress ? state : { progress })),
  reset: () => set(initialState),

  fetchClips: async (taskId: string) => {
    set({ clipsLoading: true });
    try {
      const resp = await fetch(`/api/tasks/${taskId}/clips`);
      if (!resp.ok) throw new Error("Failed to fetch clips");
      const data = await resp.json();
      set({ clips: data.clips, clipsLoading: false });
    } catch {
      set({ clips: [], clipsLoading: false });
    }
  },

  toggleClipSelection: (clipId: string) => {
    const next = new Set(get().selectedClips);
    if (next.has(clipId)) {
      next.delete(clipId);
    } else {
      next.add(clipId);
    }
    set({ selectedClips: next });
  },

  selectAllClips: () => {
    const clips = get().clips;
    if (!clips) return;
    set({ selectedClips: new Set(clips.map((c) => c.clip_id)) });
  },

  clearSelection: () => set({ selectedClips: new Set() }),
}));
