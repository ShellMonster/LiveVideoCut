import { useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { ProgressBar } from "@/components/ProgressBar";
import { ToastViewport } from "@/components/ToastViewport";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { useTaskProgress } from "@/hooks/useWebSocket";
import { useTaskStore } from "@/stores/taskStore";
import { MobileNav, Sidebar } from "@/components/admin/shared";
import { AdminContext } from "@/components/admin/context";
import type { PageKey, TaskItem } from "@/components/admin/types";

// ---------- Route-to-PageKey mapping ----------

const routeToPageKey = (pathname: string): PageKey => {
  if (pathname === "/") return "projects";
  const segment = pathname.split("/")[1];
  if (segment === "create") return "create";
  return segment as PageKey;
};

const pageKeyToPath = (key: PageKey): string => {
  if (key === "projects") return "/";
  if (key === "create") return "/create";
  return `/${key}`;
};

// ---------- Layout ----------

export function AdminLayout() {
  const [selectedTask, setSelectedTask] = useState<TaskItem | null>(null);
  const { taskId, status, currentState, error } = useTaskStore();
  useTaskProgress(taskId);

  const location = useLocation();
  const navigate = useNavigate();
  const activePage = routeToPageKey(location.pathname);

  const handlePageChange = (key: PageKey) => {
    navigate(pageKeyToPath(key));
  };

  return (
    <AdminContext.Provider value={{ selectedTask, setSelectedTask }}>
      <div className="flex h-screen overflow-hidden bg-slate-50 text-slate-900">
        <ToastViewport />
        <ConfirmDialog />
        <Sidebar page={activePage} onPageChange={handlePageChange} />
        <div className="min-w-0 flex-1 overflow-y-auto">
          <MobileNav page={activePage} onPageChange={handlePageChange} />
          <Outlet context={{ selectedTask, setSelectedTask }} />

          {taskId && (status === "processing" || status === "error") && (
            <div className="fixed bottom-4 right-4 w-[calc(100vw-2rem)] rounded-lg border border-slate-200 bg-white p-4 shadow-lg sm:w-96">
              <div className="mb-3 flex items-center justify-between">
                <div>
                  <div className="text-sm font-semibold text-slate-900">当前上传任务</div>
                  <div className="mt-1 text-xs text-slate-400">{taskId}</div>
                </div>
              </div>
              <ProgressBar currentState={status === "error" ? "ERROR" : currentState} errorMessage={error || undefined} />
            </div>
          )}
        </div>
      </div>
    </AdminContext.Provider>
  );
}
