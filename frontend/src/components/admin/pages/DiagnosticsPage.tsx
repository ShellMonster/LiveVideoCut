import { Download, FileVideo } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAdminContext } from "@/components/AdminDashboard";
import { useTaskDiagnostics, useTasks } from "@/hooks/useAdminQueries";
import { API_BASE } from "../api";
import { displayTaskName, formatDate, formatElapsed } from "../format";
import { Header, MetricCard, Warning } from "../shared";

export function DiagnosticsPage() {
  const { selectedTask, setSelectedTask } = useAdminContext();
  const { data: tasks = [] } = useTasks();
  const { data: diagnostics } = useTaskDiagnostics(selectedTask?.task_id);

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
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <span>当前项目</span>
          <select
            className="rounded-md border border-slate-200 bg-white px-2 py-1 text-xs text-slate-700"
            value={selectedTask?.task_id || ""}
            onChange={(event) => {
              const next = tasks.find((task) => task.task_id === event.target.value);
              if (next) setSelectedTask(next);
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

        <section className="grid gap-4 lg:grid-cols-5">
          <MetricCard label="总耗时" value={formatElapsed(diagnostics?.total_elapsed_s)} hint="按产物生成时间推导" />
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
                <div className="mt-2 text-xs font-medium text-slate-600">{formatElapsed(item.duration_s)}</div>
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
