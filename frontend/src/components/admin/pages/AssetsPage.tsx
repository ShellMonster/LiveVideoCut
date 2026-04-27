import { useState } from "react";
import { useLocation } from "react-router-dom";
import { Download, Eye, Film, Search } from "lucide-react";
import { useClipAssets } from "@/hooks/useAdminQueries";
import { API_BASE } from "../api";
import { formatBytes, formatDuration, reviewStatusLabel } from "../format";
import { Header, MetricCard } from "../shared";

export function AssetsPage() {
  const location = useLocation();
  const selectedProjectId = (location.state as { projectId?: string } | null)?.projectId;
  const [selectedClips, setSelectedClips] = useState<Set<string>>(new Set());
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [durationFilter, setDurationFilter] = useState("all");

  const { data: { items: assets = [], summary = null } = {} } = useClipAssets(selectedProjectId, statusFilter);

  const toggleClip = (clipId: string) => {
    setSelectedClips((current) => {
      const next = new Set(current);
      if (next.has(clipId)) next.delete(clipId);
      else next.add(clipId);
      return next;
    });
  };
  const normalizedQuery = query.trim().toLowerCase();
  const visibleAssets = assets.filter((clip) => {
    const matchesQuery =
      !normalizedQuery ||
      [clip.product_name, clip.task_id, clip.clip_id, clip.segment_id].some((value) =>
        value.toLowerCase().includes(normalizedQuery),
      );
    const matchesDuration =
      durationFilter === "all" ||
      (durationFilter === "short" && clip.duration < 30) ||
      (durationFilter === "medium" && clip.duration >= 30 && clip.duration <= 90) ||
      (durationFilter === "long" && clip.duration > 90);
    return matchesQuery && matchesDuration;
  });

  return (
    <>
      <Header
        title="片段资产"
        description="浏览、筛选、批量下载和复用已生成的短视频片段"
        action={
          <>
            <button
              onClick={() => {
                const params = new URLSearchParams({ limit: "500" });
                if (selectedProjectId) params.set("project_id", selectedProjectId);
                window.open(`${API_BASE}/api/assets/clips?${params.toString()}`, "_blank");
              }}
              className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50"
            >
              导出清单
            </button>
            <button
              onClick={() => {
                if (selectedClips.size === 0) return;
                window.open(`${API_BASE}/api/clips/batch?ids=${Array.from(selectedClips).join(",")}`, "_blank");
              }}
              className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
            >
              <Download size={16} />
              批量下载
            </button>
          </>
        }
      />
      <main className="space-y-5 p-6">
        <section className="rounded-lg border border-slate-200 bg-white p-4">
          <div className="flex flex-wrap gap-3">
            <label className="flex min-w-72 flex-1 items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-500">
              <Search size={16} />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="搜索商品名 / 项目 / 片段 ID"
                className="min-w-0 flex-1 bg-transparent text-slate-700 outline-none placeholder:text-slate-400"
              />
            </label>
            <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-600">
              <option value="all">全部状态</option>
              <option value="pending">待复核</option>
              <option value="approved">已通过</option>
              <option value="skipped">已跳过</option>
              <option value="needs_adjustment">需调整</option>
            </select>
            <select value={durationFilter} onChange={(event) => setDurationFilter(event.target.value)} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-600">
              <option value="all">全部时长</option>
              <option value="short">30 秒内</option>
              <option value="medium">30-90 秒</option>
              <option value="long">90 秒以上</option>
            </select>
          </div>
        </section>

        <section className="grid gap-4 lg:grid-cols-4">
          <MetricCard label="全部片段" value={String(summary?.total ?? assets.length)} hint="跨项目统计" />
          <MetricCard label="待复核" value={String(summary?.pending ?? 0)} hint="等待人工确认" />
          <MetricCard label="已通过" value={String(summary?.approved ?? 0)} hint="可交付片段" />
          <MetricCard label="可下载" value={String(summary?.downloadable ?? 0)} hint="文件存在的片段" />
        </section>

        <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_300px]">
          <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-4">
            {visibleAssets.length === 0 ? (
              <div className="col-span-full rounded-lg border border-dashed border-slate-200 bg-white py-16 text-center text-sm text-slate-400">
                暂无匹配片段资产。
              </div>
            ) : (
              visibleAssets.map((clip) => (
                <div key={clip.clip_id} className="overflow-hidden rounded-lg border border-slate-200 bg-white">
                  <div className="relative aspect-video bg-slate-100">
                    {clip.has_thumbnail ? (
                      <img src={clip.thumbnail_url} alt="" className="h-full w-full object-cover" />
                    ) : (
                      <div className="flex h-full items-center justify-center text-slate-300">
                        <Film size={28} />
                      </div>
                    )}
                    <label className="absolute left-2 top-2">
                      <input
                        type="checkbox"
                        checked={selectedClips.has(clip.clip_id)}
                        onChange={() => toggleClip(clip.clip_id)}
                        className="h-4 w-4 rounded border-slate-300 text-blue-600"
                      />
                    </label>
                    <span className="absolute bottom-2 right-2 rounded bg-black/70 px-1.5 py-0.5 text-xs text-white">
                      {formatDuration(clip.duration)}
                    </span>
                    <span className="absolute right-2 top-2 rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700">
                      {reviewStatusLabel(clip.review_status)}
                    </span>
                  </div>
                  <div className="p-3">
                    <div className="truncate text-sm font-medium text-slate-900">{clip.product_name}</div>
                    <div className="mt-1 text-xs text-slate-400">{clip.clip_id}</div>
                    <div className="mt-3 flex gap-2">
                      <a
                        href={clip.video_url}
                        download
                        className="inline-flex flex-1 items-center justify-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
                      >
                        <Download size={15} />
                        下载
                      </a>
                      <button
                        onClick={() => window.open(clip.video_url, "_blank")}
                        className="rounded-lg border border-slate-200 px-3 py-2 text-slate-600 hover:bg-slate-50"
                      >
                        <Eye size={15} />
                      </button>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>

          <aside className="rounded-lg border border-slate-200 bg-white p-4">
            <h2 className="text-sm font-semibold text-slate-900">批量操作</h2>
            <div className="mt-4 rounded-lg bg-slate-50 p-3">
              <div className="text-xs text-slate-500">已选片段</div>
              <div className="mt-1 text-2xl font-semibold text-slate-900">{selectedClips.size}</div>
            </div>
            <div className="mt-4 space-y-2 text-sm text-slate-500">
              <div className="flex justify-between">
                <span>总时长</span>
                <span>{formatDuration(assets.filter((clip) => selectedClips.has(clip.clip_id)).reduce((sum, clip) => sum + clip.duration, 0))}</span>
              </div>
              <div className="flex justify-between">
                <span>预计 ZIP</span>
                <span>{formatBytes(assets.filter((clip) => selectedClips.has(clip.clip_id)).reduce((sum, clip) => sum + clip.file_size, 0))}</span>
              </div>
            </div>
            <button
              onClick={() => {
                if (selectedClips.size === 0) return;
                window.open(`${API_BASE}/api/clips/batch?ids=${Array.from(selectedClips).join(",")}`, "_blank");
              }}
              className="mt-5 w-full rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
            >
              下载所选
            </button>
            <button
              onClick={() => setSelectedClips(new Set())}
              className="mt-2 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
            >
              清空选择
            </button>
          </aside>
        </section>
      </main>
    </>
  );
}
