import { create } from "zustand";

export type ToastVariant = "success" | "error";

interface ToastState {
  id: number;
  message: string;
  variant: ToastVariant;
  visible: boolean;
  showToast: (message: string, variant: ToastVariant) => void;
  hideToast: () => void;
}

const TOAST_DURATION_MS = 3000;

let nextToastId = 1;
let dismissTimer: ReturnType<typeof window.setTimeout> | null = null;

function clearDismissTimer() {
  if (dismissTimer) {
    window.clearTimeout(dismissTimer);
    dismissTimer = null;
  }
}

export const useToastStore = create<ToastState>((set) => ({
  id: 0,
  message: "",
  variant: "success",
  visible: false,
  showToast: (message, variant) => {
    clearDismissTimer();
    const id = nextToastId++;
    set({ id, message, variant, visible: true });
    dismissTimer = window.setTimeout(() => {
      set((state) => (state.id === id ? { ...state, visible: false } : state));
      dismissTimer = null;
    }, TOAST_DURATION_MS);
  },
  hideToast: () => {
    clearDismissTimer();
    set((state) => ({ ...state, visible: false }));
  },
}));
