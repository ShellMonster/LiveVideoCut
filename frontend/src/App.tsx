import { ErrorCard } from "@/components/ErrorCard";
import { ProgressBar } from "@/components/ProgressBar";
import { ResultGrid } from "@/components/ResultGrid";
import { SettingsModal } from "@/components/SettingsModal";
import { ToastViewport } from "@/components/ToastViewport";
import { UploadZone } from "@/components/UploadZone";
import { useTaskProgress } from "@/hooks/useWebSocket";
import { useTaskStore } from "@/stores/taskStore";

function App() {
  const { taskId, status, error, currentState, clips } = useTaskStore();
  const { connected } = useTaskProgress(taskId);

  const hasTask = Boolean(taskId);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <SettingsModal />
      <ToastViewport />

      <main className="mx-auto flex min-h-screen w-full max-w-6xl flex-col gap-8 px-4 py-10 sm:px-6 lg:px-8">
        <section className="space-y-3">
          <span className="inline-flex rounded-full bg-blue-50 px-3 py-1 text-xs font-medium text-blue-700">
            直播视频 AI 智能剪辑
          </span>
          <div className="space-y-2">
            <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">
              上传直播录像，自动生成可下载的商品讲解片段
            </h1>
            <p className="max-w-3xl text-sm leading-6 text-slate-600 sm:text-base">
              当前 MVP 支持上传 MP4 文件、查看任务处理状态，并在完成后浏览和下载剪辑结果。
            </p>
          </div>
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="mb-4 space-y-1">
            <h2 className="text-lg font-semibold">上传视频</h2>
            <p className="text-sm text-slate-500">拖拽或选择一个 MP4 文件开始处理。</p>
          </div>
          <UploadZone />
        </section>

        {(hasTask || status === "uploading" || status === "error") && (
          <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <h2 className="text-lg font-semibold">处理状态</h2>
                <p className="mt-1 text-sm text-slate-600">
                  {status === "uploading" && "文件正在上传，完成后会自动开始处理。"}
                  {status === "processing" && "任务已创建，系统正在持续处理视频。"}
                  {status === "done" && clips && clips.length > 0 && "处理完成，可以在下方查看和下载剪辑结果。"}
                  {status === "done" && clips && clips.length === 0 && "处理完成，但当前视频没有识别出可导出的商品片段。"}
                  {status === "error" && "任务执行失败，请检查错误信息后重新上传。"}
                </p>
              </div>

              {taskId && (
                <div className="rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-500">
                  <div>任务 ID：{taskId}</div>
                  <div className="mt-1">WebSocket：{connected ? "已连接" : "连接中 / 等待中"}</div>
                </div>
              )}
            </div>

            {(status === "processing" || status === "done" || status === "error") && (
              <div className="mt-4">
                <ProgressBar currentState={status === "error" ? "ERROR" : currentState} errorMessage={error || undefined} />
              </div>
            )}

            {error && (
              <div className="mt-4">
                <ErrorCard errorType="处理失败" errorMessage={error} />
              </div>
            )}
          </section>
        )}

        {hasTask && (
          <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="mb-4 space-y-1">
              <h2 className="text-lg font-semibold">剪辑结果</h2>
              <p className="text-sm text-slate-500">任务完成后，结果会显示在这里。</p>
            </div>
            <ResultGrid />
          </section>
        )}
      </main>
    </div>
  );
}

export default App
