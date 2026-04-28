import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { API_BASE, fetchJson } from "@/components/admin/api";
import type {
  ClipAssetsResponse,
  ClipListResponse,
  ClipReprocessJob,
  DiagnosticReport,
  MusicTrack,
  ReviewData,
  SystemResources,
  TaskListResponse,
  TaskSummary,
} from "@/components/admin/types";

// ---------- Query key factories ----------

export const adminKeys = {
  tasks: ["admin", "tasks"] as const,
  taskDetail: (id: string) => ["admin", "task", id] as const,
  taskSummary: (id: string) => ["admin", "task", id, "summary"] as const,
  taskDiagnostics: (id: string) => ["admin", "task", id, "diagnostics"] as const,
  taskReview: (id: string) => ["admin", "task", id, "review"] as const,
  taskEvents: (id: string) => ["admin", "task", id, "events"] as const,
  taskClips: (id: string) => ["admin", "task", id, "clips"] as const,
  clipReprocess: (taskId: string, segmentId: string) =>
    ["admin", "task", taskId, "clip", segmentId, "reprocess"] as const,
  systemResources: ["admin", "system", "resources"] as const,
  musicLibrary: ["admin", "music", "library"] as const,
  assets: (params: string) => ["admin", "assets", params] as const,
};

// ---------- Task queries ----------

export function useTasks() {
  return useQuery({
    queryKey: adminKeys.tasks,
    queryFn: async () => {
      const data = await fetchJson<TaskListResponse>(`${API_BASE}/api/tasks?offset=0&limit=100`);
      return data.items ?? [];
    },
    refetchInterval: 5000,
  });
}

export function useTaskSummary(taskId: string | undefined) {
  return useQuery({
    queryKey: adminKeys.taskSummary(taskId ?? ""),
    queryFn: () => fetchJson<TaskSummary>(`${API_BASE}/api/tasks/${taskId}/summary`),
    enabled: !!taskId,
  });
}

export function useTaskDiagnostics(taskId: string | undefined) {
  return useQuery({
    queryKey: adminKeys.taskDiagnostics(taskId ?? ""),
    queryFn: () => fetchJson<DiagnosticReport>(`${API_BASE}/api/tasks/${taskId}/diagnostics`),
    enabled: !!taskId,
  });
}

export function useTaskReview(taskId: string | undefined) {
  return useQuery({
    queryKey: adminKeys.taskReview(taskId ?? ""),
    queryFn: () => fetchJson<ReviewData>(`${API_BASE}/api/tasks/${taskId}/review`),
    enabled: !!taskId,
  });
}

export function useTaskEvents(taskId: string | undefined) {
  return useQuery({
    queryKey: adminKeys.taskEvents(taskId ?? ""),
    queryFn: async () => {
      const data = await fetchJson<{ events: DiagnosticReport["event_log"] }>(
        `${API_BASE}/api/tasks/${taskId}/events`,
      );
      return data.events ?? [];
    },
    enabled: !!taskId,
  });
}

export function useTaskClips(taskId: string | undefined, completed?: boolean) {
  return useQuery({
    queryKey: adminKeys.taskClips(taskId ?? ""),
    queryFn: async () => {
      const data = await fetchJson<ClipListResponse>(`${API_BASE}/api/tasks/${taskId}/clips`);
      return data.clips ?? [];
    },
    enabled: !!taskId && (completed === undefined || completed),
  });
}

// ---------- System queries ----------

export function useSystemResources() {
  return useQuery({
    queryKey: adminKeys.systemResources,
    queryFn: () => fetchJson<SystemResources>(`${API_BASE}/api/system/resources`),
    refetchInterval: 10000,
  });
}

// ---------- Music queries ----------

export function useMusicLibrary() {
  return useQuery({
    queryKey: adminKeys.musicLibrary,
    queryFn: async () => {
      const data = await fetchJson<MusicTrack[] | { tracks?: MusicTrack[] }>(
        `${API_BASE}/api/music/library`,
      );
      return Array.isArray(data) ? data : data.tracks ?? [];
    },
  });
}

// ---------- Assets queries ----------

export function useClipAssets(projectId?: string, statusFilter?: string) {
  const params = new URLSearchParams({ limit: "500" });
  if (projectId) params.set("project_id", projectId);
  if (statusFilter && statusFilter !== "all") params.set("status", statusFilter);
  const qs = params.toString();

  return useQuery({
    queryKey: adminKeys.assets(qs),
    queryFn: async () => {
      const data = await fetchJson<ClipAssetsResponse>(`${API_BASE}/api/assets/clips?${qs}`);
      return { items: data.items ?? [], summary: data.summary };
    },
  });
}

// ---------- Mutations ----------

export function useDeleteTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (taskId: string) => {
      if (!confirm("确定要删除这个任务吗？删除后无法恢复。")) throw new Error("cancelled");
      await fetch(`${API_BASE}/api/tasks/${taskId}`, { method: "DELETE" });
      return taskId;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: adminKeys.tasks });
    },
  });
}

export function useRetryTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (taskId: string) => {
      await fetch(`${API_BASE}/api/tasks/${taskId}/retry`, { method: "POST" });
      return taskId;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: adminKeys.tasks });
    },
  });
}

export function usePatchReviewSegment(taskId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ segmentId, patch }: { segmentId: string; patch: Record<string, unknown> }) => {
      const payload: Record<string, unknown> = { ...patch };
      if ("review_status" in payload) {
        payload.status = payload.review_status;
        delete payload.review_status;
      }
      const resp = await fetch(`${API_BASE}/api/tasks/${taskId}/review/segments/${segmentId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!resp.ok) throw new Error("Patch failed");
    },
    onSuccess: () => {
      if (taskId) {
        void queryClient.invalidateQueries({ queryKey: adminKeys.taskReview(taskId) });
      }
    },
  });
}

export function useReprocessSegment(taskId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (segmentId: string) => {
      const resp = await fetch(`${API_BASE}/api/tasks/${taskId}/clips/${segmentId}/reprocess`, {
        method: "POST",
      });
      if (!resp.ok) throw new Error("Reprocess failed");
      return (await resp.json()) as { status?: ClipReprocessJob["status"]; celery_id?: string };
    },
    onSuccess: () => {
      if (taskId) {
        void queryClient.invalidateQueries({ queryKey: adminKeys.taskClips(taskId) });
        void queryClient.invalidateQueries({ queryKey: adminKeys.taskReview(taskId) });
      }
    },
  });
}

export function useClipReprocessStatus(taskId: string | undefined, segmentId: string | undefined) {
  return useQuery({
    queryKey: adminKeys.clipReprocess(taskId ?? "", segmentId ?? ""),
    queryFn: async () => {
      const data = await fetchJson<{ job: ClipReprocessJob }>(
        `${API_BASE}/api/tasks/${taskId}/clips/${segmentId}/reprocess`,
      );
      return data.job;
    },
    enabled: !!taskId && !!segmentId,
    refetchInterval: (query) => {
      const job = query.state.data;
      if (job?.status === "queued" || job?.status === "running") return 2500;
      return false;
    },
  });
}

export function useUploadTrack() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData();
      form.append("file", file);
      const resp = await fetch(`${API_BASE}/api/music/upload`, { method: "POST", body: form });
      if (!resp.ok) throw new Error("Upload failed");
      return (await resp.json()) as MusicTrack;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: adminKeys.musicLibrary });
    },
  });
}

export function useDeleteTrack() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (trackId: string) => {
      if (!confirm("确定要删除这首用户曲目吗？")) throw new Error("cancelled");
      await fetch(`${API_BASE}/api/music/${trackId}`, { method: "DELETE" });
      return trackId;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: adminKeys.musicLibrary });
    },
  });
}

export function useSaveTrackTags() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      trackId,
      tags,
    }: {
      trackId: string;
      tags: {
        title: string;
        mood: string[];
        categories: string[];
        tempo: string;
        energy: string;
        genre: string;
      };
    }) => {
      const resp = await fetch(`${API_BASE}/api/music/${trackId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(tags),
      });
      if (!resp.ok) throw new Error("Save failed");
      return (await resp.json()) as MusicTrack;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: adminKeys.musicLibrary });
    },
  });
}
