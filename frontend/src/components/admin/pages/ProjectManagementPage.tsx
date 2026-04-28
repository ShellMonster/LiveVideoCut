import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Activity, FileVideo, Film, MoreHorizontal, Plus, Scissors, Search, SlidersHorizontal, Trash2, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { ProgressBar } from "@/components/ProgressBar";
import { useAdminContext } from "@/components/admin/context";
import { useTaskList, useTaskSummary, useTaskDiagnostics, useDeleteTask, useTaskClips } from "@/hooks/useAdminQueries";
import { useConfirmStore } from "@/stores/confirmStore";
import {
  Header,
  LogLine,
  MetricCard,
  MetricPill,
  Pagination,
} from "../shared";
import {
  displayAsrProvider,
  displayTaskName,
  formatDate,
  formatDuration,
  progressByStatus,
  statusBadgeClass,
  statusLabel,
} from "../format";
import type { TaskItem } from "../types";

type DrawerTab = "overview" | "clips" | "logs";

export function ProjectManagementPage() {
  const navigate = useNavigate();
  const { selectedTask, setSelectedTask } = useAdminContext();
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [page, setPage] = useState(1);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerTab, setDrawerTab] = useState<DrawerTab>("overview");
  const [menuTaskId, setMenuTaskId] = useState<string | null>(null);
  const pageSize = 10;
  const { data: taskList, isLoading: loading } = useTaskList({
    page,
    pageSize,
    status: statusFilter,
    query,
  });
  const tasks = taskList?.items ?? [];
  const totalTasks = taskList?.total ?? 0;
  const taskSummary = taskList?.summary;
  const { data: summary } = useTaskSummary(selectedTask?.task_id);
  const { data: diagnostics } = useTaskDiagnostics(selectedTask?.task_id);
  const { data: clips = [] } = useTaskClips(selectedTask?.task_id, drawerOpen && selectedTask?.status === "COMPLETED");
  const deleteTask = useDeleteTask();
  const confirm = useConfirmStore((state) => state.confirm);

  const completedCount = taskSummary?.completed ?? 0;
  const processingCount = taskSummary?.processing ?? 0;
  const failedCount = taskSummary?.failed ?? 0;
  const uploadedCount = taskSummary?.uploaded ?? 0;
  const clipCount = taskSummary?.clip_count ?? 0;
  const statusOptions = [
    { value: "all", label: "全部", count: taskSummary?.total ?? totalTasks },
    { value: "processing", label: "处理中", count: processingCount },
    { value: "COMPLETED", label: "已完成", count: completedCount },
    { value: "ERROR", label: "失败", count: failedCount },
    { value: "UPLOADED", label: "已上传", count: uploadedCount },
  ];

  const handleDeleteTask = async (taskId: string) => {
    const confirmed = await confirm({
      title: "删除任务",
      description: "删除后会移除这个任务及相关产物，操作无法恢复。",
      confirmLabel: "删除",
      danger: true,
    });
    if (!confirmed) return;
    await deleteTask.mutateAsync(taskId).then(() => {
      if (selectedTask?.task_id === taskId) {
        setSelectedTask(null);
      }
    }).catch(() => {});
  };

  const openDetails = (task: TaskItem) => {
    setSelectedTask(task);
    setDrawerTab("overview");
    setDrawerOpen(true);
    setMenuTaskId(null);
  };

  const openReview = (task: typeof tasks[number]) => {
    setSelectedTask(task);
    navigate("/review");
  };

  const openAssets = (task: typeof tasks[number]) => {
    setSelectedTask(task);
    navigate("/assets", { state: { projectId: task.task_id } });
  };

  const openDiagnostics = (task: typeof tasks[number]) => {
    setSelectedTask(task);
    navigate("/diagnostics");
  };

  return (
    <>
      <Header
        title="直播剪辑项目"
        description="管理直播剪辑项目、处理状态和导出结果"
        action={
          <button
            onClick={() => navigate("/create")}
            className="inline-flex shrink-0 items-center justify-center gap-2 rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            <Plus size={16} />
            新建项目
          </button>
        }
      />
      <main className="space-y-5 p-4 sm:p-6">
        <section className="grid gap-4 lg:grid-cols-4">
          <MetricCard label="处理中项目" value={String(processingCount)} hint="实时任务队列" />
          <MetricCard label="已完成" value={String(completedCount)} hint="按本地任务记录统计" />
          <MetricCard label="失败任务" value={String(failedCount)} hint="需要检查诊断日志" />
          <MetricCard label="导出片段" value={String(clipCount)} hint="累计可下载短视频" />
        </section>

        <section className="grid gap-5">
          <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
            <div className="border-b border-slate-100 px-4 py-3">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="text-sm font-semibold text-slate-950">项目切换中心</h2>
                  <p className="mt-1 text-xs text-slate-500">选择项目后，可直接进入复核、资产或诊断。</p>
                </div>
                <button
                  onClick={() => {
                    setQuery("");
                    setStatusFilter("all");
                    setPage(1);
                  }}
                  className="inline-flex shrink-0 items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50"
                >
                  <SlidersHorizontal size={16} />
                  重置筛选
                </button>
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                {statusOptions.map((option) => (
                  <button
                    key={option.value}
                    onClick={() => {
                      setStatusFilter(option.value);
                      setPage(1);
                    }}
                    className={cn(
                      "inline-flex items-center gap-2 rounded-full px-3 py-1.5 text-xs font-medium ring-1",
                      statusFilter === option.value
                        ? "bg-blue-50 text-blue-700 ring-blue-100"
                        : "bg-white text-slate-600 ring-slate-200 hover:bg-slate-50",
                    )}
                  >
                    {option.label}
                    <span className={cn("rounded-full px-1.5 py-0.5", statusFilter === option.value ? "bg-blue-100" : "bg-slate-100")}>
                      {option.count}
                    </span>
                  </button>
                ))}
              </div>
              <label className="mt-4 flex min-w-0 items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-500">
                <Search size={16} />
                <input
                  value={query}
                  onChange={(event) => {
                    setQuery(event.target.value);
                    setPage(1);
                  }}
                  placeholder="搜索项目 / 文件名 / 任务 ID"
                  className="min-w-0 flex-1 bg-transparent text-slate-700 outline-none placeholder:text-slate-400"
                />
              </label>
            </div>
            <div className="divide-y divide-slate-100 md:hidden">
              {loading ? (
                <div className="px-4 py-12 text-center text-sm text-slate-400">
                  加载项目中...
                </div>
              ) : tasks.length === 0 ? (
                <div className="px-4 py-12 text-center text-sm text-slate-400">
                  没有匹配的项目。
                </div>
              ) : (
                tasks.map((task) => (
                  <article
                    key={task.task_id}
                    onClick={() => openDetails(task)}
                    className={cn(
                      "space-y-3 p-4",
                      selectedTask?.task_id === task.task_id && "bg-blue-50/50",
                    )}
                  >
                    <div className="flex gap-3">
                      <div className="h-14 w-24 shrink-0 overflow-hidden rounded-md bg-slate-100">
                        {task.thumbnail_url ? (
                          <img src={task.thumbnail_url} alt="" className="h-full w-full object-cover" />
                        ) : (
                          <div className="flex h-full w-full items-center justify-center text-slate-300">
                            <Film size={20} />
                          </div>
                        )}
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="truncate font-medium text-slate-900">{displayTaskName(task)}</div>
                        <div className="mt-0.5 truncate text-xs text-slate-400">{task.original_filename || task.task_id}</div>
                        <div className="mt-2 flex flex-wrap items-center gap-2">
                          <span className={cn("whitespace-nowrap rounded-full px-2 py-1 text-xs font-medium ring-1", statusBadgeClass(task.status))}>
                            {statusLabel(task.status)}
                          </span>
                          <span className="text-xs text-slate-500">{task.clip_count || 0} 个片段</span>
                          <span className="text-xs text-slate-400">{formatDate(task.created_at)}</span>
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="h-1.5 flex-1 rounded-full bg-slate-100">
                        <div
                          className={cn(
                            "h-1.5 rounded-full",
                            task.status === "ERROR" ? "bg-red-500" : "bg-blue-500",
                          )}
                          style={{ width: `${progressByStatus(task)}%` }}
                        />
                      </div>
                      <span className="w-10 shrink-0 text-right text-xs text-slate-400">{progressByStatus(task)}%</span>
                    </div>
                    <div className="grid grid-cols-5 gap-2">
                      <button
                        onClick={(event) => {
                          event.stopPropagation();
                          openDetails(task);
                        }}
                        className="inline-flex min-w-0 items-center justify-center gap-1.5 rounded-lg border border-blue-100 bg-blue-50 px-2 py-1.5 text-xs font-medium text-blue-700 hover:bg-blue-100"
                      >
                        详情
                      </button>
                      <button
                        onClick={(event) => {
                          event.stopPropagation();
                          openReview(task);
                        }}
                        className="inline-flex min-w-0 items-center justify-center gap-1.5 rounded-lg border border-slate-200 px-2 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
                      >
                        <Scissors size={14} />
                        复核
                      </button>
                      <button
                        onClick={(event) => {
                          event.stopPropagation();
                          openAssets(task);
                        }}
                        className="inline-flex min-w-0 items-center justify-center gap-1.5 rounded-lg border border-slate-200 px-2 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
                      >
                        <FileVideo size={14} />
                        资产
                      </button>
                      <button
                        onClick={(event) => {
                          event.stopPropagation();
                          openDiagnostics(task);
                        }}
                        className="inline-flex min-w-0 items-center justify-center gap-1.5 rounded-lg border border-slate-200 px-2 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
                      >
                        <Activity size={14} />
                        诊断
                      </button>
                      <button
                        onClick={(event) => {
                          event.stopPropagation();
                          void handleDeleteTask(task.task_id);
                        }}
                        className="inline-flex min-w-0 items-center justify-center rounded-lg border border-slate-200 px-2 py-1.5 text-slate-600 hover:bg-slate-50"
                        aria-label="更多"
                      >
                        <MoreHorizontal size={14} />
                      </button>
                    </div>
                  </article>
                ))
              )}
            </div>
            <div className="hidden overflow-x-auto md:block">
              <table className="w-full min-w-[1040px] text-left text-sm">
                <thead className="bg-slate-50 text-xs font-medium text-slate-500">
                  <tr>
                    <th className="px-4 py-3">项目名称</th>
                    <th className="px-4 py-3">状态</th>
                    <th className="px-4 py-3">进度</th>
                    <th className="px-4 py-3 whitespace-nowrap">片段数</th>
                    <th className="px-4 py-3 whitespace-nowrap">ASR</th>
                    <th className="px-4 py-3 whitespace-nowrap">创建时间</th>
                    <th className="px-4 py-3 text-right">快捷入口</th>
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
                        没有匹配的项目。
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
                        onClick={() => openDetails(task)}
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
                          <span className={cn("whitespace-nowrap rounded-full px-2 py-1 text-xs font-medium ring-1", statusBadgeClass(task.status))}>
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
                        <td className="px-4 py-3 whitespace-nowrap text-slate-600">{task.clip_count || 0}</td>
                        <td className="px-4 py-3 whitespace-nowrap text-slate-600">{displayAsrProvider(task.asr_provider)}</td>
                        <td className="px-4 py-3 whitespace-nowrap text-slate-500">{formatDate(task.created_at)}</td>
                        <td className="relative px-4 py-3">
                          <div className="flex justify-end gap-1.5 whitespace-nowrap">
                            <button
                              onClick={(event) => {
                                event.stopPropagation();
                                openDetails(task);
                              }}
                              className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-blue-100 bg-blue-50 px-2.5 py-1.5 text-xs font-medium text-blue-700 hover:bg-blue-100"
                            >
                              详情
                            </button>
                            <button
                              onClick={(event) => {
                                event.stopPropagation();
                                openReview(task);
                              }}
                              className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-slate-200 px-2 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
                              aria-label="复核"
                            >
                              <Scissors size={14} />
                              复核
                            </button>
                            <button
                              onClick={(event) => {
                                event.stopPropagation();
                                openAssets(task);
                              }}
                              className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-slate-200 px-2 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
                              aria-label="资产"
                            >
                              <FileVideo size={14} />
                              资产
                            </button>
                            <button
                              onClick={(event) => {
                                event.stopPropagation();
                                openDiagnostics(task);
                              }}
                              className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-slate-200 px-2 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
                              aria-label="诊断"
                            >
                              <Activity size={14} />
                              诊断
                            </button>
                            <button
                              onClick={(event) => {
                                event.stopPropagation();
                                setMenuTaskId(menuTaskId === task.task_id ? null : task.task_id);
                              }}
                              className="shrink-0 rounded-lg border border-slate-200 p-1.5 text-slate-500 hover:bg-slate-50 hover:text-slate-700"
                              aria-label="更多"
                            >
                              <MoreHorizontal size={15} />
                            </button>
                          </div>
                          {menuTaskId === task.task_id && (
                            <div className="absolute right-4 top-10 z-20 w-32 rounded-lg border border-slate-200 bg-white p-1 shadow-lg">
                              <button
                                onClick={(event) => {
                                  event.stopPropagation();
                                  setMenuTaskId(null);
                                  void handleDeleteTask(task.task_id);
                                }}
                                className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-xs font-medium text-red-600 hover:bg-red-50"
                              >
                                <Trash2 size={14} />
                                删除项目
                              </button>
                            </div>
                          )}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
            <Pagination
              page={page}
              pageSize={pageSize}
              total={totalTasks}
              onPageChange={setPage}
            />
          </div>
        </section>
      </main>
      <ProjectDetailDrawer
        open={drawerOpen}
        task={selectedTask}
        tab={drawerTab}
        onTabChange={setDrawerTab}
        summary={summary}
        diagnostics={diagnostics}
        clips={clips}
        onClose={() => setDrawerOpen(false)}
        onReview={openReview}
        onAssets={openAssets}
        onDiagnostics={openDiagnostics}
        onDelete={(taskId) => void handleDeleteTask(taskId)}
      />
    </>
  );
}

function ProjectDetailDrawer({
  open,
  task,
  tab,
  onTabChange,
  summary,
  diagnostics,
  clips,
  onClose,
  onReview,
  onAssets,
  onDiagnostics,
  onDelete,
}: {
  open: boolean;
  task: TaskItem | null;
  tab: DrawerTab;
  onTabChange: (tab: DrawerTab) => void;
  summary?: ReturnType<typeof useTaskSummary>["data"];
  diagnostics?: ReturnType<typeof useTaskDiagnostics>["data"];
  clips: ReturnType<typeof useTaskClips>["data"];
  onClose: () => void;
  onReview: (task: TaskItem) => void;
  onAssets: (task: TaskItem) => void;
  onDiagnostics: (task: TaskItem) => void;
  onDelete: (taskId: string) => void;
}) {
  if (!open || !task) return null;

  const events = diagnostics?.event_log ?? [];
  const pipeline = diagnostics?.pipeline ?? [];
  const previewClips = clips?.slice(0, 4) ?? [];
  const tabs: { value: DrawerTab; label: string }[] = [
    { value: "overview", label: "概览" },
    { value: "clips", label: "片段" },
    { value: "logs", label: "日志" },
  ];

  return (
    <div className="fixed inset-0 z-40">
      <button className="absolute inset-0 bg-slate-950/20" onClick={onClose} aria-label="关闭项目详情" />
      <aside className="absolute right-0 top-0 flex h-full w-full max-w-[440px] flex-col border-l border-slate-200 bg-white shadow-2xl">
        <div className="flex h-16 items-center justify-between border-b border-slate-200 px-5">
          <h2 className="text-base font-semibold text-slate-950">项目详情</h2>
          <button onClick={onClose} className="rounded-lg p-2 text-slate-400 hover:bg-slate-50 hover:text-slate-700" aria-label="关闭">
            <X size={18} />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-5">
          <div className="flex gap-3">
            <div className="h-16 w-24 shrink-0 overflow-hidden rounded-lg bg-slate-100">
              {task.thumbnail_url ? (
                <img src={task.thumbnail_url} alt="" className="h-full w-full object-cover" />
              ) : (
                <div className="flex h-full w-full items-center justify-center text-slate-300">
                  <Film size={24} />
                </div>
              )}
            </div>
            <div className="min-w-0 flex-1">
              <h3 className="truncate text-sm font-semibold text-slate-950">{displayTaskName(task)}</h3>
              <div className="mt-1">
                <span className={cn("rounded-full px-2 py-1 text-xs font-medium ring-1", statusBadgeClass(task.status))}>
                  {statusLabel(task.status)}
                </span>
              </div>
              <p className="mt-2 truncate text-xs text-slate-400">任务 ID：{task.task_id}</p>
            </div>
          </div>

          <div className="mt-5 flex border-b border-slate-200">
            {tabs.map((item) => (
              <button
                key={item.value}
                onClick={() => onTabChange(item.value)}
                className={cn(
                  "mr-6 border-b-2 px-1 pb-2 text-sm font-medium",
                  tab === item.value
                    ? "border-blue-600 text-blue-700"
                    : "border-transparent text-slate-500 hover:text-slate-800",
                )}
              >
                {item.label}
              </button>
            ))}
          </div>

          {tab === "overview" && (
            <div className="mt-5 space-y-4">
              <section className="rounded-lg border border-slate-200 p-4">
                <h4 className="text-sm font-semibold text-slate-900">基础信息</h4>
                <div className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
                  <InfoItem label="片段数" value={String(summary?.clips_count ?? task.clip_count ?? 0)} />
                  <InfoItem label="总时长" value={formatDuration(task.video_duration_s)} />
                  <InfoItem label="ASR" value={displayAsrProvider(task.asr_provider)} />
                  <InfoItem label="创建时间" value={formatDate(task.created_at)} />
                  <InfoItem label="候选数" value={String(summary?.candidates_count ?? "—")} />
                  <InfoItem label="未导出" value={String(summary?.empty_screen_dropped_estimate ?? "—")} />
                </div>
              </section>

              <section className="rounded-lg border border-slate-200 p-4">
                <h4 className="text-sm font-semibold text-slate-900">处理进度</h4>
                <div className="mt-4">
                  <ProgressBar currentState={task.status} errorMessage={task.message || undefined} />
                </div>
                <div className="mt-4 grid grid-cols-5 gap-2 text-center text-[11px] text-slate-500">
                  {["视频接入", "语音识别", "片段切分", "质量检测", "导出完成"].map((label, index) => (
                    <div key={label}>
                      <div className={cn("mx-auto mb-1 h-2.5 w-2.5 rounded-full", progressByStatus(task) >= (index + 1) * 20 ? "bg-emerald-500" : "bg-slate-200")} />
                      {label}
                    </div>
                  ))}
                </div>
              </section>

              <section className="rounded-lg border border-slate-200 p-4">
                <h4 className="text-sm font-semibold text-slate-900">推荐下一步操作</h4>
                <div className="mt-3 space-y-2">
                  <DrawerAction title="进入复核" hint="人工复核片段质量、标题和封面" onClick={() => onReview(task)} />
                  <DrawerAction title="查看片段资产" hint="浏览导出片段，下载或分享" onClick={() => onAssets(task)} />
                  <DrawerAction title="诊断报告" hint="查看处理详情与系统诊断" onClick={() => onDiagnostics(task)} />
                </div>
              </section>

              <section className="rounded-lg border border-slate-200 p-4">
                <div className="flex items-center justify-between">
                  <h4 className="text-sm font-semibold text-slate-900">诊断摘要</h4>
                  <button onClick={() => onDiagnostics(task)} className="text-xs font-medium text-blue-600 hover:text-blue-700">查看完整诊断日志</button>
                </div>
                <div className="mt-3 grid grid-cols-3 gap-2">
                  <MetricPill label="确认" value={String(summary?.confirmed_count ?? "—")} />
                  <MetricPill label="导出" value={String(summary?.clips_count ?? task.clip_count ?? 0)} />
                  <MetricPill label="警告" value={String(diagnostics?.warnings.length ?? 0)} />
                </div>
              </section>
            </div>
          )}

          {tab === "clips" && (
            <div className="mt-5 space-y-3">
              {previewClips.length > 0 ? previewClips.map((clip) => (
                <div key={clip.clip_id} className="flex gap-3 rounded-lg border border-slate-200 p-3">
                  <div className="h-14 w-24 shrink-0 overflow-hidden rounded-md bg-slate-100">
                    {clip.has_thumbnail ? (
                      <img src={clip.thumbnail_url} alt="" className="h-full w-full object-cover" />
                    ) : (
                      <div className="flex h-full w-full items-center justify-center text-slate-300">
                        <Film size={18} />
                      </div>
                    )}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-medium text-slate-900">{clip.product_name || "未命名片段"}</div>
                    <div className="mt-1 text-xs text-slate-400">{formatDuration(clip.duration)}</div>
                  </div>
                </div>
              )) : (
                <p className="rounded-lg border border-dashed border-slate-200 py-8 text-center text-sm text-slate-400">暂无可预览片段</p>
              )}
              <button onClick={() => onAssets(task)} className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">
                打开片段资产页
              </button>
            </div>
          )}

          {tab === "logs" && (
            <div className="mt-5 space-y-4">
              <section className="rounded-lg border border-slate-200 p-4">
                <h4 className="text-sm font-semibold text-slate-900">流水线阶段</h4>
                <div className="mt-3 space-y-2">
                  {pipeline.length > 0 ? pipeline.map((item) => (
                    <div key={item.stage} className="flex items-center justify-between rounded-md bg-slate-50 px-3 py-2 text-xs">
                      <span className="font-medium text-slate-700">{item.stage}</span>
                      <span className="text-slate-400">{item.status}</span>
                    </div>
                  )) : (
                    <p className="text-sm text-slate-400">暂无流水线数据</p>
                  )}
                </div>
              </section>
              <section className="rounded-lg border border-slate-200 p-4">
                <h4 className="text-sm font-semibold text-slate-900">最近事件</h4>
                <div className="mt-3 space-y-2 text-xs text-slate-500">
                  {events.length > 0 ? events.slice(-6).map((event) => (
                    <LogLine
                      key={`${event.time}-${event.file}`}
                      time={formatDate(event.time)}
                      text={`${event.stage}：${event.message}`}
                    />
                  )) : (
                    <p className="text-sm text-slate-400">暂无诊断事件</p>
                  )}
                </div>
              </section>
            </div>
          )}
        </div>
        <div className="border-t border-slate-200 p-5">
          <button
            onClick={() => onDelete(task.task_id)}
            className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-red-200 px-3 py-2 text-sm font-medium text-red-600 hover:bg-red-50"
          >
            <Trash2 size={15} />
            删除项目
          </button>
        </div>
      </aside>
    </div>
  );
}

function InfoItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="border-b border-slate-100 pb-2">
      <div className="text-xs text-slate-400">{label}</div>
      <div className="mt-1 font-medium text-slate-900">{value}</div>
    </div>
  );
}

function DrawerAction({ title, hint, onClick }: { title: string; hint: string; onClick: () => void }) {
  return (
    <button onClick={onClick} className="flex w-full items-center justify-between rounded-lg border border-slate-200 px-3 py-2 text-left hover:bg-slate-50">
      <span>
        <span className="block text-sm font-medium text-slate-900">{title}</span>
        <span className="mt-0.5 block text-xs text-slate-400">{hint}</span>
      </span>
      <span className="text-xs font-medium text-blue-600">进入</span>
    </button>
  );
}
