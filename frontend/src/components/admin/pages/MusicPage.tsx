import { useRef, useState } from "react";
import {
  Folder,
  ListMusic,
  MoreVertical,
  Music,
  Pause,
  Play,
  RefreshCw,
  Repeat,
  Search,
  Shuffle,
  SkipBack,
  SkipForward,
  SlidersHorizontal,
  Tag,
  Upload,
  Volume2,
  X,
} from "lucide-react";
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
  MultiSelectField,
  Pagination,
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
    const text = `${track.title} ${track.mood.join(" ")} ${track.mood.map(moodLabel).join(" ")} ${track.categories.join(" ")} ${track.categories.map(categoryLabel).join(" ")} ${track.genre} ${genreLabel(track.genre)}`.toLowerCase();
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

        <section className="grid gap-4 xl:grid-cols-4">
          <MusicMetricCard icon={Music} tone="emerald" label="我的音乐" value={String(userCount)} suffix="首" />
          <MusicMetricCard icon={Folder} tone="slate" label="内置曲目" value={String(builtInCount)} suffix="首" />
          <MusicMetricCard icon={Tag} tone="blue" label="已匹配分类" value={`${categoryCount}`} suffix="类" />
          <MusicMetricCard icon={Volume2} tone="violet" label="默认音量" value={bgmVolume.toFixed(2)} />
        </section>

        <section className="overflow-hidden rounded-lg border border-slate-200 bg-white">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-4 py-3">
            <div>
              <h2 className="text-base font-semibold text-slate-900">曲目列表</h2>
              <p className="mt-0.5 text-xs text-slate-400">播放曲目，按来源、Mood 和商品分类筛选后编辑标签。</p>
            </div>
            <button
              onClick={() => {
                setQuery("");
                setSourceFilter("all");
                setPage(1);
              }}
              className="inline-flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50"
            >
              <SlidersHorizontal size={15} />
              重置筛选
            </button>
          </div>
          <div className="flex flex-wrap gap-3 border-b border-slate-100 px-4 py-3">
            <label className="flex min-w-0 flex-1 items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-500 sm:min-w-72">
              <Search size={16} />
              <input
                value={query}
                onChange={(event) => {
                  setQuery(event.target.value);
                  setPage(1);
                }}
                placeholder="搜索标题 / 艺术家 / 编号"
                className="min-w-0 flex-1 bg-transparent text-slate-700 outline-none placeholder:text-slate-400"
              />
            </label>
            <select
              value={sourceFilter}
              onChange={(event) => {
                setSourceFilter(event.target.value);
                setPage(1);
              }}
              className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-600"
            >
              <option value="all">来源 全部</option>
              <option value="user">我的音乐</option>
              <option value="built-in">内置曲目</option>
            </select>
            <select className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-600">
              <option>商品分类 全部</option>
              {editableCategoryOptions.map((item) => (
                <option key={item}>{categoryLabel(item)}</option>
              ))}
            </select>
            <select className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-600">
              <option>Mood 全部</option>
              {editableMoodOptions.map((item) => (
                <option key={item}>{moodLabel(item)}</option>
              ))}
            </select>
          </div>

          <div className="overflow-x-auto">
            <div className="grid min-w-[1120px] grid-cols-[32px_minmax(220px,1fr)_210px_110px_80px_150px_minmax(190px,1fr)_80px] gap-4 border-b border-slate-100 bg-slate-50 px-4 py-3 text-xs font-medium text-slate-500">
              <div />
              <div>曲目</div>
              <div>波形</div>
              <div>来源</div>
              <div>时长</div>
              <div>Mood</div>
              <div>商品分类</div>
              <div className="text-center">操作</div>
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
}: {
  track: MusicTrack;
  selected: boolean;
  playing: boolean;
  onSelect: () => void;
  onPlay: () => void;
}) {
  return (
    <article className={cn("grid min-w-[1120px] grid-cols-[32px_minmax(220px,1fr)_210px_110px_80px_150px_minmax(190px,1fr)_80px] items-center gap-4 border-b border-slate-100 px-4 py-3 last:border-b-0 hover:bg-slate-50", selected && "bg-blue-50/40")}>
      <label className="flex h-5 w-5 items-center justify-center">
        <input type="checkbox" checked={selected} onChange={onSelect} className="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500" />
      </label>
      <div className="flex min-w-0 items-center gap-3">
        <button
          onClick={onPlay}
          className={cn("flex h-9 w-9 shrink-0 items-center justify-center rounded-full border", playing ? "border-blue-600 bg-blue-600 text-white" : "border-slate-200 bg-white text-slate-600 hover:bg-blue-50 hover:text-blue-700")}
          aria-label={playing ? "暂停" : "播放"}
        >
          {playing ? <Pause size={15} /> : <Play size={15} />}
        </button>
        <button onClick={onSelect} className="min-w-0 text-left">
          <div className="truncate text-sm font-semibold text-slate-900">{track.title}</div>
          <div className="mt-1 text-xs text-slate-400">{genreLabel(track.genre)} · {formatDuration(track.duration_s)}</div>
        </button>
      </div>
      <Waveform active={playing} seed={track.id} />
      <div>
        <span className={cn("rounded-full px-2 py-1 text-xs font-medium", track.source === "user" ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-600")}>
          {track.source === "user" ? "我的音乐" : "内置曲目"}
        </span>
      </div>
      <div className="text-xs text-slate-500">{formatDuration(track.duration_s)}</div>
      <div className="flex min-w-0 flex-wrap gap-1.5">
        {(track.mood.length ? track.mood.slice(0, 3) : ["—"]).map((item) => (
          <span key={item} className="rounded-md bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-700">{moodLabel(item)}</span>
        ))}
      </div>
      <div className="flex min-w-0 flex-wrap gap-1.5">
        {(track.categories.length ? track.categories.slice(0, 2) : ["default"]).map((item) => (
          <span key={item} className="rounded-md bg-slate-100 px-2 py-1 text-xs font-medium text-slate-600">{categoryLabel(item)}</span>
        ))}
      </div>
      <div className="flex justify-center">
        <button onClick={onSelect} className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-50 hover:text-slate-800" aria-label="编辑标签">
          <MoreVertical size={16} />
        </button>
      </div>
    </article>
  );
}

function Waveform({ active, seed }: { active: boolean; seed: string }) {
  const base = seed.split("").reduce((sum, char) => sum + char.charCodeAt(0), 0);
  return (
    <div className="flex h-8 items-center gap-0.5">
      {Array.from({ length: 38 }).map((_, index) => {
        const height = 18 + ((base + index * 13) % 18);
        return (
          <span
            key={index}
            className={cn("w-0.5 rounded-full", active ? "bg-blue-500" : "bg-slate-300")}
            style={{ height: `${height}px`, opacity: active || index % 3 !== 0 ? 1 : 0.45 }}
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
          <h2 className="text-base font-semibold text-slate-950">标签编辑</h2>
          <button onClick={onClose} className="rounded-lg p-2 text-slate-400 hover:bg-slate-50 hover:text-slate-700" aria-label="关闭">
            <X size={18} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5">
          <p className="mb-5 text-sm text-slate-500">选择曲目后编辑标签</p>
          {track.source !== "user" ? (
            <div className="space-y-4">
              <Field label="标题" value={track.title} />
              <TagGroup label="Mood" values={track.mood.length ? track.mood.map(moodLabel) : ["—"]} />
              <TagGroup label="商品分类" values={track.categories.length ? track.categories.map(categoryLabel) : ["通用"]} />
              <div className="rounded-lg bg-slate-50 p-3 text-xs text-slate-500">内置曲目只读；上传到我的音乐后可编辑标签。</div>
            </div>
          ) : (
            <div className="space-y-4">
              <InputField label="标题" value={draft.title} onChange={(title) => onDraftChange({ ...draft, title })} />
              <MultiSelectField label="Mood" options={editableMoodOptions} values={draft.mood} formatOption={moodLabel} onChange={(mood) => onDraftChange({ ...draft, mood })} />
              <MultiSelectField label="商品分类" options={editableCategoryOptions} values={draft.categories} formatOption={categoryLabel} onChange={(categories) => onDraftChange({ ...draft, categories })} />
              <div>
                <div className="mb-2 text-xs font-medium text-slate-500">节奏</div>
                <div className="grid grid-cols-4 gap-2">
                  {["slow", "medium", "fast", "very_fast"].map((tempo) => (
                    <button
                      key={tempo}
                      onClick={() => onDraftChange({ ...draft, tempo })}
                      className={cn(
                        "rounded-lg border px-3 py-2 text-sm font-medium",
                        draft.tempo === tempo ? "border-blue-500 bg-blue-50 text-blue-700" : "border-slate-200 text-slate-600 hover:bg-slate-50",
                      )}
                    >
                      {tempoLabel(tempo)}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <div className="mb-2 flex items-center justify-between text-xs font-medium text-slate-500">
                  <span>能量</span>
                  <span className="rounded-md bg-slate-50 px-2 py-1 text-slate-600 ring-1 ring-slate-200">{energyLabel(draft.energy)}</span>
                </div>
                <input
                  type="range"
                  min={0}
                  max={2}
                  step={1}
                  value={energyIndex(draft.energy)}
                  onChange={(event) => onDraftChange({ ...draft, energy: ["low", "medium", "high"][Number(event.target.value)] })}
                  className="w-full accent-blue-600"
                />
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
    <div className="fixed inset-x-0 bottom-0 z-30 border-t border-slate-200 bg-white px-4 py-3 shadow-2xl lg:left-64">
      <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:gap-6">
        <div className="flex min-w-0 items-center gap-3 xl:w-80">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-slate-200 text-slate-500">
            <Music size={22} />
          </div>
          <div className="min-w-0">
            <div className="truncate text-sm font-semibold text-slate-900">{track.title}</div>
            <div className="mt-1 flex items-center gap-2">
              <span className="truncate text-xs text-slate-500">{genreLabel(track.genre)}</span>
              <span className={cn("rounded-full px-2 py-0.5 text-xs font-medium", track.source === "user" ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-600")}>
                {track.source === "user" ? "我的音乐" : "内置曲目"}
              </span>
            </div>
          </div>
        </div>
        <div className="flex flex-1 items-center gap-4">
          <button className="hidden text-slate-500 hover:text-slate-800 sm:inline-flex" aria-label="随机播放"><Shuffle size={18} /></button>
          <button className="hidden text-slate-500 hover:text-slate-800 sm:inline-flex" aria-label="上一首"><SkipBack size={18} /></button>
          <button onClick={() => onPlay(track)} className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-blue-600 text-white shadow-lg shadow-blue-200">
            {playing ? <Pause size={18} /> : <Play size={18} />}
          </button>
          <button className="hidden text-slate-500 hover:text-slate-800 sm:inline-flex" aria-label="下一首"><SkipForward size={18} /></button>
          <button className="hidden text-slate-500 hover:text-slate-800 sm:inline-flex" aria-label="循环播放"><Repeat size={18} /></button>
          <span className="w-20 shrink-0 text-right text-xs text-slate-500">{playing ? `${Math.round(progress)}%` : "0%"}</span>
          <div className="h-1.5 flex-1 rounded-full bg-slate-100">
            <div className="h-1.5 rounded-full bg-blue-500" style={{ width: `${playing ? progress : 0}%` }} />
          </div>
          <div className="hidden items-center gap-3 text-slate-500 md:flex">
            <Volume2 size={18} />
            <div className="h-1.5 w-28 rounded-full bg-slate-100">
              <div className="h-1.5 rounded-full bg-blue-500" style={{ width: `${Math.min(100, volume * 100)}%` }} />
            </div>
            <span className="w-10 text-xs text-slate-500">{volume.toFixed(2)}</span>
          </div>
          <ListMusic className="hidden text-slate-500 xl:block" size={20} />
        </div>
      </div>
    </div>
  );
}

function MusicMetricCard({
  icon: Icon,
  label,
  value,
  suffix,
  tone,
}: {
  icon: typeof Music;
  label: string;
  value: string;
  suffix?: string;
  tone: "emerald" | "slate" | "blue" | "violet";
}) {
  const toneClass = {
    emerald: "bg-emerald-50 text-emerald-600",
    slate: "bg-slate-100 text-slate-600",
    blue: "bg-blue-50 text-blue-600",
    violet: "bg-violet-50 text-violet-600",
  }[tone];

  return (
    <div className="flex items-center gap-4 rounded-lg border border-slate-200 bg-white p-5">
      <div className={cn("flex h-14 w-14 items-center justify-center rounded-full", toneClass)}>
        <Icon size={24} />
      </div>
      <div>
        <div className="text-sm font-medium text-slate-500">{label}</div>
        <div className="mt-1 flex items-baseline gap-1">
          <span className="text-2xl font-semibold text-slate-950">{value}</span>
          {suffix && <span className="text-sm text-slate-500">{suffix}</span>}
        </div>
      </div>
    </div>
  );
}

function tempoLabel(tempo: string): string {
  const labels: Record<string, string> = {
    slow: "慢",
    medium: "中",
    fast: "快",
    very_fast: "极快",
  };
  return labels[tempo] ?? tempo;
}

function moodLabel(mood: string): string {
  const labels: Record<string, string> = {
    bright: "明亮",
    casual: "轻松",
    warm: "温暖",
    luxury: "高级",
    energetic: "活力",
    soft: "柔和",
    clean: "清新",
    elegant: "优雅",
    healing: "治愈",
    romantic: "浪漫",
    relaxed: "放松",
    upbeat: "轻快",
    happy: "欢乐",
  };
  return labels[mood] ?? mood;
}

function categoryLabel(category: string): string {
  const labels: Record<string, string> = {
    default: "通用",
    dress: "连衣裙",
    coat: "外套",
    pants: "裤装",
    skirt: "半身裙",
    shoes: "鞋履",
    bag: "包袋",
    accessory: "配饰",
    beauty: "美妆",
    home: "家居",
    top: "上衣",
    tshirt: "T恤",
    t_shirt: "T恤",
    shorts: "短裤",
    sports: "运动",
    sleepwear: "睡衣",
  };
  return labels[category] ?? category;
}

function genreLabel(genre?: string): string {
  if (!genre) return "未设置风格";
  const labels: Record<string, string> = {
    pop: "流行",
    electronic: "电子",
    acoustic: "原声",
    piano: "钢琴",
    jazz: "爵士",
    ambient: "氛围",
    fashion: "时尚",
    light: "轻音乐",
  };
  return labels[genre] ?? genre;
}

function energyIndex(energy: string): number {
  if (energy === "low") return 0;
  if (energy === "high") return 2;
  return 1;
}

function energyLabel(energy: string): string {
  const labels: Record<string, string> = {
    low: "0.30",
    medium: "0.60",
    high: "0.90",
  };
  return labels[energy] ?? "0.60";
}
