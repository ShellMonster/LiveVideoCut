import { useEffect, useRef, useState } from "react";
import { Pause, Play, RefreshCw, SlidersHorizontal, Trash2, Upload } from "lucide-react";
import { cn } from "@/lib/utils";
import { useSettingsStore } from "@/stores/settingsStore";
import { API_BASE } from "../api";
import { useMusicLibrary, useUploadTrack, useDeleteTrack, useSaveTrackTags } from "@/hooks/useAdminQueries";
import { editableCategoryOptions, editableMoodOptions } from "../constants";
import { formatDuration } from "../format";
import {
  Field,
  Header,
  IconButton,
  InputField,
  MetricCard,
  MultiSelectField,
  SelectField,
  TagGroup,
} from "../shared";
import type { MusicTrack } from "../types";

export function AdminMusicPage() {
  const bgmVolume = useSettingsStore((state) => state.bgmVolume);
  const { data: tracks = [], isLoading: loading, refetch: loadTracks } = useMusicLibrary();
  const uploadTrack = useUploadTrack();
  const deleteTrack = useDeleteTrack();
  const saveTags = useSaveTrackTags();

  const [playingId, setPlayingId] = useState<string | null>(null);
  const [audioProgress, setAudioProgress] = useState(0);
  const [selectedTrack, setSelectedTrack] = useState<MusicTrack | null>(null);
  const [tagDraft, setTagDraft] = useState({
    title: "",
    mood: [] as string[],
    categories: [] as string[],
    tempo: "medium",
    energy: "medium",
    genre: "",
  });
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    if (!selectedTrack) {
      setTagDraft({ title: "", mood: [], categories: [], tempo: "medium", energy: "medium", genre: "" });
      return;
    }
    setTagDraft({
      title: selectedTrack.title,
      mood: selectedTrack.mood,
      categories: selectedTrack.categories,
      tempo: selectedTrack.tempo || "medium",
      energy: selectedTrack.energy || "medium",
      genre: selectedTrack.genre || "",
    });
  }, [selectedTrack]);

  const userCount = tracks.filter((track) => track.source === "user").length;
  const builtInCount = tracks.filter((track) => track.source === "built-in").length;
  const categoryCount = new Set(tracks.flatMap((track) => track.categories)).size;

  const togglePlay = (track: MusicTrack) => {
    setSelectedTrack(track);
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
    setSelectedTrack(newTrack ?? null);
  };

  const handleDelete = async (trackId: string) => {
    await deleteTrack.mutateAsync(trackId).catch(() => {});
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
    setSelectedTrack(updated);
  };

  return (
    <>
      <Header
        title="音乐库"
        description="管理内置曲库和用户上传 BGM，配置商品类型匹配标签"
        action={
          <>
            <button
              onClick={() => fileInputRef.current?.click()}
              className="inline-flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50"
            >
              <Upload size={16} />
              上传音乐
            </button>
            <button
              onClick={() => void loadTracks()}
              className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
            >
              <RefreshCw size={16} />
              刷新曲库
            </button>
          </>
        }
      />
      <main className="space-y-5 p-6">
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

        <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
          <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
            <div className="border-b border-slate-100 px-4 py-3">
              <h2 className="text-sm font-semibold text-slate-900">曲目列表</h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[880px] text-left text-sm">
                <thead className="bg-slate-50 text-xs text-slate-500">
                  <tr>
                    <th className="px-4 py-3">曲目</th>
                    <th className="px-4 py-3">来源</th>
                    <th className="px-4 py-3">Mood</th>
                    <th className="px-4 py-3">商品分类</th>
                    <th className="px-4 py-3">节奏</th>
                    <th className="px-4 py-3">能量</th>
                    <th className="px-4 py-3">时长</th>
                    <th className="px-4 py-3 text-right">操作</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {loading ? (
                    <tr>
                      <td colSpan={8} className="px-4 py-12 text-center text-slate-400">加载曲库中...</td>
                    </tr>
                  ) : tracks.length === 0 ? (
                    <tr>
                      <td colSpan={8} className="px-4 py-12 text-center text-slate-400">暂无曲目</td>
                    </tr>
                  ) : (
                    tracks.map((track) => (
                      <tr
                        key={track.id}
                        className={cn("cursor-pointer hover:bg-slate-50", selectedTrack?.id === track.id && "bg-blue-50/50")}
                        onClick={() => setSelectedTrack(track)}
                      >
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-3">
                            <button
                              onClick={(event) => {
                                event.stopPropagation();
                                togglePlay(track);
                              }}
                              className="flex h-8 w-8 items-center justify-center rounded-full bg-slate-100 text-slate-600 hover:bg-blue-50 hover:text-blue-700"
                              aria-label="播放"
                            >
                              {playingId === track.id ? <Pause size={14} /> : <Play size={14} />}
                            </button>
                            <span className="font-medium text-slate-900">{track.title}</span>
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <span className={cn("rounded-full px-2 py-1 text-xs font-medium", track.source === "user" ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-600")}>
                            {track.source === "user" ? "我的" : "内置"}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-slate-600">{track.mood.slice(0, 2).join(" / ") || "—"}</td>
                        <td className="px-4 py-3 text-slate-600">{track.categories.slice(0, 2).join(" / ") || "default"}</td>
                        <td className="px-4 py-3 text-slate-600">{track.tempo}</td>
                        <td className="px-4 py-3 text-slate-600">{track.energy}</td>
                        <td className="px-4 py-3 text-slate-500">{formatDuration(track.duration_s)}</td>
                        <td className="px-4 py-3">
                          <div className="flex justify-end gap-1">
                            <IconButton
                              icon={SlidersHorizontal}
                              label="编辑"
                              disabled={track.source !== "user"}
                              onClick={(event) => {
                                event.stopPropagation();
                                setSelectedTrack(track);
                              }}
                            />
                            {track.source === "user" && (
                              <IconButton
                                icon={Trash2}
                                label="删除"
                                danger
                                onClick={(event) => {
                                  event.stopPropagation();
                                  void handleDelete(track.id);
                                }}
                              />
                            )}
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>

          <aside className="space-y-5">
            <div className="rounded-lg border border-dashed border-slate-300 bg-white p-5 text-center">
              <Upload className="mx-auto h-7 w-7 text-slate-300" />
              <h2 className="mt-3 text-sm font-semibold text-slate-900">上传 MP3</h2>
              <p className="mt-1 text-xs text-slate-500">支持 20MB 以内 MP3，上传后补充匹配标签。</p>
              <button
                onClick={() => fileInputRef.current?.click()}
                className="mt-4 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
              >
                选择文件
              </button>
            </div>
            <div className="rounded-lg border border-slate-200 bg-white p-5">
              <h2 className="text-sm font-semibold text-slate-900">标签编辑</h2>
              {selectedTrack ? (
                <div className="mt-4 space-y-4">
                  {selectedTrack.source !== "user" ? (
                    <>
                      <Field label="标题" value={selectedTrack.title} />
                      <TagGroup label="Mood" values={selectedTrack.mood.length ? selectedTrack.mood : ["—"]} />
                      <TagGroup label="商品分类" values={selectedTrack.categories.length ? selectedTrack.categories : ["default"]} />
                      <div className="rounded-lg bg-slate-50 p-3 text-xs text-slate-500">
                        内置曲目只读；上传到我的音乐后可编辑标签。
                      </div>
                    </>
                  ) : (
                    <>
                      <InputField label="标题" value={tagDraft.title} onChange={(title) => setTagDraft({ ...tagDraft, title })} />
                      <MultiSelectField
                        label="Mood"
                        options={editableMoodOptions}
                        values={tagDraft.mood}
                        onChange={(mood) => setTagDraft({ ...tagDraft, mood })}
                      />
                      <MultiSelectField
                        label="商品分类"
                        options={editableCategoryOptions}
                        values={tagDraft.categories}
                        onChange={(categories) => setTagDraft({ ...tagDraft, categories })}
                      />
                      <div className="grid grid-cols-2 gap-3">
                        <SelectField
                          label="节奏"
                          value={tagDraft.tempo}
                          onChange={(tempo) => setTagDraft({ ...tagDraft, tempo })}
                          options={["slow", "medium", "fast"]}
                        />
                        <SelectField
                          label="能量"
                          value={tagDraft.energy}
                          onChange={(energy) => setTagDraft({ ...tagDraft, energy })}
                          options={["low", "medium", "high"]}
                        />
                      </div>
                      <InputField label="风格" value={tagDraft.genre} onChange={(genre) => setTagDraft({ ...tagDraft, genre })} />
                      <button
                        onClick={() => void handleSaveTags()}
                        disabled={saveTags.isPending}
                        className={cn(
                          "w-full rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700",
                          saveTags.isPending && "cursor-not-allowed opacity-60",
                        )}
                      >
                        {saveTags.isPending ? "保存中..." : "保存标签"}
                      </button>
                    </>
                  )}
                </div>
              ) : (
                <p className="mt-4 text-sm text-slate-400">选择曲目后编辑标签</p>
              )}
            </div>
          </aside>
        </section>

        {selectedTrack && (
          <div className="rounded-lg border border-slate-200 bg-white p-3">
            <div className="flex items-center gap-3">
              <button onClick={() => togglePlay(selectedTrack)} className="flex h-9 w-9 items-center justify-center rounded-full bg-blue-600 text-white">
                {playingId === selectedTrack.id ? <Pause size={16} /> : <Play size={16} />}
              </button>
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-medium text-slate-900">{selectedTrack.title}</div>
                <div className="mt-2 h-1.5 rounded-full bg-slate-100">
                  <div className="h-1.5 rounded-full bg-blue-500" style={{ width: `${playingId === selectedTrack.id ? audioProgress : 0}%` }} />
                </div>
              </div>
              <span className="text-xs text-slate-400">音量 {Math.round(bgmVolume * 100)}%</span>
            </div>
          </div>
        )}
      </main>
    </>
  );
}
