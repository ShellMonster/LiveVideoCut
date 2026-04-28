import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { UploadZone } from "@/components/UploadZone";
import { cn } from "@/lib/utils";
import { useTaskStore } from "@/stores/taskStore";
import { useSettingsStore, type Settings } from "@/stores/settingsStore";
import { stageLabels } from "../constants";
import { ChecklistItem, Chip, Header } from "../shared";

function settingsSnapshot(): Settings {
  const state = useSettingsStore.getState();
  const { setSettings, reset, ...settings } = state;
  void setSettings;
  void reset;
  return settings;
}

export function CreateProjectPage() {
  const navigate = useNavigate();
  useSettingsStore();
  const uploadInputRef = useRef<HTMLInputElement | null>(null);
  const [draftSettings, setDraftSettings] = useState<Settings>(() => settingsSnapshot());
  const uploadTaskId = useTaskStore((state) => state.taskId);
  const uploadStatus = useTaskStore((state) => state.status);
  const uploadProgress = useTaskStore((state) => state.progress);
  const uploadState = useTaskStore((state) => state.currentState);
  const updateDraftSettings = (partial: Partial<Settings>) => {
    setDraftSettings((current) => ({ ...current, ...partial }));
  };
  const applyPreset = (title: string) => {
    if (title === "高质量字幕版") {
      updateDraftSettings({
        enableVlm: true,
        exportMode: "smart",
        asrProvider: "volcengine_vc",
        subtitleMode: "karaoke",
        bgmEnabled: true,
        exportResolution: "1080p",
      });
    } else if (title === "快速低成本版") {
      updateDraftSettings({
        enableVlm: false,
        exportMode: "no_vlm",
        subtitleMode: "basic",
        asrProvider: "dashscope",
        bgmEnabled: false,
      });
    } else if (title === "全量候选调试版") {
      updateDraftSettings({
        enableVlm: false,
        exportMode: "all_candidates",
        subtitleMode: "basic",
        bgmEnabled: false,
      });
    } else if (title === "只切不烧字幕版") {
      updateDraftSettings({
        subtitleMode: "off",
        bgmEnabled: false,
      });
    }
  };
  const presets = [
    {
      title: "高质量字幕版",
      desc: "火山 VC + Karaoke 字幕 + BGM，适合正式交付。",
      active: draftSettings.asrProvider === "volcengine_vc" && draftSettings.subtitleMode === "karaoke",
    },
    {
      title: "快速低成本版",
      desc: "跳过 VLM 或使用基础字幕，适合快速预览。",
      active: draftSettings.exportMode === "no_vlm" || draftSettings.subtitleMode === "basic",
    },
    {
      title: "全量候选调试版",
      desc: "导出所有候选，用于排查召回和误切。",
      active: draftSettings.exportMode === "all_candidates",
    },
    {
      title: "只切不烧字幕版",
      desc: "关闭字幕烧录，快速获得原声片段。",
      active: draftSettings.subtitleMode === "off",
    },
  ];

  return (
    <>
      <Header
        title="创建剪辑项目"
        description="上传直播录像并选择本次任务使用的处理预设"
        action={
          <>
            <button
              onClick={() => navigate("/")}
              className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50"
            >
              取消
            </button>
            <button
              onClick={() => uploadInputRef.current?.click()}
              className="rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
            >
              选择文件开始
            </button>
          </>
        }
      />
      <main className="space-y-5 p-6">
        <div className="grid gap-2 md:grid-cols-3">
          {["上传视频", "选择预设", "确认配置"].map((label, index) => (
            <div key={label} className="rounded-lg border border-slate-200 bg-white p-3">
              <div className="flex items-center gap-2 text-sm font-medium text-slate-900">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-blue-600 text-xs text-white">
                  {index + 1}
                </span>
                {label}
              </div>
            </div>
          ))}
        </div>

        <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
          <div className="space-y-5">
            <div className="rounded-lg border border-slate-200 bg-white p-5">
              <h2 className="text-sm font-semibold text-slate-900">上传直播录像</h2>
              <p className="mt-1 text-xs text-slate-500">支持 MP4，上传后会保存当前设置快照并启动 Celery 流水线。</p>
              <div className="mt-4">
                <UploadZone settingsOverride={draftSettings} fileInputRef={uploadInputRef} />
              </div>
            </div>

            <div className="rounded-lg border border-slate-200 bg-white p-5">
              <h2 className="text-sm font-semibold text-slate-900">处理预设</h2>
              <div className="mt-4 grid gap-3 md:grid-cols-2">
                {presets.map((preset) => (
                  <button
                    key={preset.title}
                    onClick={() => applyPreset(preset.title)}
                    className={cn(
                      "rounded-lg border p-4 text-left",
                      preset.active ? "border-blue-200 bg-blue-50" : "border-slate-200 bg-white",
                    )}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <h3 className="text-sm font-semibold text-slate-900">{preset.title}</h3>
                      <span
                        className={cn(
                          "h-4 w-4 rounded-full border",
                          preset.active ? "border-blue-600 bg-blue-600" : "border-slate-300",
                        )}
                      />
                    </div>
                    <p className="mt-2 text-xs leading-5 text-slate-500">{preset.desc}</p>
                  </button>
                ))}
              </div>
            </div>
          </div>

          <aside className="space-y-5">
            <div className="rounded-lg border border-slate-200 bg-white p-5">
              <h2 className="text-sm font-semibold text-slate-900">本次任务配置</h2>
              <p className="mt-1 text-xs text-slate-500">预设只影响本次上传，不会覆盖系统设置默认值。</p>
              <div className="mt-4 flex flex-wrap gap-2">
                <Chip label={draftSettings.exportMode === "smart" ? "智能模式" : draftSettings.exportMode} tone="blue" />
                <Chip label={draftSettings.provider.toUpperCase()} tone="blue" />
                <Chip label={draftSettings.asrProvider === "volcengine_vc" ? "火山 VC" : draftSettings.asrProvider} tone="emerald" />
                <Chip label={`${draftSettings.subtitleMode} 字幕`} tone="amber" />
                <Chip label={draftSettings.exportResolution} tone="blue" />
                <Chip label={draftSettings.bgmEnabled ? "BGM开启" : "BGM关闭"} tone="emerald" />
              </div>
              <div className="mt-5 space-y-3 text-sm">
                <ChecklistItem label="格式校验" state={uploadTaskId ? "done" : "pending"} />
                <ChecklistItem label="编码校验" state={uploadTaskId ? "done" : "pending"} />
                <ChecklistItem label="音频流" state={uploadTaskId ? (uploadStatus === "uploading" ? "checking" : "done") : "pending"} />
                <ChecklistItem label="设置校验" state={uploadTaskId ? "done" : "pending"} />
              </div>
              <div className="mt-5 rounded-lg bg-slate-50 p-3">
                <div className="text-xs text-slate-500">当前上传任务</div>
                <div className="mt-1 text-lg font-semibold text-slate-900">
                  {uploadTaskId ? `${stageLabels[uploadState] || uploadStatus} · ${uploadProgress}%` : "等待选择文件"}
                </div>
                <p className="mt-1 break-all text-xs text-slate-400">
                  {uploadTaskId || "选择 MP4 后会显示真实上传进度和后端流水线状态。"}
                </p>
              </div>
            </div>
          </aside>
        </section>
      </main>
    </>
  );
}
