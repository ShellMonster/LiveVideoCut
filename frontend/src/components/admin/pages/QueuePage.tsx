import { useNavigate } from "react-router-dom";
import { Cpu, Eye, HardDrive, RefreshCw, Server, Trash2, Upload } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAdminContext } from "@/components/AdminDashboard";
import { useTasks, useSystemResources, useTaskEvents, useDeleteTask, useRetryTask } from "@/hooks/useAdminQueries";
import { stageLabels } from "../constants";
import { classifyStatus, displayTaskName, formatDate, formatDuration, progressByStatus, resourcePercent, statusBadgeClass, statusLabel } from "../format";
import { Header, IconButton, LogLine, MetricCard, ResourceLine } from "../shared";

export function QueuePage() {
  const navigate = useNavigate();
  const { selectedTask, setSelectedTask } = useAdminContext();
  const { data: tasks = [] } = useTasks();
  const { data: resources } = useSystemResources();
  const { data: events = [] } = useTaskEvents(selectedTask?.task_id);
  const deleteTask = useDeleteTask();
  const retryTask = useRetryTask();

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
            onClick={() => navigate("/create")}
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
          <MetricCard label="Redis" value={resources?.redis === "ok" ? "正常" : resources?.redis ? "异常" : "—"} hint={resources?.redis ?? "队列连接状态"} />
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
                    onClick={() => setSelectedTask(task)}
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
                      {resources ? `${resources.clip_workers} workers` : "等待资源"}
                    </div>
                    <div className="text-xs text-slate-500">{formatDuration(task.video_duration_s)}</div>
                    <div className="flex justify-end gap-1">
                      <IconButton icon={Eye} label="查看" />
                      <IconButton
                        icon={RefreshCw}
                        label="重试"
                        onClick={(event) => {
                          event.stopPropagation();
                          void retryTask.mutateAsync(task.task_id);
                        }}
                        disabled={task.status !== "ERROR"}
                      />
                      <IconButton
                        icon={Trash2}
                        label="删除"
                        danger
                        onClick={(event) => {
                          event.stopPropagation();
                          void deleteTask.mutateAsync(task.task_id).catch(() => {});
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
                <ResourceLine icon={Cpu} label="CPU 配额" value={resources ? `${resources.cpu_cores.toFixed(1)} cores` : "—"} tone="blue" percent={resourcePercent(resources?.cpu_cores, 16)} />
                <ResourceLine icon={HardDrive} label="内存上限" value={resources ? `${resources.memory_gb.toFixed(1)}GB` : "—"} tone="emerald" percent={resourcePercent(resources?.memory_gb, 16)} />
                <ResourceLine icon={Server} label="FFmpeg 实例" value={String(resources?.clip_workers ?? "—")} tone="amber" percent={resourcePercent(resources?.clip_workers, 4)} />
                <ResourceLine icon={Server} label="Redis 状态" value={resources?.redis ?? "—"} tone={resources?.redis === "ok" ? "emerald" : "amber"} />
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
