import { useCallback, useEffect, useRef, useState } from "react";
import {
  Activity,
  AlertTriangle,
  Bell,
  Check,
  ChevronRight,
  Cpu,
  Download,
  Eye,
  FileVideo,
  Film,
  HardDrive,
  LayoutDashboard,
  ListChecks,
  Music,
  Pause,
  Play,
  Plus,
  RefreshCw,
  Save,
  Scissors,
  Search,
  Server,
  Settings,
  SlidersHorizontal,
  Trash2,
  Upload,
  UserCircle,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { UploadZone } from "@/components/UploadZone";
import { ProgressBar } from "@/components/ProgressBar";
import { VideoPreview } from "@/components/VideoPreview";
import { ToastViewport } from "@/components/ToastViewport";
import { useTaskProgress } from "@/hooks/useWebSocket";
import { useTaskStore, type ClipData } from "@/stores/taskStore";
import {
  DEFAULT_API_BASES,
  DEFAULT_MODELS,
  useSettingsStore,
  type AsrProvider,
  type ExportMode,
  type ExportResolution,
  type FillerFilterMode,
  type SegmentGranularity,
  type SubtitleMode,
  type VlmProvider,
} from "@/stores/settingsStore";

const API_BASE = import.meta.env.VITE_API_URL || "";

async function fetchJson<T>(url: string, signal?: AbortSignal): Promise<T> {
  const resp = await fetch(url, { signal });
  const contentType = resp.headers.get("content-type") || "";
  if (!resp.ok || !contentType.includes("application/json")) {
    throw new Error(`Unexpected response for ${url}`);
  }
  return (await resp.json()) as T;
}

type PageKey = "projects" | "create" | "queue" | "review" | "assets" | "music" | "diagnostics" | "settings";

interface TaskItem {
  task_id: string;
  status: string;
  stage?: string;
  message?: string | null;
  created_at?: string | null;
  original_filename?: string | null;
  display_name?: string | null;
  video_duration_s?: number;
  clip_count: number;
  thumbnail_url?: string | null;
}

interface TaskListResponse {
  items?: TaskItem[];
  total?: number;
}

interface ClipListResponse {
  clips?: ClipData[];
  total?: number;
}

interface TaskSummary {
  candidates_count: number;
  confirmed_count: number;
  transcript_segments_count: number;
  text_boundaries_count: number;
  fused_candidates_count: number;
  enriched_segments_count: number;
  clips_count: number;
  empty_screen_dropped_estimate: number;
  artifact_status: Record<string, boolean>;
}

interface DiagnosticReport {
  pipeline: { stage: string; status: string; artifact: string }[];
  funnel: { label: string; count: number }[];
  warnings: { level: string; message: string }[];
  event_log: { time: string; stage: string; level: string; message: string; file: string }[];
  summary: TaskSummary;
}

interface ReviewSegment {
  segment_id: string;
  product_name?: string;
  title?: string;
  start_time: number;
  end_time: number;
  confidence?: number;
  text?: string;
  review_status: "pending" | "approved" | "skipped" | "needs_adjustment";
}

interface ReviewData {
  segments: ReviewSegment[];
  transcript: { start_time: number; end_time: number; text: string }[];
}

interface MusicTrack {
  id: string;
  title: string;
  mood: string[];
  genre: string;
  tempo: string;
  energy: string;
  categories: string[];
  duration_s: number;
  source: "user" | "built-in";
}

interface ClipAsset {
  clip_id: string;
  task_id: string;
  segment_id: string;
  product_name: string;
  duration: number;
  start_time: number;
  end_time: number;
  confidence: number;
  review_status: ReviewSegment["review_status"];
  file_size: number;
  created_at: string;
  video_url: string;
  thumbnail_url: string;
  has_video: boolean;
  has_thumbnail: boolean;
}

interface ClipAssetsResponse {
  items: ClipAsset[];
  summary: {
    total: number;
    pending: number;
    approved: number;
    skipped: number;
    needs_adjustment: number;
    downloadable: number;
    total_size: number;
  };
}

interface SystemResources {
  cpu_cores: number;
  memory_gb: number;
  clip_workers: number;
  frame_workers: number;
  queue: {
    waiting: number;
    active: number;
    completed: number;
    failed: number;
  };
  redis: string;
}

const navItems: { key: PageKey; label: string; icon: React.ElementType }[] = [
  { key: "projects", label: "项目总览", icon: LayoutDashboard },
  { key: "queue", label: "任务队列", icon: ListChecks },
  { key: "review", label: "剪辑复核", icon: Scissors },
  { key: "assets", label: "片段资产", icon: FileVideo },
  { key: "music", label: "音乐库", icon: Music },
  { key: "diagnostics", label: "数据诊断", icon: Activity },
  { key: "settings", label: "系统设置", icon: Settings },
];

const statusMap = {
  completed: { label: "已完成", className: "bg-emerald-50 text-emerald-700 ring-emerald-100" },
  failed: { label: "失败", className: "bg-red-50 text-red-700 ring-red-100" },
  uploaded: { label: "已上传", className: "bg-slate-100 text-slate-600 ring-slate-200" },
  processing: { label: "处理中", className: "bg-blue-50 text-blue-700 ring-blue-100" },
} as const;

const stageLabels: Record<string, string> = {
  UPLOADED: "上传完成",
  EXTRACTING_FRAMES: "抽帧中",
  SCENE_DETECTING: "换衣检测",
  VISUAL_SCREENING: "视觉预筛",
  VLM_CONFIRMING: "VLM确认",
  TRANSCRIBING: "ASR转写",
  LLM_ANALYZING: "LLM融合",
  PROCESSING: "导出中",
  COMPLETED: "完成",
  ERROR: "失败",
};

function classifyStatus(raw: string): keyof typeof statusMap {
  if (raw === "COMPLETED") return "completed";
  if (raw === "ERROR") return "failed";
  if (raw === "UPLOADED") return "uploaded";
  return "processing";
}

function statusLabel(raw: string): string {
  return statusMap[classifyStatus(raw)].label;
}

function statusBadgeClass(raw: string): string {
  return statusMap[classifyStatus(raw)].className;
}

function formatDuration(seconds?: number): string {
  if (!seconds || seconds <= 0) return "—";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.round(seconds % 60);
  if (h > 0) return `${h}h ${m}m`;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function formatDate(dateStr?: string | null): string {
  if (!dateStr) return "—";
  const d = new Date(dateStr);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatBytes(bytes?: number): string {
  if (!bytes || bytes <= 0) return "0MB";
  const mb = bytes / (1024 * 1024);
  if (mb < 1024) return `${mb.toFixed(mb >= 10 ? 0 : 1)}MB`;
  return `${(mb / 1024).toFixed(1)}GB`;
}

function displayTaskName(task: TaskItem): string {
  return task.display_name || task.original_filename || "未命名直播项目";
}

function progressByStatus(task: TaskItem): number {
  const order = [
    "UPLOADED",
    "EXTRACTING_FRAMES",
    "SCENE_DETECTING",
    "VISUAL_SCREENING",
    "VLM_CONFIRMING",
    "TRANSCRIBING",
    "LLM_ANALYZING",
    "PROCESSING",
    "COMPLETED",
  ];
  if (task.status === "COMPLETED") return 100;
  if (task.status === "ERROR") return 100;
  const idx = order.indexOf(task.status);
  if (idx < 0) return 18;
  return Math.max(10, Math.round(((idx + 1) / order.length) * 100));
}

function Sidebar({
  page,
  onPageChange,
}: {
  page: PageKey;
  onPageChange: (page: PageKey) => void;
}) {
  return (
    <aside className="flex h-screen w-64 shrink-0 flex-col border-r border-slate-200 bg-white">
      <div className="flex h-16 items-center gap-3 border-b border-slate-100 px-5">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-600 text-white">
          <Scissors size={18} />
        </div>
        <div>
          <div className="text-sm font-semibold text-slate-950">ClipFlow AI</div>
          <div className="text-xs text-slate-400">直播智能剪辑后台</div>
        </div>
      </div>
      <nav className="flex-1 space-y-1 px-3 py-4">
        {navItems.map((item) => {
          const Icon = item.icon;
          const active = page === item.key;
          return (
            <button
              key={item.key}
              onClick={() => onPageChange(item.key)}
              className={cn(
                "flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors",
                active
                  ? "bg-blue-50 font-medium text-blue-700"
                  : "text-slate-600 hover:bg-slate-50 hover:text-slate-950",
              )}
            >
              <Icon size={17} />
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>
      <div className="border-t border-slate-100 p-4">
        <div className="rounded-lg bg-slate-50 p-3">
          <div className="flex items-center gap-2 text-xs font-medium text-slate-700">
            <Server size={14} />
            Worker 运行正常
          </div>
          <div className="mt-2 h-1.5 rounded-full bg-slate-200">
            <div className="h-1.5 w-2/3 rounded-full bg-emerald-500" />
          </div>
          <p className="mt-2 text-xs text-slate-400">2 个 FFmpeg 实例可用</p>
        </div>
      </div>
    </aside>
  );
}

function Header({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return (
    <header className="flex min-h-16 items-center justify-between border-b border-slate-200 bg-white px-6">
      <div>
        <h1 className="text-lg font-semibold text-slate-950">{title}</h1>
        <p className="mt-0.5 text-xs text-slate-500">{description}</p>
      </div>
      <div className="flex items-center gap-2">
        {action}
        <button className="rounded-lg p-2 text-slate-500 hover:bg-slate-100" aria-label="通知">
          <Bell size={18} />
        </button>
        <button className="rounded-lg p-2 text-slate-500 hover:bg-slate-100" aria-label="账号">
          <UserCircle size={20} />
        </button>
      </div>
    </header>
  );
}

function MetricCard({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="mt-2 text-2xl font-semibold text-slate-950">{value}</div>
      <div className="mt-1 text-xs text-slate-400">{hint}</div>
    </div>
  );
}

function EmptyPreview() {
  return (
    <div className="flex h-full min-h-40 flex-col items-center justify-center rounded-lg border border-dashed border-slate-200 bg-slate-50 text-slate-400">
      <Film size={28} />
      <p className="mt-2 text-sm">选择一个项目查看详情</p>
    </div>
  );
}

function ProjectManagementPage({
  tasks,
  loading,
  selectedTask,
  onSelectTask,
  onDeleteTask,
  onOpenReview,
  onCreateProject,
  summary,
  diagnostics,
}: {
  tasks: TaskItem[];
  loading: boolean;
  selectedTask: TaskItem | null;
  onSelectTask: (task: TaskItem) => void;
  onDeleteTask: (taskId: string) => void;
  onOpenReview: () => void;
  onCreateProject: () => void;
  summary: TaskSummary | null;
  diagnostics: DiagnosticReport | null;
}) {
  const completedCount = tasks.filter((task) => task.status === "COMPLETED").length;
  const processingCount = tasks.filter((task) => classifyStatus(task.status) === "processing").length;
  const failedCount = tasks.filter((task) => task.status === "ERROR").length;
  const clipCount = tasks.reduce((sum, task) => sum + (task.clip_count || 0), 0);

  return (
    <>
      <Header
        title="直播剪辑项目"
        description="管理直播剪辑项目、处理状态和导出结果"
        action={
          <button
            onClick={onCreateProject}
            className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            <Plus size={16} />
            新建项目
          </button>
        }
      />
      <main className="space-y-5 p-6">
        <section className="grid gap-4 lg:grid-cols-4">
          <MetricCard label="处理中项目" value={String(processingCount)} hint="实时任务队列" />
          <MetricCard label="今日完成" value={String(completedCount)} hint="按本地任务记录统计" />
          <MetricCard label="失败任务" value={String(failedCount)} hint="需要检查诊断日志" />
          <MetricCard label="导出片段" value={String(clipCount)} hint="累计可下载短视频" />
        </section>

        <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
          <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
            <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
              <div className="flex min-w-0 flex-1 items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-400">
                <Search size={16} />
                <span>搜索项目 / 文件名 / 商品关键词</span>
              </div>
              <button className="ml-3 inline-flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50">
                <SlidersHorizontal size={16} />
                筛选
              </button>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[860px] text-left text-sm">
                <thead className="bg-slate-50 text-xs font-medium text-slate-500">
                  <tr>
                    <th className="px-4 py-3">项目名称</th>
                    <th className="px-4 py-3">状态</th>
                    <th className="px-4 py-3">进度</th>
                    <th className="px-4 py-3">片段数</th>
                    <th className="px-4 py-3">ASR</th>
                    <th className="px-4 py-3">创建时间</th>
                    <th className="px-4 py-3 text-right">操作</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {loading ? (
                    <tr>
                      <td colSpan={7} className="px-4 py-12 text-center text-slate-400">
                        加载项目中...
                      </td>
                    </tr>
                  ) : tasks.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="px-4 py-12 text-center text-slate-400">
                        还没有项目，点击新建项目上传直播录像。
                      </td>
                    </tr>
                  ) : (
                    tasks.map((task) => (
                      <tr
                        key={task.task_id}
                        className={cn(
                          "cursor-pointer hover:bg-slate-50",
                          selectedTask?.task_id === task.task_id && "bg-blue-50/50",
                        )}
                        onClick={() => onSelectTask(task)}
                      >
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-3">
                            <div className="h-10 w-16 overflow-hidden rounded-md bg-slate-100">
                              {task.thumbnail_url ? (
                                <img src={task.thumbnail_url} alt="" className="h-full w-full object-cover" />
                              ) : (
                                <div className="flex h-full w-full items-center justify-center text-slate-300">
                                  <Film size={18} />
                                </div>
                              )}
                            </div>
                            <div className="min-w-0">
                              <div className="truncate font-medium text-slate-900">{displayTaskName(task)}</div>
                              <div className="mt-0.5 truncate text-xs text-slate-400">{task.original_filename || task.task_id}</div>
                            </div>
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <span className={cn("rounded-full px-2 py-1 text-xs font-medium ring-1", statusBadgeClass(task.status))}>
                            {statusLabel(task.status)}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <div className="h-1.5 w-24 rounded-full bg-slate-100">
                              <div
                                className={cn(
                                  "h-1.5 rounded-full",
                                  task.status === "ERROR" ? "bg-red-500" : "bg-blue-500",
                                )}
                                style={{ width: `${progressByStatus(task)}%` }}
                              />
                            </div>
                            <span className="text-xs text-slate-400">{progressByStatus(task)}%</span>
                          </div>
                        </td>
                        <td className="px-4 py-3 text-slate-600">{task.clip_count || 0}</td>
                        <td className="px-4 py-3 text-slate-600">火山 VC</td>
                        <td className="px-4 py-3 text-slate-500">{formatDate(task.created_at)}</td>
                        <td className="px-4 py-3">
                          <div className="flex justify-end gap-1">
                            <button className="rounded p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700" aria-label="查看">
                              <Eye size={15} />
                            </button>
                            <button
                              onClick={(event) => {
                                event.stopPropagation();
                                onDeleteTask(task.task_id);
                              }}
                              className="rounded p-1.5 text-slate-300 hover:bg-red-50 hover:text-red-500"
                              aria-label="删除"
                            >
                              <Trash2 size={15} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>

          <aside className="rounded-lg border border-slate-200 bg-white p-4">
            {selectedTask ? (
              <div className="space-y-4">
                <div className="aspect-video overflow-hidden rounded-lg bg-slate-100">
                  {selectedTask.thumbnail_url ? (
                    <img src={selectedTask.thumbnail_url} alt="" className="h-full w-full object-cover" />
                  ) : (
                    <div className="flex h-full items-center justify-center text-slate-300">
                      <Film size={32} />
                    </div>
                  )}
                </div>
                <div>
                  <h2 className="text-base font-semibold text-slate-950">{displayTaskName(selectedTask)}</h2>
                  <p className="mt-1 text-xs text-slate-500">{selectedTask.original_filename || selectedTask.task_id}</p>
                </div>
                <ProgressBar currentState={selectedTask.status} errorMessage={selectedTask.message || undefined} />
                <div className="grid grid-cols-2 gap-2">
                  <MetricPill label="候选" value={String(summary?.candidates_count ?? "—")} />
                  <MetricPill label="确认" value={String(summary?.confirmed_count ?? "—")} />
                  <MetricPill label="导出" value={String(summary?.clips_count ?? selectedTask.clip_count ?? 0)} />
                  <MetricPill label="未导出" value={String(summary?.empty_screen_dropped_estimate ?? "—")} />
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={onOpenReview}
                    className="flex-1 rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
                  >
                    进入复核
                  </button>
                  <button
                    disabled
                    title="请到片段资产页选择真实片段后批量下载"
                    className="flex-1 cursor-not-allowed rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-400"
                  >
                    到资产页下载
                  </button>
                </div>
                <div className="border-t border-slate-100 pt-3">
                  <h3 className="text-xs font-semibold text-slate-700">最近诊断事件</h3>
                  <div className="mt-2 space-y-2 text-xs text-slate-500">
                    {(diagnostics?.event_log.length ? diagnostics.event_log.slice(-3) : []).map((event) => (
                      <LogLine
                        key={`${event.time}-${event.file}`}
                        time={formatDate(event.time)}
                        text={`${event.stage}：${event.message}`}
                      />
                    ))}
                    {!diagnostics?.event_log.length && (
                      <p className="text-xs text-slate-400">暂无诊断事件</p>
                    )}
                  </div>
                </div>
              </div>
            ) : (
              <EmptyPreview />
            )}
          </aside>
        </section>
      </main>
    </>
  );
}

function MetricPill({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-slate-50 p-3">
      <div className="text-xs text-slate-400">{label}</div>
      <div className="mt-1 text-lg font-semibold text-slate-900">{value}</div>
    </div>
  );
}

function CreateProjectPage({ onCancel }: { onCancel: () => void }) {
  const settings = useSettingsStore();
  const applyPreset = (title: string) => {
    if (title === "高质量字幕版") {
      settings.setSettings({
        exportMode: "smart",
        asrProvider: "volcengine_vc",
        subtitleMode: "karaoke",
        bgmEnabled: true,
        exportResolution: "1080p",
      });
    } else if (title === "快速低成本版") {
      settings.setSettings({
        exportMode: "no_vlm",
        subtitleMode: "basic",
        asrProvider: "dashscope",
        bgmEnabled: false,
      });
    } else if (title === "全量候选调试版") {
      settings.setSettings({
        exportMode: "all_candidates",
        subtitleMode: "basic",
      });
    } else if (title === "只切不烧字幕版") {
      settings.setSettings({
        subtitleMode: "off",
        bgmEnabled: false,
      });
    }
  };
  const presets = [
    {
      title: "高质量字幕版",
      desc: "火山 VC + Karaoke 字幕 + BGM，适合正式交付。",
      active: settings.asrProvider === "volcengine_vc" && settings.subtitleMode === "karaoke",
    },
    {
      title: "快速低成本版",
      desc: "跳过 VLM 或使用基础字幕，适合快速预览。",
      active: settings.exportMode === "no_vlm" || settings.subtitleMode === "basic",
    },
    {
      title: "全量候选调试版",
      desc: "导出所有候选，用于排查召回和误切。",
      active: settings.exportMode === "all_candidates",
    },
    {
      title: "只切不烧字幕版",
      desc: "关闭字幕烧录，快速获得原声片段。",
      active: settings.subtitleMode === "off",
    },
  ];

  return (
    <>
      <Header
        title="创建剪辑项目"
        description="上传直播录像并选择本次任务使用的处理预设"
        action={
          <>
            <button
              onClick={onCancel}
              className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50"
            >
              取消
            </button>
            <button
              disabled
              title="选择文件后上传框会自动开始处理"
              className="cursor-not-allowed rounded-lg bg-blue-100 px-3 py-2 text-sm font-medium text-blue-500"
            >
              选择文件后开始
            </button>
          </>
        }
      />
      <main className="space-y-5 p-6">
        <div className="grid gap-2 md:grid-cols-3">
          {["上传视频", "选择预设", "确认配置"].map((label, index) => (
            <div key={label} className="rounded-lg border border-slate-200 bg-white p-3">
              <div className="flex items-center gap-2 text-sm font-medium text-slate-900">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-blue-600 text-xs text-white">
                  {index + 1}
                </span>
                {label}
              </div>
            </div>
          ))}
        </div>

        <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
          <div className="space-y-5">
            <div className="rounded-lg border border-slate-200 bg-white p-5">
              <h2 className="text-sm font-semibold text-slate-900">上传直播录像</h2>
              <p className="mt-1 text-xs text-slate-500">支持 MP4，上传后会保存当前设置快照并启动 Celery 流水线。</p>
              <div className="mt-4">
                <UploadZone />
              </div>
            </div>

            <div className="rounded-lg border border-slate-200 bg-white p-5">
              <h2 className="text-sm font-semibold text-slate-900">处理预设</h2>
              <div className="mt-4 grid gap-3 md:grid-cols-2">
                {presets.map((preset) => (
                  <button
                    key={preset.title}
                    onClick={() => applyPreset(preset.title)}
                    className={cn(
                      "rounded-lg border p-4 text-left",
                      preset.active ? "border-blue-200 bg-blue-50" : "border-slate-200 bg-white",
                    )}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <h3 className="text-sm font-semibold text-slate-900">{preset.title}</h3>
                      <span
                        className={cn(
                          "h-4 w-4 rounded-full border",
                          preset.active ? "border-blue-600 bg-blue-600" : "border-slate-300",
                        )}
                      />
                    </div>
                    <p className="mt-2 text-xs leading-5 text-slate-500">{preset.desc}</p>
                  </button>
                ))}
              </div>
            </div>
          </div>

          <aside className="space-y-5">
            <div className="rounded-lg border border-slate-200 bg-white p-5">
              <h2 className="text-sm font-semibold text-slate-900">本次任务配置</h2>
              <div className="mt-4 flex flex-wrap gap-2">
                <Chip label={settings.exportMode === "smart" ? "智能模式" : settings.exportMode} tone="blue" />
                <Chip label={settings.provider.toUpperCase()} tone="blue" />
                <Chip label={settings.asrProvider === "volcengine_vc" ? "火山 VC" : settings.asrProvider} tone="emerald" />
                <Chip label={`${settings.subtitleMode} 字幕`} tone="amber" />
                <Chip label={settings.exportResolution} tone="blue" />
                <Chip label={settings.bgmEnabled ? "BGM开启" : "BGM关闭"} tone="emerald" />
              </div>
              <div className="mt-5 space-y-3 text-sm">
                <ChecklistItem label="格式校验" />
                <ChecklistItem label="编码校验" />
                <ChecklistItem label="音频流" />
                <ChecklistItem label="设置校验" />
              </div>
              <div className="mt-5 rounded-lg bg-slate-50 p-3">
                <div className="text-xs text-slate-500">预计耗时</div>
                <div className="mt-1 text-lg font-semibold text-slate-900">上传后估算</div>
                <p className="mt-1 text-xs text-slate-400">系统会根据视频时长、ASR Provider 和导出配置估算耗时。</p>
              </div>
            </div>
          </aside>
        </section>
      </main>
    </>
  );
}

function ChecklistItem({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-2 text-slate-600">
      <Check className="h-4 w-4 text-emerald-500" />
      {label}
    </div>
  );
}

function LogLine({ time, text }: { time: string; text: string }) {
  return (
    <div className="flex gap-2">
      <span className="shrink-0 font-mono text-slate-400">{time}</span>
      <span>{text}</span>
    </div>
  );
}

function QueuePage({
  tasks,
  onSelectTask,
  onRetryTask,
  onDeleteTask,
  resources,
  events,
  onCreateProject,
}: {
  tasks: TaskItem[];
  onSelectTask: (task: TaskItem) => void;
  onRetryTask: (taskId: string) => void;
  onDeleteTask: (taskId: string) => void;
  resources: SystemResources | null;
  events: DiagnosticReport["event_log"];
  onCreateProject: () => void;
}) {
  const waiting = resources?.queue.waiting ?? tasks.filter((task) => task.status === "UPLOADED").length;
  const processing = resources?.queue.active ?? tasks.filter((task) => classifyStatus(task.status) === "processing").length;
  const completed = resources?.queue.completed ?? tasks.filter((task) => task.status === "COMPLETED").length;
  const failed = resources?.queue.failed ?? tasks.filter((task) => task.status === "ERROR").length;

  return (
    <>
      <Header
        title="任务队列"
        description="查看上传、抽帧、ASR、LLM 融合和导出任务的实时状态"
        action={
          <button
            onClick={onCreateProject}
            className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            <Upload size={16} />
            上传视频
          </button>
        }
      />
      <main className="space-y-5 p-6">
        <section className="grid gap-4 lg:grid-cols-5">
          <MetricCard label="等待中" value={String(waiting)} hint="等待 Celery 调度" />
          <MetricCard label="处理中" value={String(processing)} hint="正在执行流水线" />
          <MetricCard label="已完成" value={String(completed)} hint="可进入复核下载" />
          <MetricCard label="失败" value={String(failed)} hint="需要重试或诊断" />
          <MetricCard label="Worker" value={String(resources?.clip_workers ?? "—")} hint="FFmpeg 并发实例" />
        </section>

        <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_340px]">
          <div className="rounded-lg border border-slate-200 bg-white">
            <div className="border-b border-slate-100 px-4 py-3">
              <h2 className="text-sm font-semibold text-slate-900">实时任务</h2>
            </div>
            <div className="divide-y divide-slate-100">
              {tasks.length === 0 ? (
                <p className="py-12 text-center text-sm text-slate-400">暂无队列任务</p>
              ) : (
                tasks.map((task) => (
                  <button
                    key={task.task_id}
                    onClick={() => onSelectTask(task)}
                    className="grid w-full gap-3 px-4 py-3 text-left hover:bg-slate-50 lg:grid-cols-[minmax(0,1.5fr)_140px_minmax(160px,1fr)_110px_100px_110px]"
                  >
                    <div className="min-w-0">
                      <div className="truncate text-sm font-medium text-slate-900">{displayTaskName(task)}</div>
                      <div className="mt-1 text-xs text-slate-400">{task.original_filename || task.task_id}</div>
                    </div>
                    <div>
                      <span className={cn("rounded-full px-2 py-1 text-xs font-medium ring-1", statusBadgeClass(task.status))}>
                        {stageLabels[task.status] || statusLabel(task.status)}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="h-2 flex-1 rounded-full bg-slate-100">
                        <div
                          className={cn("h-2 rounded-full", task.status === "ERROR" ? "bg-red-500" : "bg-blue-500")}
                          style={{ width: `${progressByStatus(task)}%` }}
                        />
                      </div>
                      <span className="w-9 text-xs text-slate-400">{progressByStatus(task)}%</span>
                    </div>
                    <div className="text-xs text-slate-500">
                      {resources ? `${resources.clip_workers} workers` : "资源未知"}
                    </div>
                    <div className="text-xs text-slate-500">{formatDuration(task.video_duration_s)}</div>
                    <div className="flex justify-end gap-1">
                      <IconButton icon={Eye} label="查看" />
                      <IconButton
                        icon={RefreshCw}
                        label="重试"
                        onClick={(event) => {
                          event.stopPropagation();
                          onRetryTask(task.task_id);
                        }}
                        disabled={task.status !== "ERROR"}
                      />
                      <IconButton
                        icon={Trash2}
                        label="删除"
                        danger
                        onClick={(event) => {
                          event.stopPropagation();
                          onDeleteTask(task.task_id);
                        }}
                      />
                    </div>
                  </button>
                ))
              )}
            </div>
          </div>

          <aside className="space-y-5">
            <div className="rounded-lg border border-slate-200 bg-white p-4">
              <h2 className="text-sm font-semibold text-slate-900">Worker 资源</h2>
              <div className="mt-4 space-y-4">
                <ResourceLine icon={Cpu} label="CPU 配额" value={resources ? `${resources.cpu_cores.toFixed(1)} cores` : "—"} tone="blue" />
                <ResourceLine icon={HardDrive} label="内存上限" value={resources ? `${resources.memory_gb.toFixed(1)}GB` : "—"} tone="emerald" />
                <ResourceLine icon={Server} label="FFmpeg 实例" value={String(resources?.clip_workers ?? "—")} tone="amber" />
              </div>
            </div>
            <div className="rounded-lg border border-slate-200 bg-white p-4">
              <h2 className="text-sm font-semibold text-slate-900">当前任务日志</h2>
              <div className="mt-3 space-y-2 font-mono text-xs text-slate-500">
                {events.length > 0 ? (
                  events.slice(-6).map((event) => (
                    <LogLine
                      key={`${event.time}-${event.file}`}
                      time={formatDate(event.time)}
                      text={`${event.stage}：${event.message}`}
                    />
                  ))
                ) : (
                  <p className="text-slate-400">暂无任务事件</p>
                )}
              </div>
            </div>
          </aside>
        </section>
      </main>
    </>
  );
}

function IconButton({
  icon: Icon,
  label,
  danger,
  onClick,
  disabled,
}: {
  icon: React.ElementType;
  label: string;
  danger?: boolean;
  onClick?: React.MouseEventHandler<HTMLButtonElement>;
  disabled?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={cn(
        "rounded p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700",
        danger && "hover:bg-red-50 hover:text-red-500",
        disabled && "cursor-not-allowed opacity-40 hover:bg-transparent hover:text-slate-400",
      )}
      aria-label={label}
    >
      <Icon size={15} />
    </button>
  );
}

function ResourceLine({
  icon: Icon,
  label,
  value,
  tone,
}: {
  icon: React.ElementType;
  label: string;
  value: string;
  tone: "blue" | "emerald" | "amber";
}) {
  const barClass = {
    blue: "bg-blue-500",
    emerald: "bg-emerald-500",
    amber: "bg-amber-500",
  }[tone];
  return (
    <div>
      <div className="mb-2 flex items-center justify-between text-xs">
        <span className="flex items-center gap-2 text-slate-600">
          <Icon size={14} />
          {label}
        </span>
        <span className="font-medium text-slate-900">{value}</span>
      </div>
      <div className="h-1.5 rounded-full bg-slate-100">
        <div className={cn("h-1.5 w-2/3 rounded-full", barClass)} />
      </div>
    </div>
  );
}

function ReviewPage({
  tasks,
  selectedTask,
  clips,
  clipsLoading,
  onSelectTask,
  reviewData,
  onPatchReviewSegment,
  onReprocessSegment,
}: {
  tasks: TaskItem[];
  selectedTask: TaskItem | null;
  clips: ClipData[];
  clipsLoading: boolean;
  onSelectTask: (task: TaskItem) => void;
  reviewData: ReviewData | null;
  onPatchReviewSegment: (segmentId: string, patch: Partial<ReviewSegment>) => void;
  onReprocessSegment: (segmentId: string) => void;
}) {
  const [previewClip, setPreviewClip] = useState<ClipData | null>(null);
  const currentClip = clips[0] ?? null;
  const currentSegment = reviewData?.segments[0] ?? null;
  const approvedClipIds = clips
    .filter((_clip, index) => reviewData?.segments[index]?.review_status === "approved")
    .map((clip) => clip.clip_id);
  const transcriptLines = reviewData?.transcript
    .filter((line) => {
      if (!currentSegment) return true;
      return line.end_time >= currentSegment.start_time && line.start_time <= currentSegment.end_time;
    })
    .slice(0, 6) ?? [];

  return (
    <>
      <Header
        title="剪辑复核"
        description="复核 AI 生成片段，调整标题、时间边界、封面和导出状态"
        action={
          <>
            <button
              disabled
              title="单项复核按钮会即时保存"
              className="inline-flex cursor-not-allowed items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-400"
            >
              <Save size={16} />
              自动保存
            </button>
            <button
              onClick={() => {
                if (approvedClipIds.length === 0) return;
                window.open(`/api/clips/batch?ids=${approvedClipIds.join(",")}`, "_blank");
              }}
              className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
            >
              <Download size={16} />
              下载通过片段
            </button>
          </>
        }
      />
      <main className="grid min-h-[calc(100vh-4rem)] gap-5 p-6 xl:grid-cols-[minmax(0,1fr)_360px]">
        <section className="space-y-5">
          <div className="rounded-lg border border-slate-200 bg-white p-4">
            <div className="mb-3 flex items-center gap-2 text-xs text-slate-500">
              <span>项目总览</span>
              <ChevronRight size={14} />
              <select
                className="rounded-md border border-slate-200 bg-white px-2 py-1 text-xs text-slate-700"
                value={selectedTask?.task_id || ""}
                onChange={(event) => {
                  const next = tasks.find((task) => task.task_id === event.target.value);
                  if (next) onSelectTask(next);
                }}
              >
                <option value="">选择项目</option>
                {tasks.map((task) => (
                  <option key={task.task_id} value={task.task_id}>
                    {displayTaskName(task)}
                  </option>
                ))}
              </select>
            </div>
            <div className="aspect-video overflow-hidden rounded-lg bg-slate-950">
              {currentClip ? (
                <video src={currentClip.video_url} controls className="h-full w-full bg-black object-contain" />
              ) : (
                <div className="flex h-full flex-col items-center justify-center text-slate-500">
                  <Play size={40} />
                  <p className="mt-3 text-sm">选择已完成项目后查看片段预览</p>
                </div>
              )}
            </div>
            <div className="mt-3 flex items-center justify-between text-xs text-slate-500">
              <span>{currentClip ? `${formatDuration(currentClip.start_time)} - ${formatDuration(currentClip.end_time)}` : "00:00 - 00:00"}</span>
              <span>速度 1.0x · 音量 80%</span>
            </div>
            <div className="mt-4 h-12 rounded-lg bg-slate-50 p-2">
              <div className="relative h-full rounded bg-slate-200">
                <div className="absolute left-[18%] top-0 h-full w-[24%] rounded bg-blue-500/80" />
                <div className="absolute left-[46%] top-0 h-full w-[18%] rounded bg-emerald-500/80" />
                <div className="absolute left-[70%] top-0 h-full w-[12%] rounded bg-amber-400/90" />
              </div>
            </div>
          </div>

          <div className="rounded-lg border border-slate-200 bg-white">
            <div className="border-b border-slate-100 px-4 py-3">
              <h2 className="text-sm font-semibold text-slate-900">生成片段队列</h2>
            </div>
            {clipsLoading ? (
              <p className="py-10 text-center text-sm text-slate-400">加载片段中...</p>
            ) : clips.length === 0 ? (
              <p className="py-10 text-center text-sm text-slate-400">当前项目暂无可复核片段</p>
            ) : (
              <div className="grid gap-3 p-4 md:grid-cols-2 xl:grid-cols-3">
                {clips.map((clip, index) => (
                  <button
                    key={clip.clip_id}
                    onClick={() => setPreviewClip(clip)}
                    className="overflow-hidden rounded-lg border border-slate-200 bg-white text-left hover:border-blue-200 hover:shadow-sm"
                  >
                    <div className="relative aspect-video bg-slate-100">
                      {clip.has_thumbnail ? (
                        <img src={clip.thumbnail_url} alt="" className="h-full w-full object-cover" />
                      ) : (
                        <div className="flex h-full items-center justify-center text-slate-300">
                          <Film size={24} />
                        </div>
                      )}
                  <span className="absolute left-2 top-2 rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700">
                        {reviewStatusLabel(reviewData?.segments[index]?.review_status ?? "pending")}
                      </span>
                    </div>
                    <div className="p-3">
                      <div className="truncate text-sm font-medium text-slate-900">{clip.product_name || "未命名片段"}</div>
                      <div className="mt-1 text-xs text-slate-400">{formatDuration(clip.duration)}</div>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </section>

        <aside className="space-y-5">
          <div className="rounded-lg border border-slate-200 bg-white p-4">
            <h2 className="text-sm font-semibold text-slate-900">片段编辑</h2>
            {currentSegment ? (
              <div className="mt-4 space-y-4">
                <Field label="商品名" value={currentSegment.product_name || currentClip?.product_name || "未命名商品"} />
                <Field label="标题建议" value={currentSegment.title || `${currentSegment.product_name || "商品"}直播讲解片段`} />
                <div className="grid grid-cols-2 gap-3">
                  <Field label="起始时间" value={formatDuration(currentSegment.start_time)} />
                  <Field label="结束时间" value={formatDuration(currentSegment.end_time)} />
                </div>
                <div className="flex flex-wrap gap-2">
                  <Chip label={reviewStatusLabel(currentSegment.review_status)} tone="amber" />
                  <Chip label={reviewData?.transcript.length ? "字幕已生成" : "无字幕"} tone="blue" />
                  <Chip label={currentClip ? "已导出" : "待导出"} tone="emerald" />
                </div>
                <div className="grid grid-cols-3 gap-2">
                  <MetricPill label="置信度" value={String(currentSegment.confidence ?? "—")} />
                  <MetricPill label="文本句数" value={String(transcriptLines.length)} />
                  <MetricPill label="导出状态" value={currentClip ? "已导出" : "未导出"} />
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    onClick={() => onPatchReviewSegment(currentSegment.segment_id, { review_status: "approved" })}
                    className="rounded-lg bg-emerald-600 px-3 py-2 text-sm font-medium text-white hover:bg-emerald-700"
                  >
                    通过
                  </button>
                  <button
                    onClick={() => onPatchReviewSegment(currentSegment.segment_id, { review_status: "skipped" })}
                    className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
                  >
                    跳过
                  </button>
                  <button
                    onClick={() => onPatchReviewSegment(currentSegment.segment_id, { review_status: "needs_adjustment" })}
                    className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
                  >
                    设为封面
                  </button>
                  <button
                    onClick={() => onReprocessSegment(currentSegment.segment_id)}
                    className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
                  >
                    重跑单片段
                  </button>
                </div>
              </div>
            ) : (
              <p className="mt-4 text-sm text-slate-400">暂无可编辑片段</p>
            )}
          </div>
          <div className="rounded-lg border border-slate-200 bg-white p-4">
            <h2 className="text-sm font-semibold text-slate-900">字幕文本</h2>
            <div className="mt-3 space-y-2 text-xs text-slate-600">
              {transcriptLines.length > 0 ? (
                transcriptLines.map((line) => (
                  <TranscriptLine
                    key={`${line.start_time}-${line.end_time}`}
                    time={formatDuration(line.start_time)}
                    text={line.text}
                  />
                ))
              ) : (
                <p className="text-sm text-slate-400">暂无可展示字幕文本</p>
              )}
            </div>
          </div>
        </aside>
      </main>
      <VideoPreview clip={previewClip} onClose={() => setPreviewClip(null)} />
    </>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs text-slate-500">{label}</span>
      <input
        className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 focus:border-blue-400 focus:outline-none"
        defaultValue={value}
      />
    </label>
  );
}

function Chip({ label, tone }: { label: string; tone: "amber" | "blue" | "emerald" }) {
  const className = {
    amber: "bg-amber-50 text-amber-700",
    blue: "bg-blue-50 text-blue-700",
    emerald: "bg-emerald-50 text-emerald-700",
  }[tone];
  return <span className={cn("rounded-full px-2 py-1 text-xs font-medium", className)}>{label}</span>;
}

function reviewStatusLabel(status: ReviewSegment["review_status"]): string {
  const labels: Record<ReviewSegment["review_status"], string> = {
    pending: "待复核",
    approved: "已通过",
    skipped: "已跳过",
    needs_adjustment: "需调整",
  };
  return labels[status] ?? "待复核";
}

function TranscriptLine({ time, text }: { time: string; text: string }) {
  return (
    <div className="rounded-lg bg-slate-50 p-2">
      <span className="font-mono text-slate-400">{time}</span>
      <span className="ml-2">{text}</span>
    </div>
  );
}

function DiagnosticsPage({
  selectedTask,
  diagnostics,
}: {
  selectedTask: TaskItem | null;
  diagnostics: DiagnosticReport | null;
}) {
  const summary = diagnostics?.summary;
  const maxFunnel = Math.max(...(diagnostics?.funnel.map((item) => item.count) ?? [1]), 1);
  const taskId = selectedTask?.task_id;

  return (
    <>
      <Header
        title="任务诊断报告"
        description="理解片段生成、过滤、失败和耗时原因"
        action={
          <>
            <button
              disabled={!taskId}
              onClick={() => taskId && window.open(`${API_BASE}/api/tasks/${taskId}/diagnostics/export`, "_blank")}
              className={cn(
                "inline-flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50",
                !taskId && "cursor-not-allowed opacity-50",
              )}
            >
              <Download size={16} />
              导出报告
            </button>
            <button
              disabled={!taskId}
              onClick={() => taskId && window.open(`${API_BASE}/api/tasks/${taskId}/artifacts.zip`, "_blank")}
              className={cn(
                "inline-flex items-center gap-2 rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700",
                !taskId && "cursor-not-allowed opacity-50",
              )}
            >
              <FileVideo size={16} />
              下载诊断包
            </button>
          </>
        }
      />
      <main className="space-y-5 p-6">
        <section className="grid gap-4 lg:grid-cols-5">
          <MetricCard label="总耗时" value="—" hint="后续接入阶段耗时记录" />
          <MetricCard label="候选片段" value={String(summary?.candidates_count ?? 0)} hint="视觉预筛输出" />
          <MetricCard label="VLM确认" value={String(summary?.confirmed_count ?? 0)} hint="智能模式复核" />
          <MetricCard label="最终导出" value={String(summary?.clips_count ?? selectedTask?.clip_count ?? 0)} hint="clips 目录统计" />
          <MetricCard label="未导出" value={String(summary?.empty_screen_dropped_estimate ?? 0)} hint="空镜/时长/导出过滤" />
        </section>

        <section className="rounded-lg border border-slate-200 bg-white p-4">
          <h2 className="text-sm font-semibold text-slate-900">流水线耗时</h2>
          <div className="mt-5 grid gap-3 md:grid-cols-7">
            {(diagnostics?.pipeline ?? []).map((item) => (
              <div key={item.stage} className="relative rounded-lg bg-slate-50 p-3">
                <div className="flex items-center gap-2">
                  <span className={cn("h-2.5 w-2.5 rounded-full", item.status === "done" ? "bg-emerald-500" : item.status === "skipped" ? "bg-slate-300" : "bg-amber-500")} />
                  <span className="text-xs font-medium text-slate-700">{item.stage}</span>
                </div>
                <div className="mt-2 truncate text-xs font-mono text-slate-500">{item.artifact}</div>
              </div>
            ))}
            {!diagnostics?.pipeline.length && (
              <p className="col-span-full py-6 text-center text-sm text-slate-400">选择项目后查看流水线诊断</p>
            )}
          </div>
        </section>

        <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_380px]">
          <div className="rounded-lg border border-slate-200 bg-white p-4">
            <h2 className="text-sm font-semibold text-slate-900">片段漏斗</h2>
            <div className="mt-4 space-y-3">
              {(diagnostics?.funnel ?? []).map((item) => (
                <div key={item.label} className="grid grid-cols-[90px_minmax(0,1fr)_40px] items-center gap-3 text-sm">
                  <span className="text-slate-600">{item.label}</span>
                  <div className="h-2 rounded-full bg-slate-100">
                    <div className="h-2 rounded-full bg-blue-500" style={{ width: `${Math.round((item.count / maxFunnel) * 100)}%` }} />
                  </div>
                  <span className="text-right font-medium text-slate-900">{item.count}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-lg border border-slate-200 bg-white p-4">
            <h2 className="text-sm font-semibold text-slate-900">异常与建议</h2>
            <div className="mt-4 space-y-3">
              {(diagnostics?.warnings ?? []).map((item) => (
                <Warning key={item.message} text={item.message} />
              ))}
              {!diagnostics?.warnings.length && (
                <p className="text-sm text-slate-400">暂无异常建议</p>
              )}
            </div>
          </div>
        </section>

        <section className="rounded-lg border border-slate-200 bg-white">
          <div className="border-b border-slate-100 px-4 py-3">
            <h2 className="text-sm font-semibold text-slate-900">详细事件日志</h2>
          </div>
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-xs text-slate-500">
              <tr>
                <th className="px-4 py-3">时间</th>
                <th className="px-4 py-3">阶段</th>
                <th className="px-4 py-3">级别</th>
                <th className="px-4 py-3">信息</th>
                <th className="px-4 py-3">文件</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {(diagnostics?.event_log ?? []).map((event) => (
                <tr key={`${event.time}-${event.file}`}>
                  <td className="px-4 py-3 font-mono text-xs text-slate-500">{formatDate(event.time)}</td>
                  <td className="px-4 py-3 text-slate-700">{event.stage}</td>
                  <td className="px-4 py-3">
                    <span className={cn("rounded-full px-2 py-0.5 text-xs font-medium", event.level === "WARN" ? "bg-amber-50 text-amber-700" : "bg-emerald-50 text-emerald-700")}>
                      {event.level}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-600">{event.message}</td>
                  <td className="px-4 py-3 font-mono text-xs text-slate-500">{event.file}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </main>
    </>
  );
}

function AdminMusicPage() {
  const bgmVolume = useSettingsStore((state) => state.bgmVolume);
  const [tracks, setTracks] = useState<MusicTrack[]>([]);
  const [loading, setLoading] = useState(true);
  const [playingId, setPlayingId] = useState<string | null>(null);
  const [selectedTrack, setSelectedTrack] = useState<MusicTrack | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const loadTracks = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchJson<MusicTrack[] | { tracks?: MusicTrack[] }>(`${API_BASE}/api/music/library`);
      const nextTracks = Array.isArray(data) ? data : data.tracks ?? [];
      setTracks(nextTracks);
      setSelectedTrack((current) => current ?? nextTracks[0] ?? null);
    } catch {
      setTracks([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadTracks();
  }, [loadTracks]);

  const userCount = tracks.filter((track) => track.source === "user").length;
  const builtInCount = tracks.filter((track) => track.source === "built-in").length;
  const categoryCount = new Set(tracks.flatMap((track) => track.categories)).size;

  const togglePlay = (track: MusicTrack) => {
    setSelectedTrack(track);
    setPlayingId((current) => (current === track.id ? null : track.id));
  };

  const uploadTrack = async (file: File) => {
    const form = new FormData();
    form.append("file", file);
    await fetch(`${API_BASE}/api/music/upload`, { method: "POST", body: form });
    await loadTracks();
  };

  const deleteTrack = async (trackId: string) => {
    if (!confirm("确定要删除这首用户曲目吗？")) return;
    await fetch(`${API_BASE}/api/music/${trackId}`, { method: "DELETE" });
    await loadTracks();
  };

  return (
    <>
      <Header
        title="音乐库"
        description="管理内置曲库和用户上传 BGM，配置商品类型匹配标签"
        action={
          <>
            <button
              onClick={() => fileInputRef.current?.click()}
              className="inline-flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50"
            >
              <Upload size={16} />
              上传音乐
            </button>
            <button
              onClick={loadTracks}
              className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
            >
              <RefreshCw size={16} />
              刷新曲库
            </button>
          </>
        }
      />
      <main className="space-y-5 p-6">
        <input
          ref={fileInputRef}
          type="file"
          accept=".mp3,audio/mpeg"
          className="hidden"
          onChange={(event) => {
            const file = event.target.files?.[0];
            event.target.value = "";
            if (file) void uploadTrack(file);
          }}
        />
        <section className="grid gap-4 lg:grid-cols-4">
          <MetricCard label="我的音乐" value={String(userCount)} hint="用户上传曲目" />
          <MetricCard label="内置曲目" value={String(builtInCount)} hint="系统预置 BGM" />
          <MetricCard label="已匹配分类" value={String(categoryCount)} hint="商品类型标签" />
          <MetricCard label="默认音量" value={`${Math.round(bgmVolume * 100)}%`} hint="导出混音配置" />
        </section>

        <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
          <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
            <div className="border-b border-slate-100 px-4 py-3">
              <h2 className="text-sm font-semibold text-slate-900">曲目列表</h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[880px] text-left text-sm">
                <thead className="bg-slate-50 text-xs text-slate-500">
                  <tr>
                    <th className="px-4 py-3">曲目</th>
                    <th className="px-4 py-3">来源</th>
                    <th className="px-4 py-3">Mood</th>
                    <th className="px-4 py-3">商品分类</th>
                    <th className="px-4 py-3">节奏</th>
                    <th className="px-4 py-3">能量</th>
                    <th className="px-4 py-3">时长</th>
                    <th className="px-4 py-3 text-right">操作</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {loading ? (
                    <tr>
                      <td colSpan={8} className="px-4 py-12 text-center text-slate-400">加载曲库中...</td>
                    </tr>
                  ) : tracks.length === 0 ? (
                    <tr>
                      <td colSpan={8} className="px-4 py-12 text-center text-slate-400">暂无曲目</td>
                    </tr>
                  ) : (
                    tracks.map((track) => (
                      <tr
                        key={track.id}
                        className={cn("cursor-pointer hover:bg-slate-50", selectedTrack?.id === track.id && "bg-blue-50/50")}
                        onClick={() => setSelectedTrack(track)}
                      >
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-3">
                            <button
                              onClick={(event) => {
                                event.stopPropagation();
                                togglePlay(track);
                              }}
                              className="flex h-8 w-8 items-center justify-center rounded-full bg-slate-100 text-slate-600 hover:bg-blue-50 hover:text-blue-700"
                              aria-label="播放"
                            >
                              {playingId === track.id ? <Pause size={14} /> : <Play size={14} />}
                            </button>
                            <span className="font-medium text-slate-900">{track.title}</span>
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <span className={cn("rounded-full px-2 py-1 text-xs font-medium", track.source === "user" ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-600")}>
                            {track.source === "user" ? "我的" : "内置"}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-slate-600">{track.mood.slice(0, 2).join(" / ") || "—"}</td>
                        <td className="px-4 py-3 text-slate-600">{track.categories.slice(0, 2).join(" / ") || "default"}</td>
                        <td className="px-4 py-3 text-slate-600">{track.tempo}</td>
                        <td className="px-4 py-3 text-slate-600">{track.energy}</td>
                        <td className="px-4 py-3 text-slate-500">{formatDuration(track.duration_s)}</td>
                        <td className="px-4 py-3">
                          <div className="flex justify-end gap-1">
                            <IconButton icon={SlidersHorizontal} label="编辑" disabled />
                            {track.source === "user" && (
                              <IconButton
                                icon={Trash2}
                                label="删除"
                                danger
                                onClick={(event) => {
                                  event.stopPropagation();
                                  void deleteTrack(track.id);
                                }}
                              />
                            )}
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>

          <aside className="space-y-5">
            <div className="rounded-lg border border-dashed border-slate-300 bg-white p-5 text-center">
              <Upload className="mx-auto h-7 w-7 text-slate-300" />
              <h2 className="mt-3 text-sm font-semibold text-slate-900">上传 MP3</h2>
              <p className="mt-1 text-xs text-slate-500">支持 20MB 以内 MP3，上传后补充匹配标签。</p>
              <button
                onClick={() => fileInputRef.current?.click()}
                className="mt-4 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
              >
                选择文件
              </button>
            </div>
            <div className="rounded-lg border border-slate-200 bg-white p-5">
              <h2 className="text-sm font-semibold text-slate-900">标签编辑</h2>
              {selectedTrack ? (
                <div className="mt-4 space-y-4">
                  <Field label="标题" value={selectedTrack.title} />
                  <TagGroup label="Mood" values={selectedTrack.mood.length ? selectedTrack.mood : ["bright", "casual"]} />
                  <TagGroup label="商品分类" values={selectedTrack.categories.length ? selectedTrack.categories : ["default"]} />
                  <div className="grid grid-cols-2 gap-3">
                    <Field label="节奏" value={selectedTrack.tempo || "medium"} />
                    <Field label="能量" value={selectedTrack.energy || "medium"} />
                  </div>
                  <button
                    disabled
                    title="请选择曲目后在后续版本接入标签编辑表单"
                    className="w-full cursor-not-allowed rounded-lg bg-blue-100 px-3 py-2 text-sm font-medium text-blue-500"
                  >
                    标签编辑待启用
                  </button>
                </div>
              ) : (
                <p className="mt-4 text-sm text-slate-400">选择曲目后编辑标签</p>
              )}
            </div>
          </aside>
        </section>

        {selectedTrack && (
          <div className="rounded-lg border border-slate-200 bg-white p-3">
            <div className="flex items-center gap-3">
              <button className="flex h-9 w-9 items-center justify-center rounded-full bg-blue-600 text-white">
                {playingId === selectedTrack.id ? <Pause size={16} /> : <Play size={16} />}
              </button>
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-medium text-slate-900">{selectedTrack.title}</div>
                <div className="mt-2 h-1.5 rounded-full bg-slate-100">
                  <div className="h-1.5 w-1/3 rounded-full bg-blue-500" />
                </div>
              </div>
              <span className="text-xs text-slate-400">音量 {Math.round(bgmVolume * 100)}%</span>
            </div>
          </div>
        )}
      </main>
    </>
  );
}

function TagGroup({ label, values }: { label: string; values: string[] }) {
  return (
    <div>
      <div className="mb-2 text-xs text-slate-500">{label}</div>
      <div className="flex flex-wrap gap-2">
        {values.map((value) => (
          <span key={value} className="rounded-full bg-blue-50 px-2 py-1 text-xs font-medium text-blue-700">
            {value}
          </span>
        ))}
      </div>
    </div>
  );
}

function Warning({ text }: { text: string }) {
  return (
    <div className="flex gap-3 rounded-lg bg-amber-50 p-3 text-sm text-amber-800">
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
      <span>{text}</span>
    </div>
  );
}

function AssetsPage() {
  const [assets, setAssets] = useState<ClipAsset[]>([]);
  const [summary, setSummary] = useState<ClipAssetsResponse["summary"] | null>(null);
  const [selectedClips, setSelectedClips] = useState<Set<string>>(new Set());

  useEffect(() => {
    const controller = new AbortController();
    fetchJson<ClipAssetsResponse>(`${API_BASE}/api/assets/clips?limit=500`, controller.signal)
      .then((data) => {
        if (controller.signal.aborted) return;
        setAssets(data.items ?? []);
        setSummary(data.summary ?? null);
      })
      .catch(() => {
        if (controller.signal.aborted) return;
        setAssets([]);
        setSummary(null);
      });
    return () => controller.abort();
  }, []);

  const toggleClip = (clipId: string) => {
    setSelectedClips((current) => {
      const next = new Set(current);
      if (next.has(clipId)) next.delete(clipId);
      else next.add(clipId);
      return next;
    });
  };

  return (
    <>
      <Header
        title="片段资产"
        description="浏览、筛选、批量下载和复用已生成的短视频片段"
        action={
          <>
            <button
              onClick={() => window.open(`${API_BASE}/api/assets/clips?limit=500`, "_blank")}
              className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50"
            >
              导出清单
            </button>
            <button
              onClick={() => {
                if (selectedClips.size === 0) return;
                window.open(`/api/clips/batch?ids=${Array.from(selectedClips).join(",")}`, "_blank");
              }}
              className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
            >
              <Download size={16} />
              批量下载
            </button>
          </>
        }
      />
      <main className="space-y-5 p-6">
        <section className="rounded-lg border border-slate-200 bg-white p-4">
          <div className="flex flex-wrap gap-3">
            <div className="flex min-w-72 flex-1 items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-400">
              <Search size={16} />
              <span>搜索商品名 / 项目 / 文件名</span>
            </div>
            {["全部状态", "全部项目", "全部时长", "最近 30 天"].map((label) => (
              <button key={label} className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50">
                {label}
              </button>
            ))}
          </div>
        </section>

        <section className="grid gap-4 lg:grid-cols-4">
          <MetricCard label="全部片段" value={String(summary?.total ?? assets.length)} hint="跨项目统计" />
          <MetricCard label="待复核" value={String(summary?.pending ?? 0)} hint="等待人工确认" />
          <MetricCard label="已通过" value={String(summary?.approved ?? 0)} hint="可交付片段" />
          <MetricCard label="可下载" value={String(summary?.downloadable ?? 0)} hint="文件存在的片段" />
        </section>

        <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_300px]">
          <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-4">
            {assets.length === 0 ? (
              <div className="col-span-full rounded-lg border border-dashed border-slate-200 bg-white py-16 text-center text-sm text-slate-400">
                暂无片段资产，请先完成项目处理。
              </div>
            ) : (
              assets.map((clip) => (
                <div key={clip.clip_id} className="overflow-hidden rounded-lg border border-slate-200 bg-white">
                  <div className="relative aspect-video bg-slate-100">
                    {clip.has_thumbnail ? (
                      <img src={clip.thumbnail_url} alt="" className="h-full w-full object-cover" />
                    ) : (
                      <div className="flex h-full items-center justify-center text-slate-300">
                        <Film size={28} />
                      </div>
                    )}
                    <label className="absolute left-2 top-2">
                      <input
                        type="checkbox"
                        checked={selectedClips.has(clip.clip_id)}
                        onChange={() => toggleClip(clip.clip_id)}
                        className="h-4 w-4 rounded border-slate-300 text-blue-600"
                      />
                    </label>
                    <span className="absolute bottom-2 right-2 rounded bg-black/70 px-1.5 py-0.5 text-xs text-white">
                      {formatDuration(clip.duration)}
                    </span>
                    <span className="absolute right-2 top-2 rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700">
                      {reviewStatusLabel(clip.review_status)}
                    </span>
                  </div>
                  <div className="p-3">
                    <div className="truncate text-sm font-medium text-slate-900">{clip.product_name}</div>
                    <div className="mt-1 text-xs text-slate-400">{clip.clip_id}</div>
                    <div className="mt-3 flex gap-2">
                      <a
                        href={clip.video_url}
                        download
                        className="inline-flex flex-1 items-center justify-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
                      >
                        <Download size={15} />
                        下载
                      </a>
                      <button className="rounded-lg border border-slate-200 px-3 py-2 text-slate-600 hover:bg-slate-50">
                        <Eye size={15} />
                      </button>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>

          <aside className="rounded-lg border border-slate-200 bg-white p-4">
            <h2 className="text-sm font-semibold text-slate-900">批量操作</h2>
            <div className="mt-4 rounded-lg bg-slate-50 p-3">
              <div className="text-xs text-slate-500">已选片段</div>
              <div className="mt-1 text-2xl font-semibold text-slate-900">{selectedClips.size}</div>
            </div>
            <div className="mt-4 space-y-2 text-sm text-slate-500">
              <div className="flex justify-between">
                <span>总时长</span>
                <span>{formatDuration(assets.filter((clip) => selectedClips.has(clip.clip_id)).reduce((sum, clip) => sum + clip.duration, 0))}</span>
              </div>
              <div className="flex justify-between">
                <span>预计 ZIP</span>
                <span>{formatBytes(assets.filter((clip) => selectedClips.has(clip.clip_id)).reduce((sum, clip) => sum + clip.file_size, 0))}</span>
              </div>
            </div>
            <button
              onClick={() => {
                if (selectedClips.size === 0) return;
                window.open(`/api/clips/batch?ids=${Array.from(selectedClips).join(",")}`, "_blank");
              }}
              className="mt-5 w-full rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
            >
              下载所选
            </button>
            <button
              onClick={() => setSelectedClips(new Set())}
              className="mt-2 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
            >
              清空选择
            </button>
          </aside>
        </section>
      </main>
    </>
  );
}

function AdminSettingsPage() {
  const settings = useSettingsStore();
  const [draft, setDraft] = useState({
    enableVlm: settings.enableVlm,
    exportMode: settings.exportMode,
    provider: settings.provider,
    apiKey: settings.apiKey,
    apiBase: settings.apiBase,
    model: settings.model,
    subtitleMode: settings.subtitleMode,
    asrProvider: settings.asrProvider,
    asrApiKey: settings.asrApiKey,
    enableLlmAnalysis: settings.enableLlmAnalysis,
    llmApiBase: settings.llmApiBase,
    llmModel: settings.llmModel,
    enableBoundaryRefinement: settings.enableBoundaryRefinement,
    exportResolution: settings.exportResolution,
    fillerFilterMode: settings.fillerFilterMode,
    segmentGranularity: settings.segmentGranularity,
    bgmEnabled: settings.bgmEnabled,
    bgmVolume: settings.bgmVolume,
    originalVolume: settings.originalVolume,
    videoSpeed: settings.videoSpeed,
  });

  const saveSettings = () => {
    settings.setSettings(draft);
  };

  const resetSettings = () => {
    settings.reset();
    const latest = useSettingsStore.getState();
    setDraft({
      enableVlm: latest.enableVlm,
      exportMode: latest.exportMode,
      provider: latest.provider,
      apiKey: latest.apiKey,
      apiBase: latest.apiBase,
      model: latest.model,
      subtitleMode: latest.subtitleMode,
      asrProvider: latest.asrProvider,
      asrApiKey: latest.asrApiKey,
      enableLlmAnalysis: latest.enableLlmAnalysis,
      llmApiBase: latest.llmApiBase,
      llmModel: latest.llmModel,
      enableBoundaryRefinement: latest.enableBoundaryRefinement,
      exportResolution: latest.exportResolution,
      fillerFilterMode: latest.fillerFilterMode,
      segmentGranularity: latest.segmentGranularity,
      bgmEnabled: latest.bgmEnabled,
      bgmVolume: latest.bgmVolume,
      originalVolume: latest.originalVolume,
      videoSpeed: latest.videoSpeed,
    });
  };

  return (
    <>
      <Header
        title="系统设置"
        description="配置新上传任务使用的 AI 服务、分段策略、字幕和导出参数"
        action={
          <>
            <button
              onClick={resetSettings}
              className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50"
            >
              恢复默认
            </button>
            <button
              onClick={saveSettings}
              className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
            >
              <Save size={16} />
              保存设置
            </button>
          </>
        }
      />
      <main className="grid gap-5 p-6 xl:grid-cols-[190px_minmax(0,1fr)_320px]">
        <aside className="rounded-lg border border-slate-200 bg-white p-3">
          {["AI 服务", "分段策略", "字幕样式", "导出与音频", "高级参数"].map((item, index) => (
            <button
              key={item}
              className={cn(
                "w-full rounded-lg px-3 py-2 text-left text-sm",
                index === 0 ? "bg-blue-50 font-medium text-blue-700" : "text-slate-600 hover:bg-slate-50",
              )}
            >
              {item}
            </button>
          ))}
        </aside>

        <section className="grid gap-5 lg:grid-cols-2">
          <SettingsPanel title="VLM 设置" desc="控制视觉多模态确认和模型参数。">
            <ToggleRow
              label="启用 VLM"
              checked={draft.enableVlm}
              onChange={(enableVlm) => setDraft({ ...draft, enableVlm, exportMode: enableVlm ? draft.exportMode : "no_vlm" })}
            />
            <SelectField
              label="导出模式"
              value={draft.exportMode}
              onChange={(exportMode) => setDraft({ ...draft, exportMode: exportMode as ExportMode })}
              options={[
                ["smart", "智能模式"],
                ["no_vlm", "跳过 VLM"],
                ["all_candidates", "候选全切"],
                ["all_scenes", "场景全切"],
              ]}
            />
            <SelectField
              label="Provider"
              value={draft.provider}
              onChange={(provider) =>
                setDraft({
                  ...draft,
                  provider: provider as VlmProvider,
                  apiBase: DEFAULT_API_BASES[provider as VlmProvider],
                  model: DEFAULT_MODELS[provider as VlmProvider],
                })
              }
              options={[
                ["qwen", "Qwen"],
                ["glm", "GLM"],
              ]}
            />
            <InputField label="API Base" value={draft.apiBase} onChange={(apiBase) => setDraft({ ...draft, apiBase })} />
            <InputField label="Model" value={draft.model} onChange={(model) => setDraft({ ...draft, model })} />
            <InputField label="API Key" value={draft.apiKey} onChange={(apiKey) => setDraft({ ...draft, apiKey })} password />
          </SettingsPanel>

          <SettingsPanel title="ASR 与 LLM" desc="配置字幕转写、文本分析和边界精修。">
            <SelectField
              label="ASR Provider"
              value={draft.asrProvider}
              onChange={(asrProvider) => setDraft({ ...draft, asrProvider: asrProvider as AsrProvider })}
              options={[
                ["volcengine_vc", "火山 VC"],
                ["volcengine", "火山标准"],
                ["dashscope", "DashScope"],
              ]}
            />
            <InputField label="ASR API Key" value={draft.asrApiKey} onChange={(asrApiKey) => setDraft({ ...draft, asrApiKey })} password />
            <ToggleRow
              label="LLM 文本分析"
              checked={draft.enableLlmAnalysis}
              onChange={(enableLlmAnalysis) => setDraft({ ...draft, enableLlmAnalysis })}
            />
            <InputField label="LLM API Base" value={draft.llmApiBase} onChange={(llmApiBase) => setDraft({ ...draft, llmApiBase })} />
            <InputField label="LLM Model" value={draft.llmModel} onChange={(llmModel) => setDraft({ ...draft, llmModel })} />
            <ToggleRow
              label="边界精修"
              checked={draft.enableBoundaryRefinement}
              onChange={(enableBoundaryRefinement) => setDraft({ ...draft, enableBoundaryRefinement })}
            />
          </SettingsPanel>

          <SettingsPanel title="字幕与切分" desc="控制字幕样式、语气词过滤和切分粒度。">
            <SelectField
              label="字幕模式"
              value={draft.subtitleMode}
              onChange={(subtitleMode) => setDraft({ ...draft, subtitleMode: subtitleMode as SubtitleMode })}
              options={[
                ["off", "关闭"],
                ["basic", "基础字幕"],
                ["styled", "样式字幕"],
                ["karaoke", "Karaoke"],
              ]}
            />
            <SelectField
              label="语气词过滤"
              value={draft.fillerFilterMode}
              onChange={(fillerFilterMode) => setDraft({ ...draft, fillerFilterMode: fillerFilterMode as FillerFilterMode })}
              options={[
                ["off", "关闭"],
                ["subtitle", "仅字幕"],
                ["video", "字幕+视频裁剪"],
              ]}
            />
            <SelectField
              label="切分粒度"
              value={draft.segmentGranularity}
              onChange={(segmentGranularity) => setDraft({ ...draft, segmentGranularity: segmentGranularity as SegmentGranularity })}
              options={[
                ["single_item", "单品"],
                ["outfit", "整套搭配"],
              ]}
            />
          </SettingsPanel>

          <SettingsPanel title="导出与音频" desc="控制分辨率、倍速、封面和 BGM 混音。">
            <SelectField
              label="导出分辨率"
              value={draft.exportResolution}
              onChange={(exportResolution) => setDraft({ ...draft, exportResolution: exportResolution as ExportResolution })}
              options={[
                ["1080p", "1080p"],
                ["4k", "4K"],
                ["original", "原始"],
              ]}
            />
            <SelectField
              label="视频倍速"
              value={String(draft.videoSpeed)}
              onChange={(videoSpeed) => setDraft({ ...draft, videoSpeed: Number(videoSpeed) as typeof draft.videoSpeed })}
              options={[
                ["0.5", "0.5x"],
                ["0.75", "0.75x"],
                ["1", "1x"],
                ["1.25", "1.25x"],
                ["1.5", "1.5x"],
                ["1.75", "1.75x"],
                ["2", "2x"],
                ["3", "3x"],
              ]}
            />
            <ToggleRow label="启用 BGM" checked={draft.bgmEnabled} onChange={(bgmEnabled) => setDraft({ ...draft, bgmEnabled })} />
            <SliderField label="BGM 音量" value={draft.bgmVolume} max={1} onChange={(bgmVolume) => setDraft({ ...draft, bgmVolume })} />
            <SliderField label="原声音量" value={draft.originalVolume} max={2} onChange={(originalVolume) => setDraft({ ...draft, originalVolume })} />
          </SettingsPanel>
        </section>

        <aside className="space-y-5">
          <div className="rounded-lg border border-slate-200 bg-white p-5">
            <h2 className="text-sm font-semibold text-slate-900">当前配置预览</h2>
            <div className="mt-4 flex flex-wrap gap-2">
              <Chip label={draft.exportMode === "smart" ? "智能模式" : draft.exportMode} tone="blue" />
              <Chip label={draft.provider.toUpperCase()} tone="blue" />
              <Chip label={draft.asrProvider === "volcengine_vc" ? "火山 VC" : draft.asrProvider} tone="emerald" />
              <Chip label={`${draft.subtitleMode} 字幕`} tone="amber" />
              <Chip label={draft.exportResolution} tone="blue" />
              <Chip label={draft.bgmEnabled ? `BGM ${Math.round(draft.bgmVolume * 100)}%` : "BGM关闭"} tone="emerald" />
            </div>
            <div className="mt-5 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-700">
              设置结构有效，将在新上传任务时写入 settings.json。
            </div>
          </div>
        </aside>
      </main>
    </>
  );
}

function SettingsPanel({ title, desc, children }: { title: string; desc: string; children: React.ReactNode }) {
  return (
    <section className="space-y-4 rounded-lg border border-slate-200 bg-white p-5">
      <div>
        <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
        <p className="mt-1 text-xs text-slate-500">{desc}</p>
      </div>
      {children}
    </section>
  );
}

function InputField({
  label,
  value,
  onChange,
  password,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  password?: boolean;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs text-slate-500">{label}</span>
      <input
        type={password ? "password" : "text"}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 focus:border-blue-400 focus:outline-none"
      />
    </label>
  );
}

function SelectField({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: string[] | [string, string][];
}) {
  const normalized = options.map((option) => (Array.isArray(option) ? option : [option, option]));
  return (
    <label className="block">
      <span className="mb-1 block text-xs text-slate-500">{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 focus:border-blue-400 focus:outline-none"
      >
        {normalized.map(([optionValue, optionLabel]) => (
          <option key={optionValue} value={optionValue}>
            {optionLabel}
          </option>
        ))}
      </select>
    </label>
  );
}

function ToggleRow({ label, checked, onChange }: { label: string; checked: boolean; onChange: (checked: boolean) => void }) {
  return (
    <div className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2">
      <span className="text-sm text-slate-700">{label}</span>
      <button
        onClick={() => onChange(!checked)}
        className={cn("h-6 w-11 rounded-full p-0.5 transition-colors", checked ? "bg-blue-600" : "bg-slate-300")}
        aria-label={label}
      >
        <span className={cn("block h-5 w-5 rounded-full bg-white transition-transform", checked && "translate-x-5")} />
      </button>
    </div>
  );
}

function SliderField({
  label,
  value,
  max,
  onChange,
}: {
  label: string;
  value: number;
  max: number;
  onChange: (value: number) => void;
}) {
  return (
    <label className="block">
      <div className="mb-1 flex items-center justify-between text-xs">
        <span className="text-slate-500">{label}</span>
        <span className="font-medium text-slate-700">{Math.round(value * 100)}%</span>
      </div>
      <input
        type="range"
        min={0}
        max={max}
        step={0.05}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
        className="w-full"
      />
    </label>
  );
}

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
      return;
    }
    const controller = new AbortController();
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
      await fetch(`${API_BASE}/api/tasks/${selectedTask.task_id}/clips/${segmentId}/reprocess`, {
        method: "POST",
      });
    },
    [selectedTask],
  );

  const handlePageChange = (nextPage: PageKey) => {
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
          />
        )}
        {page === "assets" && <AssetsPage />}
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
