import { useEffect, useState } from "react";
import { useLocation, useSearchParams } from "react-router-dom";
import { Check, Download, Eye, Film, MoreHorizontal, Search, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { useClipAssets } from "@/hooks/useAdminQueries";
import { API_BASE } from "../api";
import { formatBytes, formatConfidence, formatDate, formatDuration, reviewStatusLabel } from "../format";
import { Header, MetricCard, MetricPill, Pagination } from "../shared";
import type { ClipAsset } from "../types";

type AssetDrawerTab = "preview" | "metadata" | "actions";

export function AssetsPage() {
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  const stateProjectId = (location.state as { projectId?: string } | null)?.projectId;
  const selectedProjectId = searchParams.get("project_id") || stateProjectId;
  const [selectedClips, setSelectedClips] = useState<Set<string>>(new Set());
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [durationFilter, setDurationFilter] = useState("all");
  const [page, setPage] = useState(1);
  const [activeClip, setActiveClip] = useState<ClipAsset | null>(null);
  const [drawerTab, setDrawerTab] = useState<AssetDrawerTab>("preview");
  const pageSize = 12;

  const { data: { items: assets = [], summary = null, total = 0 } = {} } = useClipAssets({
    projectId: selectedProjectId,
    statusFilter,
    query,
    durationFilter,
    page,
    pageSize,
  });

  useEffect(() => {
    if (!stateProjectId || searchParams.get("project_id") === stateProjectId) return;
    const next = new URLSearchParams(searchParams);
    next.set("project_id", stateProjectId);
    setSearchParams(next, { replace: true });
  }, [stateProjectId, searchParams, setSearchParams]);

  const toggleClip = (clipId: string) => {
    setSelectedClips((current) => {
      const next = new Set(current);
      if (next.has(clipId)) next.delete(clipId);
      else next.add(clipId);
      return next;
    });
  };

  const visibleAssets = assets;
  const selectedAssets = assets.filter((clip) => selectedClips.has(clip.clip_id));
  const selectedClipIds = selectedAssets.map((clip) => clip.clip_id);
  const hasSelectedClips = selectedClipIds.length > 0;
  const batchDownloadUrl = `${API_BASE}/api/clips/batch?ids=${selectedClipIds.join(",")}`;
  const groupedAssets = groupAssetsByProject(visibleAssets);

  const clearSelection = () => setSelectedClips(new Set());

  const openDrawer = (clip: ClipAsset, tab: AssetDrawerTab = "preview") => {
    setActiveClip(clip);
    setDrawerTab(tab);
  };

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
                if (!hasSelectedClips) return;
                window.open(batchDownloadUrl, "_blank");
              }}
              disabled={!hasSelectedClips || selectedClipIds.length > 20}
              className={cn(
                "inline-flex items-center gap-2 rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700",
                (!hasSelectedClips || selectedClipIds.length > 20) && "cursor-not-allowed opacity-50 hover:bg-blue-600",
              )}
            >
              <Download size={16} />
              批量下载
            </button>
          </>
        }
      />
      <main className="space-y-5 p-4 sm:p-6">
        <section className="rounded-lg border border-slate-200 bg-white p-4">
          <div className="flex flex-wrap gap-3">
            <label className="flex min-w-72 flex-1 items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-500">
              <Search size={16} />
              <input
                value={query}
                onChange={(event) => {
                  setQuery(event.target.value);
                  clearSelection();
                  setPage(1);
                }}
                placeholder="搜索商品名 / 项目 / 片段 ID"
                className="min-w-0 flex-1 bg-transparent text-slate-700 outline-none placeholder:text-slate-400"
              />
            </label>
            <select
              value={statusFilter}
              onChange={(event) => {
                setStatusFilter(event.target.value);
                clearSelection();
                setPage(1);
              }}
              className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-600"
            >
              <option value="all">全部状态</option>
              <option value="pending">待复核</option>
              <option value="approved">已通过</option>
              <option value="skipped">已跳过</option>
              <option value="needs_adjustment">需调整</option>
            </select>
            <select
              value={durationFilter}
              onChange={(event) => {
                setDurationFilter(event.target.value);
                clearSelection();
                setPage(1);
              }}
              className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-600"
            >
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

        <section className="rounded-lg border border-slate-200 bg-white">
          <div className="border-b border-slate-100 px-4 py-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-sm font-semibold text-slate-900">资产集合</h2>
              <div className="flex items-center gap-2 text-xs text-slate-500">
                <span>当前页 {visibleAssets.length} 个片段</span>
                <button
                  onClick={() => setSelectedClips(new Set(visibleAssets.map((clip) => clip.clip_id)))}
                  disabled={visibleAssets.length === 0}
                  className="rounded-lg border border-slate-200 px-2.5 py-1.5 font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  选择当前页
                </button>
              </div>
            </div>
          </div>

          {visibleAssets.length === 0 ? (
            <div className="rounded-lg border border-dashed border-slate-200 bg-white py-16 text-center text-sm text-slate-400">
              暂无匹配片段资产。
            </div>
          ) : (
            <div className="space-y-5 p-4">
              {groupedAssets.map((group) => (
                <section key={group.taskId} className="space-y-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="min-w-0">
                      <h3 className="truncate text-sm font-semibold text-slate-900">{group.title}</h3>
                      <p className="mt-0.5 text-xs text-slate-400">
                        {group.items.length} 个片段 · {formatDate(group.latestCreatedAt)}
                      </p>
                    </div>
                    <button
                      onClick={() => {
                        setSelectedClips((current) => {
                          const next = new Set(current);
                          group.items.forEach((clip) => next.add(clip.clip_id));
                          return next;
                        });
                      }}
                      className="rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
                    >
                      选择本组
                    </button>
                  </div>
                  <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-4">
                    {group.items.map((clip) => (
                      <AssetCard
                        key={clip.clip_id}
                        clip={clip}
                        selected={selectedClips.has(clip.clip_id)}
                        active={activeClip?.clip_id === clip.clip_id}
                        onToggle={() => toggleClip(clip.clip_id)}
                        onOpen={() => openDrawer(clip)}
                        onMore={() => openDrawer(clip, "actions")}
                      />
                    ))}
                  </div>
                </section>
              ))}
            </div>
          )}

          <Pagination
            page={page}
            pageSize={pageSize}
            total={total}
            onPageChange={(nextPage) => {
              clearSelection();
              setPage(nextPage);
            }}
          />
        </section>
      </main>

      <AssetDetailDrawer
        clip={activeClip}
        tab={drawerTab}
        onTabChange={setDrawerTab}
        onClose={() => setActiveClip(null)}
        selected={activeClip ? selectedClips.has(activeClip.clip_id) : false}
        onToggleSelected={() => activeClip && toggleClip(activeClip.clip_id)}
      />
      <SelectionBar clips={selectedAssets} batchDownloadUrl={batchDownloadUrl} onClear={clearSelection} />
    </>
  );
}

function groupAssetsByProject(assets: ClipAsset[]) {
  const groups = new Map<string, ClipAsset[]>();
  assets.forEach((clip) => {
    const key = clip.task_id || "unknown";
    groups.set(key, [...(groups.get(key) ?? []), clip]);
  });

  return Array.from(groups.entries()).map(([taskId, items]) => {
    const latestCreatedAt = items
      .map((clip) => clip.created_at)
      .filter(Boolean)
      .sort()
      .at(-1);
    return {
      taskId,
      items,
      latestCreatedAt,
      title: `项目 ${taskId.slice(0, 8)}`,
    };
  });
}

function AssetCard({
  clip,
  selected,
  active,
  onToggle,
  onOpen,
  onMore,
}: {
  clip: ClipAsset;
  selected: boolean;
  active: boolean;
  onToggle: () => void;
  onOpen: () => void;
  onMore: () => void;
}) {
  return (
    <article className={cn("overflow-hidden rounded-lg border bg-white", active ? "border-blue-300 ring-2 ring-blue-100" : "border-slate-200")}>
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
          <span className="absolute left-2 top-2 rounded-full bg-white/95 px-2 py-0.5 text-xs font-medium text-slate-700 shadow-sm">
            {reviewStatusLabel(clip.review_status)}
          </span>
        </div>
        <div className="p-3">
          <div className="truncate text-sm font-medium text-slate-900">{clip.product_name || "未命名片段"}</div>
          <div className="mt-1 truncate text-xs text-slate-400">{clip.clip_id}</div>
          <div className="mt-3 grid grid-cols-3 gap-2 text-xs text-slate-500">
            <span>{formatBytes(clip.file_size)}</span>
            <span>{formatConfidence(clip.confidence)}</span>
            <span>{formatDate(clip.created_at)}</span>
          </div>
        </div>
      </button>
      <div className="grid grid-cols-[36px_1fr_36px] gap-2 border-t border-slate-100 p-3">
        <button
          onClick={onToggle}
          className={cn(
            "flex h-9 items-center justify-center rounded-lg border text-sm",
            selected ? "border-blue-200 bg-blue-50 text-blue-700" : "border-slate-200 text-slate-500 hover:bg-slate-50",
          )}
          aria-label={selected ? "取消选择" : "选择片段"}
        >
          {selected ? <Check size={15} /> : <span className="h-3.5 w-3.5 rounded border border-current" />}
        </button>
        <a
          href={clip.video_url}
          download
          className="inline-flex min-w-0 items-center justify-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
        >
          <Download size={15} />
          下载
        </a>
        <button onClick={onMore} className="rounded-lg border border-slate-200 px-2 py-2 text-slate-600 hover:bg-slate-50" aria-label="更多">
          <MoreHorizontal size={15} />
        </button>
      </div>
    </article>
  );
}

function AssetDetailDrawer({
  clip,
  tab,
  onTabChange,
  onClose,
  selected,
  onToggleSelected,
}: {
  clip: ClipAsset | null;
  tab: AssetDrawerTab;
  onTabChange: (tab: AssetDrawerTab) => void;
  onClose: () => void;
  selected: boolean;
  onToggleSelected: () => void;
}) {
  if (!clip) return null;

  const tabs: { value: AssetDrawerTab; label: string }[] = [
    { value: "preview", label: "预览" },
    { value: "metadata", label: "元数据" },
    { value: "actions", label: "操作" },
  ];

  return (
    <div className="fixed inset-0 z-40">
      <button className="absolute inset-0 bg-slate-950/20" onClick={onClose} aria-label="关闭资产详情" />
      <aside className="absolute right-0 top-0 flex h-full w-full max-w-[460px] flex-col border-l border-slate-200 bg-white shadow-2xl">
        <div className="flex h-16 items-center justify-between border-b border-slate-200 px-5">
          <div className="min-w-0">
            <h2 className="truncate text-base font-semibold text-slate-950">片段详情</h2>
            <p className="mt-0.5 truncate text-xs text-slate-400">{clip.clip_id}</p>
          </div>
          <button onClick={onClose} className="rounded-lg p-2 text-slate-400 hover:bg-slate-50 hover:text-slate-700" aria-label="关闭">
            <X size={18} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5">
          <div className="aspect-video overflow-hidden rounded-lg bg-slate-950">
            {clip.has_video ? (
              <video src={clip.video_url} controls className="h-full w-full bg-black object-contain" />
            ) : (
              <div className="flex h-full items-center justify-center text-slate-500">
                <Film size={32} />
              </div>
            )}
          </div>
          <div className="mt-4">
            <h3 className="text-sm font-semibold text-slate-900">{clip.product_name || "未命名片段"}</h3>
            <div className="mt-2 flex flex-wrap gap-2">
              <span className="rounded-full bg-blue-50 px-2 py-1 text-xs font-medium text-blue-700">{reviewStatusLabel(clip.review_status)}</span>
              <span className="rounded-full bg-slate-100 px-2 py-1 text-xs font-medium text-slate-600">{formatDuration(clip.duration)}</span>
              <span className="rounded-full bg-slate-100 px-2 py-1 text-xs font-medium text-slate-600">{formatBytes(clip.file_size)}</span>
            </div>
          </div>

          <div className="mt-5 flex border-b border-slate-200">
            {tabs.map((item) => (
              <button
                key={item.value}
                onClick={() => onTabChange(item.value)}
                className={cn(
                  "mr-6 border-b-2 px-1 pb-2 text-sm font-medium",
                  tab === item.value ? "border-blue-600 text-blue-700" : "border-transparent text-slate-500 hover:text-slate-800",
                )}
              >
                {item.label}
              </button>
            ))}
          </div>

          {tab === "preview" && (
            <div className="mt-5 grid grid-cols-3 gap-2">
              <MetricPill label="置信度" value={formatConfidence(clip.confidence)} />
              <MetricPill label="开始" value={formatDuration(clip.start_time)} />
              <MetricPill label="结束" value={formatDuration(clip.end_time)} />
            </div>
          )}

          {tab === "metadata" && (
            <div className="mt-5 space-y-3 rounded-lg border border-slate-200 p-4 text-sm">
              <MetadataRow label="项目 ID" value={clip.task_id} />
              <MetadataRow label="片段 ID" value={clip.clip_id} />
              <MetadataRow label="Segment ID" value={clip.segment_id} />
              <MetadataRow label="创建时间" value={formatDate(clip.created_at)} />
              <MetadataRow label="文件大小" value={formatBytes(clip.file_size)} />
              <MetadataRow label="缩略图" value={clip.has_thumbnail ? "已生成" : "未生成"} />
            </div>
          )}

          {tab === "actions" && (
            <div className="mt-5 space-y-2">
              <a
                href={clip.video_url}
                download
                className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
              >
                <Download size={15} />
                下载片段
              </a>
              <button
                onClick={() => window.open(clip.video_url, "_blank")}
                className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                <Eye size={15} />
                新窗口预览
              </button>
              <button
                onClick={onToggleSelected}
                className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                {selected ? "从批量选择移除" : "加入批量选择"}
              </button>
            </div>
          )}
        </div>
      </aside>
    </div>
  );
}

function MetadataRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-[88px_minmax(0,1fr)] gap-3 border-b border-slate-100 pb-2 last:border-b-0 last:pb-0">
      <span className="text-xs text-slate-400">{label}</span>
      <span className="break-all text-sm font-medium text-slate-800">{value || "—"}</span>
    </div>
  );
}

function SelectionBar({
  clips,
  batchDownloadUrl,
  onClear,
}: {
  clips: ClipAsset[];
  batchDownloadUrl: string;
  onClear: () => void;
}) {
  if (clips.length === 0) return null;

  const selectedCount = clips.length;
  const overLimit = selectedCount > 20;
  const totalDuration = clips.reduce((sum, clip) => sum + clip.duration, 0);
  const totalSize = clips.reduce((sum, clip) => sum + clip.file_size, 0);

  return (
    <div className="fixed inset-x-0 bottom-4 z-30 px-4">
      <div className="mx-auto flex max-w-3xl flex-col gap-3 rounded-lg border border-slate-200 bg-white p-3 shadow-2xl sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <div className="text-sm font-semibold text-slate-900">已选择 {selectedCount} 个片段</div>
          <div className={cn("mt-0.5 text-xs", overLimit ? "text-amber-600" : "text-slate-500")}>
            总时长 {formatDuration(totalDuration)} · 预计 {formatBytes(totalSize)}
            {overLimit ? " · 批量 ZIP 单次最多 20 个" : ""}
          </div>
        </div>
        <div className="flex shrink-0 gap-2">
          <button onClick={onClear} className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">
            清空
          </button>
          <button
            onClick={() => {
              if (overLimit) return;
              window.open(batchDownloadUrl, "_blank");
            }}
            disabled={overLimit}
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-blue-600"
          >
            <Download size={15} />
            批量下载
          </button>
        </div>
      </div>
    </div>
  );
}
