import { useRef, useState } from "react";
import { Pause, Play, RefreshCw, SlidersHorizontal, Trash2, Upload, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { useSettingsStore } from "@/stores/settingsStore";
import { useConfirmStore } from "@/stores/confirmStore";
import { API_BASE } from "../api";
import { useMusicLibrary, useUploadTrack, useDeleteTrack, useSaveTrackTags } from "@/hooks/useAdminQueries";
import { editableCategoryOptions, editableMoodOptions } from "../constants";
import { formatDuration } from "../format";
import {
  Field,
  Header,
  InputField,
  MetricCard,
  MultiSelectField,
  Pagination,
  SelectField,
  TagGroup,
} from "../shared";
import type { MusicTrack } from "../types";

const emptyTagDraft = {
  title: "",
  mood: [] as string[],
  categories: [] as string[],
  tempo: "medium",
  energy: "medium",
  genre: "",
};

const tagDraftFromTrack = (track: MusicTrack | null) => {
  if (!track) return { ...emptyTagDraft };
  return {
    title: track.title,
    mood: track.mood,
    categories: track.categories,
    tempo: track.tempo || "medium",
    energy: track.energy || "medium",
    genre: track.genre || "",
  };
};

export function AdminMusicPage() {
  const bgmVolume = useSettingsStore((state) => state.bgmVolume);
  const { data: tracks = [], isLoading: loading, refetch: loadTracks } = useMusicLibrary();
  const uploadTrack = useUploadTrack();
  const deleteTrack = useDeleteTrack();
  const saveTags = useSaveTrackTags();
  const confirm = useConfirmStore((state) => state.confirm);

  const [playingId, setPlayingId] = useState<string | null>(null);
  const [audioProgress, setAudioProgress] = useState(0);
  const [selectedTrack, setSelectedTrack] = useState<MusicTrack | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [sourceFilter, setSourceFilter] = useState("all");
  const [query, setQuery] = useState("");
  const [tagDraft, setTagDraft] = useState(() => tagDraftFromTrack(null));
  const [page, setPage] = useState(1);
  const pageSize = 10;
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const selectTrack = (track: MusicTrack | null, openDrawer = true) => {
    setSelectedTrack(track);
    setTagDraft(tagDraftFromTrack(track));
    if (openDrawer && track) setDrawerOpen(true);
  };

  const userCount = tracks.filter((track) => track.source === "user").length;
  const builtInCount = tracks.filter((track) => track.source === "built-in").length;
  const categoryCount = new Set(tracks.flatMap((track) => track.categories)).size;
  const filteredTracks = tracks.filter((track) => {
    if (sourceFilter !== "all" && track.source !== sourceFilter) return false;
    if (!query.trim()) return true;
    const text = `${track.title} ${track.mood.join(" ")} ${track.categories.join(" ")} ${track.genre}`.toLowerCase();
    return text.includes(query.trim().toLowerCase());
  });
  const visibleTracks = filteredTracks.slice((page - 1) * pageSize, page * pageSize);
  const currentTrack = tracks.find((track) => track.id === playingId) ?? selectedTrack;

  const togglePlay = (track: MusicTrack) => {
    selectTrack(track, false);
    const audio = audioRef.current;
    if (!audio) return;
    if (playingId === track.id) {
      audio.pause();
      setPlayingId(null);
      return;
    }
    audio.src = `${API_BASE}/api/music/${track.id}/audio`;
    audio.play().then(() => setPlayingId(track.id)).catch(() => setPlayingId(null));
  };

  const handleUpload = async (file: File) => {
    const newTrack = await uploadTrack.mutateAsync(file);
    selectTrack(newTrack ?? null, true);
  };

  const handleDelete = async (trackId: string) => {
    const confirmed = await confirm({
      title: "删除用户曲目",
      description: "删除后这首上传音乐会从曲库移除，已生成的视频不会受影响。",
      confirmLabel: "删除",
      danger: true,
    });
    if (!confirmed) return;
    await deleteTrack.mutateAsync(trackId).then(() => {
      if (selectedTrack?.id === trackId) {
        setSelectedTrack(null);
        setDrawerOpen(false);
      }
      if (playingId === trackId) setPlayingId(null);
    }).catch(() => {});
  };

  const handleSaveTags = async () => {
    if (!selectedTrack || selectedTrack.source !== "user") return;
    const updated = await saveTags.mutateAsync({
      trackId: selectedTrack.id,
      tags: {
        title: tagDraft.title.trim() || selectedTrack.title,
        mood: tagDraft.mood,
        categories: tagDraft.categories,
        tempo: tagDraft.tempo,
        energy: tagDraft.energy,
        genre: tagDraft.genre.trim(),
      },
    });
    selectTrack(updated, true);
  };

  return (
    <>
      <Header
        title="音乐库"
        description="管理内置曲库和用户上传 BGM，配置商品类型匹配标签"
        action={
          <>
            <button
              onClick={() => void loadTracks()}
              className="inline-flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50"
            >
              <RefreshCw size={16} />
              刷新曲库
            </button>
            <button
              onClick={() => fileInputRef.current?.click()}
              className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
            >
              <Upload size={16} />
              上传音乐
            </button>
          </>
        }
      />
      <main className="space-y-5 p-4 pb-28 sm:p-6 sm:pb-28">
        <input
          ref={fileInputRef}
          type="file"
          accept=".mp3,audio/mpeg"
          className="hidden"
          onChange={(event) => {
            const file = event.target.files?.[0];
            event.target.value = "";
            if (file) void handleUpload(file);
          }}
        />
        <audio
          ref={audioRef}
          onTimeUpdate={(event) => {
            const audio = event.currentTarget;
            setAudioProgress(audio.duration ? Math.min(100, (audio.currentTime / audio.duration) * 100) : 0);
          }}
          onEnded={() => {
            setPlayingId(null);
            setAudioProgress(0);
          }}
        />

        <section className="grid gap-4 lg:grid-cols-4">
          <MetricCard label="我的音乐" value={String(userCount)} hint="用户上传曲目" />
          <MetricCard label="内置曲目" value={String(builtInCount)} hint="系统预置 BGM" />
          <MetricCard label="已匹配分类" value={String(categoryCount)} hint="商品类型标签" />
          <MetricCard label="默认音量" value={`${Math.round(bgmVolume * 100)}%`} hint="导出混音配置" />
        </section>

        <section className="rounded-lg border border-slate-200 bg-white p-4">
          <div className="flex flex-wrap gap-3">
            <input
              value={query}
              onChange={(event) => {
                setQuery(event.target.value);
                setPage(1);
              }}
              placeholder="搜索曲目 / mood / 商品分类"
              className="min-w-72 flex-1 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700 outline-none placeholder:text-slate-400"
            />
            <select
              value={sourceFilter}
              onChange={(event) => {
                setSourceFilter(event.target.value);
                setPage(1);
              }}
              className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-600"
            >
              <option value="all">全部来源</option>
              <option value="user">我的音乐</option>
              <option value="built-in">内置曲目</option>
            </select>
          </div>
        </section>

        <section className="overflow-hidden rounded-lg border border-slate-200 bg-white">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-4 py-3">
            <div>
              <h2 className="text-sm font-semibold text-slate-900">曲目列表</h2>
              <p className="mt-0.5 text-xs text-slate-400">播放曲目或打开标签编辑抽屉。</p>
            </div>
            <button
              onClick={() => fileInputRef.current?.click()}
              className="rounded-lg border border-dashed border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              上传 MP3
            </button>
          </div>

          <div className="overflow-x-auto">
            <div className="grid min-w-[1080px] grid-cols-[minmax(220px,1fr)_220px_110px_90px_minmax(260px,1.2fr)_120px] gap-4 border-b border-slate-100 bg-slate-50 px-4 py-3 text-xs font-medium text-slate-500">
              <div>曲目</div>
              <div>波形</div>
              <div>来源</div>
              <div>时长</div>
              <div>Mood / 商品分类</div>
              <div className="text-right">操作</div>
            </div>
            {loading ? (
              <p className="py-12 text-center text-sm text-slate-400">加载曲库中...</p>
            ) : filteredTracks.length === 0 ? (
              <p className="py-12 text-center text-sm text-slate-400">暂无匹配曲目</p>
            ) : (
              visibleTracks.map((track) => (
                <TrackRow
                  key={track.id}
                  track={track}
                  selected={selectedTrack?.id === track.id}
                  playing={playingId === track.id}
                  onSelect={() => selectTrack(track, true)}
                  onPlay={() => togglePlay(track)}
                  onDelete={() => void handleDelete(track.id)}
                />
              ))
            )}
          </div>
          <Pagination page={page} pageSize={pageSize} total={filteredTracks.length} onPageChange={setPage} />
        </section>
      </main>

      <TrackEditorDrawer
        open={drawerOpen}
        track={selectedTrack}
        draft={tagDraft}
        onDraftChange={setTagDraft}
        savePending={saveTags.isPending}
        onClose={() => setDrawerOpen(false)}
        onSave={() => void handleSaveTags()}
        onDelete={(track) => void handleDelete(track.id)}
      />
      <MusicPlayerBar track={currentTrack} playing={!!playingId} progress={audioProgress} volume={bgmVolume} onPlay={(track) => togglePlay(track)} />
    </>
  );
}

function TrackRow({
  track,
  selected,
  playing,
  onSelect,
  onPlay,
  onDelete,
}: {
  track: MusicTrack;
  selected: boolean;
  playing: boolean;
  onSelect: () => void;
  onPlay: () => void;
  onDelete: () => void;
}) {
  return (
    <article className={cn("grid min-w-[1080px] grid-cols-[minmax(220px,1fr)_220px_110px_90px_minmax(260px,1.2fr)_120px] gap-4 border-b border-slate-100 px-4 py-3 last:border-b-0 hover:bg-slate-50 items-center", selected && "bg-blue-50/40")}>
      <div className="flex min-w-0 items-center gap-3">
        <button
          onClick={onPlay}
          className={cn("flex h-9 w-9 shrink-0 items-center justify-center rounded-full", playing ? "bg-blue-600 text-white" : "bg-slate-100 text-slate-600 hover:bg-blue-50 hover:text-blue-700")}
          aria-label={playing ? "暂停" : "播放"}
        >
          {playing ? <Pause size={15} /> : <Play size={15} />}
        </button>
        <button onClick={onSelect} className="min-w-0 text-left">
          <div className="truncate text-sm font-semibold text-slate-900">{track.title}</div>
          <div className="mt-1 text-xs text-slate-400">{track.genre || "未设置风格"} · {formatDuration(track.duration_s)}</div>
        </button>
      </div>
      <Waveform active={playing} seed={track.id} />
      <div>
        <span className={cn("rounded-full px-2 py-1 text-xs font-medium", track.source === "user" ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-600")}>
          {track.source === "user" ? "我的" : "内置"}
        </span>
      </div>
      <div className="text-xs text-slate-500">{formatDuration(track.duration_s)}</div>
      <div className="flex min-w-0 flex-wrap gap-1.5">
        {(track.mood.length ? track.mood.slice(0, 3) : ["—"]).map((item) => (
          <span key={item} className="rounded-full bg-blue-50 px-2 py-1 text-xs font-medium text-blue-700">{item}</span>
        ))}
        {(track.categories.length ? track.categories.slice(0, 2) : ["default"]).map((item) => (
          <span key={item} className="rounded-full bg-slate-100 px-2 py-1 text-xs font-medium text-slate-600">{item}</span>
        ))}
      </div>
      <div className="grid grid-cols-2 gap-2">
        <button onClick={onSelect} className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-slate-200 px-2 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50">
          <SlidersHorizontal size={14} />
          编辑
        </button>
        <button
          onClick={onDelete}
          disabled={track.source !== "user"}
          className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-red-100 px-2 py-1.5 text-xs font-medium text-red-600 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-white"
        >
          <Trash2 size={14} />
          删除
        </button>
      </div>
    </article>
  );
}

function Waveform({ active, seed }: { active: boolean; seed: string }) {
  const base = seed.split("").reduce((sum, char) => sum + char.charCodeAt(0), 0);
  return (
    <div className="flex h-8 items-center gap-0.5">
      {Array.from({ length: 34 }).map((_, index) => {
        const height = 18 + ((base + index * 13) % 18);
        return (
          <span
            key={index}
            className={cn("w-0.5 rounded-full", active ? "bg-blue-500" : "bg-slate-300")}
            style={{ height: `${height}px`, opacity: active || index % 3 !== 0 ? 1 : 0.55 }}
          />
        );
      })}
    </div>
  );
}

function TrackEditorDrawer({
  open,
  track,
  draft,
  onDraftChange,
  savePending,
  onClose,
  onSave,
  onDelete,
}: {
  open: boolean;
  track: MusicTrack | null;
  draft: typeof emptyTagDraft;
  onDraftChange: (draft: typeof emptyTagDraft) => void;
  savePending: boolean;
  onClose: () => void;
  onSave: () => void;
  onDelete: (track: MusicTrack) => void;
}) {
  if (!open || !track) return null;

  return (
    <div className="fixed inset-0 z-40">
      <button className="absolute inset-0 bg-slate-950/20" onClick={onClose} aria-label="关闭标签编辑" />
      <aside className="absolute right-0 top-0 flex h-full w-full max-w-[460px] flex-col border-l border-slate-200 bg-white shadow-2xl">
        <div className="flex h-16 items-center justify-between border-b border-slate-200 px-5">
          <div className="min-w-0">
            <h2 className="truncate text-base font-semibold text-slate-950">标签编辑</h2>
            <p className="mt-0.5 truncate text-xs text-slate-400">{track.title}</p>
          </div>
          <button onClick={onClose} className="rounded-lg p-2 text-slate-400 hover:bg-slate-50 hover:text-slate-700" aria-label="关闭">
            <X size={18} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5">
          {track.source !== "user" ? (
            <div className="space-y-4">
              <Field label="标题" value={track.title} />
              <TagGroup label="Mood" values={track.mood.length ? track.mood : ["—"]} />
              <TagGroup label="商品分类" values={track.categories.length ? track.categories : ["default"]} />
              <div className="rounded-lg bg-slate-50 p-3 text-xs text-slate-500">内置曲目只读；上传到我的音乐后可编辑标签。</div>
            </div>
          ) : (
            <div className="space-y-4">
              <InputField label="标题" value={draft.title} onChange={(title) => onDraftChange({ ...draft, title })} />
              <MultiSelectField label="Mood" options={editableMoodOptions} values={draft.mood} onChange={(mood) => onDraftChange({ ...draft, mood })} />
              <MultiSelectField label="商品分类" options={editableCategoryOptions} values={draft.categories} onChange={(categories) => onDraftChange({ ...draft, categories })} />
              <div className="grid grid-cols-2 gap-3">
                <SelectField label="节奏" value={draft.tempo} onChange={(tempo) => onDraftChange({ ...draft, tempo })} options={["slow", "medium", "fast"]} />
                <SelectField label="能量" value={draft.energy} onChange={(energy) => onDraftChange({ ...draft, energy })} options={["low", "medium", "high"]} />
              </div>
              <InputField label="风格" value={draft.genre} onChange={(genre) => onDraftChange({ ...draft, genre })} />
            </div>
          )}
        </div>

        <div className="grid grid-cols-2 gap-2 border-t border-slate-200 p-5">
          <button
            onClick={onSave}
            disabled={track.source !== "user" || savePending}
            className="rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-blue-600"
          >
            {savePending ? "保存中..." : "保存标签"}
          </button>
          <button
            onClick={() => onDelete(track)}
            disabled={track.source !== "user"}
            className="rounded-lg border border-red-200 px-3 py-2 text-sm font-medium text-red-600 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-white"
          >
            删除曲目
          </button>
        </div>
      </aside>
    </div>
  );
}

function MusicPlayerBar({
  track,
  playing,
  progress,
  volume,
  onPlay,
}: {
  track: MusicTrack | null;
  playing: boolean;
  progress: number;
  volume: number;
  onPlay: (track: MusicTrack) => void;
}) {
  if (!track) return null;

  return (
    <div className="fixed inset-x-0 bottom-4 z-30 px-4">
      <div className="mx-auto flex max-w-4xl flex-col gap-3 rounded-lg border border-slate-200 bg-white p-3 shadow-2xl sm:flex-row sm:items-center">
        <button onClick={() => onPlay(track)} className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-blue-600 text-white">
          {playing ? <Pause size={16} /> : <Play size={16} />}
        </button>
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-semibold text-slate-900">{track.title}</div>
          <div className="mt-2 h-1.5 rounded-full bg-slate-100">
            <div className="h-1.5 rounded-full bg-blue-500" style={{ width: `${playing ? progress : 0}%` }} />
          </div>
        </div>
        <span className="shrink-0 text-xs text-slate-400">音量 {Math.round(volume * 100)}%</span>
      </div>
    </div>
  );
}
