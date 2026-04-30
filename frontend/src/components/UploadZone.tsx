import { useCallback, useMemo, useRef, useState, type RefObject } from "react";
import { Upload } from "lucide-react";
import { cn } from "@/lib/utils";
import { userFacingMessage } from "@/components/admin/format";
import { settingsToPayload, useSettingsStore, type Settings } from "@/stores/settingsStore";
import { useTaskStore } from "@/stores/taskStore";

const API_BASE = import.meta.env.VITE_API_URL || "";

interface UploadSettingsPayload {
  api_key: string;
  enable_vlm: boolean;
  export_mode: Settings["exportMode"];
  vlm_provider: Settings["provider"];
  api_base: string;
  model: string;
  review_strictness: Settings["reviewStrictness"];
  review_mode: Settings["reviewMode"];
  scene_threshold: number;
  frame_sample_fps: number;
  recall_cooldown_seconds: number;
  candidate_looseness: Settings["candidateLooseness"];
  min_segment_duration_seconds: number;
  dedupe_window_seconds: number;
  merge_count: number;
  allow_returned_product: boolean;
  max_candidate_count: number;
  subtitle_mode: Settings["subtitleMode"];
  subtitle_position: Settings["subtitlePosition"];
  subtitle_template: Settings["subtitleTemplate"];
  subtitle_font_size: number;
  subtitle_highlight_font_size: number;
  boundary_snap: boolean;
  custom_position_y: number | null;
  asr_provider: Settings["asrProvider"];
  asr_api_key: Settings["asrApiKey"];
  tos_ak: string;
  tos_sk: string;
  tos_bucket: string;
  tos_region: string;
  tos_endpoint: string;
  filter_filler_mode: Settings["fillerFilterMode"];
  sensitive_filter_enabled: boolean;
  sensitive_words: string[];
  sensitive_filter_mode: Settings["sensitiveFilterMode"];
  sensitive_match_mode: Settings["sensitiveMatchMode"];
  cover_strategy: Settings["coverStrategy"];
  video_speed: number;
  enable_llm_analysis: boolean;
  llm_api_key: string;
  llm_api_base: string;
  llm_model: string;
  llm_type: Settings["llmType"];
  export_resolution: Settings["exportResolution"];
  segment_granularity: Settings["segmentGranularity"];
  change_detection_fusion_mode: Settings["changeDetectionFusionMode"];
  change_detection_sensitivity: Settings["changeDetectionSensitivity"];
  clothing_yolo_confidence: number;
  ffmpeg_preset: Settings["ffmpegPreset"];
  ffmpeg_crf: number;
  bgm_enabled: boolean;
  bgm_volume: number;
  original_volume: number;
  commerce_gemini_api_key: string;
  commerce_gemini_api_base: string;
  commerce_gemini_model: string;
  commerce_gemini_timeout_seconds: number;
  commerce_image_api_key: string;
  commerce_image_api_base: string;
  commerce_image_model: string;
  commerce_image_size: Settings["commerceImageSize"];
  commerce_image_quality: Settings["commerceImageQuality"];
  commerce_image_timeout_seconds: number;
}

interface UploadContext {
  enableVlm: boolean;
  exportMode: Settings["exportMode"];
  provider: Settings["provider"];
  subtitleMode: Settings["subtitleMode"];
}

const VLM_STATUS_LABELS: Record<"on" | "off", string> = {
  on: "开启",
  off: "关闭",
};

const PROVIDER_LABELS: Record<UploadContext["provider"], string> = {
  qwen: "Qwen",
  glm: "GLM",
};

const EXPORT_MODE_LABELS: Record<UploadContext["exportMode"], string> = {
  smart: "智能模式",
  no_vlm: "跳过 VLM",
  all_candidates: "候选全切",
  all_scenes: "场景全切",
};

const SUBTITLE_MODE_LABELS: Record<UploadContext["subtitleMode"], string> = {
  off: "关闭",
  basic: "基础字幕",
  styled: "样式字幕",
  karaoke: "卡拉 OK",
};

function buildUploadSettingsPayload(settings: Settings): UploadSettingsPayload {
  return settingsToPayload(settings) as UploadSettingsPayload;
}

export function UploadZone({
  settingsOverride,
  fileInputRef: externalFileInputRef,
}: {
  settingsOverride?: Settings;
  fileInputRef?: RefObject<HTMLInputElement | null>;
} = {}) {
  const [dragging, setDragging] = useState(false);
  const [activeUploadContext, setActiveUploadContext] = useState<UploadContext | null>(null);
  const internalFileInputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = externalFileInputRef ?? internalFileInputRef;
  const { status, progress, error, setTask, setStatus, setError, setProgress, reset } =
    useTaskStore();
  const storeProvider = useSettingsStore((state) => state.provider);
  const storeEnableVlm = useSettingsStore((state) => state.enableVlm);
  const storeExportMode = useSettingsStore((state) => state.exportMode);
  const storeSubtitleMode = useSettingsStore((state) => state.subtitleMode);
  const provider = settingsOverride?.provider ?? storeProvider;
  const enableVlm = settingsOverride?.enableVlm ?? storeEnableVlm;
  const exportMode = settingsOverride?.exportMode ?? storeExportMode;
  const subtitleMode = settingsOverride?.subtitleMode ?? storeSubtitleMode;

  const previewContext = useMemo<UploadContext>(
    () => ({ enableVlm, exportMode, provider, subtitleMode }),
    [enableVlm, exportMode, provider, subtitleMode],
  );

  const displayContext = activeUploadContext ?? previewContext;
  const contextLabel = activeUploadContext ? "当前任务使用" : "新上传将使用";

  const upload = useCallback(
    async (file: File) => {
      if (!file.name.toLowerCase().endsWith(".mp4")) {
        setError("请上传 MP4 格式的视频文件");
        return;
      }

      const currentSettings = settingsOverride ?? useSettingsStore.getState();
      const uploadContext: UploadContext = {
        enableVlm: currentSettings.enableVlm,
        exportMode: currentSettings.exportMode,
        provider: currentSettings.provider,
        subtitleMode: currentSettings.subtitleMode,
      };

      reset();
      setActiveUploadContext(uploadContext);
      setStatus("uploading");

      const form = new FormData();
      form.append("file", file);
      form.append("settings_json", JSON.stringify(buildUploadSettingsPayload(currentSettings)));

      try {
        const xhr = new XMLHttpRequest();

        const done = new Promise<{ task_id: string; metadata: Record<string, unknown> }>(
          (resolve, reject) => {
            xhr.open("POST", `${API_BASE}/api/upload`);
            xhr.onload = () => {
              if (xhr.status >= 200 && xhr.status < 300) {
                resolve(JSON.parse(xhr.responseText));
              } else {
                const body = JSON.parse(xhr.responseText || "{}");
                reject(new Error(body.detail || `上传失败 (${xhr.status})`));
              }
            };
            xhr.onerror = () => reject(new Error("网络错误，请检查连接"));
            xhr.send(form);
          },
        );

        xhr.upload.onprogress = (e) => {
          if (e.lengthComputable) {
            setProgress(Math.round((e.loaded / e.total) * 100));
          }
        };

        const result = await done;
        setTask(result.task_id, result.metadata);
      } catch (err) {
        const message = err instanceof Error ? err.message : "上传失败";
        setError(userFacingMessage(message) || "上传失败");
      }
    },
    [settingsOverride, reset, setTask, setStatus, setError, setProgress],
  );

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) upload(file);
    },
    [upload],
  );

  const onFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) upload(file);
    },
    [upload],
  );

  const isUploading = status === "uploading";

  return (
    <div className="w-full">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => !isUploading && fileInputRef.current?.click()}
        className={cn(
          "upload-zone flex cursor-pointer flex-col items-center justify-center gap-4 rounded-lg border-2 border-dashed p-10 transition-colors",
          dragging
            ? "border-blue-500 bg-blue-50"
            : "border-gray-300 bg-gray-50 hover:border-gray-400 hover:bg-gray-100",
          isUploading && "pointer-events-none opacity-60",
        )}
      >
        <Upload className="h-10 w-10 text-gray-400" />
        <p className="text-sm text-gray-600">
          {isUploading ? "上传中..." : "拖拽 MP4 文件到此处，或点击选择文件"}
        </p>
        <input
          ref={fileInputRef}
          type="file"
          accept=".mp4"
          onChange={onFileChange}
          className="hidden"
        />
      </div>

      <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
        <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
          <span className="font-medium text-slate-600">{contextLabel}</span>
          <span className="inline-flex items-center rounded-full bg-white px-2.5 py-1 text-xs font-medium text-slate-700 ring-1 ring-slate-200">
            VLM：{VLM_STATUS_LABELS[displayContext.enableVlm ? "on" : "off"]}
          </span>
          <span className="inline-flex items-center rounded-full bg-white px-2.5 py-1 text-xs font-medium text-slate-700 ring-1 ring-slate-200">
            模式：{EXPORT_MODE_LABELS[displayContext.exportMode]}
          </span>
          <span className="inline-flex items-center rounded-full bg-white px-2.5 py-1 text-xs font-medium text-slate-700 ring-1 ring-slate-200">
            Provider：{PROVIDER_LABELS[displayContext.provider]}
          </span>
          <span className="inline-flex items-center rounded-full bg-white px-2.5 py-1 text-xs font-medium text-slate-700 ring-1 ring-slate-200">
            字幕：{SUBTITLE_MODE_LABELS[displayContext.subtitleMode]}
          </span>
        </div>
      </div>

      {isUploading && (
        <div className="mt-4">
          <div className="h-2 w-full rounded-full bg-gray-200">
            <div
              className="upload-progress h-2 rounded-full bg-blue-500 transition-all"
              style={{ width: `${progress}%` }}
            />
          </div>
          <p className="mt-1 text-xs text-gray-500 text-right">{progress}%</p>
        </div>
      )}

      {status === "processing" && (
        <p className="mt-4 text-center text-sm text-green-600">
          上传成功！任务处理中...
        </p>
      )}

      {error && (
        <p className="mt-4 text-center text-sm text-red-600">{error}</p>
      )}
    </div>
  );
}
