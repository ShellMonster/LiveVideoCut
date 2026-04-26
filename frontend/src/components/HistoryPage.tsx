import { useCallback, useEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  ChevronDown,
  ChevronRight,
  Download,
  Film,
  Trash2,
} from "lucide-react";

const API_BASE = import.meta.env.VITE_API_URL || "";

interface TaskItem {
  task_id: string;
  status: string;
  stage: string;
  message: string | null;
  created_at: string | null;
  original_filename: string | null;
  display_name: string | null;
  video_duration_s: number;
  clip_count: number;
  thumbnail_url: string | null;
}

interface ClipItem {
  clip_id: string;
  product_name: string;
  duration: number;
  thumbnail_url: string;
  video_url: string;
}

type FilterTab = "all" | "processing" | "completed" | "failed";

function classifyStatus(raw: string): "processing" | "completed" | "failed" | "uploaded" {
  if (raw === "COMPLETED") return "completed";
  if (raw === "ERROR") return "failed";
  if (raw === "UPLOADED") return "uploaded";
  return "processing";
}

function relativeTime(dateStr: string | null): string {
  if (!dateStr) return "—";
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return "—";
  const now = Date.now();
  const diffMs = now - d.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return "刚刚";
  if (diffMin < 60) return `${diffMin}分钟前`;
  const diffH = Math.floor(diffMin / 60);
  if (diffH < 24) return `${diffH}小时前`;
  const diffD = Math.floor(diffH / 24);
  if (diffD < 7) return `${diffD}天前`;
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function absoluteTime(dateStr: string | null): string {
  if (!dateStr) return "";
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return "";
  return d.toLocaleString("zh-CN");
}

function formatDuration(s: number): string {
  if (!s || s <= 0) return "—";
  const m = Math.floor(s / 60);
  const sec = Math.round(s % 60);
  return `${m}:${String(sec).padStart(2, "0")}`;
}

function truncate(name: string | null | undefined, max = 28): string {
  if (!name) return "视频";
  return name.length > max ? name.slice(0, max) + "…" : name;
}

function statusLabel(raw: string): string {
  const c = classifyStatus(raw);
  if (c === "completed") return "已完成";
  if (c === "failed") return "失败";
  if (c === "uploaded") return "已上传";
  return "处理中";
}

function statusBadgeClass(raw: string): string {
  const c = classifyStatus(raw);
  switch (c) {
    case "completed":
      return "bg-green-50 text-green-700";
    case "processing":
      return "bg-blue-50 text-blue-700";
    case "failed":
      return "bg-red-50 text-red-700";
    default:
      return "bg-slate-100 text-slate-600";
  }
}

const FILTER_TABS: { key: FilterTab; label: string; apiParam: string | null }[] = [
  { key: "all", label: "全部", apiParam: null },
  { key: "processing", label: "处理中", apiParam: "PROCESSING" },
  { key: "completed", label: "已完成", apiParam: "COMPLETED" },
  { key: "failed", label: "失败", apiParam: "ERROR" },
];

const PAGE_SIZE = 20;

interface HistoryPageProps {
  onBack: () => void;
}

export function HistoryPage({ onBack }: HistoryPageProps) {
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<FilterTab>("all");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [clips, setClips] = useState<ClipItem[]>([]);
  const [clipsLoading, setClipsLoading] = useState(false);
  const [offset, setOffset] = useState(0);
  const [counts, setCounts] = useState({ all: 0, processing: 0, completed: 0, failed: 0 });
  const clipsCacheRef = useRef<Record<string, ClipItem[]>>({});
  const clipsRequestRef = useRef(0);

  useEffect(() => {
    const controller = new AbortController();
    const tab = FILTER_TABS.find((t) => t.key === filter);
    const params = new URLSearchParams({ offset: "0", limit: String(PAGE_SIZE) });
    if (tab?.apiParam) params.set("status", tab.apiParam);

    setLoading(true);
    fetch(`${API_BASE}/api/tasks?${params}`, { signal: controller.signal })
      .then((r) => r.json())
      .then((data) => {
        setTasks(data.items ?? []);
        setTotal(data.total ?? 0);
        setOffset(0);

        if (filter === "all") {
          setCounts((prev) => ({ ...prev, all: data.total ?? 0 }));
        } else {
          setCounts((prev) => ({ ...prev, [filter]: data.total ?? 0 }));
        }
      })
      .catch(() => {
        if (controller.signal.aborted) return;
        setTasks([]);
        setTotal(0);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [filter]);

  useEffect(() => {
    const controller = new AbortController();

    Promise.all(
      FILTER_TABS.map((tab) => {
        const params = new URLSearchParams({ offset: "0", limit: "1" });
        if (tab.apiParam) params.set("status", tab.apiParam);
        return fetch(`${API_BASE}/api/tasks?${params}`, { signal: controller.signal })
          .then((r) => r.json())
          .then((data) => [tab.key, data.total ?? 0] as const);
      }),
    )
      .then((entries) => {
        if (controller.signal.aborted) return;
        setCounts((prev) => ({ ...prev, ...Object.fromEntries(entries) }));
      })
      .catch(() => {});

    return () => controller.abort();
  }, []);

  const loadMore = useCallback(() => {
    const newOffset = offset + PAGE_SIZE;
    const tab = FILTER_TABS.find((t) => t.key === filter);
    const params = new URLSearchParams({ offset: String(newOffset), limit: String(PAGE_SIZE) });
    if (tab?.apiParam) params.set("status", tab.apiParam);

    fetch(`${API_BASE}/api/tasks?${params}`)
      .then((r) => r.json())
      .then((data) => {
        setTasks((prev) => [...prev, ...(data.items ?? [])]);
        setOffset(newOffset);
      })
      .catch(() => {});
  }, [filter, offset]);

  const toggleExpand = useCallback((taskId: string) => {
    if (expandedId === taskId) {
      clipsRequestRef.current += 1;
      setExpandedId(null);
      setClips([]);
      return;
    }
    const requestId = clipsRequestRef.current + 1;
    clipsRequestRef.current = requestId;
    setExpandedId(taskId);
    const cachedClips = clipsCacheRef.current[taskId];
    if (cachedClips) {
      setClips(cachedClips);
      setClipsLoading(false);
      return;
    }

    setClips([]);
    setClipsLoading(true);
    fetch(`${API_BASE}/api/tasks/${taskId}/clips`)
      .then((r) => r.json())
      .then((data) => {
        if (clipsRequestRef.current !== requestId) return;
        const nextClips = data.clips ?? [];
        clipsCacheRef.current[taskId] = nextClips;
        setClips(nextClips);
      })
      .catch(() => {
        if (clipsRequestRef.current === requestId) setClips([]);
      })
      .finally(() => {
        if (clipsRequestRef.current === requestId) setClipsLoading(false);
      });
  }, [expandedId]);

  const deleteTask = (taskId: string) => {
    if (!confirm("确定要删除这个任务吗？删除后无法恢复。")) return;
    fetch(`${API_BASE}/api/tasks/${taskId}`, { method: "DELETE" })
      .then((r) => {
        if (r.ok) {
          setTasks((prev) => prev.filter((t) => t.task_id !== taskId));
          delete clipsCacheRef.current[taskId];
          setTotal((prev) => prev - 1);
          setCounts((prev) => ({
            ...prev,
            all: Math.max(0, prev.all - 1),
            [filter]: Math.max(0, prev[filter] - 1),
          }));
          if (expandedId === taskId) {
            setExpandedId(null);
            setClips([]);
          }
        }
      })
      .catch(() => {});
  };

  const hasMore = tasks.length < total;

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <nav className="sticky top-0 z-10 border-b border-slate-200 bg-white/80 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-4xl items-center gap-3 px-4 sm:px-6">
          <button
            className="flex items-center gap-1 rounded-md px-2 py-1 text-sm text-slate-600 hover:bg-slate-100 hover:text-slate-900"
            onClick={onBack}
          >
            <ArrowLeft size={16} />
            返回
          </button>
          <h1 className="text-sm font-semibold text-slate-900">处理历史</h1>
        </div>
      </nav>

      <div className="mx-auto max-w-4xl space-y-5 px-4 py-6 sm:px-6">
        <div className="flex flex-wrap gap-2">
          {FILTER_TABS.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setFilter(tab.key)}
              className={`rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
                filter === tab.key
                  ? "bg-slate-900 text-white"
                  : "bg-white text-slate-600 ring-1 ring-slate-200 hover:bg-slate-100"
              }`}
            >
              {tab.label}
              {counts[tab.key] > 0 && (
                <span className="ml-1 opacity-70">({counts[tab.key]})</span>
              )}
            </button>
          ))}
        </div>

        {loading ? (
          <p className="py-16 text-center text-sm text-slate-400">加载中...</p>
        ) : tasks.length === 0 ? (
          <div className="py-16 text-center">
            <p className="text-4xl">🎬</p>
            <p className="mt-3 text-sm text-slate-400">还没有处理过任何视频</p>
          </div>
        ) : (
          <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
            <ul>
              {tasks.map((task, idx) => {
                const isExpanded = expandedId === task.task_id;
                const isCompleted = classifyStatus(task.status) === "completed";
                const showChevron = isCompleted;
                const borderClass = idx > 0 ? "border-t border-slate-100" : "";

                return (
                  <li key={task.task_id} className={borderClass}>
                    <div
                      className={`flex items-center gap-3 px-4 py-3 transition-colors ${
                        isCompleted ? "cursor-pointer hover:bg-slate-50" : ""
                      }`}
                      onClick={() => isCompleted && toggleExpand(task.task_id)}
                    >
                      <div className="h-9 w-16 shrink-0 overflow-hidden rounded bg-slate-100">
                        {task.thumbnail_url ? (
                          <img
                            src={task.thumbnail_url}
                            alt=""
                            className="h-full w-full object-cover"
                            loading="lazy"
                            decoding="async"
                          />
                        ) : (
                          <div className="flex h-full w-full items-center justify-center text-slate-300">
                            <Film size={18} />
                          </div>
                        )}
                      </div>

                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <span className="truncate text-sm font-medium text-slate-900">
                            {truncate(task.display_name || task.original_filename)}
                          </span>
                          <span
                            className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${statusBadgeClass(task.status)}`}
                          >
                            {statusLabel(task.status)}
                          </span>
                        </div>
                        <div className="mt-0.5 flex items-center gap-3 text-xs text-slate-400">
                          {isCompleted && task.clip_count > 0 && (
                            <span>{task.clip_count} 片段</span>
                          )}
                          {classifyStatus(task.status) === "processing" && task.stage && (
                            <span className="text-blue-500">{task.stage}</span>
                          )}
                          {task.video_duration_s > 0 && (
                            <span>{formatDuration(task.video_duration_s)}</span>
                          )}
                          <span title={absoluteTime(task.created_at)}>
                            {relativeTime(task.created_at)}
                          </span>
                        </div>
                      </div>

                      <div className="flex shrink-0 items-center gap-1">
                        {isCompleted && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              toggleExpand(task.task_id);
                            }}
                            className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
                            aria-label={isExpanded ? "收起" : "查看片段"}
                          >
                            {showChevron &&
                              (isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />)}
                          </button>
                        )}
                        {classifyStatus(task.status) === "processing" && (
                          <span className="px-2 text-xs text-blue-500">处理中…</span>
                        )}
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            deleteTask(task.task_id);
                          }}
                          className="rounded p-1 text-slate-300 hover:bg-red-50 hover:text-red-500"
                          aria-label="删除"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </div>

                    {isExpanded && (
                      <div className="border-t border-slate-100 bg-slate-50/50 px-4 py-3">
                        {clipsLoading ? (
                          <p className="py-4 text-center text-xs text-slate-400">加载片段...</p>
                        ) : clips.length === 0 ? (
                          <p className="py-4 text-center text-xs text-slate-400">暂无片段</p>
                        ) : (
                          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
                            {clips.map((clip) => (
                              <div
                                key={clip.clip_id}
                                className="overflow-hidden rounded-lg border border-slate-200 bg-white"
                              >
                                <div className="relative aspect-video bg-slate-100">
                                  {clip.thumbnail_url ? (
                                    <img
                                      src={clip.thumbnail_url}
                                      alt={clip.product_name}
                                      className="h-full w-full object-cover"
                                      loading="lazy"
                                      decoding="async"
                                    />
                                  ) : (
                                    <div className="flex h-full w-full items-center justify-center text-slate-300">
                                      <Film size={20} />
                                    </div>
                                  )}
                                  {clip.duration > 0 && (
                                    <span className="absolute bottom-1 right-1 rounded bg-black/60 px-1 py-0.5 text-[10px] font-medium text-white">
                                      {formatDuration(clip.duration)}
                                    </span>
                                  )}
                                </div>
                                <div className="flex items-center justify-between gap-1 px-2 py-1.5">
                                  <span className="truncate text-xs text-slate-700">
                                    {clip.product_name || "未命名"}
                                  </span>
                                  {clip.video_url && (
                                    <a
                                      href={clip.video_url}
                                      download
                                      className="shrink-0 rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
                                      aria-label="下载"
                                    >
                                      <Download size={12} />
                                    </a>
                                  )}
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
          </div>
        )}

        {hasMore && (
          <div className="flex justify-center pt-2">
            <button
              onClick={loadMore}
              className="rounded-full bg-white px-5 py-2 text-sm font-medium text-slate-600 ring-1 ring-slate-200 hover:bg-slate-100"
            >
              加载更多
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
