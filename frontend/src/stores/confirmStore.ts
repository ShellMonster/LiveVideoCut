import { create } from "zustand";

interface ConfirmOptions {
  title: string;
  description: string;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
}

interface ConfirmState extends ConfirmOptions {
  visible: boolean;
  resolver: ((confirmed: boolean) => void) | null;
  confirm: (options: ConfirmOptions) => Promise<boolean>;
  resolve: (confirmed: boolean) => void;
}

export const useConfirmStore = create<ConfirmState>((set, get) => ({
  title: "",
  description: "",
  confirmLabel: "确认",
  cancelLabel: "取消",
  danger: false,
  visible: false,
  resolver: null,
  confirm: (options) =>
    new Promise<boolean>((resolve) => {
      const currentResolver = get().resolver;
      if (currentResolver) currentResolver(false);
      set({
        ...options,
        confirmLabel: options.confirmLabel ?? "确认",
        cancelLabel: options.cancelLabel ?? "取消",
        danger: options.danger ?? false,
        visible: true,
        resolver: resolve,
      });
    }),
  resolve: (confirmed) => {
    const resolver = get().resolver;
    set({
      title: "",
      description: "",
      confirmLabel: "确认",
      cancelLabel: "取消",
      danger: false,
      visible: false,
      resolver: null,
    });
    resolver?.(confirmed);
  },
}));
