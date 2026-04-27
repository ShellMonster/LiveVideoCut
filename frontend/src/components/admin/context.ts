import { createContext, useContext } from "react";
import type { TaskItem } from "./types";

interface AdminContextValue {
  selectedTask: TaskItem | null;
  setSelectedTask: (task: TaskItem | null) => void;
}

export const AdminContext = createContext<AdminContextValue | null>(null);

export function useAdminContext() {
  const ctx = useContext(AdminContext);
  if (!ctx) throw new Error("useAdminContext must be used inside AdminLayout");
  return ctx;
}
