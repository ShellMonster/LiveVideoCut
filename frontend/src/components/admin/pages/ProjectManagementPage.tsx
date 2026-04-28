import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Activity, FileVideo, Film, Plus, Scissors, Search, SlidersHorizontal, Trash2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { ProgressBar } from "@/components/ProgressBar";
import { useAdminContext } from "@/components/admin/context";
import { useTaskList, useTaskSummary, useTaskDiagnostics, useDeleteTask } from "@/hooks/useAdminQueries";
import { useConfirmStore } from "@/stores/confirmStore";
import {
  EmptyPreview,
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
  progressByStatus,
  statusBadgeClass,
  statusLabel,
} from "../format";

export function ProjectManagementPage() {
  const navigate = useNavigate();
  const { selectedTask, setSelectedTask } = useAdminContext();
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [page, setPage] = useState(1);
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

        <section className="grid gap-5 min-[1700px]:grid-cols-[minmax(0,1fr)_360px]">
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
                    onClick={() => setSelectedTask(task)}
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
                    <div className="grid grid-cols-4 gap-2">
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
                          handleDeleteTask(task.task_id);
                        }}
                        className="inline-flex min-w-0 items-center justify-center gap-1.5 rounded-lg border border-red-100 px-2 py-1.5 text-xs font-medium text-red-500 hover:bg-red-50"
                      >
                        <Trash2 size={14} />
                        删除
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
                        onClick={() => setSelectedTask(task)}
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
                        <td className="px-4 py-3">
                          <div className="flex justify-end gap-1.5 whitespace-nowrap">
                            <button
                              onClick={(event) => {
                                event.stopPropagation();
                                openReview(task);
                              }}
                              className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
                            >
                              <Scissors size={14} />
                              复核
                            </button>
                            <button
                              onClick={(event) => {
                                event.stopPropagation();
                                openAssets(task);
                              }}
                              className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
                            >
                              <FileVideo size={14} />
                              资产
                            </button>
                            <button
                              onClick={(event) => {
                                event.stopPropagation();
                                openDiagnostics(task);
                              }}
                              className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
                            >
                              <Activity size={14} />
                              诊断
                            </button>
                            <button
                              onClick={(event) => {
                                event.stopPropagation();
                                handleDeleteTask(task.task_id);
                              }}
                              className="shrink-0 rounded-lg p-1.5 text-slate-300 hover:bg-red-50 hover:text-red-500"
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
            <Pagination
              page={page}
              pageSize={pageSize}
              total={totalTasks}
              onPageChange={setPage}
            />
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
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-3 min-[1700px]:grid-cols-1 min-[1900px]:grid-cols-3">
                  <button
                    onClick={() => openReview(selectedTask)}
                    className="inline-flex min-w-0 items-center justify-center gap-2 rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
                  >
                    <Scissors size={15} />
                    复核
                  </button>
                  <button
                    onClick={() => openAssets(selectedTask)}
                    className="inline-flex min-w-0 items-center justify-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
                  >
                    <FileVideo size={15} />
                    资产
                  </button>
                  <button
                    onClick={() => openDiagnostics(selectedTask)}
                    className="inline-flex min-w-0 items-center justify-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
                  >
                    <Activity size={15} />
                    诊断
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
