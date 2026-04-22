import { useCallback, useEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  Check,
  Pause,
  Pencil,
  Play,
  Trash2,
  Upload,
  X,
} from "lucide-react";

const API_BASE = import.meta.env.VITE_API_URL || "";
const MAX_FILE_SIZE = 20 * 1024 * 1024;

const MOOD_OPTIONS = [
  "happy",
  "uplifting",
  "bright",
  "calm",
  "romantic",
  "elegant",
  "energetic",
  "confident",
  "trendy",
  "chill",
  "casual",
  "gentle",
] as const;

const CATEGORY_OPTIONS = [
  "上衣",
  "裙装",
  "外套",
  "裤子",
  "背心",
  "套装",
  "美妆",
  "配饰",
  "日常穿搭",
  "default",
] as const;

const TEMPO_OPTIONS = ["slow", "medium", "fast"] as const;
const ENERGY_OPTIONS = ["low", "medium", "high"] as const;

const inputClassName =
  "w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none";

interface MusicTrack {
  id: string;
  title: string;
  mood: string[];
  genre: string;
  tempo: string;
  energy: string;
  categories: string[];
  duration_s: number;
  source: "user" | "built-in";
}

interface MusicPageProps {
  onBack: () => void;
}

interface TagEditorState {
  trackId: string;
  title: string;
  mood: string[];
  categories: string[];
  tempo: string;
  energy: string;
  saving: boolean;
}

export function MusicPage({ onBack }: MusicPageProps) {
  const [tracks, setTracks] = useState<MusicTrack[]>([]);
  const [loading, setLoading] = useState(true);
  const [playingId, setPlayingId] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const [tagEditor, setTagEditor] = useState<TagEditorState | null>(null);
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  const fetchLibrary = useCallback(() => {
    fetch(`${API_BASE}/api/music/library`)
      .then((res) => res.json())
      .then((data) => {
        setTracks(Array.isArray(data) ? data : data.tracks ?? []);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    fetchLibrary();
  }, [fetchLibrary]);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    const onTimeUpdate = () => {
      if (audio.duration) setProgress(audio.currentTime / audio.duration);
    };
    const onEnded = () => {
      setPlayingId(null);
      setProgress(0);
    };
    audio.addEventListener("timeupdate", onTimeUpdate);
    audio.addEventListener("ended", onEnded);
    return () => {
      audio.removeEventListener("timeupdate", onTimeUpdate);
      audio.removeEventListener("ended", onEnded);
    };
  }, [playingId]);

  const togglePlay = (track: MusicTrack) => {
    if (playingId === track.id) {
      audioRef.current?.pause();
      setPlayingId(null);
      return;
    }
    if (audioRef.current) {
      audioRef.current.pause();
    }
    const audio = new Audio(`${API_BASE}/api/music/${track.id}/audio`);
    audioRef.current = audio;
    audio.play().catch(() => {});
    setPlayingId(track.id);
    setProgress(0);
  };

  const formatDuration = (s: number) => {
    if (s < 60) return `${Math.round(s)}秒`;
    const m = Math.floor(s / 60);
    const sec = Math.round(s % 60);
    return `${m}分${sec}秒`;
  };

  const handleFiles = (files: FileList | File[]) => {
    const file = files[0];
    if (!file) return;

    if (!file.name.toLowerCase().endsWith(".mp3")) {
      setUploadError("仅支持 MP3 格式");
      return;
    }

    if (file.size > MAX_FILE_SIZE) {
      setUploadError("文件大小不能超过 20MB");
      return;
    }

    setUploadError(null);
    setUploading(true);
    setUploadProgress(0);

    const formData = new FormData();
    formData.append("file", file);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE}/api/music/upload`);

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        setUploadProgress(Math.round((e.loaded / e.total) * 100));
      }
    };

    xhr.onload = () => {
      setUploading(false);
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const track: MusicTrack = JSON.parse(xhr.responseText);
          setTagEditor({
            trackId: track.id,
            title: track.title || file.name.replace(/\.mp3$/i, ""),
            mood: track.mood ?? [],
            categories: track.categories ?? [],
            tempo: track.tempo || "medium",
            energy: track.energy || "medium",
            saving: false,
          });
        } catch {
          fetchLibrary();
        }
      } else {
        try {
          const err = JSON.parse(xhr.responseText);
          setUploadError(err.detail || "上传失败");
        } catch {
          setUploadError("上传失败");
        }
      }
    };

    xhr.onerror = () => {
      setUploading(false);
      setUploadError("网络错误");
    };

    xhr.send(formData);
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    handleFiles(e.dataTransfer.files);
  };

  const onDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  };

  const onDragLeave = () => {
    setDragOver(false);
  };

  const onFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      handleFiles(e.target.files);
      e.target.value = "";
    }
  };

  const saveTagEditor = async () => {
    if (!tagEditor) return;
    setTagEditor({ ...tagEditor, saving: true });
    try {
      await fetch(`${API_BASE}/api/music/${tagEditor.trackId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: tagEditor.title,
          mood: tagEditor.mood,
          categories: tagEditor.categories,
          tempo: tagEditor.tempo,
          energy: tagEditor.energy,
        }),
      });
      setTagEditor(null);
      fetchLibrary();
    } catch {
      setTagEditor({ ...tagEditor, saving: false });
    }
  };

  const openEditDialog = (track: MusicTrack) => {
    setTagEditor({
      trackId: track.id,
      title: track.title,
      mood: [...track.mood],
      categories: [...track.categories],
      tempo: track.tempo,
      energy: track.energy,
      saving: false,
    });
  };

  const handleDelete = async () => {
    if (!deleteConfirmId) return;
    setDeleting(true);
    try {
      await fetch(`${API_BASE}/api/music/${deleteConfirmId}`, {
        method: "DELETE",
      });
      setTracks((prev) => prev.filter((t) => t.id !== deleteConfirmId));
      if (playingId === deleteConfirmId) {
        audioRef.current?.pause();
        setPlayingId(null);
      }
    } catch {
      // keep list unchanged on error
    } finally {
      setDeleting(false);
      setDeleteConfirmId(null);
    }
  };

  const toggleArrayItem = (
    arr: string[],
    item: string,
  ): string[] => {
    return arr.includes(item) ? arr.filter((v) => v !== item) : [...arr, item];
  };

  const userTracks = tracks.filter((t) => t.source === "user");
  const builtinTracks = tracks.filter((t) => t.source === "built-in");

  const renderTrackCard = (track: MusicTrack) => {
    const isPlaying = playingId === track.id;
    const isUser = track.source === "user";

    return (
      <div
        key={track.id}
        className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm"
      >
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2 min-w-0">
            <span
              className={`shrink-0 inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                isUser
                  ? "bg-blue-50 text-blue-700"
                  : "bg-slate-100 text-slate-500"
              }`}
            >
              {isUser ? "我的" : "内置"}
            </span>
            <h3 className="text-sm font-semibold text-slate-900 leading-tight truncate">
              {track.title}
            </h3>
          </div>
          <span className="shrink-0 text-xs text-slate-400">
            {formatDuration(track.duration_s)}
          </span>
        </div>

        <p className="mt-1 text-xs text-slate-400">
          {track.tempo} · {track.energy}
        </p>

        <div className="mt-3 flex items-center gap-3">
          <button
            onClick={() => togglePlay(track)}
            className="flex shrink-0 items-center justify-center rounded-full bg-slate-900 p-3 text-white hover:bg-slate-800"
          >
            {isPlaying ? <Pause size={16} /> : <Play size={16} />}
          </button>
          {isPlaying && (
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-100">
              <div
                className="h-full rounded-full bg-slate-900 transition-[width] duration-200"
                style={{ width: `${progress * 100}%` }}
              />
            </div>
          )}
        </div>

        <div className="mt-3 flex flex-wrap gap-1">
          {track.mood.map((m) => (
            <span
              key={m}
              className="inline-flex rounded-full bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700"
            >
              {m}
            </span>
          ))}
          {track.categories.map((c) => (
            <span
              key={c}
              className="inline-flex rounded-full bg-purple-50 px-2 py-0.5 text-xs font-medium text-purple-700"
            >
              {c}
            </span>
          ))}
        </div>

        {isUser && (
          <div className="mt-3 flex items-center gap-2 border-t border-slate-100 pt-3">
            <button
              onClick={() => openEditDialog(track)}
              className="flex items-center gap-1 rounded-md px-2 py-1 text-xs text-slate-500 hover:bg-slate-100 hover:text-slate-700"
            >
              <Pencil size={12} />
              编辑
            </button>
            <button
              onClick={() => setDeleteConfirmId(track.id)}
              className="flex items-center gap-1 rounded-md px-2 py-1 text-xs text-red-400 hover:bg-red-50 hover:text-red-600"
            >
              <Trash2 size={12} />
              删除
            </button>
          </div>
        )}
      </div>
    );
  };

  const renderTrackSection = (title: string, items: MusicTrack[]) => {
    if (items.length === 0) return null;
    return (
      <div>
        <h3 className="mb-3 text-sm font-semibold text-slate-700">{title}</h3>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {items.map(renderTrackCard)}
        </div>
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <nav className="sticky top-0 z-10 border-b border-slate-200 bg-white/80 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-4xl items-center gap-3 px-4 sm:px-6">
          <button
            className="flex items-center gap-1 rounded-md px-2 py-1 text-sm text-slate-600 hover:bg-slate-100 hover:text-slate-900"
            onClick={onBack}
          >
            <ArrowLeft size={16} />
            返回
          </button>
          <h1 className="text-sm font-semibold text-slate-900">音乐库</h1>
        </div>
      </nav>

      <div className="mx-auto max-w-4xl space-y-6 px-4 py-6 sm:px-6">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">
            📁 音乐库{tracks.length > 0 ? ` (${tracks.length} 首)` : ""}
          </h2>
          <p className="mt-1 text-sm text-slate-500">管理导出视频的背景音乐</p>
        </div>

        {/* Upload Area */}
        <div
          onDrop={onDrop}
          onDragOver={onDragOver}
          onDragLeave={onDragLeave}
          onClick={() => fileInputRef.current?.click()}
          className={`cursor-pointer rounded-xl border-2 border-dashed p-8 text-center transition-colors ${
            dragOver
              ? "border-blue-400 bg-blue-50/50"
              : "border-slate-300 hover:border-slate-400 hover:bg-slate-50/50"
          }`}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".mp3"
            className="hidden"
            onChange={onFileInputChange}
          />
          <Upload
            size={32}
            className={`mx-auto mb-3 ${dragOver ? "text-blue-500" : "text-slate-400"}`}
          />
          {uploading ? (
            <div>
              <p className="text-sm font-medium text-slate-700">
                上传中... {uploadProgress}%
              </p>
              <div className="mx-auto mt-3 h-2 w-48 overflow-hidden rounded-full bg-slate-100">
                <div
                  className="h-full rounded-full bg-slate-900 transition-[width] duration-300"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
            </div>
          ) : (
            <>
              <p className="text-sm font-medium text-slate-700">
                拖放 MP3 文件到此处，或点击选择
              </p>
              <p className="mt-1 text-xs text-slate-400">
                仅支持 MP3 格式，最大 20MB
              </p>
            </>
          )}
          {uploadError && (
            <p className="mt-2 text-sm text-red-500">{uploadError}</p>
          )}
        </div>

        {/* Track List */}
        {loading ? (
          <p className="py-12 text-center text-sm text-slate-400">
            加载中...
          </p>
        ) : tracks.length === 0 ? (
          <p className="py-12 text-center text-sm text-slate-400">暂无音乐</p>
        ) : (
          <div className="space-y-8">
            {renderTrackSection(
              `我的音乐${userTracks.length > 0 ? ` (${userTracks.length})` : ""}`,
              userTracks,
            )}
            {renderTrackSection(
              `内置曲目${builtinTracks.length > 0 ? ` (${builtinTracks.length})` : ""}`,
              builtinTracks,
            )}
          </div>
        )}

        <div className="mt-6 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3">
          <p className="text-sm text-amber-800">
            💡 提示
            <br />
            上传 MP3 文件即可扩充音乐库。系统会根据商品类型自动选择最合适的背景音乐。
          </p>
        </div>
      </div>

      {/* Tag Editor Modal */}
      {tagEditor && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-lg rounded-xl bg-white p-6 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-base font-semibold text-slate-900">
                编辑曲目信息
              </h3>
              <button
                onClick={() => {
                  if (!tagEditor.saving) {
                    setTagEditor(null);
                    fetchLibrary();
                  }
                }}
                className="rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
              >
                <X size={18} />
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">
                  曲目名称
                </label>
                <input
                  type="text"
                  className={inputClassName}
                  value={tagEditor.title}
                  onChange={(e) =>
                    setTagEditor({ ...tagEditor, title: e.target.value })
                  }
                />
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">
                  情绪标签
                </label>
                <div className="flex flex-wrap gap-1.5">
                  {MOOD_OPTIONS.map((m) => (
                    <button
                      key={m}
                      type="button"
                      onClick={() =>
                        setTagEditor({
                          ...tagEditor,
                          mood: toggleArrayItem(tagEditor.mood, m),
                        })
                      }
                      className={`rounded-full px-2.5 py-1 text-xs font-medium transition-colors ${
                        tagEditor.mood.includes(m)
                          ? "bg-blue-600 text-white"
                          : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                      }`}
                    >
                      {m}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">
                  适用分类
                </label>
                <div className="flex flex-wrap gap-1.5">
                  {CATEGORY_OPTIONS.map((c) => (
                    <button
                      key={c}
                      type="button"
                      onClick={() =>
                        setTagEditor({
                          ...tagEditor,
                          categories: toggleArrayItem(tagEditor.categories, c),
                        })
                      }
                      className={`rounded-full px-2.5 py-1 text-xs font-medium transition-colors ${
                        tagEditor.categories.includes(c)
                          ? "bg-purple-600 text-white"
                          : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                      }`}
                    >
                      {c}
                    </button>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="mb-1 block text-sm font-medium text-slate-700">
                    节奏
                  </label>
                  <select
                    className={inputClassName}
                    value={tagEditor.tempo}
                    onChange={(e) =>
                      setTagEditor({ ...tagEditor, tempo: e.target.value })
                    }
                  >
                    {TEMPO_OPTIONS.map((t) => (
                      <option key={t} value={t}>
                        {t === "slow" ? "慢" : t === "medium" ? "中" : "快"}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-slate-700">
                    能量
                  </label>
                  <select
                    className={inputClassName}
                    value={tagEditor.energy}
                    onChange={(e) =>
                      setTagEditor({ ...tagEditor, energy: e.target.value })
                    }
                  >
                    {ENERGY_OPTIONS.map((e_opt) => (
                      <option key={e_opt} value={e_opt}>
                        {e_opt === "low"
                          ? "低"
                          : e_opt === "medium"
                            ? "中"
                            : "高"}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </div>

            <div className="mt-6 flex items-center justify-end gap-3">
              <button
                onClick={() => {
                  if (!tagEditor.saving) {
                    setTagEditor(null);
                    fetchLibrary();
                  }
                }}
                disabled={tagEditor.saving}
                className="rounded-md px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 disabled:opacity-50"
              >
                跳过
              </button>
              <button
                onClick={saveTagEditor}
                disabled={tagEditor.saving}
                className="flex items-center gap-1.5 rounded-md bg-slate-900 px-4 py-2 text-sm text-white hover:bg-slate-800 disabled:opacity-50"
              >
                <Check size={14} />
                {tagEditor.saving ? "保存中..." : "保存"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirm Modal */}
      {deleteConfirmId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-sm rounded-xl bg-white p-6 shadow-xl">
            <div className="mb-1 flex items-center gap-2">
              <Trash2 size={18} className="text-red-500" />
              <h3 className="text-base font-semibold text-slate-900">
                确认删除
              </h3>
            </div>
            <p className="mt-2 text-sm text-slate-600">
              确定要删除这首曲目吗？此操作不可撤销。
            </p>
            <div className="mt-5 flex items-center justify-end gap-3">
              <button
                onClick={() => setDeleteConfirmId(null)}
                disabled={deleting}
                className="rounded-md px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 disabled:opacity-50"
              >
                取消
              </button>
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="flex items-center gap-1.5 rounded-md bg-red-600 px-4 py-2 text-sm text-white hover:bg-red-700 disabled:opacity-50"
              >
                <Trash2 size={14} />
                {deleting ? "删除中..." : "删除"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
