import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  Clock3,
  CloudUpload,
  Download,
  Eye,
  FileText,
  Filter,
  Image,
  Info,
  RefreshCw,
  X,
  XCircle,
} from "lucide-react";
import type React from "react";
import { useState } from "react";
import { cn } from "@/lib/utils";
import { useAdminContext } from "@/components/admin/context";
import { useTaskDiagnostics, useTasks } from "@/hooks/useAdminQueries";
import { API_BASE } from "../api";
import { stageLabels } from "../constants";
import { displayTaskName, formatDate } from "../format";
import { Pagination } from "../shared";
import type { DiagnosticReport } from "../types";

type DiagnosticEvent = DiagnosticReport["event_log"][number];

export function DiagnosticsPage() {
  const { selectedTask, setSelectedTask } = useAdminContext();
  const { data: tasks = [] } = useTasks();
  const { data: diagnostics, refetch, isFetching } = useTaskDiagnostics(selectedTask?.task_id);

  const summary = diagnostics?.summary;
  const funnel = diagnostics?.funnel ?? [];
  const eventLog = diagnostics?.event_log ?? [];
  const [eventPage, setEventPage] = useState(1);
  const [selectedEvent, setSelectedEvent] = useState<DiagnosticEvent | null>(null);
  const eventPageSize = 10;
  const visibleEvents = eventLog.slice((eventPage - 1) * eventPageSize, eventPage * eventPageSize);
  const maxFunnel = Math.max(...funnel.map((item) => item.count), 1);
  const taskId = selectedTask?.task_id;
  const pipeline = diagnostics?.pipeline ?? [];
  const warningItems = diagnostics?.warnings ?? [];
  const errorCount = eventLog.filter((event) => normalizeLevel(event.level) === "error").length;
  const warningCount = warningItems.length + eventLog.filter((event) => normalizeLevel(event.level) === "warn").length;
  const infoCount = eventLog.filter((event) => normalizeLevel(event.level) === "info").length;
  const dataUpdatedAt = eventLog[0]?.time || selectedTask?.created_at;
  const funnelStart = funnel[0]?.count || 0;
  const funnelEnd = funnel[funnel.length - 1]?.count || 0;
  const overallPassRate = funnelStart > 0 ? (funnelEnd / funnelStart) * 100 : 0;
  const vlmDropRate = rateBetween(summary?.confirmed_count, summary?.candidates_count, true);
  const asrPassRate = rateBetween(summary?.enriched_segments_count, summary?.confirmed_count);
  const exportFailRate = rateBetween(summary?.empty_screen_dropped_estimate, Math.max(summary?.enriched_segments_count ?? 0, 1));

  return (
    <>
      <header className="border-b border-slate-200 bg-white">
        <div className="flex min-h-16 flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <div>
            <h1 className="text-xl font-semibold text-slate-950">任务诊断报告</h1>
          </div>
          <div className="grid grid-cols-2 gap-2 sm:flex sm:flex-wrap sm:items-center">
            <button
              disabled={!taskId}
              onClick={() => taskId && window.open(`${API_BASE}/api/tasks/${taskId}/diagnostics/export`, "_blank")}
              className={cn(
                "inline-flex items-center justify-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50 sm:px-4",
                !taskId && "cursor-not-allowed opacity-50",
              )}
            >
              <FileText size={16} />
              导出报告
            </button>
            <button
              disabled={!taskId}
              onClick={() => taskId && window.open(`${API_BASE}/api/tasks/${taskId}/artifacts.zip`, "_blank")}
              className={cn(
                "inline-flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white shadow-sm shadow-blue-600/20 hover:bg-blue-700 sm:px-4",
                !taskId && "cursor-not-allowed opacity-50",
              )}
            >
              <Download size={16} />
              下载诊断包
            </button>
          </div>
        </div>
        <div className="flex flex-col gap-3 border-t border-slate-100 px-4 py-3 text-sm lg:flex-row lg:items-center lg:justify-between sm:px-6">
          <label className="grid min-w-0 gap-2 text-slate-500 sm:grid-cols-[auto_minmax(240px,360px)_minmax(0,1fr)] sm:items-center">
            <span className="font-medium text-slate-700">当前项目</span>
            <select
              className="h-10 w-full min-w-0 rounded-lg border border-slate-200 bg-white px-3 text-sm font-medium text-slate-700"
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
            {selectedTask && <span className="text-xs text-slate-400">{selectedTask.clip_count} 个片段 · {formatDate(selectedTask.created_at)}</span>}
            {!taskId && <span className="text-xs text-slate-400">选择一个任务后查看耗时、漏斗、事件和诊断包。</span>}
          </label>
          <div className="flex items-center gap-3 text-xs text-slate-500">
            <button
              disabled={!taskId}
              onClick={() => void refetch()}
              className={cn("inline-flex items-center gap-1.5 font-medium text-slate-600 hover:text-blue-600", !taskId && "cursor-not-allowed opacity-50")}
            >
              <RefreshCw size={15} className={cn(isFetching && "animate-spin")} />
              刷新
            </button>
            <span className="hidden h-4 w-px bg-slate-200 sm:block" />
            <span>数据更新时间：{formatDate(dataUpdatedAt)}</span>
          </div>
        </div>
      </header>

      <main className="space-y-3 p-3 sm:space-y-4 sm:p-5">
        <section className="grid grid-cols-2 gap-3 xl:grid-cols-5">
          <DiagnosticsMetric icon={Clock3} tone="blue" label="总耗时" value={taskId ? formatStopwatch(diagnostics?.total_elapsed_s) : "—"} hint="按产物时间推导" />
          <DiagnosticsMetric icon={Filter} tone="blue" label="候选片段" value={taskId ? String(summary?.candidates_count ?? 0) : "—"} hint="预筛输出" />
          <DiagnosticsMetric icon={CheckCircle2} tone="blue" label="VLM确认" value={taskId ? String(summary?.confirmed_count ?? 0) : "—"} hint="通过确认" />
          <DiagnosticsMetric icon={CloudUpload} tone="emerald" label="最终导出" value={taskId ? String(summary?.clips_count ?? selectedTask?.clip_count ?? 0) : "—"} hint="导出成功" />
          <DiagnosticsMetric icon={AlertTriangle} tone="amber" label="未导出" value={taskId ? String(summary?.empty_screen_dropped_estimate ?? 0) : "—"} hint="未达到阈值 / 过滤" />
        </section>

        <section className="grid gap-4 2xl:grid-cols-[minmax(0,1fr)_390px]">
          <div className="space-y-4">
            <section className="rounded-lg border border-slate-200 bg-white p-4">
              <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_220px]">
                <div>
                  <h2 className="text-base font-semibold text-slate-900">流水线耗时</h2>
                  <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                    {pipeline.length > 0 ? pipeline.map((item, index) => (
                      <PipelineStep key={item.stage} item={item} index={index} total={pipeline.length} totalSeconds={diagnostics?.total_elapsed_s} />
                    )) : (
                      <p className="col-span-full py-8 text-center text-sm text-slate-400">选择项目后查看流水线诊断</p>
                    )}
                  </div>
                </div>
                <div className="border-slate-100 xl:border-l xl:pl-6">
                  <p className="text-sm font-semibold text-slate-700">流水线总耗时</p>
                  <p className="mt-3 text-2xl font-semibold text-slate-950">{taskId ? formatStopwatch(diagnostics?.total_elapsed_s) : "—"}</p>
                  <p className="mt-1 text-xs text-blue-500">{pipeline.length > 0 ? "100%" : "—"}</p>
                  <dl className="mt-5 space-y-3 text-sm">
                    <InfoLine label="开始时间" value={formatDate(selectedTask?.created_at)} />
                    <InfoLine label="结束时间" value={formatDate(eventLog[0]?.time)} />
                  </dl>
                </div>
              </div>
            </section>

            <div className="rounded-lg border border-slate-200 bg-white p-4">
              <h2 className="text-base font-semibold text-slate-900">片段漏斗</h2>
              <div className="mt-4 grid gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
                <div className="grid gap-4 lg:grid-cols-[190px_minmax(280px,1fr)_150px]">
                  <div className="space-y-4 pt-1">
                    {funnel.length > 0 ? funnel.map((item, index) => (
                      <FunnelLabel key={item.label} item={item} index={index} />
                    )) : (
                      <p className="text-sm text-slate-400">选择项目后查看片段漏斗</p>
                    )}
                  </div>
                  <div className="flex min-h-44 flex-col items-center justify-center gap-0.5">
                    {funnel.length > 0 ? funnel.map((item, index) => (
                      <div
                        key={item.label}
                        className={cn("h-10", index < 2 ? "bg-blue-600" : index === 2 ? "bg-sky-400" : "bg-emerald-500")}
                        style={{
                          width: `${Math.max(24, 86 - index * 14)}%`,
                          clipPath: "polygon(9% 0, 91% 0, 100% 100%, 0% 100%)",
                          opacity: 0.95,
                        }}
                      />
                    )) : null}
                  </div>
                  <div className="space-y-4 pt-1">
                    {funnel.map((item) => (
                      <div key={item.label} className="h-9 text-sm font-semibold text-blue-600">
                        {item.count} <span className="text-xs font-medium">({Math.round((item.count / maxFunnel) * 100)}%)</span>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="rounded-lg border border-slate-200 text-sm">
                  <RateRow label="整体通过率" value={`${overallPassRate.toFixed(1)}%`} tone="emerald" />
                  <RateRow label="VLM过滤率" value={`${vlmDropRate.toFixed(1)}%`} tone={vlmDropRate > 30 ? "amber" : "emerald"} />
                  <RateRow label="ASR通过率" value={`${asrPassRate.toFixed(1)}%`} tone="emerald" />
                  <RateRow label="导出失败率" value={`${exportFailRate.toFixed(1)}%`} tone={exportFailRate > 0 ? "amber" : "emerald"} />
                  <p className="px-3 py-2 text-xs text-slate-400">* 比率根据现有诊断字段推导</p>
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

          <aside className="space-y-3 2xl:sticky 2xl:top-4 2xl:self-start">
            <IssuePanel
              warnings={warningItems}
              eventLog={eventLog}
              errorCount={errorCount}
              warningCount={warningCount}
              infoCount={infoCount}
              onSelectEvent={setSelectedEvent}
            />
            <EventDetailPanel event={selectedEvent} onClose={() => setSelectedEvent(null)} />
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
          <h2 className="text-base font-semibold text-slate-900">详细事件日志</h2>
        </div>
        <span className="text-xs text-slate-400">共 {eventLog.length} 条</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[940px] text-left text-sm">
          <thead className="bg-slate-50 text-xs text-slate-500">
            <tr>
              <th className="px-4 py-3">时间</th>
              <th className="px-4 py-3">阶段</th>
              <th className="px-4 py-3">级别</th>
              <th className="px-4 py-3">事件类型</th>
              <th className="px-4 py-3">信息</th>
              <th className="px-4 py-3">关联文件</th>
              <th className="px-4 py-3 text-center">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {eventLog.length > 0 ? visibleEvents.map((event) => (
              <tr key={`${event.time}-${event.file}`} className="cursor-pointer hover:bg-slate-50" onClick={() => onSelectEvent(event)}>
                <td className="px-4 py-3 font-mono text-xs text-slate-500">{formatDate(event.time)}</td>
                <td className="px-4 py-3 text-slate-700">{stageLabels[event.stage] || event.stage}</td>
                <td className="px-4 py-3">
                  <LevelBadge level={event.level} />
                </td>
                <td className="max-w-[160px] truncate px-4 py-3 text-slate-700">{eventTitle(event.message)}</td>
                <td className="max-w-[360px] truncate px-4 py-3 text-slate-600">{event.message}</td>
                <td className="max-w-[160px] truncate px-4 py-3 font-mono text-xs text-slate-500">{event.file}</td>
                <td className="px-4 py-3 text-center">
                  <button className="inline-flex items-center gap-1 text-xs font-medium text-blue-600 hover:text-blue-700">
                    <Eye size={14} />
                    查看
                  </button>
                </td>
              </tr>
            )) : (
              <tr>
                <td colSpan={7} className="px-4 py-10 text-center text-sm text-slate-400">
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

function EventDetailPanel({ event, onClose }: { event: DiagnosticEvent | null; onClose: () => void }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-slate-900">事件详情</h2>
        {event && (
          <button onClick={onClose} className="rounded-md p-1 text-slate-400 hover:bg-slate-50 hover:text-slate-700" aria-label="关闭事件详情">
            <X size={16} />
          </button>
        )}
      </div>
      {!event ? (
        <p className="mt-4 text-sm text-slate-400">选择一条事件后查看完整消息。</p>
      ) : (
        <>
          <section className="mt-4 space-y-3 text-sm">
            <InfoRow label="时间" value={formatDate(event.time)} />
            <InfoRow label="阶段" value={stageLabels[event.stage] || event.stage} />
            <InfoRow label="级别" value={levelLabel(event.level)} />
            <InfoRow label="事件类型" value={eventTitle(event.message)} />
            <InfoRow label="事件描述" value={event.message} />
            <InfoRow label="关联文件" value={event.file} />
            <InfoRow label="建议" value={eventSuggestion(event)} />
          </section>
          <pre className="mt-4 overflow-auto rounded-lg bg-slate-50 p-3 text-xs leading-5 text-slate-600">{`stage: ${event.stage}
level: ${event.level}
file: ${event.file || "—"}`}</pre>
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

function DiagnosticsMetric({
  icon: Icon,
  tone,
  label,
  value,
  hint,
  trend,
}: {
  icon: React.ElementType;
  tone: "blue" | "emerald" | "amber";
  label: string;
  value: string;
  hint: string;
  trend?: "down";
}) {
  const toneClass = {
    blue: "bg-blue-50 text-blue-600 ring-blue-100",
    emerald: "bg-emerald-50 text-emerald-600 ring-emerald-100",
    amber: "bg-amber-50 text-amber-600 ring-amber-100",
  }[tone];

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3 sm:p-4">
      <div className="flex items-center gap-3 sm:gap-4">
        <div className={cn("flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ring-1 sm:h-10 sm:w-10", toneClass)}>
          <Icon size={18} />
        </div>
        <div className="min-w-0">
          <div className="text-xs text-slate-500">{label}</div>
          <div className="mt-1 text-xl font-semibold tracking-tight text-slate-950 sm:text-2xl">{value}</div>
          <div className={cn("mt-1 text-xs", trend === "down" ? "text-emerald-600" : "text-slate-400")}>{hint}</div>
        </div>
      </div>
    </div>
  );
}

function PipelineStep({
  item,
  index,
  total,
  totalSeconds,
}: {
  item: DiagnosticReport["pipeline"][number];
  index: number;
  total: number;
  totalSeconds?: number | null;
}) {
  const done = item.status === "done";

  return (
    <div className="relative">
      {index < total - 1 && <div className="absolute left-[calc(50%+2.25rem)] top-1/2 hidden h-0.5 w-[calc(100%-4.5rem)] -translate-y-1/2 bg-blue-500 xl:block" />}
      <div className="relative rounded-lg border border-slate-200 bg-white p-3 shadow-sm sm:p-4">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-50 text-blue-600">
            {pipelineIcon(item.stage)}
          </div>
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm font-semibold text-slate-800">{stageLabels[item.stage] || item.stage}</div>
            <div className={cn("mt-1 flex items-center gap-1 text-xs", done ? "text-emerald-600" : item.status === "skipped" ? "text-slate-400" : "text-amber-600")}>
              <CheckCircle2 size={12} />
              {done ? "完成" : item.status === "skipped" ? "跳过" : "处理中"}
            </div>
          </div>
          <div className="text-right sm:hidden">
            <div className="text-sm font-semibold text-slate-950">{formatStopwatch(item.duration_s)}</div>
            <div className="text-xs text-slate-400">{totalSeconds && item.duration_s ? `${((item.duration_s / totalSeconds) * 100).toFixed(1)}%` : "—"}</div>
          </div>
        </div>
        <div className="mt-4 hidden text-center text-lg font-semibold text-slate-950 sm:block">{formatStopwatch(item.duration_s)}</div>
        <div className="mt-1 hidden text-center text-xs text-slate-400 sm:block">占比 {totalSeconds && item.duration_s ? `${((item.duration_s / totalSeconds) * 100).toFixed(1)}%` : "—"}</div>
      </div>
    </div>
  );
}

function FunnelLabel({ item, index }: { item: DiagnosticReport["funnel"][number]; index: number }) {
  const descriptions = ["视觉候选输出的候选片段", "通过 VLM 语义确认", "成功转写文本", "最终成功导出"];
  return (
    <div className="h-9">
      <div className="text-sm font-semibold text-slate-800">{item.label}</div>
      <div className="text-xs text-slate-400">{descriptions[index] ?? "阶段输出数量"}</div>
    </div>
  );
}

function RateRow({ label, value, tone }: { label: string; value: string; tone: "emerald" | "amber" }) {
  return (
    <div className="grid grid-cols-[minmax(0,1fr)_80px] border-b border-slate-100 px-4 py-3 last:border-b-0">
      <span className="text-slate-500">{label}</span>
      <span className={cn("text-right font-semibold", tone === "emerald" ? "text-emerald-600" : "text-amber-600")}>{value}</span>
    </div>
  );
}

function IssuePanel({
  warnings,
  eventLog,
  errorCount,
  warningCount,
  infoCount,
  onSelectEvent,
}: {
  warnings: DiagnosticReport["warnings"];
  eventLog: DiagnosticEvent[];
  errorCount: number;
  warningCount: number;
  infoCount: number;
  onSelectEvent: (event: DiagnosticEvent) => void;
}) {
  const issues = eventLog.slice(0, 5);

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <h2 className="text-base font-semibold text-slate-900">异常与建议</h2>
      <div className="mt-5 grid grid-cols-3 divide-x divide-slate-100 text-center">
        <IssueCount icon={XCircle} tone="red" value={errorCount} label="错误" />
        <IssueCount icon={AlertTriangle} tone="amber" value={warningCount} label="告警" />
        <IssueCount icon={Info} tone="blue" value={infoCount} label="提示" />
      </div>
      <div className="mt-5 space-y-2">
        {issues.length > 0 ? issues.map((event) => (
          <button
            key={`${event.time}-${event.file}-${event.message}`}
            onClick={() => onSelectEvent(event)}
            className="flex w-full items-start gap-3 rounded-lg border border-slate-200 p-3 text-left hover:bg-slate-50"
          >
            <LevelIcon level={event.level} />
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-medium text-slate-800">{eventTitle(event.message)}</span>
              <span className="mt-0.5 block truncate text-xs text-slate-500">{event.message}</span>
            </span>
            <span className="shrink-0 text-xs text-slate-400">{formatDate(event.time)}</span>
          </button>
        )) : warnings.length > 0 ? warnings.map((item) => (
          <div key={item.message} className="rounded-lg border border-amber-100 bg-amber-50 p-3 text-sm text-amber-700">{item.message}</div>
        )) : (
          <p className="rounded-lg bg-slate-50 p-4 text-sm text-slate-400">暂无异常建议</p>
        )}
      </div>
    </div>
  );
}

function IssueCount({ icon: Icon, tone, value, label }: { icon: React.ElementType; tone: "red" | "amber" | "blue"; value: number; label: string }) {
  const className = {
    red: "text-red-600",
    amber: "text-amber-600",
    blue: "text-blue-600",
  }[tone];
  return (
    <div className="flex items-center justify-center gap-2">
      <Icon size={18} className={className} />
      <div className="text-left">
        <div className="text-sm font-semibold text-slate-950">{value}</div>
        <div className="text-xs text-slate-500">{label}</div>
      </div>
    </div>
  );
}

function InfoLine({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <dt className="text-slate-400">{label}</dt>
      <dd className="text-right font-medium text-slate-600">{value}</dd>
    </div>
  );
}

function LevelBadge({ level }: { level: string }) {
  const normalized = normalizeLevel(level);
  return (
    <span className={cn(
      "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
      normalized === "error" && "bg-red-50 text-red-700",
      normalized === "warn" && "bg-amber-50 text-amber-700",
      normalized === "info" && "bg-blue-50 text-blue-700",
      normalized === "ok" && "bg-emerald-50 text-emerald-700",
    )}>
      {levelLabel(level)}
    </span>
  );
}

function LevelIcon({ level }: { level: string }) {
  const normalized = normalizeLevel(level);
  if (normalized === "error") return <XCircle size={18} className="mt-0.5 shrink-0 text-red-600" />;
  if (normalized === "warn") return <AlertTriangle size={18} className="mt-0.5 shrink-0 text-amber-600" />;
  return <Info size={18} className="mt-0.5 shrink-0 text-blue-600" />;
}

function pipelineIcon(stage: string) {
  if (stage.includes("VISUAL") || stage.includes("SCENE")) return <Image size={18} />;
  if (stage.includes("VLM")) return <Bot size={18} />;
  if (stage.includes("TRANSCRIB")) return <FileText size={18} />;
  if (stage.includes("PROCESS") || stage.includes("EXPORT") || stage.includes("COMPLETED")) return <Download size={18} />;
  return <CheckCircle2 size={18} />;
}

function normalizeLevel(level: string): "error" | "warn" | "info" | "ok" {
  const value = level.toLowerCase();
  if (value.includes("error") || value.includes("fail")) return "error";
  if (value.includes("warn")) return "warn";
  if (value.includes("info")) return "info";
  return "ok";
}

function levelLabel(level: string): string {
  const normalized = normalizeLevel(level);
  if (normalized === "error") return "错误";
  if (normalized === "warn") return "告警";
  if (normalized === "info") return "提示";
  return "正常";
}

function eventTitle(message: string): string {
  if (!message) return "事件";
  return message.split(/[，,。:：]/)[0] || message;
}

function eventSuggestion(event: DiagnosticEvent): string {
  const normalized = normalizeLevel(event.level);
  if (normalized === "error") return "检查对应产物文件、后端错误日志和任务重试记录。";
  if (normalized === "warn") return "关注阈值配置、输入质量和该阶段耗时是否异常。";
  return "作为诊断参考，无需立即处理。";
}

function formatStopwatch(seconds?: number | null): string {
  if (seconds == null || seconds < 0) return "—";
  const total = Math.round(seconds);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

function rateBetween(current?: number, base?: number, inverse = false): number {
  if (!base || base <= 0 || current == null) return 0;
  const ratio = current / base;
  return Math.max(0, Math.min(100, (inverse ? 1 - ratio : ratio) * 100));
}
