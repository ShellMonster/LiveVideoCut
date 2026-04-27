import { useState } from "react";
import { Save } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  DEFAULT_API_BASES,
  DEFAULT_MODELS,
  useSettingsStore,
  type AsrProvider,
  type ExportMode,
  type ExportResolution,
  type FillerFilterMode,
  type SegmentGranularity,
  type SubtitleMode,
  type VlmProvider,
} from "@/stores/settingsStore";
import {
  Chip,
  Header,
  InputField,
  SelectField,
  SettingsPanel,
  SliderField,
  ToggleRow,
} from "../shared";

export function AdminSettingsPage() {
  const settings = useSettingsStore();
  const [draft, setDraft] = useState({
    enableVlm: settings.enableVlm,
    exportMode: settings.exportMode,
    provider: settings.provider,
    apiKey: settings.apiKey,
    apiBase: settings.apiBase,
    model: settings.model,
    subtitleMode: settings.subtitleMode,
    asrProvider: settings.asrProvider,
    asrApiKey: settings.asrApiKey,
    enableLlmAnalysis: settings.enableLlmAnalysis,
    llmApiBase: settings.llmApiBase,
    llmModel: settings.llmModel,
    enableBoundaryRefinement: settings.enableBoundaryRefinement,
    exportResolution: settings.exportResolution,
    fillerFilterMode: settings.fillerFilterMode,
    segmentGranularity: settings.segmentGranularity,
    bgmEnabled: settings.bgmEnabled,
    bgmVolume: settings.bgmVolume,
    originalVolume: settings.originalVolume,
    videoSpeed: settings.videoSpeed,
  });

  const saveSettings = () => {
    settings.setSettings(draft);
  };

  const resetSettings = () => {
    settings.reset();
    const latest = useSettingsStore.getState();
    setDraft({
      enableVlm: latest.enableVlm,
      exportMode: latest.exportMode,
      provider: latest.provider,
      apiKey: latest.apiKey,
      apiBase: latest.apiBase,
      model: latest.model,
      subtitleMode: latest.subtitleMode,
      asrProvider: latest.asrProvider,
      asrApiKey: latest.asrApiKey,
      enableLlmAnalysis: latest.enableLlmAnalysis,
      llmApiBase: latest.llmApiBase,
      llmModel: latest.llmModel,
      enableBoundaryRefinement: latest.enableBoundaryRefinement,
      exportResolution: latest.exportResolution,
      fillerFilterMode: latest.fillerFilterMode,
      segmentGranularity: latest.segmentGranularity,
      bgmEnabled: latest.bgmEnabled,
      bgmVolume: latest.bgmVolume,
      originalVolume: latest.originalVolume,
      videoSpeed: latest.videoSpeed,
    });
  };

  return (
    <>
      <Header
        title="系统设置"
        description="配置新上传任务使用的 AI 服务、分段策略、字幕和导出参数"
        action={
          <>
            <button
              onClick={resetSettings}
              className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50"
            >
              恢复默认
            </button>
            <button
              onClick={saveSettings}
              className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
            >
              <Save size={16} />
              保存设置
            </button>
          </>
        }
      />
      <main className="grid gap-5 p-6 xl:grid-cols-[190px_minmax(0,1fr)_320px]">
        <aside className="rounded-lg border border-slate-200 bg-white p-3">
          {["AI 服务", "分段策略", "字幕样式", "导出与音频", "高级参数"].map((item, index) => (
            <button
              key={item}
              className={cn(
                "w-full rounded-lg px-3 py-2 text-left text-sm",
                index === 0 ? "bg-blue-50 font-medium text-blue-700" : "text-slate-600 hover:bg-slate-50",
              )}
            >
              {item}
            </button>
          ))}
        </aside>

        <section className="grid gap-5 lg:grid-cols-2">
          <SettingsPanel title="VLM 设置" desc="控制视觉多模态确认和模型参数。">
            <ToggleRow
              label="启用 VLM"
              checked={draft.enableVlm}
              onChange={(enableVlm) => setDraft({ ...draft, enableVlm, exportMode: enableVlm ? draft.exportMode : "no_vlm" })}
            />
            <SelectField
              label="导出模式"
              value={draft.exportMode}
              onChange={(exportMode) => setDraft({ ...draft, exportMode: exportMode as ExportMode })}
              options={[
                ["smart", "智能模式"],
                ["no_vlm", "跳过 VLM"],
                ["all_candidates", "候选全切"],
                ["all_scenes", "场景全切"],
              ]}
            />
            <SelectField
              label="Provider"
              value={draft.provider}
              onChange={(provider) =>
                setDraft({
                  ...draft,
                  provider: provider as VlmProvider,
                  apiBase: DEFAULT_API_BASES[provider as VlmProvider],
                  model: DEFAULT_MODELS[provider as VlmProvider],
                })
              }
              options={[
                ["qwen", "Qwen"],
                ["glm", "GLM"],
              ]}
            />
            <InputField label="API Base" value={draft.apiBase} onChange={(apiBase) => setDraft({ ...draft, apiBase })} />
            <InputField label="Model" value={draft.model} onChange={(model) => setDraft({ ...draft, model })} />
            <InputField label="API Key" value={draft.apiKey} onChange={(apiKey) => setDraft({ ...draft, apiKey })} password />
          </SettingsPanel>

          <SettingsPanel title="ASR 与 LLM" desc="配置字幕转写、文本分析和边界精修。">
            <SelectField
              label="ASR Provider"
              value={draft.asrProvider}
              onChange={(asrProvider) => setDraft({ ...draft, asrProvider: asrProvider as AsrProvider })}
              options={[
                ["volcengine_vc", "火山 VC"],
                ["volcengine", "火山标准"],
                ["dashscope", "DashScope"],
              ]}
            />
            <InputField label="ASR API Key" value={draft.asrApiKey} onChange={(asrApiKey) => setDraft({ ...draft, asrApiKey })} password />
            <ToggleRow
              label="LLM 文本分析"
              checked={draft.enableLlmAnalysis}
              onChange={(enableLlmAnalysis) => setDraft({ ...draft, enableLlmAnalysis })}
            />
            <InputField label="LLM API Base" value={draft.llmApiBase} onChange={(llmApiBase) => setDraft({ ...draft, llmApiBase })} />
            <InputField label="LLM Model" value={draft.llmModel} onChange={(llmModel) => setDraft({ ...draft, llmModel })} />
            <ToggleRow
              label="边界精修"
              checked={draft.enableBoundaryRefinement}
              onChange={(enableBoundaryRefinement) => setDraft({ ...draft, enableBoundaryRefinement })}
            />
          </SettingsPanel>

          <SettingsPanel title="字幕与切分" desc="控制字幕样式、语气词过滤和切分粒度。">
            <SelectField
              label="字幕模式"
              value={draft.subtitleMode}
              onChange={(subtitleMode) => setDraft({ ...draft, subtitleMode: subtitleMode as SubtitleMode })}
              options={[
                ["off", "关闭"],
                ["basic", "基础字幕"],
                ["styled", "样式字幕"],
                ["karaoke", "Karaoke"],
              ]}
            />
            <SelectField
              label="语气词过滤"
              value={draft.fillerFilterMode}
              onChange={(fillerFilterMode) => setDraft({ ...draft, fillerFilterMode: fillerFilterMode as FillerFilterMode })}
              options={[
                ["off", "关闭"],
                ["subtitle", "仅字幕"],
                ["video", "字幕+视频裁剪"],
              ]}
            />
            <SelectField
              label="切分粒度"
              value={draft.segmentGranularity}
              onChange={(segmentGranularity) => setDraft({ ...draft, segmentGranularity: segmentGranularity as SegmentGranularity })}
              options={[
                ["single_item", "单品"],
                ["outfit", "整套搭配"],
              ]}
            />
          </SettingsPanel>

          <SettingsPanel title="导出与音频" desc="控制分辨率、倍速、封面和 BGM 混音。">
            <SelectField
              label="导出分辨率"
              value={draft.exportResolution}
              onChange={(exportResolution) => setDraft({ ...draft, exportResolution: exportResolution as ExportResolution })}
              options={[
                ["1080p", "1080p"],
                ["4k", "4K"],
                ["original", "原始"],
              ]}
            />
            <SelectField
              label="视频倍速"
              value={String(draft.videoSpeed)}
              onChange={(videoSpeed) => setDraft({ ...draft, videoSpeed: Number(videoSpeed) as typeof draft.videoSpeed })}
              options={[
                ["0.5", "0.5x"],
                ["0.75", "0.75x"],
                ["1", "1x"],
                ["1.25", "1.25x"],
                ["1.5", "1.5x"],
                ["1.75", "1.75x"],
                ["2", "2x"],
                ["3", "3x"],
              ]}
            />
            <ToggleRow label="启用 BGM" checked={draft.bgmEnabled} onChange={(bgmEnabled) => setDraft({ ...draft, bgmEnabled })} />
            <SliderField label="BGM 音量" value={draft.bgmVolume} max={1} onChange={(bgmVolume) => setDraft({ ...draft, bgmVolume })} />
            <SliderField label="原声音量" value={draft.originalVolume} max={2} onChange={(originalVolume) => setDraft({ ...draft, originalVolume })} />
          </SettingsPanel>
        </section>

        <aside className="space-y-5">
          <div className="rounded-lg border border-slate-200 bg-white p-5">
            <h2 className="text-sm font-semibold text-slate-900">当前配置预览</h2>
            <div className="mt-4 flex flex-wrap gap-2">
              <Chip label={draft.exportMode === "smart" ? "智能模式" : draft.exportMode} tone="blue" />
              <Chip label={draft.provider.toUpperCase()} tone="blue" />
              <Chip label={draft.asrProvider === "volcengine_vc" ? "火山 VC" : draft.asrProvider} tone="emerald" />
              <Chip label={`${draft.subtitleMode} 字幕`} tone="amber" />
              <Chip label={draft.exportResolution} tone="blue" />
              <Chip label={draft.bgmEnabled ? `BGM ${Math.round(draft.bgmVolume * 100)}%` : "BGM关闭"} tone="emerald" />
            </div>
            <div className="mt-5 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-700">
              设置结构有效，将在新上传任务时写入 settings.json。
            </div>
          </div>
        </aside>
      </main>
    </>
  );
}
