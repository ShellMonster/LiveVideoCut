import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Eye, Film, Plus, Search, SlidersHorizontal, Trash2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { ProgressBar } from "@/components/ProgressBar";
import { useAdminContext } from "@/components/AdminDashboard";
import { useTasks, useTaskSummary, useTaskDiagnostics, useDeleteTask } from "@/hooks/useAdminQueries";
import {
  EmptyPreview,
  Header,
  LogLine,
  MetricCard,
  MetricPill,
} from "../shared";
import {
  classifyStatus,
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
  const { data: tasks = [], isLoading: loading } = useTasks();
  const { data: summary } = useTaskSummary(selectedTask?.task_id);
  const { data: diagnostics } = useTaskDiagnostics(selectedTask?.task_id);
  const deleteTask = useDeleteTask();

  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const completedCount = tasks.filter((task) => task.status === "COMPLETED").length;
  const processingCount = tasks.filter((task) => classifyStatus(task.status) === "processing").length;
  const failedCount = tasks.filter((task) => task.status === "ERROR").length;
  const clipCount = tasks.reduce((sum, task) => sum + (task.clip_count || 0), 0);
  const normalizedQuery = query.trim().toLowerCase();
  const filteredTasks = tasks.filter((task) => {
    const matchesQuery =
      !normalizedQuery ||
      [displayTaskName(task), task.original_filename, task.task_id]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(normalizedQuery));
    const matchesStatus =
      statusFilter === "all" ||
      (statusFilter === "processing" && classifyStatus(task.status) === "processing") ||
      task.status === statusFilter;
    return matchesQuery && matchesStatus;
  });

  const handleDeleteTask = (taskId: string) => {
    void deleteTask.mutateAsync(taskId).catch(() => {});
  };

  return (
    <>
      <Header
        title="直播剪辑项目"
        description="管理直播剪辑项目、处理状态和导出结果"
        action={
          <button
            onClick={() => navigate("/create")}
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
              <label className="flex min-w-0 flex-1 items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-500">
                <Search size={16} />
                <input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="搜索项目 / 文件名 / 任务 ID"
                  className="min-w-0 flex-1 bg-transparent text-slate-700 outline-none placeholder:text-slate-400"
                />
              </label>
              <select
                value={statusFilter}
                onChange={(event) => setStatusFilter(event.target.value)}
                className="ml-3 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-600"
              >
                <option value="all">全部状态</option>
                <option value="processing">处理中</option>
                <option value="COMPLETED">已完成</option>
                <option value="ERROR">失败</option>
                <option value="UPLOADED">已上传</option>
              </select>
              <button onClick={() => { setQuery(""); setStatusFilter("all"); }} className="ml-2 inline-flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50">
                <SlidersHorizontal size={16} />
                重置
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
                  ) : filteredTasks.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="px-4 py-12 text-center text-slate-400">
                        没有匹配的项目。
                      </td>
                    </tr>
                  ) : (
                    filteredTasks.map((task) => (
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
                        <td className="px-4 py-3 text-slate-600">{displayAsrProvider(task.asr_provider)}</td>
                        <td className="px-4 py-3 text-slate-500">{formatDate(task.created_at)}</td>
                        <td className="px-4 py-3">
                          <div className="flex justify-end gap-1">
                            <button className="rounded p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700" aria-label="查看">
                              <Eye size={15} />
                            </button>
                            <button
                              onClick={(event) => {
                                event.stopPropagation();
                                handleDeleteTask(task.task_id);
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
                    onClick={() => navigate("/review")}
                    className="flex-1 rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
                  >
                    进入复核
                  </button>
                  <button
                    onClick={() => navigate("/assets", { state: { projectId: selectedTask?.task_id } })}
                    className="flex-1 rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
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
