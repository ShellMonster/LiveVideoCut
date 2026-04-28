import { useEffect, useState } from "react";
import { ChevronRight, Download, Film, MoreHorizontal, Play, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAdminContext } from "@/components/admin/context";
import {
  useClipReprocessStatus,
  usePatchReviewSegment,
  useReprocessSegment,
  useTaskClips,
  useTaskReview,
  useTasks,
} from "@/hooks/useAdminQueries";
import { API_BASE } from "../api";
import {
  clipJobStatusLabel,
  displayTaskName,
  formatConfidence,
  formatDuration,
  reviewStatusLabel,
} from "../format";
import {
  Chip,
  Header,
  MetricPill,
  Pagination,
  SegmentTimeline,
} from "../shared";
import type { ClipData } from "@/stores/taskStore";
import type { ReviewSegment } from "../types";

type ReviewFilter = "all" | ReviewSegment["review_status"];
type DrawerTab = "details" | "subtitles" | "advice";

const reviewFilters: { value: ReviewFilter; label: string }[] = [
  { value: "all", label: "全部" },
  { value: "pending", label: "待复核" },
  { value: "approved", label: "已通过" },
  { value: "needs_adjustment", label: "需调整" },
  { value: "skipped", label: "已跳过" },
];

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

  const [selectedIndex, setSelectedIndex] = useState(0);
  const [clipPage, setClipPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<ReviewFilter>("all");
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerTab, setDrawerTab] = useState<DrawerTab>("details");
  const clipPageSize = 12;

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
  const isMutating = patchMutation.isPending || reprocessMutation.isPending;
  const approvedClipIds = clips
    .filter((_clip, index) => reviewData?.segments[index]?.review_status === "approved")
    .map((clip) => clip.clip_id);
  const clipEntries = clips.map((clip, index) => ({
    clip,
    index,
    segment: reviewData?.segments[index],
  }));
  const filteredEntries = clipEntries.filter(({ segment }) => {
    if (statusFilter === "all") return true;
    return (segment?.review_status ?? "pending") === statusFilter;
  });
  const clipPageStart = (clipPage - 1) * clipPageSize;
  const visibleEntries = filteredEntries.slice(clipPageStart, clipPageStart + clipPageSize);
  const transcriptLines = reviewData?.transcript
    .filter((line) => {
      if (!currentSegment) return true;
      return line.end_time >= currentSegment.start_time && line.start_time <= currentSegment.end_time;
    }) ?? [];
  const statusCounts = reviewFilters.reduce<Record<ReviewFilter, number>>((acc, option) => {
    acc[option.value] = option.value === "all"
      ? clipEntries.length
      : clipEntries.filter(({ segment }) => (segment?.review_status ?? "pending") === option.value).length;
    return acc;
  }, {
    all: 0,
    pending: 0,
    approved: 0,
    needs_adjustment: 0,
    skipped: 0,
  });

  const handlePatch = (segmentId: string, patch: Partial<ReviewSegment>) => {
    patchMutation.mutate({ segmentId, patch: patch as Record<string, unknown> });
  };

  const handleReprocess = (segmentId: string) => {
    reprocessMutation.mutate(segmentId);
  };

  const selectClip = (index: number, tab: DrawerTab = "details") => {
    setSelectedIndex(index);
    setDrawerTab(tab);
    setDrawerOpen(true);
  };

  return (
    <>
      <Header
        title="剪辑复核"
        description="复核 AI 生成片段，调整标题、时间边界、封面和导出状态"
        action={
          <>
            <span className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-500">
              {isMutating ? "操作提交中" : "操作实时生效"}
            </span>
            <button
              onClick={() => {
                if (approvedClipIds.length === 0) return;
                window.open(`${API_BASE}/api/clips/batch?ids=${approvedClipIds.join(",")}`, "_blank");
              }}
              disabled={approvedClipIds.length === 0}
              className={cn(
                "inline-flex items-center gap-2 rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700",
                approvedClipIds.length === 0 && "cursor-not-allowed opacity-50 hover:bg-blue-600",
              )}
            >
              <Download size={16} />
              下载通过片段
            </button>
          </>
        }
      />
      <main className="space-y-5 p-4 sm:p-6">
        <section className="rounded-lg border border-slate-200 bg-white p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex min-w-0 items-center gap-2 text-xs text-slate-500">
              <span>项目总览</span>
              <ChevronRight size={14} />
              <select
                className="min-w-72 rounded-md border border-slate-200 bg-white px-2 py-1.5 text-xs text-slate-700"
                value={selectedTask?.task_id || ""}
                onChange={(event) => {
                  const next = tasks.find((task) => task.task_id === event.target.value);
                  if (next) {
                    setSelectedTask(next);
                    setSelectedIndex(0);
                    setClipPage(1);
                    setDrawerOpen(false);
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
            </div>
            <div className="flex flex-wrap gap-2">
              {reviewFilters.map((option) => (
                <button
                  key={option.value}
                  onClick={() => {
                    setStatusFilter(option.value);
                    setClipPage(1);
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
                    {statusCounts[option.value]}
                  </span>
                </button>
              ))}
            </div>
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-4">
            <MetricPill label="全部片段" value={String(statusCounts.all)} />
            <MetricPill label="待复核" value={String(statusCounts.pending)} />
            <MetricPill label="已通过" value={String(statusCounts.approved)} />
            <MetricPill label="需调整" value={String(statusCounts.needs_adjustment)} />
          </div>
        </section>

        <section className="rounded-lg border border-slate-200 bg-white">
          <div className="border-b border-slate-100 px-4 py-3">
            <h2 className="text-sm font-semibold text-slate-900">片段复核卡片</h2>
          </div>
          {clipsLoading ? (
            <p className="py-10 text-center text-sm text-slate-400">加载片段中...</p>
          ) : clips.length === 0 ? (
            <p className="py-10 text-center text-sm text-slate-400">当前项目暂无可复核片段</p>
          ) : filteredEntries.length === 0 ? (
            <p className="py-10 text-center text-sm text-slate-400">当前筛选下暂无片段</p>
          ) : (
            <>
              <div className="grid gap-4 p-4 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
                {visibleEntries.map(({ clip, index, segment }) => (
                  <ClipReviewCard
                    key={clip.clip_id}
                    clip={clip}
                    segment={segment}
                    active={safeSelectedIndex === index && drawerOpen}
                    onOpen={() => selectClip(index)}
                    onPreview={() => selectClip(index, "details")}
                    onApprove={() => segment && handlePatch(segment.segment_id, { review_status: "approved" })}
                    onMore={() => selectClip(index, "advice")}
                  />
                ))}
              </div>
              <Pagination
                page={clipPage}
                pageSize={clipPageSize}
                total={filteredEntries.length}
                onPageChange={setClipPage}
              />
            </>
          )}
        </section>
      </main>

      <ReviewInspectorDrawer
        open={drawerOpen}
        tab={drawerTab}
        onTabChange={setDrawerTab}
        onClose={() => setDrawerOpen(false)}
        clip={currentClip}
        segment={currentSegment}
        transcriptLines={transcriptLines}
        timelineDuration={timelineDuration}
        segments={reviewData?.segments ?? []}
        selectedIndex={safeSelectedIndex}
        onSelectSegment={(index) => setSelectedIndex(index)}
        currentJob={currentJob}
        isCurrentReprocessing={isCurrentReprocessing}
        patchPending={patchMutation.isPending}
        reprocessPending={reprocessMutation.isPending}
        onPatch={handlePatch}
        onReprocess={handleReprocess}
      />
    </>
  );
}

function ClipReviewCard({
  clip,
  segment,
  active,
  onOpen,
  onPreview,
  onApprove,
  onMore,
}: {
  clip: ClipData;
  segment?: ReviewSegment;
  active: boolean;
  onOpen: () => void;
  onPreview: () => void;
  onApprove: () => void;
  onMore: () => void;
}) {
  const status = segment?.review_status ?? "pending";
  return (
    <article
      className={cn(
        "overflow-hidden rounded-lg border bg-white",
        active ? "border-blue-300 ring-2 ring-blue-100" : "border-slate-200",
      )}
    >
      <button onClick={onOpen} className="block w-full text-left">
        <div className="relative aspect-video bg-slate-100">
          {clip.has_thumbnail ? (
            <img src={clip.thumbnail_url} alt="" className="h-full w-full object-cover" />
          ) : (
            <div className="flex h-full items-center justify-center text-slate-300">
              <Film size={28} />
            </div>
          )}
          <span className="absolute bottom-2 right-2 rounded bg-black/70 px-1.5 py-0.5 text-xs text-white">
            {formatDuration(clip.duration)}
          </span>
          <span className={cn(
            "absolute left-2 top-2 rounded-full px-2 py-0.5 text-xs font-medium",
            status === "approved" && "bg-emerald-50 text-emerald-700",
            status === "needs_adjustment" && "bg-amber-50 text-amber-700",
            status === "skipped" && "bg-slate-100 text-slate-600",
            status === "pending" && "bg-blue-50 text-blue-700",
          )}>
            {reviewStatusLabel(status)}
          </span>
        </div>
        <div className="p-3">
          <div className="truncate text-sm font-medium text-slate-900">{clip.product_name || "未命名片段"}</div>
          <div className="mt-1 text-xs text-slate-400">
            {formatDuration(clip.start_time)} - {formatDuration(clip.end_time)}
          </div>
          <div className="mt-3 flex items-center gap-2 text-xs text-slate-500">
            <span>置信度 {formatConfidence(segment?.confidence)}</span>
            <span className="h-1 w-1 rounded-full bg-slate-300" />
            <span>{clip.clip_id.split("/").pop()}</span>
          </div>
        </div>
      </button>
      <div className="grid grid-cols-[1fr_1fr_36px] gap-2 border-t border-slate-100 p-3">
        <button onClick={onPreview} className="rounded-lg border border-slate-200 px-2 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50">
          预览
        </button>
        <button onClick={onApprove} disabled={!segment} className="rounded-lg bg-emerald-600 px-2 py-1.5 text-xs font-medium text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50">
          通过
        </button>
        <button onClick={onMore} className="rounded-lg border border-slate-200 px-2 py-1.5 text-slate-600 hover:bg-slate-50" aria-label="更多">
          <MoreHorizontal size={15} />
        </button>
      </div>
    </article>
  );
}

function ReviewInspectorDrawer({
  open,
  tab,
  onTabChange,
  onClose,
  clip,
  segment,
  transcriptLines,
  timelineDuration,
  segments,
  selectedIndex,
  onSelectSegment,
  currentJob,
  isCurrentReprocessing,
  patchPending,
  reprocessPending,
  onPatch,
  onReprocess,
}: {
  open: boolean;
  tab: DrawerTab;
  onTabChange: (tab: DrawerTab) => void;
  onClose: () => void;
  clip: ClipData | null;
  segment?: ReviewSegment | null;
  transcriptLines: { start_time: number; end_time: number; text: string }[];
  timelineDuration: number;
  segments: ReviewSegment[];
  selectedIndex: number;
  onSelectSegment: (index: number) => void;
  currentJob?: { status?: "queued" | "running" | "completed" | "failed"; error?: string };
  isCurrentReprocessing: boolean;
  patchPending: boolean;
  reprocessPending: boolean;
  onPatch: (segmentId: string, patch: Partial<ReviewSegment>) => void;
  onReprocess: (segmentId: string) => void;
}) {
  if (!open) return null;

  const tabs: { value: DrawerTab; label: string }[] = [
    { value: "details", label: "详情" },
    { value: "subtitles", label: "字幕草稿" },
    { value: "advice", label: "AI建议" },
  ];
  const [subtitleDraft, setSubtitleDraft] = useState<{ start_time: number; end_time: number; text: string }[]>([]);

  useEffect(() => {
    if (!segment) {
      setSubtitleDraft([]);
      return;
    }
    const source = segment.subtitle_overrides?.length ? segment.subtitle_overrides : transcriptLines;
    setSubtitleDraft(source.map((line) => ({
      start_time: Number(line.start_time),
      end_time: Number(line.end_time),
      text: line.text ?? "",
    })));
  }, [segment?.segment_id, segment?.subtitle_overrides, transcriptLines]);

  return (
    <div className="fixed inset-0 z-40">
      <button className="absolute inset-0 bg-slate-950/20" onClick={onClose} aria-label="关闭复核抽屉" />
      <aside className="absolute right-0 top-0 flex h-full w-full max-w-[460px] flex-col border-l border-slate-200 bg-white shadow-2xl">
        <div className="flex h-16 items-center justify-between border-b border-slate-200 px-5">
          <div>
            <h2 className="text-base font-semibold text-slate-950">片段复核</h2>
            <p className="mt-0.5 text-xs text-slate-400">{clip?.clip_id ?? "未选择片段"}</p>
          </div>
          <button onClick={onClose} className="rounded-lg p-2 text-slate-400 hover:bg-slate-50 hover:text-slate-700" aria-label="关闭">
            <X size={18} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5">
          <div className="aspect-video overflow-hidden rounded-lg bg-slate-950">
            {clip ? (
              <video src={clip.video_url} controls className="h-full w-full bg-black object-contain" />
            ) : (
              <div className="flex h-full flex-col items-center justify-center text-slate-500">
                <Play size={36} />
                <p className="mt-3 text-sm">选择片段后查看预览</p>
              </div>
            )}
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-slate-500">
            <span>{clip ? `${formatDuration(clip.start_time)} - ${formatDuration(clip.end_time)}` : "00:00 - 00:00"}</span>
            <span>{timelineDuration > 0 ? `源视频 ${formatDuration(timelineDuration)} · ${segments.length} 段` : "等待片段数据"}</span>
          </div>
          <SegmentTimeline
            segments={segments}
            duration={timelineDuration}
            selectedIndex={selectedIndex}
            onSelect={onSelectSegment}
          />

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

          {tab === "details" && (
            <div className="mt-5 space-y-4">
              <section className="rounded-lg border border-slate-200 p-4">
                <h3 className="text-sm font-semibold text-slate-900">{clip?.product_name || segment?.product_name || "未命名片段"}</h3>
                <div className="mt-3 flex flex-wrap gap-2">
                  <Chip label={reviewStatusLabel(segment?.review_status ?? "pending")} tone="amber" />
                  <Chip label={transcriptLines.length ? "字幕已生成" : "无字幕"} tone="blue" />
                  <Chip label={clip ? "已导出" : "待导出"} tone="emerald" />
                </div>
                <div className="mt-4 grid grid-cols-3 gap-2">
                  <MetricPill label="置信度" value={formatConfidence(segment?.confidence)} />
                  <MetricPill label="文本句数" value={String(transcriptLines.length)} />
                  <MetricPill label="时长" value={formatDuration(clip?.duration)} />
                </div>
              </section>

              {segment && (
                <section className="rounded-lg border border-slate-200 p-4">
                  <h3 className="text-sm font-semibold text-slate-900">复核操作</h3>
                  <div className="mt-3 grid grid-cols-2 gap-2">
                    <button
                      onClick={() => onPatch(segment.segment_id, { review_status: "approved" })}
                      disabled={patchPending}
                      className="rounded-lg bg-emerald-600 px-3 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      通过
                    </button>
                    <button
                      onClick={() => onPatch(segment.segment_id, { review_status: "skipped" })}
                      disabled={patchPending}
                      className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      跳过
                    </button>
                    <button
                      onClick={() => onPatch(segment.segment_id, { review_status: "needs_adjustment" })}
                      disabled={patchPending}
                      className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      标记需调整
                    </button>
                    <button
                      onClick={() => onReprocess(segment.segment_id)}
                      disabled={isCurrentReprocessing || reprocessPending}
                      className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {isCurrentReprocessing ? "重导出中" : "重跑单片段"}
                    </button>
                  </div>
                  {currentJob?.status && (
                    <div
                      className={cn(
                        "mt-3 rounded-lg p-3 text-xs",
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
                </section>
              )}
            </div>
          )}

          {tab === "subtitles" && (
            <div className="mt-5 rounded-lg border border-slate-200 p-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-semibold text-slate-900">字幕草稿</h3>
                  <p className="mt-1 text-xs text-slate-500">不修改原始 ASR，保存后重导出会使用覆盖草稿。</p>
                </div>
                <span className="rounded-full bg-amber-50 px-2 py-1 text-xs text-amber-700">
                  {segment?.subtitle_overrides?.length ? "已有草稿" : "未保存草稿"}
                </span>
              </div>
              <div className="mt-3 max-h-[420px] space-y-2 overflow-y-auto text-xs text-slate-600">
                {subtitleDraft.length > 0 ? (
                  subtitleDraft.map((line, index) => (
                    <div key={`${line.start_time}-${line.end_time}-${index}`} className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                      <div className="mb-2 flex items-center justify-between gap-2">
                        <span className="font-medium text-slate-500">
                          {formatDuration(line.start_time)} - {formatDuration(line.end_time)}
                        </span>
                        <button
                          onClick={() => setSubtitleDraft((current) => current.filter((_, itemIndex) => itemIndex !== index))}
                          className="text-xs font-medium text-red-600 hover:text-red-700"
                        >
                          删除
                        </button>
                      </div>
                      <textarea
                        value={line.text}
                        onChange={(event) => {
                          const text = event.target.value;
                          setSubtitleDraft((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, text } : item));
                        }}
                        className="min-h-16 w-full resize-y rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm leading-6 text-slate-700 outline-none focus:border-blue-400"
                      />
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-slate-400">暂无可展示字幕文本</p>
                )}
              </div>
              {segment && (
                <div className="mt-4 grid grid-cols-2 gap-2">
                  <button
                    onClick={() => {
                      const source = transcriptLines.map((line) => ({
                        start_time: line.start_time,
                        end_time: line.end_time,
                        text: line.text,
                      }));
                      setSubtitleDraft(source);
                    }}
                    className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
                  >
                    还原原字幕
                  </button>
                  <button
                    onClick={() => onPatch(segment.segment_id, { subtitle_overrides: subtitleDraft.filter((line) => line.text.trim()) })}
                    disabled={patchPending}
                    className="rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    保存字幕草稿
                  </button>
                  <button
                    onClick={() => onReprocess(segment.segment_id)}
                    disabled={isCurrentReprocessing || reprocessPending}
                    className="col-span-2 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-sm font-medium text-blue-700 hover:bg-blue-100 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {isCurrentReprocessing ? "重导出中" : "用草稿重导出单片段"}
                  </button>
                </div>
              )}
            </div>
          )}

          {tab === "advice" && (
            <div className="mt-5 space-y-4">
              <section className="rounded-lg border border-slate-200 p-4">
                <h3 className="text-sm font-semibold text-slate-900">AI 片段建议</h3>
                <div className="mt-3 space-y-3 text-sm text-slate-600">
                  <div className="rounded-lg bg-slate-50 p-3">
                    <div className="text-xs text-slate-400">标题建议</div>
                    <div className="mt-1 font-medium text-slate-900">{segment?.title || `${segment?.product_name || clip?.product_name || "商品"}直播讲解片段`}</div>
                  </div>
                  <div className="rounded-lg bg-slate-50 p-3">
                    <div className="text-xs text-slate-400">时间边界</div>
                    <div className="mt-1 font-medium text-slate-900">
                      {segment ? `${formatDuration(segment.start_time)} - ${formatDuration(segment.end_time)}` : "—"}
                    </div>
                  </div>
                  <div className="rounded-lg bg-slate-50 p-3">
                    <div className="text-xs text-slate-400">复核结论</div>
                    <div className="mt-1 font-medium text-slate-900">{reviewStatusLabel(segment?.review_status ?? "pending")}</div>
                  </div>
                </div>
              </section>
              <section className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-xs text-amber-800">
                字幕编辑建议单独做成“文本修订 → 重生成字幕 → 单片段重导出”的闭环，避免只改前端文本但视频里的烧录字幕不一致。
              </section>
            </div>
          )}
        </div>
      </aside>
    </div>
  );
}
