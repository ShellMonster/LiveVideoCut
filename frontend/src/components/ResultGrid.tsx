import { useEffect, useState } from "react";
import { useTaskStore, type ClipData } from "@/stores/taskStore";
import { VideoPreview } from "./VideoPreview";
import { API_BASE } from "./admin/api";

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
}

function ClipCard({
  clip,
  selected,
  onToggle,
  onPlay,
}: {
  clip: ClipData;
  selected: boolean;
  onToggle: () => void;
  onPlay: () => void;
}) {
  return (
    <div className="group relative rounded-lg border border-slate-200 bg-white overflow-hidden transition-shadow hover:shadow-md">
      <div className="relative aspect-video bg-slate-100">
        {clip.has_thumbnail ? (
          <img
            src={clip.thumbnail_url}
            alt={clip.product_name}
            className="h-full w-full object-cover"
            loading="lazy"
          />
        ) : (
          <div className="flex h-full items-center justify-center text-slate-400">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <rect x="2" y="2" width="20" height="20" rx="2" />
              <circle cx="12" cy="12" r="3" />
            </svg>
          </div>
        )}

        <div className="absolute inset-0 flex items-center justify-center bg-black/0 opacity-0 transition-all group-hover:bg-black/20 group-hover:opacity-100">
          <button
            onClick={onPlay}
            className="flex h-12 w-12 items-center justify-center rounded-full bg-white/90 text-slate-800 shadow-lg transition-transform hover:scale-105"
            aria-label="播放预览"
          >
            <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
              <path d="M6 4l10 6-10 6V4z" />
            </svg>
          </button>
        </div>

        <label className="absolute left-2 top-2 flex items-center">
          <input
            type="checkbox"
            checked={selected}
            onChange={onToggle}
            className="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
          />
        </label>

        <span className="absolute bottom-2 right-2 rounded bg-black/70 px-1.5 py-0.5 text-xs font-medium text-white">
          {formatDuration(clip.duration)}
        </span>
      </div>

      <div className="p-3">
        <p className="truncate text-sm font-medium text-slate-900">{clip.product_name}</p>
        <div className="mt-2 flex items-center justify-between">
          <span className="text-xs text-slate-500">
            {formatDuration(clip.start_time)} - {formatDuration(clip.end_time)}
          </span>
          <a
            href={clip.video_url}
            download
            className="rounded p-1 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600"
            aria-label="下载"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M8 2v8m0 0l-3-3m3 3l3-3M3 12h10" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </a>
        </div>
      </div>
    </div>
  );
}

export function ResultGrid() {
  const { clips, clipsLoading, selectedClips, fetchClips, toggleClipSelection, selectAllClips, clearSelection, taskId, status } =
    useTaskStore();
  const [previewClip, setPreviewClip] = useState<ClipData | null>(null);

  useEffect(() => {
    if (taskId && status === "done") {
      fetchClips(taskId);
    }
  }, [taskId, status, fetchClips]);

  if (clipsLoading) {
    return (
      <div className="grid gap-4" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))" }}>
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="animate-pulse rounded-lg border border-slate-200 bg-white">
            <div className="aspect-video bg-slate-200" />
            <div className="p-3 space-y-2">
              <div className="h-4 w-3/4 rounded bg-slate-200" />
              <div className="h-3 w-1/2 rounded bg-slate-200" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (!clips || clips.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-slate-400">
        <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1">
          <rect x="2" y="2" width="20" height="20" rx="2" />
          <path d="M10 8l6 4-6 4V8z" />
        </svg>
        <p className="mt-4 text-sm">暂无剪辑结果</p>
      </div>
    );
  }

  const allSelected = clips.length > 0 && selectedClips.size === clips.length;

  const handleBatchDownload = () => {
    if (selectedClips.size === 0) return;
    const ids = Array.from(selectedClips).join(",");
    window.open(`${API_BASE}/api/clips/batch?ids=${ids}`, "_blank");
  };

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-slate-600">
            <input
              type="checkbox"
              checked={allSelected}
              onChange={allSelected ? clearSelection : selectAllClips}
              className="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
            />
            全选
          </label>
          <span className="text-sm text-slate-400">
            已选 {selectedClips.size}/{clips.length}
          </span>
        </div>

        {selectedClips.size > 0 && (
          <button
            onClick={handleBatchDownload}
            className="rounded-md bg-blue-600 px-4 py-1.5 text-sm font-medium text-white transition-colors hover:bg-blue-700"
          >
            下载所选 ({selectedClips.size})
          </button>
        )}
      </div>

      <div className="grid gap-4" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))" }}>
        {clips.map((clip) => (
          <ClipCard
            key={clip.clip_id}
            clip={clip}
            selected={selectedClips.has(clip.clip_id)}
            onToggle={() => toggleClipSelection(clip.clip_id)}
            onPlay={() => setPreviewClip(clip)}
          />
        ))}
      </div>

      <VideoPreview clip={previewClip} onClose={() => setPreviewClip(null)} />
    </div>
  );
}
