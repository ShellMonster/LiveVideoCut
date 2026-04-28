import { Download, FileVideo } from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/utils";
import { useAdminContext } from "@/components/admin/context";
import { useTaskDiagnostics, useTasks } from "@/hooks/useAdminQueries";
import { API_BASE } from "../api";
import { stageLabels } from "../constants";
import { displayTaskName, formatDate, formatElapsed } from "../format";
import { Header, MetricCard, Pagination, Warning } from "../shared";
import type { DiagnosticReport } from "../types";

type DiagnosticEvent = DiagnosticReport["event_log"][number];

export function DiagnosticsPage() {
  const { selectedTask, setSelectedTask } = useAdminContext();
  const { data: tasks = [] } = useTasks();
  const { data: diagnostics } = useTaskDiagnostics(selectedTask?.task_id);

  const summary = diagnostics?.summary;
  const funnel = diagnostics?.funnel ?? [];
  const eventLog = diagnostics?.event_log ?? [];
  const [eventPage, setEventPage] = useState(1);
  const [selectedEvent, setSelectedEvent] = useState<DiagnosticEvent | null>(null);
  const eventPageSize = 10;
  const visibleEvents = eventLog.slice((eventPage - 1) * eventPageSize, eventPage * eventPageSize);
  const maxFunnel = Math.max(...funnel.map((item) => item.count), 1);
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
      <main className="space-y-5 p-4 sm:p-6">
        <section className="rounded-lg border border-slate-200 bg-white p-4">
          <label className="flex flex-wrap items-center gap-3 text-sm text-slate-600">
            <span className="font-medium text-slate-900">当前项目</span>
            <select
              className="min-w-80 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700"
              value={selectedTask?.task_id || ""}
              onChange={(event) => {
                const next = tasks.find((task) => task.task_id === event.target.value);
                if (next) {
                  setSelectedTask(next);
                  setEventPage(1);
                  setSelectedEvent(null);
                }
              }}
            >
              <option value="">选择项目</option>
              {tasks.map((task) => (
                <option key={task.task_id} value={task.task_id}>
                  {displayTaskName(task)}
                </option>
              ))}
            </select>
            {!taskId && <span className="text-xs text-slate-400">选择一个任务后查看耗时、漏斗、事件和诊断包。</span>}
          </label>
        </section>

        <section className="grid gap-4 lg:grid-cols-5">
          <MetricCard label="总耗时" value={taskId ? formatElapsed(diagnostics?.total_elapsed_s) : "—"} hint="按产物生成时间推导" />
          <MetricCard label="候选片段" value={taskId ? String(summary?.candidates_count ?? 0) : "—"} hint="视觉预筛输出" />
          <MetricCard label="VLM确认" value={taskId ? String(summary?.confirmed_count ?? 0) : "—"} hint="智能模式复核" />
          <MetricCard label="最终导出" value={taskId ? String(summary?.clips_count ?? selectedTask?.clip_count ?? 0) : "—"} hint="clips 目录统计" />
          <MetricCard label="未导出" value={taskId ? String(summary?.empty_screen_dropped_estimate ?? 0) : "—"} hint="空镜/时长/导出过滤" />
        </section>

        <section className="rounded-lg border border-slate-200 bg-white p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-sm font-semibold text-slate-900">流水线耗时</h2>
            <span className="text-xs text-slate-400">{diagnostics?.pipeline.length ?? 0} 个阶段</span>
          </div>
          <div className="mt-5 grid gap-3 md:grid-cols-4 2xl:grid-cols-7">
            {(diagnostics?.pipeline ?? []).map((item) => (
              <div key={item.stage} className="relative rounded-lg bg-slate-50 p-3">
                <div className="flex items-center gap-2">
                  <span className={cn("h-2.5 w-2.5 rounded-full", item.status === "done" ? "bg-emerald-500" : item.status === "skipped" ? "bg-slate-300" : "bg-amber-500")} />
                  <span className="truncate text-xs font-medium text-slate-700">{stageLabels[item.stage] || item.stage}</span>
                </div>
                <div className="mt-2 truncate text-xs font-mono text-slate-500">{item.artifact}</div>
                <div className="mt-2 text-xs font-medium text-slate-600">{formatElapsed(item.duration_s)}</div>
              </div>
            ))}
            {!diagnostics?.pipeline.length && (
              <p className="col-span-full py-6 text-center text-sm text-slate-400">选择项目后查看流水线诊断</p>
            )}
          </div>
        </section>

        <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
          <div className="space-y-5">
            <div className="rounded-lg border border-slate-200 bg-white p-4">
              <h2 className="text-sm font-semibold text-slate-900">片段漏斗</h2>
              <div className="mt-4 grid gap-5 lg:grid-cols-[360px_minmax(0,1fr)]">
                <div className="flex h-56 items-center justify-center">
                  <div className="flex h-full w-full max-w-sm flex-col items-center justify-center gap-1">
                    {funnel.length > 0 ? funnel.map((item, index) => (
                      <div
                        key={item.label}
                        className={cn("h-9 rounded-sm", index < 2 ? "bg-blue-500" : index === 2 ? "bg-sky-400" : "bg-emerald-500")}
                        style={{ width: `${Math.max(26, 92 - index * 16)}%`, opacity: 0.9 }}
                      />
                    )) : (
                      <p className="text-sm text-slate-400">选择项目后查看片段漏斗</p>
                    )}
                  </div>
                </div>
                <div className="space-y-3">
                  {funnel.length > 0 ? funnel.map((item) => (
                    <div key={item.label} className="grid grid-cols-[100px_minmax(0,1fr)_64px] items-center gap-3 text-sm">
                      <span className="truncate text-slate-600">{item.label}</span>
                      <div className="h-2 rounded-full bg-slate-100">
                        <div className="h-2 rounded-full bg-blue-500" style={{ width: `${Math.round((item.count / maxFunnel) * 100)}%` }} />
                      </div>
                      <span className="text-right font-medium text-slate-900">{item.count}</span>
                    </div>
                  )) : (
                    <p className="py-6 text-center text-sm text-slate-400">选择项目后查看片段漏斗</p>
                  )}
                </div>
              </div>
            </div>

            <EventLogTable
              eventLog={eventLog}
              visibleEvents={visibleEvents}
              eventPage={eventPage}
              eventPageSize={eventPageSize}
              onPageChange={setEventPage}
              onSelectEvent={setSelectedEvent}
            />
          </div>

          <aside className="space-y-5">
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
            <EventDetailPanel event={selectedEvent} />
          </aside>
        </section>
      </main>
    </>
  );
}

function EventLogTable({
  eventLog,
  visibleEvents,
  eventPage,
  eventPageSize,
  onPageChange,
  onSelectEvent,
}: {
  eventLog: DiagnosticEvent[];
  visibleEvents: DiagnosticEvent[];
  eventPage: number;
  eventPageSize: number;
  onPageChange: (page: number) => void;
  onSelectEvent: (event: DiagnosticEvent) => void;
}) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-4 py-3">
        <div>
          <h2 className="text-sm font-semibold text-slate-900">详细事件日志</h2>
          <p className="mt-0.5 text-xs text-slate-400">点击事件在右侧查看完整消息。</p>
        </div>
        <span className="text-xs text-slate-400">{eventLog.length} 条事件</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[760px] text-left text-sm">
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
            {eventLog.length > 0 ? visibleEvents.map((event) => (
              <tr key={`${event.time}-${event.file}`} className="cursor-pointer hover:bg-slate-50" onClick={() => onSelectEvent(event)}>
                <td className="px-4 py-3 font-mono text-xs text-slate-500">{formatDate(event.time)}</td>
                <td className="px-4 py-3 text-slate-700">{stageLabels[event.stage] || event.stage}</td>
                <td className="px-4 py-3">
                  <span className={cn("rounded-full px-2 py-0.5 text-xs font-medium", event.level === "WARN" ? "bg-amber-50 text-amber-700" : "bg-emerald-50 text-emerald-700")}>
                    {event.level}
                  </span>
                </td>
                <td className="max-w-[360px] truncate px-4 py-3 text-slate-600">{event.message}</td>
                <td className="max-w-[160px] truncate px-4 py-3 font-mono text-xs text-slate-500">{event.file}</td>
              </tr>
            )) : (
              <tr>
                <td colSpan={5} className="px-4 py-10 text-center text-sm text-slate-400">
                  选择项目后查看详细事件日志
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <Pagination page={eventPage} pageSize={eventPageSize} total={eventLog.length} onPageChange={onPageChange} />
    </section>
  );
}

function EventDetailPanel({ event }: { event: DiagnosticEvent | null }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <h2 className="text-sm font-semibold text-slate-900">事件详情</h2>
      {!event ? (
        <p className="mt-4 text-sm text-slate-400">选择一条事件后查看完整消息。</p>
      ) : (
        <>
          <div className="mt-4 flex flex-wrap gap-2">
            <span className="rounded-full bg-blue-50 px-2 py-1 text-xs font-medium text-blue-700">{stageLabels[event.stage] || event.stage}</span>
            <span className={cn("rounded-full px-2 py-1 text-xs font-medium", event.level === "WARN" ? "bg-amber-50 text-amber-700" : "bg-emerald-50 text-emerald-700")}>{event.level}</span>
          </div>

          <section className="mt-5 rounded-lg border border-slate-200 p-4">
            <h3 className="text-sm font-semibold text-slate-900">消息</h3>
            <p className="mt-3 whitespace-pre-wrap break-words text-sm leading-6 text-slate-600">{event.message}</p>
          </section>

          <section className="mt-4 space-y-3 rounded-lg border border-slate-200 p-4 text-sm">
            <InfoRow label="时间" value={formatDate(event.time)} />
            <InfoRow label="阶段" value={event.stage} />
            <InfoRow label="级别" value={event.level} />
            <InfoRow label="文件" value={event.file} />
          </section>
        </>
      )}
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-[72px_minmax(0,1fr)] gap-3 border-b border-slate-100 pb-2 last:border-b-0 last:pb-0">
      <span className="text-xs text-slate-400">{label}</span>
      <span className="break-all font-medium text-slate-800">{value || "—"}</span>
    </div>
  );
}
