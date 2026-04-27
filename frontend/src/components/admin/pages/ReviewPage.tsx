import { useState } from "react";
import { ChevronRight, Download, Film, Play } from "lucide-react";
import { cn } from "@/lib/utils";
import { VideoPreview } from "@/components/VideoPreview";
import { useAdminContext } from "@/components/AdminDashboard";
import { useTasks, useTaskClips, useTaskReview, usePatchReviewSegment, useReprocessSegment, useClipReprocessStatus } from "@/hooks/useAdminQueries";
import { API_BASE } from "../api";
import { clipJobStatusLabel, displayTaskName, formatDuration, reviewStatusLabel } from "../format";
import {
  Chip,
  Field,
  Header,
  MetricPill,
  SegmentTimeline,
  TranscriptLine,
} from "../shared";
import type { ClipData } from "@/stores/taskStore";
import type { ReviewSegment } from "../types";

export function ReviewPage() {
  const { selectedTask, setSelectedTask } = useAdminContext();
  const { data: tasks = [] } = useTasks();
  const { data: clips = [], isLoading: clipsLoading } = useTaskClips(
    selectedTask?.task_id,
    selectedTask?.status === "COMPLETED",
  );
  const { data: reviewData } = useTaskReview(selectedTask?.task_id);
  const patchMutation = usePatchReviewSegment(selectedTask?.task_id);
  const reprocessMutation = useReprocessSegment(selectedTask?.task_id);

  const [previewClip, setPreviewClip] = useState<ClipData | null>(null);
  const [selectedIndex, setSelectedIndex] = useState(0);

  const segmentCount = Math.max(clips.length, reviewData?.segments.length ?? 0);
  const safeSelectedIndex = selectedIndex < segmentCount ? selectedIndex : 0;
  const currentClip = clips[safeSelectedIndex] ?? clips[0] ?? null;
  const currentSegment = reviewData?.segments[safeSelectedIndex] ?? reviewData?.segments[0] ?? null;

  const { data: currentJob } = useClipReprocessStatus(
    selectedTask?.task_id,
    currentSegment?.segment_id,
  );

  const timelineDuration = Math.max(
    selectedTask?.video_duration_s ?? 0,
    ...(reviewData?.segments.map((segment) => segment.end_time) ?? [0]),
    currentClip?.end_time ?? 0,
  );
  const isCurrentReprocessing = currentJob?.status === "queued" || currentJob?.status === "running";
  const approvedClipIds = clips
    .filter((_clip, index) => reviewData?.segments[index]?.review_status === "approved")
    .map((clip) => clip.clip_id);
  const transcriptLines = reviewData?.transcript
    .filter((line) => {
      if (!currentSegment) return true;
      return line.end_time >= currentSegment.start_time && line.start_time <= currentSegment.end_time;
    })
    .slice(0, 6) ?? [];

  const handlePatch = (segmentId: string, patch: Partial<ReviewSegment>) => {
    patchMutation.mutate({ segmentId, patch: patch as Record<string, unknown> });
  };

  const handleReprocess = (segmentId: string) => {
    reprocessMutation.mutate(segmentId);
  };

  return (
    <>
      <Header
        title="剪辑复核"
        description="复核 AI 生成片段，调整标题、时间边界、封面和导出状态"
        action={
          <>
            <span className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-500">
              操作实时生效
            </span>
            <button
              onClick={() => {
                if (approvedClipIds.length === 0) return;
                window.open(`${API_BASE}/api/clips/batch?ids=${approvedClipIds.join(",")}`, "_blank");
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
              <span>{timelineDuration > 0 ? `源视频 ${formatDuration(timelineDuration)} · ${reviewData?.segments.length ?? 0} 段` : "等待片段数据"}</span>
            </div>
            <SegmentTimeline
              segments={reviewData?.segments ?? []}
              duration={timelineDuration}
              selectedIndex={safeSelectedIndex}
              onSelect={setSelectedIndex}
            />
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
                    onClick={() => {
                      setSelectedIndex(index);
                      setPreviewClip(clip);
                    }}
                    className={cn(
                      "overflow-hidden rounded-lg border bg-white text-left hover:border-blue-200 hover:shadow-sm",
                      safeSelectedIndex === index ? "border-blue-300 ring-2 ring-blue-100" : "border-slate-200",
                    )}
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
                    onClick={() => handlePatch(currentSegment.segment_id, { review_status: "approved" })}
                    className="rounded-lg bg-emerald-600 px-3 py-2 text-sm font-medium text-white hover:bg-emerald-700"
                  >
                    通过
                  </button>
                  <button
                    onClick={() => handlePatch(currentSegment.segment_id, { review_status: "skipped" })}
                    className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
                  >
                    跳过
                  </button>
                  <button
                    onClick={() => handlePatch(currentSegment.segment_id, { review_status: "needs_adjustment" })}
                    className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
                  >
                    标记需调整
                  </button>
                  <button
                    onClick={() => handleReprocess(currentSegment.segment_id)}
                    disabled={isCurrentReprocessing}
                    className={cn(
                      "rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50",
                      isCurrentReprocessing && "cursor-not-allowed opacity-60",
                    )}
                  >
                    {isCurrentReprocessing ? "重导出中" : "重跑单片段"}
                  </button>
                </div>
                {currentJob?.status && (
                  <div
                    className={cn(
                      "rounded-lg p-3 text-xs",
                      currentJob.status === "failed"
                        ? "bg-red-50 text-red-700"
                        : currentJob.status === "completed"
                          ? "bg-emerald-50 text-emerald-700"
                          : "bg-blue-50 text-blue-700",
                    )}
                  >
                    单片段重导出：{clipJobStatusLabel(currentJob.status)}
                    {currentJob.error ? `，${currentJob.error}` : ""}
                  </div>
                )}
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
