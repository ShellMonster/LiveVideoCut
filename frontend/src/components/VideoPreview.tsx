import { useEffect, useRef } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import type { ClipData } from "@/stores/taskStore";

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
}

export function VideoPreview({
  clip,
  onClose,
}: {
  clip: ClipData | null;
  onClose: () => void;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const open = clip !== null;

  useEffect(() => {
    if (open && videoRef.current) {
      videoRef.current.play().catch(() => {});
    }
  }, [open]);

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose(); }}>
      <DialogContent className="max-w-3xl p-0 overflow-hidden">
        <DialogHeader className="px-6 pt-5 pb-3">
          <div className="flex items-center justify-between pr-6">
            <DialogTitle className="truncate">{clip?.product_name ?? ""}</DialogTitle>
            {clip && (
              <span className="ml-3 shrink-0 text-sm text-slate-400">
                {formatDuration(clip.duration)}
              </span>
            )}
          </div>
        </DialogHeader>

        {clip && (
          <div className="bg-black">
            <video
              ref={videoRef}
              src={clip.video_url}
              controls
              className="w-full max-h-[70vh]"
              preload="metadata"
            />
          </div>
        )}

        {clip && (
          <div className="flex items-center justify-end gap-3 border-t border-slate-100 px-6 py-3">
            <a
              href={clip.video_url}
              download
              className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700"
            >
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M8 2v8m0 0l-3-3m3 3l3-3M3 12h10" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              下载视频
            </a>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
