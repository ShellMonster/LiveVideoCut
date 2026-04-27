import { useCallback, useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { ProgressBar } from "@/components/ProgressBar";
import { ToastViewport } from "@/components/ToastViewport";
import { useTaskProgress } from "@/hooks/useWebSocket";
import { useTaskStore, type ClipData } from "@/stores/taskStore";
import { API_BASE, fetchJson } from "@/components/admin/api";
import { Sidebar } from "@/components/admin/shared";
import { ProjectManagementPage } from "@/components/admin/pages/ProjectManagementPage";
import { CreateProjectPage } from "@/components/admin/pages/CreateProjectPage";
import { QueuePage } from "@/components/admin/pages/QueuePage";
import { ReviewPage } from "@/components/admin/pages/ReviewPage";
import { AssetsPage } from "@/components/admin/pages/AssetsPage";
import { AdminMusicPage } from "@/components/admin/pages/MusicPage";
import { DiagnosticsPage } from "@/components/admin/pages/DiagnosticsPage";
import { AdminSettingsPage } from "@/components/admin/pages/SettingsPage";
import type {
  ClipListResponse,
  ClipReprocessJob,
  DiagnosticReport,
  PageKey,
  ReviewData,
  ReviewSegment,
  SystemResources,
  TaskItem,
  TaskListResponse,
  TaskSummary,
} from "@/components/admin/types";

export function AdminDashboard() {
  const [page, setPage] = useState<PageKey>("projects");
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [tasksLoading, setTasksLoading] = useState(true);
  const [selectedTask, setSelectedTask] = useState<TaskItem | null>(null);
  const [selectedTaskClips, setSelectedTaskClips] = useState<ClipData[]>([]);
  const [selectedSummary, setSelectedSummary] = useState<TaskSummary | null>(null);
  const [selectedDiagnostics, setSelectedDiagnostics] = useState<DiagnosticReport | null>(null);
  const [selectedReview, setSelectedReview] = useState<ReviewData | null>(null);
  const [resources, setResources] = useState<SystemResources | null>(null);
  const [selectedEvents, setSelectedEvents] = useState<DiagnosticReport["event_log"]>([]);
  const [reprocessJobs, setReprocessJobs] = useState<Record<string, ClipReprocessJob>>({});
  const [assetProjectId, setAssetProjectId] = useState<string | undefined>();
  const [clipsLoading, setClipsLoading] = useState(false);
  const { taskId, status, currentState, error } = useTaskStore();
  useTaskProgress(taskId);

  const loadTasks = useCallback(async () => {
    setTasksLoading(true);
    try {
      const data = await fetchJson<TaskListResponse>(`${API_BASE}/api/tasks?offset=0&limit=100`);
      const nextTasks = data.items ?? [];
      setTasks(nextTasks);
      setSelectedTask((current) => current ?? nextTasks[0] ?? null);
    } catch {
      setTasks([]);
    } finally {
      setTasksLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadTasks();
  }, [loadTasks, taskId, status, currentState]);

  useEffect(() => {
    const controller = new AbortController();
    fetchJson<SystemResources>(`${API_BASE}/api/system/resources`, controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setResources(data);
      })
      .catch(() => {
        if (!controller.signal.aborted) setResources(null);
      });
    return () => controller.abort();
  }, [tasks]);

  useEffect(() => {
    if (!selectedTask || selectedTask.status !== "COMPLETED") {
      setSelectedTaskClips([]);
      setClipsLoading(false);
      return;
    }
    const controller = new AbortController();
    setClipsLoading(true);
    fetchJson<ClipListResponse>(`${API_BASE}/api/tasks/${selectedTask.task_id}/clips`, controller.signal)
      .then((data) => setSelectedTaskClips(data.clips ?? []))
      .catch(() => {
        if (!controller.signal.aborted) setSelectedTaskClips([]);
      })
      .finally(() => {
        if (!controller.signal.aborted) setClipsLoading(false);
      });
    return () => controller.abort();
  }, [selectedTask]);

  useEffect(() => {
    if (!selectedTask) {
      setSelectedSummary(null);
      setSelectedDiagnostics(null);
      setSelectedReview(null);
      setSelectedEvents([]);
      setReprocessJobs({});
      return;
    }
    const controller = new AbortController();

    Promise.all([
      fetchJson<TaskSummary>(`${API_BASE}/api/tasks/${selectedTask.task_id}/summary`, controller.signal),
      fetchJson<DiagnosticReport>(`${API_BASE}/api/tasks/${selectedTask.task_id}/diagnostics`, controller.signal),
      fetchJson<ReviewData>(`${API_BASE}/api/tasks/${selectedTask.task_id}/review`, controller.signal),
      fetchJson<{ events: DiagnosticReport["event_log"] }>(`${API_BASE}/api/tasks/${selectedTask.task_id}/events`, controller.signal),
    ])
      .then(([summary, diagnostics, review, events]) => {
        if (controller.signal.aborted) return;
        setSelectedSummary(summary);
        setSelectedDiagnostics(diagnostics);
        setSelectedReview(review);
        setSelectedEvents(events.events ?? []);
        setReprocessJobs({});
      })
      .catch(() => {
        if (controller.signal.aborted) return;
        setSelectedSummary(null);
        setSelectedDiagnostics(null);
        setSelectedReview(null);
        setSelectedEvents([]);
      });
    return () => controller.abort();
  }, [selectedTask]);

  useEffect(() => {
    if (!selectedTask || !selectedReview?.segments.length) return;
    const controller = new AbortController();
    Promise.all(
      selectedReview.segments.map(async (segment) => {
        const data = await fetchJson<{ job: ClipReprocessJob }>(
          `${API_BASE}/api/tasks/${selectedTask.task_id}/clips/${segment.segment_id}/reprocess`,
          controller.signal,
        );
        return [segment.segment_id, data.job] as const;
      }),
    )
      .then((entries) => {
        if (controller.signal.aborted) return;
        const jobs = Object.fromEntries(entries.filter(([, job]) => job.status));
        setReprocessJobs(jobs);
      })
      .catch(() => undefined);
    return () => controller.abort();
  }, [selectedTask, selectedReview?.segments]);

  useEffect(() => {
    if (!selectedTask) return;
    const activeSegmentIds = Object.entries(reprocessJobs)
      .filter(([, job]) => job.status === "queued" || job.status === "running")
      .map(([segmentId]) => segmentId);
    if (activeSegmentIds.length === 0) return;

    const timer = window.setInterval(() => {
      void Promise.all(
        activeSegmentIds.map(async (segmentId) => {
          const data = await fetchJson<{ job: ClipReprocessJob }>(
            `${API_BASE}/api/tasks/${selectedTask.task_id}/clips/${segmentId}/reprocess`,
          );
          return [segmentId, data.job] as const;
        }),
      ).then(async (entries) => {
        setReprocessJobs((current) => {
          const next = { ...current };
          entries.forEach(([segmentId, job]) => {
            next[segmentId] = job;
          });
          return next;
        });
        if (entries.some(([, job]) => job.status === "completed")) {
          const [clipsData, reviewData] = await Promise.all([
            fetchJson<ClipListResponse>(`${API_BASE}/api/tasks/${selectedTask.task_id}/clips`),
            fetchJson<ReviewData>(`${API_BASE}/api/tasks/${selectedTask.task_id}/review`),
          ]);
          setSelectedTaskClips(clipsData.clips ?? []);
          setSelectedReview(reviewData);
        }
      }).catch(() => undefined);
    }, 2500);

    return () => window.clearInterval(timer);
  }, [selectedTask, reprocessJobs]);

  const deleteTask = useCallback(
    async (taskIdToDelete: string) => {
      if (!confirm("确定要删除这个任务吗？删除后无法恢复。")) return;
      await fetch(`${API_BASE}/api/tasks/${taskIdToDelete}`, { method: "DELETE" });
      setTasks((current) => current.filter((task) => task.task_id !== taskIdToDelete));
      setSelectedTask((current) => (current?.task_id === taskIdToDelete ? null : current));
    },
    [],
  );

  const retryTask = useCallback(
    async (taskIdToRetry: string) => {
      await fetch(`${API_BASE}/api/tasks/${taskIdToRetry}/retry`, { method: "POST" });
      await loadTasks();
    },
    [loadTasks],
  );

  const patchReviewSegment = useCallback(
    async (segmentId: string, patch: Partial<ReviewSegment>) => {
      if (!selectedTask) return;
      const payload: Record<string, unknown> = { ...patch };
      if ("review_status" in payload) {
        payload.status = payload.review_status;
        delete payload.review_status;
      }
      const resp = await fetch(
        `${API_BASE}/api/tasks/${selectedTask.task_id}/review/segments/${segmentId}`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        },
      );
      if (!resp.ok) return;
      const review = await fetchJson<ReviewData>(`${API_BASE}/api/tasks/${selectedTask.task_id}/review`);
      setSelectedReview(review);
    },
    [selectedTask],
  );

  const reprocessSegment = useCallback(
    async (segmentId: string) => {
      if (!selectedTask) return;
      setReprocessJobs((current) => ({
        ...current,
        [segmentId]: { ...(current[segmentId] ?? {}), status: "queued" },
      }));
      const resp = await fetch(`${API_BASE}/api/tasks/${selectedTask.task_id}/clips/${segmentId}/reprocess`, {
        method: "POST",
      });
      if (!resp.ok) {
        setReprocessJobs((current) => ({
          ...current,
          [segmentId]: { ...(current[segmentId] ?? {}), status: "failed", error: "请求失败" },
        }));
        return;
      }
      const data = (await resp.json()) as { status?: ClipReprocessJob["status"]; celery_id?: string };
      setReprocessJobs((current) => ({
        ...current,
        [segmentId]: { ...(current[segmentId] ?? {}), status: data.status ?? "queued", celery_id: data.celery_id },
      }));
    },
    [selectedTask],
  );

  const handlePageChange = (nextPage: PageKey) => {
    if (nextPage === "assets") setAssetProjectId(undefined);
    setPage(nextPage);
  };

  return (
    <div className="flex min-h-screen bg-slate-50 text-slate-900">
      <ToastViewport />
      <Sidebar page={page} onPageChange={handlePageChange} />
      <div className="min-w-0 flex-1">
        {page === "projects" && (
          <ProjectManagementPage
            tasks={tasks}
            loading={tasksLoading}
            selectedTask={selectedTask}
            onSelectTask={setSelectedTask}
            onDeleteTask={deleteTask}
            onOpenReview={() => setPage("review")}
            onOpenAssets={() => {
              setAssetProjectId(selectedTask?.task_id);
              setPage("assets");
            }}
            onCreateProject={() => setPage("create")}
            summary={selectedSummary}
            diagnostics={selectedDiagnostics}
          />
        )}
        {page === "create" && <CreateProjectPage onCancel={() => setPage("projects")} />}
        {page === "queue" && (
          <QueuePage
            tasks={tasks}
            onSelectTask={setSelectedTask}
            onRetryTask={retryTask}
            onDeleteTask={deleteTask}
            resources={resources}
            events={selectedEvents}
            onCreateProject={() => setPage("create")}
          />
        )}
        {page === "review" && (
          <ReviewPage
            tasks={tasks}
            selectedTask={selectedTask}
            clips={selectedTaskClips}
            clipsLoading={clipsLoading}
            onSelectTask={setSelectedTask}
            reviewData={selectedReview}
            onPatchReviewSegment={patchReviewSegment}
            onReprocessSegment={reprocessSegment}
            reprocessJobs={reprocessJobs}
          />
        )}
        {page === "assets" && <AssetsPage selectedProjectId={assetProjectId} />}
        {page === "music" && <AdminMusicPage />}
        {page === "diagnostics" && <DiagnosticsPage selectedTask={selectedTask} diagnostics={selectedDiagnostics} />}
        {page === "settings" && <AdminSettingsPage />}

        {taskId && (status === "processing" || status === "error") && (
          <div className="fixed bottom-4 right-4 w-96 rounded-lg border border-slate-200 bg-white p-4 shadow-lg">
            <div className="mb-3 flex items-center justify-between">
              <div>
                <div className="text-sm font-semibold text-slate-900">当前上传任务</div>
                <div className="mt-1 text-xs text-slate-400">{taskId}</div>
              </div>
              <button onClick={loadTasks} className="rounded p-1 text-slate-400 hover:bg-slate-100">
                <RefreshCw size={15} />
              </button>
            </div>
            <ProgressBar currentState={status === "error" ? "ERROR" : currentState} errorMessage={error || undefined} />
          </div>
        )}
      </div>
    </div>
  );
}
