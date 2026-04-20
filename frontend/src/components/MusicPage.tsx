import { useEffect, useRef, useState } from "react";
import { ArrowLeft, Pause, Play } from "lucide-react";

const API_BASE = import.meta.env.VITE_API_URL || "";

interface MusicTrack {
  id: string;
  title: string;
  mood: string[];
  genre: string;
  tempo: string;
  energy: string;
  categories: string[];
  duration_s: number;
}

interface MusicPageProps {
  onBack: () => void;
}

export function MusicPage({ onBack }: MusicPageProps) {
  const [tracks, setTracks] = useState<MusicTrack[]>([]);
  const [loading, setLoading] = useState(true);
  const [playingId, setPlayingId] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/music/library`)
      .then((res) => res.json())
      .then((data) => {
        setTracks(Array.isArray(data) ? data : data.tracks ?? []);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

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

        {loading ? (
          <p className="py-12 text-center text-sm text-slate-400">加载中...</p>
        ) : tracks.length === 0 ? (
          <p className="py-12 text-center text-sm text-slate-400">暂无音乐</p>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {tracks.map((track) => {
              const isPlaying = playingId === track.id;
              return (
                <div
                  key={track.id}
                  className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm"
                >
                  <div className="flex items-start justify-between gap-2">
                    <h3 className="text-sm font-semibold text-slate-900 leading-tight">
                      {track.title}
                    </h3>
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
                </div>
              );
            })}
          </div>
        )}

        <div className="mt-6 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3">
          <p className="text-sm text-amber-800">
            💡 提示
            <br />
            将 MP3 文件放入 backend/assets/bgm/ 目录，并在 bgm_library.json 中添加条目即可扩充音乐库。
            系统会根据商品类型自动选择最合适的背景音乐。
          </p>
        </div>
      </div>
    </div>
  );
}
