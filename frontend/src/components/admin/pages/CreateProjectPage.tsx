import { UploadZone } from "@/components/UploadZone";
import { cn } from "@/lib/utils";
import { useTaskStore } from "@/stores/taskStore";
import { useSettingsStore } from "@/stores/settingsStore";
import { stageLabels } from "../constants";
import { ChecklistItem, Chip, Header } from "../shared";

export function CreateProjectPage({ onCancel }: { onCancel: () => void }) {
  const settings = useSettingsStore();
  const uploadTaskId = useTaskStore((state) => state.taskId);
  const uploadStatus = useTaskStore((state) => state.status);
  const uploadProgress = useTaskStore((state) => state.progress);
  const uploadState = useTaskStore((state) => state.currentState);
  const applyPreset = (title: string) => {
    if (title === "高质量字幕版") {
      settings.setSettings({
        exportMode: "smart",
        asrProvider: "volcengine_vc",
        subtitleMode: "karaoke",
        bgmEnabled: true,
        exportResolution: "1080p",
      });
    } else if (title === "快速低成本版") {
      settings.setSettings({
        exportMode: "no_vlm",
        subtitleMode: "basic",
        asrProvider: "dashscope",
        bgmEnabled: false,
      });
    } else if (title === "全量候选调试版") {
      settings.setSettings({
        exportMode: "all_candidates",
        subtitleMode: "basic",
      });
    } else if (title === "只切不烧字幕版") {
      settings.setSettings({
        subtitleMode: "off",
        bgmEnabled: false,
      });
    }
  };
  const presets = [
    {
      title: "高质量字幕版",
      desc: "火山 VC + Karaoke 字幕 + BGM，适合正式交付。",
      active: settings.asrProvider === "volcengine_vc" && settings.subtitleMode === "karaoke",
    },
    {
      title: "快速低成本版",
      desc: "跳过 VLM 或使用基础字幕，适合快速预览。",
      active: settings.exportMode === "no_vlm" || settings.subtitleMode === "basic",
    },
    {
      title: "全量候选调试版",
      desc: "导出所有候选，用于排查召回和误切。",
      active: settings.exportMode === "all_candidates",
    },
    {
      title: "只切不烧字幕版",
      desc: "关闭字幕烧录，快速获得原声片段。",
      active: settings.subtitleMode === "off",
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
              onClick={onCancel}
              className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50"
            >
              取消
            </button>
            <button
              onClick={() => document.querySelector<HTMLElement>(".upload-zone")?.click()}
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
                <UploadZone />
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
              <div className="mt-4 flex flex-wrap gap-2">
                <Chip label={settings.exportMode === "smart" ? "智能模式" : settings.exportMode} tone="blue" />
                <Chip label={settings.provider.toUpperCase()} tone="blue" />
                <Chip label={settings.asrProvider === "volcengine_vc" ? "火山 VC" : settings.asrProvider} tone="emerald" />
                <Chip label={`${settings.subtitleMode} 字幕`} tone="amber" />
                <Chip label={settings.exportResolution} tone="blue" />
                <Chip label={settings.bgmEnabled ? "BGM开启" : "BGM关闭"} tone="emerald" />
              </div>
              <div className="mt-5 space-y-3 text-sm">
                <ChecklistItem label="格式校验" />
                <ChecklistItem label="编码校验" />
                <ChecklistItem label="音频流" />
                <ChecklistItem label="设置校验" />
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
