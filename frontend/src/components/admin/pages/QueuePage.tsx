import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Activity, Calendar, CheckCircle2, Circle, Cpu, Ellipsis, Eye, Film, HardDrive, RefreshCw, Server, Trash2, Upload } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAdminContext } from "@/components/admin/context";
import { useTaskList, useSystemResources, useTaskEvents, useDeleteTask, useRetryTask } from "@/hooks/useAdminQueries";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { useConfirmStore } from "@/stores/confirmStore";
import { stageLabels } from "../constants";
import {
  displayTaskName,
  formatDate,
  formatDuration,
  progressByStatus,
  resourcePercent,
  statusBadgeClass,
  statusLabel,
  userFacingMessage,
} from "../format";
import { Button, DrawerSection, DrawerShell, DrawerTabs, FilterToolbar, Header, LogLine, MetricCard, Pagination, ResourceLine, SearchInput, ToolbarSelect } from "../shared";
import type { TaskItem } from "../types";

type QueueDrawerTab = "overview" | "logs" | "resources";

export function QueuePage() {
  const navigate = useNavigate();
  const { selectedTask, setSelectedTask } = useAdminContext();
  const [page, setPage] = useState(1);
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerTab, setDrawerTab] = useState<QueueDrawerTab>("overview");
  const [openMenuTaskId, setOpenMenuTaskId] = useState<string | null>(null);
  const pageSize = 10;
  const debouncedQuery = useDebouncedValue(query);
  const { data: taskList } = useTaskList({ page, pageSize, query: debouncedQuery, status: statusFilter });
  const tasks = taskList?.items ?? [];
  const { data: resources } = useSystemResources();
  const { data: events = [] } = useTaskEvents(selectedTask?.task_id);
  const deleteTask = useDeleteTask();
  const retryTask = useRetryTask();
  const confirm = useConfirmStore((state) => state.confirm);

  const waiting = resources?.queue.waiting ?? taskList?.summary?.uploaded ?? 0;
  const processing = resources?.queue.active ?? taskList?.summary?.processing ?? 0;
  const completed = resources?.queue.completed ?? taskList?.summary?.completed ?? 0;
  const failed = resources?.queue.failed ?? taskList?.summary?.failed ?? 0;

  const openTask = (task: TaskItem, tab: QueueDrawerTab = "overview") => {
    setSelectedTask(task);
    setDrawerTab(tab);
    setDrawerOpen(true);
    setOpenMenuTaskId(null);
  };

  const handleDeleteTask = async (task: TaskItem) => {
    const confirmed = await confirm({
      title: "删除任务",
      description: "删除后会移除这个任务及相关产物，操作无法恢复。",
      confirmLabel: "删除",
      danger: true,
    });
    if (!confirmed) return;
    await deleteTask.mutateAsync(task.task_id).then(() => {
      if (selectedTask?.task_id === task.task_id) {
        setSelectedTask(null);
        setDrawerOpen(false);
      }
    }).catch(() => {});
  };

  return (
    <>
      <Header
        title="任务队列"
        description="查看上传、抽帧、ASR、LLM 融合和导出任务的实时状态"
        action={
          <button
            onClick={() => navigate("/create")}
            className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            <Upload size={16} />
            上传视频
          </button>
        }
      />
      <main className="space-y-5 p-4 sm:p-6">
        <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_260px]">
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4 lg:gap-4">
            <MetricCard label="等待中" value={String(waiting)} hint="等待 Celery 调度" />
            <MetricCard label="处理中" value={String(processing)} hint="正在执行流水线" />
            <MetricCard label="已完成" value={String(completed)} hint="可进入复核下载" />
            <MetricCard label="失败" value={String(failed)} hint="需要重试或诊断" />
          </div>
          <div className="rounded-lg border border-slate-200 bg-white p-4">
            <div className="text-sm font-semibold text-slate-900">Worker 资源</div>
            <div className="mt-3 flex items-end justify-between">
              <div className="text-2xl font-semibold text-slate-950">{resources?.clip_workers ?? "—"} <span className="text-sm text-slate-400">/ 4</span></div>
              <span className={cn("rounded-full px-2 py-1 text-xs font-medium", resources?.redis === "ok" ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700")}>
                Redis {resources?.redis ?? "—"}
              </span>
            </div>
            <div className="mt-3 h-2 rounded-full bg-slate-100">
              <div className="h-2 rounded-full bg-emerald-500" style={{ width: `${resourcePercent(resources?.clip_workers, 4) ?? 0}%` }} />
            </div>
          </div>
        </section>

        <section className="rounded-lg border border-slate-200 bg-white">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-4 py-3">
            <div>
              <h2 className="text-sm font-semibold text-slate-900">实时任务</h2>
              <p className="mt-0.5 text-xs text-slate-400">按处理进度扫描任务，点击查看完整日志和资源状态。</p>
            </div>
            <div className="flex flex-wrap gap-3 text-xs text-slate-500">
              <ResourceSummary label="CPU" value={resources ? `${resources.cpu_cores.toFixed(1)} cores` : "—"} />
              <ResourceSummary label="内存" value={resources ? `${resources.memory_gb.toFixed(1)}GB` : "—"} />
            </div>
          </div>
          <FilterToolbar>
            <SearchInput
              value={query}
              onChange={(value) => {
                setQuery(value);
                setPage(1);
              }}
              placeholder="搜索项目 ID / 任务 ID / 视频名称"
            />
            <ToolbarSelect
              value={statusFilter}
              onChange={(value) => {
                setStatusFilter(value);
                setPage(1);
              }}
            >
              <option value="all">全部状态</option>
              <option value="processing">处理中</option>
              <option value="completed">已完成</option>
              <option value="failed">失败</option>
              <option value="uploaded">等待中</option>
            </ToolbarSelect>
            <ToolbarSelect>
              <option>全部优先级</option>
              <option>高优先级</option>
              <option>普通优先级</option>
            </ToolbarSelect>
            <ToolbarSelect>
              <option>全部项目</option>
            </ToolbarSelect>
            <button className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-500 hover:bg-slate-50">
              <Calendar size={15} />
              开始日期
              <span className="text-slate-300">→</span>
              结束日期
            </button>
          </FilterToolbar>

          <div className="hidden overflow-x-auto lg:block">
            <div className="grid min-w-[1120px] grid-cols-[minmax(280px,1.4fr)_90px_160px_120px_80px_80px_110px_100px] gap-4 border-b border-slate-100 bg-slate-50 px-4 py-3 text-xs font-medium text-slate-500">
              <div>任务信息</div>
              <div>状态</div>
              <div>进度</div>
              <div>当前阶段</div>
              <div>时长</div>
              <div>Worker</div>
              <div>创建时间</div>
              <div className="text-right">操作</div>
            </div>
            {tasks.length === 0 ? (
              <p className="py-12 text-center text-sm text-slate-400">暂无队列任务</p>
            ) : (
              tasks.map((task) => (
                <QueueTaskRow
                  key={task.task_id}
                  task={task}
                  active={selectedTask?.task_id === task.task_id && drawerOpen}
                  workerText={resources ? String(resources.clip_workers) : "—"}
                  onOpen={() => openTask(task)}
                  onView={() => openTask(task)}
                  onOpenResult={() => {
                    if (task.status === "COMPLETED") navigate("/assets");
                    else navigate("/review");
                  }}
                  onLogs={() => openTask(task, "logs")}
                  onRetry={() => void retryTask.mutateAsync(task.task_id)}
                  onDelete={() => void handleDeleteTask(task)}
                  menuOpen={openMenuTaskId === task.task_id}
                  onToggleMenu={() => setOpenMenuTaskId((current) => current === task.task_id ? null : task.task_id)}
                />
              ))
            )}
          </div>
          <div className="divide-y divide-slate-100 lg:hidden">
            {tasks.length === 0 ? (
              <p className="py-12 text-center text-sm text-slate-400">暂无队列任务</p>
            ) : (
              tasks.map((task) => (
                <QueueMobileTaskCard
                  key={task.task_id}
                  task={task}
                  active={selectedTask?.task_id === task.task_id && drawerOpen}
                  resourcesText={resources ? `${resources.clip_workers} workers` : "等待资源"}
                  onOpen={() => openTask(task)}
                  onView={() => openTask(task)}
                  onOpenResult={() => {
                    if (task.status === "COMPLETED") navigate("/assets");
                    else navigate("/review");
                  }}
                  onLogs={() => openTask(task, "logs")}
                  onRetry={() => void retryTask.mutateAsync(task.task_id)}
                  onDelete={() => void handleDeleteTask(task)}
                  menuOpen={openMenuTaskId === task.task_id}
                  onToggleMenu={() => setOpenMenuTaskId((current) => current === task.task_id ? null : task.task_id)}
                />
              ))
            )}
          </div>
          <Pagination page={page} pageSize={pageSize} total={taskList?.total ?? 0} onPageChange={setPage} />
        </section>
      </main>

      <QueueDetailDrawer
        open={drawerOpen}
        task={selectedTask}
        tab={drawerTab}
        onTabChange={setDrawerTab}
        events={events}
        resources={resources}
        onClose={() => setDrawerOpen(false)}
        onRetry={(task) => void retryTask.mutateAsync(task.task_id)}
        onDelete={(task) => void handleDeleteTask(task)}
        onOpenResult={(task) => {
          if (task.status === "COMPLETED") navigate("/assets");
          else navigate("/review");
        }}
      />
    </>
  );
}

function QueueTaskRow({
  task,
  active,
  workerText,
  onOpen,
  onView,
  onOpenResult,
  onLogs,
  onRetry,
  onDelete,
  menuOpen,
  onToggleMenu,
}: {
  task: TaskItem;
  active: boolean;
  workerText: string;
  onOpen: () => void;
  onView: () => void;
  onOpenResult: () => void;
  onLogs: () => void;
  onRetry: () => void;
  onDelete: () => void;
  menuOpen: boolean;
  onToggleMenu: () => void;
}) {
  const progress = progressByStatus(task);
  const currentStage = displayQueueStage(task);
  return (
    <article className={cn("min-w-[1120px] border-b border-slate-100 px-4 py-3 last:border-b-0", active && "bg-blue-50/40")}>
      <div className="grid grid-cols-[minmax(280px,1.4fr)_90px_160px_120px_80px_80px_110px_100px] items-center gap-4">
        <button onClick={onOpen} className="min-w-0 text-left">
          <div className="flex min-w-0 items-center gap-3">
            <div className="h-12 w-16 shrink-0 overflow-hidden rounded-lg bg-slate-100">
              {task.thumbnail_url ? (
                <img src={task.thumbnail_url} alt="" className="h-full w-full object-cover" />
              ) : (
                <div className="flex h-full w-full items-center justify-center text-slate-300">
                  <Film size={18} />
                </div>
              )}
            </div>
            <div className="min-w-0">
              <div className="truncate text-sm font-semibold text-slate-900">{displayTaskName(task)}</div>
              <div className="mt-1 truncate text-xs text-slate-400">{task.original_filename || task.task_id}</div>
            </div>
          </div>
        </button>
        <div>
          <span className={cn("rounded-full px-2 py-1 text-xs font-medium ring-1", statusBadgeClass(task.status))}>
            {stageLabels[task.status] || statusLabel(task.status)}
          </span>
        </div>
        <button onClick={onOpen} className="text-left">
          <div className="flex items-center justify-between gap-3">
            <span className="text-xs text-slate-400">{progress}%</span>
          </div>
          <div className="mt-2 h-2 rounded-full bg-slate-100">
            <div className={cn("h-2 rounded-full", task.status === "ERROR" ? "bg-red-500" : "bg-blue-500")} style={{ width: `${progress}%` }} />
          </div>
        </button>
        <div className="text-xs text-slate-500">
          <div>{currentStage}</div>
        </div>
        <div className="text-xs text-slate-500">{formatDuration(task.video_duration_s)}</div>
        <div className="text-xs text-slate-500">{workerText}</div>
        <div className="text-xs text-slate-500">
          {formatDate(task.created_at)}
        </div>
        <div className="relative flex justify-end gap-2">
          <QueueIconAction icon={Eye} label="查看" onClick={onView} />
          <button
            onClick={onToggleMenu}
            className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50"
            aria-label="更多操作"
          >
            <Ellipsis size={16} />
          </button>
          {menuOpen && (
            <div className="absolute right-0 top-9 z-20 w-32 overflow-hidden rounded-lg border border-slate-200 bg-white py-1 text-sm shadow-lg">
              <button onClick={onLogs} className="flex w-full items-center gap-2 px-3 py-2 text-left text-slate-700 hover:bg-slate-50">
                <Activity size={14} /> 日志
              </button>
              <button onClick={onOpenResult} className="flex w-full items-center gap-2 px-3 py-2 text-left text-slate-700 hover:bg-slate-50">
                <Eye size={14} /> 结果
              </button>
              <button
                onClick={onRetry}
                disabled={task.status !== "ERROR"}
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
              >
                <RefreshCw size={14} /> 重试
              </button>
              <button onClick={onDelete} className="flex w-full items-center gap-2 px-3 py-2 text-left text-red-600 hover:bg-red-50">
                <Trash2 size={14} /> 删除
              </button>
            </div>
          )}
        </div>
      </div>
    </article>
  );
}

function QueueMobileTaskCard({
  task,
  active,
  resourcesText,
  onOpen,
  onView,
  onOpenResult,
  onLogs,
  onRetry,
  onDelete,
  menuOpen,
  onToggleMenu,
}: {
  task: TaskItem;
  active: boolean;
  resourcesText: string;
  onOpen: () => void;
  onView: () => void;
  onOpenResult: () => void;
  onLogs: () => void;
  onRetry: () => void;
  onDelete: () => void;
  menuOpen: boolean;
  onToggleMenu: () => void;
}) {
  const progress = progressByStatus(task);
  const currentStage = displayQueueStage(task);
  return (
    <article className={cn("px-4 py-4", active && "bg-blue-50/40")}>
      <button onClick={onOpen} className="flex w-full min-w-0 gap-3 text-left">
        <div className="h-16 w-20 shrink-0 overflow-hidden rounded-lg bg-slate-100">
          {task.thumbnail_url ? (
            <img src={task.thumbnail_url} alt="" className="h-full w-full object-cover" />
          ) : (
            <div className="flex h-full w-full items-center justify-center text-slate-300">
              <Film size={18} />
            </div>
          )}
        </div>
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-semibold text-slate-900">{displayTaskName(task)}</div>
          <div className="mt-1 truncate text-xs text-slate-400">{task.original_filename || task.task_id}</div>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <span className={cn("rounded-full px-2 py-1 text-xs font-medium ring-1", statusBadgeClass(task.status))}>
              {stageLabels[task.status] || statusLabel(task.status)}
            </span>
            <span className="text-xs text-slate-400">{formatDuration(task.video_duration_s)}</span>
          </div>
        </div>
      </button>
      <button onClick={onOpen} className="mt-3 w-full text-left">
        <div className="flex items-center justify-between text-xs text-slate-500">
          <span>{currentStage}</span>
          <span>{progress}%</span>
        </div>
        <div className="mt-2 h-2 rounded-full bg-slate-100">
          <div className={cn("h-2 rounded-full", task.status === "ERROR" ? "bg-red-500" : "bg-blue-500")} style={{ width: `${progress}%` }} />
        </div>
      </button>
      <div className="mt-3 flex items-center justify-between gap-3">
        <span className="truncate text-xs text-slate-400">{resourcesText} · {formatDate(task.created_at)}</span>
        <div className="relative flex shrink-0 gap-2">
          <QueueIconAction icon={Eye} label="查看" onClick={onView} />
          <button
            onClick={onToggleMenu}
            className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50"
            aria-label="更多操作"
          >
            <Ellipsis size={16} />
          </button>
          {menuOpen && (
            <div className="absolute right-0 top-9 z-20 w-32 overflow-hidden rounded-lg border border-slate-200 bg-white py-1 text-sm shadow-lg">
              <button onClick={onLogs} className="flex w-full items-center gap-2 px-3 py-2 text-left text-slate-700 hover:bg-slate-50">
                <Activity size={14} /> 日志
              </button>
              <button onClick={onOpenResult} className="flex w-full items-center gap-2 px-3 py-2 text-left text-slate-700 hover:bg-slate-50">
                <Eye size={14} /> 结果
              </button>
              <button
                onClick={onRetry}
                disabled={task.status !== "ERROR"}
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
              >
                <RefreshCw size={14} /> 重试
              </button>
              <button onClick={onDelete} className="flex w-full items-center gap-2 px-3 py-2 text-left text-red-600 hover:bg-red-50">
                <Trash2 size={14} /> 删除
              </button>
            </div>
          )}
        </div>
      </div>
    </article>
  );
}

function QueueIconAction({
  icon: Icon,
  label,
  onClick,
}: {
  icon: typeof Eye;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      aria-label={label}
      title={label}
      className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 hover:text-slate-900"
    >
      <Icon size={14} />
    </button>
  );
}

function displayQueueStage(task: TaskItem): string {
  const rawStage = task.stage || task.status;
  const normalized = rawStage.trim();
  const upper = normalized.toUpperCase();
  const lower = normalized.toLowerCase();
  const queueStageLabels: Record<string, string> = {
    completed: "已完成",
    complete: "已完成",
    failed: "失败",
    error: "失败",
    uploaded: "排队中",
    pending: "排队中",
    queued: "排队中",
    processing: "处理中",
    running: "处理中",
    extracting_frames: "抽帧中",
    scene_detecting: "场景切分",
    visual_screening: "视觉预筛",
    vlm_confirming: "片段筛选",
    transcribing: "字幕转写",
    llm_analyzing: "内容理解",
    exporting: "导出中",
    processing_clips: "片段生成",
  };

  return stageLabels[normalized] || stageLabels[upper] || queueStageLabels[lower] || statusLabel(task.status);
}

function QueueDetailDrawer({
  open,
  task,
  tab,
  onTabChange,
  events,
  resources,
  onClose,
  onRetry,
  onDelete,
  onOpenResult,
}: {
  open: boolean;
  task: TaskItem | null;
  tab: QueueDrawerTab;
  onTabChange: (tab: QueueDrawerTab) => void;
  events: { time: string; stage: string; level: string; message: string; file: string }[];
  resources?: ReturnType<typeof useSystemResources>["data"];
  onClose: () => void;
  onRetry: (task: TaskItem) => void;
  onDelete: (task: TaskItem) => void;
  onOpenResult: (task: TaskItem) => void;
}) {
  if (!open || !task) return null;

  return (
    <DrawerShell
      open={open}
      title="任务详情"
      onClose={onClose}
      closeLabel="关闭任务详情"
      footer={
        <div className="grid grid-cols-3 gap-2">
          <Button onClick={() => onOpenResult(task)} variant="primary">
            查看
          </Button>
          <Button
            onClick={() => onRetry(task)}
            disabled={task.status !== "ERROR"}
            icon={RefreshCw}
          >
            重试
          </Button>
          <Button onClick={() => onDelete(task)} variant="danger" icon={Trash2}>
            删除
          </Button>
        </div>
      }
    >
      <QueueDetailBody task={task} tab={tab} onTabChange={onTabChange} events={events} resources={resources} />
    </DrawerShell>
  );
}

function QueueDetailBody({
  task,
  tab,
  onTabChange,
  events,
  resources,
}: {
  task: TaskItem;
  tab: QueueDrawerTab;
  onTabChange: (tab: QueueDrawerTab) => void;
  events: { time: string; stage: string; level: string; message: string; file: string }[];
  resources?: ReturnType<typeof useSystemResources>["data"];
}) {
  const tabs: { value: QueueDrawerTab; label: string }[] = [
    { value: "overview", label: "概览" },
    { value: "logs", label: "日志" },
    { value: "resources", label: "资源" },
  ];
  const progress = progressByStatus(task);
  const currentStage = displayQueueStage(task);
  const currentStageIndex = queueStageSteps.findIndex((item) => item.key === currentStage);
  const activeStepIndex = currentStageIndex >= 0 ? currentStageIndex : Math.max(0, Math.min(queueStageSteps.length - 1, Math.floor(progress / 20)));
  const recentEvents = events.slice(-5);

  return (
    <>
      <div className="flex gap-4">
        <div className="relative h-24 w-36 shrink-0 overflow-hidden rounded-lg bg-slate-100">
          {task.thumbnail_url ? (
            <img src={task.thumbnail_url} alt="" className="h-full w-full object-cover" />
          ) : (
            <div className="flex h-full w-full items-center justify-center text-slate-300">
              <Film size={24} />
            </div>
          )}
          <span className="absolute bottom-2 right-2 rounded bg-slate-950/75 px-1.5 py-0.5 text-[11px] font-medium text-white">
            {formatDuration(task.video_duration_s)}
          </span>
        </div>
        <div className="min-w-0 flex-1">
          <h3 className="truncate text-base font-semibold text-slate-900">{displayTaskName(task)}</h3>
          <div className="mt-2 space-y-1 text-xs text-slate-500">
            <div>任务 ID</div>
            <div className="truncate font-medium text-slate-500">{task.task_id}</div>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <span className={cn("rounded-full px-2 py-1 text-xs font-medium ring-1", statusBadgeClass(task.status))}>
              {statusLabel(task.status)}
            </span>
            <span className="rounded-full bg-slate-100 px-2 py-1 text-xs font-medium text-slate-600">{task.clip_count ?? 0} clips</span>
            <span className="rounded-full bg-blue-50 px-2 py-1 text-xs font-medium text-blue-700">{currentStage}</span>
          </div>
        </div>
      </div>

      <DrawerTabs tabs={tabs} value={tab} onChange={onTabChange} />

      {tab === "overview" && (
        <div className="mt-5 space-y-4">
          <section>
            <div className="flex items-center justify-between text-sm">
              <span className="font-medium text-slate-700">进度</span>
              <span className="font-semibold text-slate-700">{progress}%</span>
            </div>
            <div className="mt-3 h-2 rounded-full bg-slate-100">
              <div className={cn("h-2 rounded-full", task.status === "ERROR" ? "bg-red-500" : "bg-blue-600")} style={{ width: `${progress}%` }} />
            </div>
          </section>

          <section className="grid grid-cols-3 gap-3">
            <QueueInfoCard label="开始时间" value={formatDate(task.created_at)} />
            <QueueInfoCard label="视频时长" value={formatDuration(task.video_duration_s)} />
            <QueueInfoCard label="导出片段" value={String(task.clip_count ?? 0)} />
          </section>

          <DrawerSection>
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-xs font-medium text-slate-400">当前阶段</div>
                <div className="mt-1 text-sm font-semibold text-slate-900">{currentStage}</div>
                <p className="mt-1 line-clamp-2 text-xs text-slate-500">
                  {userFacingMessage(task.message) || "任务状态正常，等待下一步处理结果。"}
                </p>
              </div>
              <span className="rounded-full bg-blue-50 px-2 py-1 text-xs font-medium text-blue-700">{Math.min(activeStepIndex + 1, queueStageSteps.length)} / {queueStageSteps.length}</span>
            </div>
            <div className="mt-4 space-y-3">
              {queueStageSteps.map((step, index) => {
                const done = progress >= 100 || index < activeStepIndex;
                const active = index === activeStepIndex && progress < 100;
                return (
                  <div key={step.key} className="flex items-center gap-3 text-sm">
                    {done ? (
                      <CheckCircle2 size={16} className="text-emerald-500" />
                    ) : active ? (
                      <span className="flex h-4 w-4 items-center justify-center rounded-full bg-blue-600">
                        <span className="h-1.5 w-1.5 rounded-full bg-white" />
                      </span>
                    ) : (
                      <Circle size={16} className="text-slate-300" />
                    )}
                    <span className={cn(done || active ? "text-slate-700" : "text-slate-400")}>{step.label}</span>
                    <span className="ml-auto text-xs text-slate-400">{done ? "完成" : active ? "进行中" : "待开始"}</span>
                  </div>
                );
              })}
            </div>
          </DrawerSection>

          <DrawerSection title="最近日志">
            <div className="mt-3 space-y-2 text-xs text-slate-600">
              {recentEvents.length > 0 ? recentEvents.map((event) => (
                <LogLine key={`${event.time}-${event.file}`} time={formatDate(event.time)} text={`${displayEventStage(event.stage)}：${event.message}`} />
              )) : (
                <p className="text-slate-400">暂无任务事件</p>
              )}
            </div>
          </DrawerSection>
        </div>
      )}

      {tab === "logs" && (
        <DrawerSection title="最近日志" className="mt-5">
          <div className="mt-3 space-y-2 font-mono text-xs text-slate-500">
            {events.length > 0 ? events.slice(-8).map((event) => (
              <LogLine key={`${event.time}-${event.file}`} time={formatDate(event.time)} text={`${displayEventStage(event.stage)}：${event.message}`} />
            )) : (
              <p className="text-slate-400">暂无任务事件</p>
            )}
          </div>
        </DrawerSection>
      )}

      {tab === "resources" && (
        <DrawerSection title="Worker 资源" className="mt-5">
          <div className="mt-4 space-y-4">
            <ResourceLine icon={Cpu} label="CPU 配额" value={resources ? `${resources.cpu_cores.toFixed(1)} cores` : "—"} tone="blue" percent={resourcePercent(resources?.cpu_cores, 16)} />
            <ResourceLine icon={HardDrive} label="内存上限" value={resources ? `${resources.memory_gb.toFixed(1)}GB` : "—"} tone="emerald" percent={resourcePercent(resources?.memory_gb, 16)} />
            <ResourceLine icon={Server} label="FFmpeg 实例" value={String(resources?.clip_workers ?? "—")} tone="amber" percent={resourcePercent(resources?.clip_workers, 4)} />
            <ResourceLine icon={Server} label="Redis 状态" value={resources?.redis ?? "—"} tone={resources?.redis === "ok" ? "emerald" : "amber"} />
          </div>
        </DrawerSection>
      )}
    </>
  );
}

const queueStageSteps = [
  { key: "上传完成", label: "视频解码" },
  { key: "场景切分", label: "场景切分" },
  { key: "内容理解", label: "内容理解" },
  { key: "片段筛选", label: "片段筛选" },
  { key: "片段生成", label: "片段评分" },
];

function ResourceSummary({ label, value }: { label: string; value: string }) {
  return (
    <span className="rounded-full bg-slate-50 px-2.5 py-1 font-medium text-slate-600 ring-1 ring-slate-200">
      {label} {value}
    </span>
  );
}

function QueueInfoCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-200 p-3">
      <div className="text-xs text-slate-400">{label}</div>
      <div className="mt-1 truncate text-sm font-semibold text-slate-900">{value}</div>
    </div>
  );
}

function displayEventStage(stage: string): string {
  const normalized = stage.trim();
  return stageLabels[normalized] || stageLabels[normalized.toUpperCase()] || normalized;
}
