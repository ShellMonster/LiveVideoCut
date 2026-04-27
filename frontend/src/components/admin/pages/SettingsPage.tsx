import { useMemo, useState } from "react";
import { Check, Info, Save, SlidersHorizontal } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  DEFAULT_API_BASES,
  DEFAULT_MODELS,
  useSettingsStore,
  type AsrProvider,
  type CoverStrategy,
  type ExportMode,
  type ExportResolution,
  type FillerFilterMode,
  type LlmType,
  type Settings,
  type SubtitleMode,
  type SubtitlePosition,
  type SubtitleTemplate,
  type VlmProvider,
} from "@/stores/settingsStore";
import { Chip, Header } from "../shared";

type SettingsDraft = Settings;

const sectionTabs = ["处理预设", "AI 服务", "字幕与转写", "切分策略", "导出与音频", "高级参数"];

const exportModeLabels: Record<ExportMode, string> = {
  smart: "智能模式",
  no_vlm: "跳过 VLM",
  all_candidates: "候选全切",
  all_scenes: "场景全切",
};

const asrLabels: Record<AsrProvider, string> = {
  volcengine_vc: "火山 VC",
  volcengine: "火山标准",
  dashscope: "DashScope",
};

const subtitleLabels: Record<SubtitleMode, string> = {
  off: "关闭",
  basic: "基础字幕",
  styled: "样式字幕",
  karaoke: "Karaoke",
};

const initialDraft = (settings: ReturnType<typeof useSettingsStore.getState>): SettingsDraft => ({
  enableVlm: settings.enableVlm,
  exportMode: settings.exportMode,
  provider: settings.provider,
  apiKey: settings.apiKey,
  apiBase: settings.apiBase,
  model: settings.model,
  reviewStrictness: settings.reviewStrictness,
  reviewMode: settings.reviewMode,
  sceneThreshold: settings.sceneThreshold,
  frameSampleFps: settings.frameSampleFps,
  recallCooldownSeconds: settings.recallCooldownSeconds,
  candidateLooseness: settings.candidateLooseness,
  minSegmentDurationSeconds: settings.minSegmentDurationSeconds,
  dedupeWindowSeconds: settings.dedupeWindowSeconds,
  mergeCount: settings.mergeCount,
  allowReturnedProduct: settings.allowReturnedProduct,
  maxCandidateCount: settings.maxCandidateCount,
  subtitleMode: settings.subtitleMode,
  subtitlePosition: settings.subtitlePosition,
  subtitleTemplate: settings.subtitleTemplate,
  fillerFilterMode: settings.fillerFilterMode,
  coverStrategy: settings.coverStrategy,
  videoSpeed: settings.videoSpeed,
  boundarySnap: settings.boundarySnap,
  enableBoundaryRefinement: settings.enableBoundaryRefinement,
  customPositionY: settings.customPositionY,
  asrProvider: settings.asrProvider,
  asrApiKey: settings.asrApiKey,
  tosAk: settings.tosAk,
  tosSk: settings.tosSk,
  tosBucket: settings.tosBucket,
  tosRegion: settings.tosRegion,
  tosEndpoint: settings.tosEndpoint,
  enableLlmAnalysis: settings.enableLlmAnalysis,
  llmApiKey: settings.llmApiKey,
  llmApiBase: settings.llmApiBase,
  llmModel: settings.llmModel,
  llmType: settings.llmType,
  exportResolution: settings.exportResolution,
  segmentGranularity: settings.segmentGranularity,
  bgmEnabled: settings.bgmEnabled,
  bgmVolume: settings.bgmVolume,
  originalVolume: settings.originalVolume,
});

const isVolcengineAsr = (provider: AsrProvider) => provider === "volcengine" || provider === "volcengine_vc";

export function AdminSettingsPage() {
  const settings = useSettingsStore();
  const [draft, setDraft] = useState<SettingsDraft>(() => initialDraft(useSettingsStore.getState()));
  const [expandedAdvanced, setExpandedAdvanced] = useState(false);

  const savedSnapshot = useMemo(() => JSON.stringify(initialDraft(settings)), [settings]);
  const draftSnapshot = useMemo(() => JSON.stringify(draft), [draft]);
  const hasUnsavedChanges = savedSnapshot !== draftSnapshot;

  const updateDraft = (partial: Partial<SettingsDraft>) => {
    setDraft((current) => ({ ...current, ...partial }));
  };

  const applyPreset = (preset: "quality" | "fast" | "debug" | "plain") => {
    if (preset === "quality") {
      updateDraft({
        enableVlm: true,
        exportMode: "smart",
        asrProvider: "volcengine_vc",
        subtitleMode: "karaoke",
        bgmEnabled: true,
        exportResolution: "1080p",
        videoSpeed: 1.25,
      });
      return;
    }
    if (preset === "fast") {
      updateDraft({
        enableVlm: false,
        exportMode: "no_vlm",
        asrProvider: "dashscope",
        subtitleMode: "basic",
        bgmEnabled: false,
        exportResolution: "1080p",
      });
      return;
    }
    if (preset === "debug") {
      updateDraft({
        enableVlm: false,
        exportMode: "all_candidates",
        subtitleMode: "basic",
        bgmEnabled: false,
      });
      return;
    }
    updateDraft({
      subtitleMode: "off",
      bgmEnabled: false,
      fillerFilterMode: "off",
    });
  };

  const saveSettings = () => {
    settings.setSettings(draft);
  };

  const resetSettings = () => {
    settings.reset();
    setDraft(initialDraft(useSettingsStore.getState()));
  };

  const needsVlmKey = draft.exportMode === "smart" && draft.enableVlm;
  const needsTos = isVolcengineAsr(draft.asrProvider);
  const llmReady = !draft.enableLlmAnalysis || Boolean(draft.llmApiKey.trim());
  const tosReady =
    !needsTos ||
    Boolean(draft.tosAk.trim() && draft.tosSk.trim() && draft.tosBucket.trim() && draft.tosRegion.trim() && draft.tosEndpoint.trim());

  return (
    <>
      <Header
        title="系统设置"
        description="配置新上传任务使用的 AI 服务、字幕、切分策略和导出参数"
        action={
          <>
            {hasUnsavedChanges && (
              <span className="rounded-full bg-amber-50 px-3 py-1.5 text-xs font-medium text-amber-700">
                有未保存更改
              </span>
            )}
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

      <main className="grid gap-5 p-6 xl:grid-cols-[minmax(0,1fr)_340px]">
        <section className="min-w-0 space-y-5">
          <div className="flex flex-wrap gap-2 rounded-lg border border-slate-200 bg-white p-2">
            {sectionTabs.map((tab, index) => (
              <a
                key={tab}
                href={`#settings-section-${index}`}
                className="rounded-md px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50 hover:text-slate-950"
              >
                {tab}
              </a>
            ))}
          </div>

          <SettingsCard
            id="settings-section-0"
            title="处理预设"
            desc="先选择本次剪辑目标，再微调下方参数。预设只更新草稿，保存后才会生效。"
            badge="推荐先选"
          >
            <div className="grid gap-3 md:grid-cols-2">
              <PresetCard
                title="高质量字幕版"
                desc="火山 VC + Karaoke 字幕 + BGM，适合正式交付和公开视频。"
                selected={draft.asrProvider === "volcengine_vc" && draft.subtitleMode === "karaoke" && draft.bgmEnabled}
                tags={["质量高", "推荐"]}
                onClick={() => applyPreset("quality")}
              />
              <PresetCard
                title="快速低成本版"
                desc="跳过 VLM，使用基础字幕，适合快速预览切片结果。"
                selected={draft.exportMode === "no_vlm" && draft.subtitleMode === "basic"}
                tags={["速度快", "成本低"]}
                onClick={() => applyPreset("fast")}
              />
              <PresetCard
                title="全量候选调试版"
                desc="导出所有候选片段，用于排查召回不足或误切问题。"
                selected={draft.exportMode === "all_candidates"}
                tags={["调试", "候选全切"]}
                onClick={() => applyPreset("debug")}
              />
              <PresetCard
                title="纯切片无字幕版"
                desc="关闭字幕和 BGM，只导出原声片段，适合二次剪辑。"
                selected={draft.subtitleMode === "off" && !draft.bgmEnabled}
                tags={["无字幕", "无混音"]}
                onClick={() => applyPreset("plain")}
              />
            </div>
          </SettingsCard>

          <SettingsCard
            id="settings-section-1"
            title="AI 服务"
            desc="控制视觉多模态确认和模型调用。非智能模式会自动收起 VLM 凭证。"
            badge={needsVlmKey ? "VLM 已启用" : "VLM 未启用"}
          >
            <Field label="导出模式" hint="影响是否调用 VLM">
              <SegmentedControl
                value={draft.exportMode}
                onChange={(exportMode) =>
                  updateDraft({
                    exportMode: exportMode as ExportMode,
                    enableVlm: exportMode === "smart",
                  })
                }
                options={[
                  ["smart", "智能模式"],
                  ["no_vlm", "跳过 VLM"],
                  ["all_candidates", "候选全切"],
                  ["all_scenes", "场景全切"],
                ]}
              />
            </Field>

            {needsVlmKey ? (
              <div className="mt-4 grid gap-4 md:grid-cols-2">
                <Field label="Provider" hint="视觉模型">
                  <select
                    value={draft.provider}
                    onChange={(event) => {
                      const provider = event.target.value as VlmProvider;
                      updateDraft({
                        provider,
                        apiBase: DEFAULT_API_BASES[provider],
                        model: DEFAULT_MODELS[provider],
                      });
                    }}
                    className={fieldClassName}
                  >
                    <option value="qwen">Qwen</option>
                    <option value="glm">GLM</option>
                  </select>
                </Field>
                <Field label="Model">
                  <input value={draft.model} onChange={(event) => updateDraft({ model: event.target.value })} className={fieldClassName} />
                </Field>
                <Field label="API Base" className="md:col-span-2">
                  <input value={draft.apiBase} onChange={(event) => updateDraft({ apiBase: event.target.value })} className={fieldClassName} />
                </Field>
                <Field label="API Key" hint="敏感字段，上传时写入 secrets.json" className="md:col-span-2">
                  <input
                    type="password"
                    value={draft.apiKey}
                    onChange={(event) => updateDraft({ apiKey: event.target.value })}
                    className={fieldClassName}
                  />
                </Field>
              </div>
            ) : (
              <Notice text="当前导出模式不会调用 VLM，Provider、Model 和 VLM API Key 会保留但不会用于新任务。" />
            )}
          </SettingsCard>

          <SettingsCard
            id="settings-section-2"
            title="字幕与转写"
            desc="ASR 决定字幕时间轴质量。Karaoke 模式推荐火山 VC。"
            badge={draft.asrProvider === "volcengine_vc" ? "火山 VC 推荐" : undefined}
          >
            <div className="grid gap-3 md:grid-cols-3">
              <OptionCard
                title="火山 VC 字幕"
                desc="剪映引擎分句，真实节奏时间戳，适合 Karaoke 字幕。"
                selected={draft.asrProvider === "volcengine_vc"}
                onClick={() => updateDraft({ asrProvider: "volcengine_vc" })}
              />
              <OptionCard
                title="火山标准版"
                desc="真实时间戳，成本低于 VC，中文词边界略弱。"
                selected={draft.asrProvider === "volcengine"}
                onClick={() => updateDraft({ asrProvider: "volcengine" })}
              />
              <OptionCard
                title="DashScope"
                desc="成本较低，基础字幕可用，不推荐 Karaoke 跳字。"
                selected={draft.asrProvider === "dashscope"}
                onClick={() => updateDraft({ asrProvider: "dashscope" })}
              />
            </div>

            <div className="mt-4 grid gap-4 md:grid-cols-2">
              <Field label="字幕模式">
                <select
                  value={draft.subtitleMode}
                  onChange={(event) => updateDraft({ subtitleMode: event.target.value as SubtitleMode })}
                  className={fieldClassName}
                >
                  <option value="off">关闭</option>
                  <option value="basic">基础字幕</option>
                  <option value="styled">样式字幕</option>
                  <option value="karaoke">Karaoke</option>
                </select>
              </Field>
              <Field label="语气词过滤">
                <select
                  value={draft.fillerFilterMode}
                  onChange={(event) => updateDraft({ fillerFilterMode: event.target.value as FillerFilterMode })}
                  className={fieldClassName}
                  disabled={draft.subtitleMode === "off"}
                >
                  <option value="off">关闭</option>
                  <option value="subtitle">仅字幕</option>
                  <option value="video">字幕+视频裁剪</option>
                </select>
              </Field>
              <Field label="字幕位置">
                <select
                  value={draft.subtitlePosition}
                  onChange={(event) => updateDraft({ subtitlePosition: event.target.value as SubtitlePosition })}
                  className={fieldClassName}
                  disabled={draft.subtitleMode === "off"}
                >
                  <option value="bottom">底部</option>
                  <option value="middle">中部</option>
                  <option value="custom">自定义</option>
                </select>
              </Field>
              <Field label="字幕模板">
                <select
                  value={draft.subtitleTemplate}
                  onChange={(event) => updateDraft({ subtitleTemplate: event.target.value as SubtitleTemplate })}
                  className={fieldClassName}
                  disabled={draft.subtitleMode === "off"}
                >
                  <option value="clean">Clean</option>
                  <option value="ecommerce">电商</option>
                  <option value="bold">加粗</option>
                  <option value="karaoke">Karaoke</option>
                </select>
              </Field>
              <Field label="ASR API Key" className="md:col-span-2">
                <input
                  type="password"
                  value={draft.asrApiKey}
                  onChange={(event) => updateDraft({ asrApiKey: event.target.value })}
                  className={fieldClassName}
                />
              </Field>
            </div>

            {needsTos && (
              <div className="mt-4 rounded-lg border border-blue-100 bg-blue-50 p-4">
                <div className="flex items-center gap-2 text-sm font-semibold text-blue-900">
                  <Info size={16} />
                  火山存储配置
                </div>
                <p className="mt-1 text-xs leading-5 text-blue-700">
                  火山标准版和 VC 字幕需要 TOS 上传音频。敏感字段上传时会写入 secrets.json。
                </p>
                <div className="mt-4 grid gap-4 md:grid-cols-2">
                  <Field label="TOS AK">
                    <input value={draft.tosAk} onChange={(event) => updateDraft({ tosAk: event.target.value })} className={fieldClassName} />
                  </Field>
                  <Field label="TOS SK">
                    <input
                      type="password"
                      value={draft.tosSk}
                      onChange={(event) => updateDraft({ tosSk: event.target.value })}
                      className={fieldClassName}
                    />
                  </Field>
                  <Field label="Bucket">
                    <input value={draft.tosBucket} onChange={(event) => updateDraft({ tosBucket: event.target.value })} className={fieldClassName} />
                  </Field>
                  <Field label="Region">
                    <input value={draft.tosRegion} onChange={(event) => updateDraft({ tosRegion: event.target.value })} className={fieldClassName} />
                  </Field>
                  <Field label="Endpoint" className="md:col-span-2">
                    <input
                      value={draft.tosEndpoint}
                      onChange={(event) => updateDraft({ tosEndpoint: event.target.value })}
                      className={fieldClassName}
                    />
                  </Field>
                </div>
              </div>
            )}
          </SettingsCard>

          <SettingsCard
            id="settings-section-3"
            title="切分策略"
            desc="控制商品讨论段和视觉换衣信号如何融合。"
          >
            <div className="grid gap-3 md:grid-cols-2">
              <OptionCard
                title="单品切分"
                desc="搭配中的毛衣、裙子、背心等分别导出，适合商品讲解短视频。"
                selected={draft.segmentGranularity === "single_item"}
                onClick={() => updateDraft({ segmentGranularity: "single_item" })}
              />
              <OptionCard
                title="整套搭配"
                desc="把同一套穿搭合并成一个片段，适合穿搭整体展示。"
                selected={draft.segmentGranularity === "outfit"}
                onClick={() => updateDraft({ segmentGranularity: "outfit" })}
              />
            </div>

            <div className="mt-4 space-y-3">
              <ToggleCard
                title="句边界对齐"
                desc="将片段起止时间对齐到 ASR 句子边界，避免截断半句话。"
                checked={draft.boundarySnap}
                onChange={(boundarySnap) => updateDraft({ boundarySnap })}
              />
              <ToggleCard
                title="LLM 文本分析"
                desc="根据 transcript 识别换品边界，与视觉候选融合。"
                checked={draft.enableLlmAnalysis}
                onChange={(enableLlmAnalysis) =>
                  updateDraft({
                    enableLlmAnalysis,
                    enableBoundaryRefinement: enableLlmAnalysis ? draft.enableBoundaryRefinement : false,
                  })
                }
              />
              {draft.enableLlmAnalysis && (
                <div className="grid gap-4 md:grid-cols-3">
                  <Field label="LLM 类型">
                    <select
                      value={draft.llmType}
                      onChange={(event) => updateDraft({ llmType: event.target.value as LlmType })}
                      className={fieldClassName}
                    >
                      <option value="openai">OpenAI Compatible</option>
                      <option value="gemini">Gemini</option>
                    </select>
                  </Field>
                  <Field label="LLM API Base">
                    <input value={draft.llmApiBase} onChange={(event) => updateDraft({ llmApiBase: event.target.value })} className={fieldClassName} />
                  </Field>
                  <Field label="LLM Model">
                    <input value={draft.llmModel} onChange={(event) => updateDraft({ llmModel: event.target.value })} className={fieldClassName} />
                  </Field>
                  <Field label="LLM API Key" className="md:col-span-3">
                    <input
                      type="password"
                      value={draft.llmApiKey}
                      onChange={(event) => updateDraft({ llmApiKey: event.target.value })}
                      className={fieldClassName}
                    />
                  </Field>
                </div>
              )}
              <ToggleCard
                title="LLM 边界精修"
                desc="依赖 LLM 文本分析。关闭 LLM 时自动禁用。"
                checked={draft.enableBoundaryRefinement}
                disabled={!draft.enableLlmAnalysis}
                onChange={(enableBoundaryRefinement) => updateDraft({ enableBoundaryRefinement })}
              />
            </div>
          </SettingsCard>

          <SettingsCard
            id="settings-section-4"
            title="导出与音频"
            desc="控制分辨率、视频倍速、封面选择和 BGM 混音。"
          >
            <div className="grid gap-4 md:grid-cols-2">
              <Field label="导出分辨率">
                <select
                  value={draft.exportResolution}
                  onChange={(event) => updateDraft({ exportResolution: event.target.value as ExportResolution })}
                  className={fieldClassName}
                >
                  <option value="1080p">1080p</option>
                  <option value="4k">4K</option>
                  <option value="original">原始</option>
                </select>
              </Field>
              <Field label="封面策略">
                <select
                  value={draft.coverStrategy}
                  onChange={(event) => updateDraft({ coverStrategy: event.target.value as CoverStrategy })}
                  className={fieldClassName}
                >
                  <option value="content_first">商品优先</option>
                  <option value="person_first">主播优先</option>
                </select>
              </Field>
              <Field label="视频倍速" hint="先烧字幕再变速" className="md:col-span-2">
                <SegmentedControl
                  value={String(draft.videoSpeed)}
                  onChange={(videoSpeed) => updateDraft({ videoSpeed: Number(videoSpeed) as SettingsDraft["videoSpeed"] })}
                  options={[
                    ["1", "1x"],
                    ["1.25", "1.25x"],
                    ["1.5", "1.5x"],
                    ["2", "2x"],
                  ]}
                />
              </Field>
            </div>

            <div className="mt-4 space-y-3">
              <ToggleCard
                title="启用 BGM"
                desc="自动从内置曲库和用户曲库中按商品类型选曲。"
                checked={draft.bgmEnabled}
                onChange={(bgmEnabled) => updateDraft({ bgmEnabled })}
              />
              {draft.bgmEnabled && (
                <div className="grid gap-4 md:grid-cols-2">
                  <RangeField label="BGM 音量" value={draft.bgmVolume} max={1} onChange={(bgmVolume) => updateDraft({ bgmVolume })} />
                  <RangeField label="原声音量" value={draft.originalVolume} max={2} onChange={(originalVolume) => updateDraft({ originalVolume })} />
                </div>
              )}
            </div>
          </SettingsCard>

          <SettingsCard
            id="settings-section-5"
            title="高级参数"
            desc="默认只展示关键数值。需要排查召回、误切或性能问题时再展开完整表单。"
            badge="谨慎调整"
          >
            <div className="grid gap-3 md:grid-cols-4">
              <MetricBox label="场景阈值" value={String(draft.sceneThreshold)} hint="越低越敏感" />
              <MetricBox label="抽帧帧率" value={String(draft.frameSampleFps)} hint="fps" />
              <MetricBox label="最小时长" value={`${draft.minSegmentDurationSeconds}s`} hint="短于此值回退" />
              <MetricBox label="最大候选" value={String(draft.maxCandidateCount)} hint="限制导出数量" />
            </div>
            <button
              onClick={() => setExpandedAdvanced((value) => !value)}
              className="mt-4 inline-flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50"
            >
              <SlidersHorizontal size={16} />
              {expandedAdvanced ? "收起高级参数" : "展开高级参数"}
            </button>
            {expandedAdvanced && (
              <div className="mt-4 grid gap-4 md:grid-cols-2">
                <NumberField label="场景检测阈值" value={draft.sceneThreshold} fallback={27} onChange={(sceneThreshold) => updateDraft({ sceneThreshold })} />
                <NumberField label="抽帧帧率 (fps)" value={draft.frameSampleFps} fallback={0.5} onChange={(frameSampleFps) => updateDraft({ frameSampleFps })} />
                <NumberField
                  label="最小片段时长 (秒)"
                  value={draft.minSegmentDurationSeconds}
                  fallback={25}
                  onChange={(minSegmentDurationSeconds) => updateDraft({ minSegmentDurationSeconds })}
                />
                <NumberField label="去重窗口 (秒)" value={draft.dedupeWindowSeconds} fallback={90} onChange={(dedupeWindowSeconds) => updateDraft({ dedupeWindowSeconds })} />
                <NumberField label="最大候选数" value={draft.maxCandidateCount} fallback={20} onChange={(maxCandidateCount) => updateDraft({ maxCandidateCount })} />
                <NumberField
                  label="召回冷却时间 (秒)"
                  value={draft.recallCooldownSeconds}
                  fallback={15}
                  onChange={(recallCooldownSeconds) => updateDraft({ recallCooldownSeconds })}
                />
                <NumberField label="合并数量" value={draft.mergeCount} fallback={1} onChange={(mergeCount) => updateDraft({ mergeCount })} />
                <ToggleCard
                  title="允许回讲商品"
                  desc="同一商品被主播回讲时允许再次生成候选。"
                  checked={draft.allowReturnedProduct}
                  onChange={(allowReturnedProduct) => updateDraft({ allowReturnedProduct })}
                />
              </div>
            )}
          </SettingsCard>
        </section>

        <aside className="space-y-5 xl:sticky xl:top-6 xl:self-start">
          <div className="rounded-lg border border-slate-200 bg-white p-5">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="text-sm font-semibold text-slate-900">当前配置摘要</h2>
                <p className="mt-1 text-xs text-slate-500">保存后，新上传任务会使用这组配置。</p>
              </div>
              <span className="rounded-full bg-blue-50 px-2.5 py-1 text-xs font-medium text-blue-700">
                {hasUnsavedChanges ? "草稿" : "已保存"}
              </span>
            </div>

            <div className="mt-4 flex flex-wrap gap-2">
              <Chip label={exportModeLabels[draft.exportMode]} tone="blue" />
              <Chip label={asrLabels[draft.asrProvider]} tone="emerald" />
              <Chip label={`${subtitleLabels[draft.subtitleMode]} 字幕`} tone="amber" />
              <Chip label={draft.exportResolution} tone="blue" />
            </div>

            <div className="mt-5 divide-y divide-slate-100 text-sm">
              <SummaryRow label="处理模式" value={exportModeLabels[draft.exportMode]} />
              <SummaryRow label="质量倾向" value={draft.asrProvider === "volcengine_vc" ? "高质量" : "标准"} />
              <SummaryRow label="成本倾向" value={draft.asrProvider === "volcengine_vc" || needsVlmKey ? "偏高" : "较低"} />
              <SummaryRow label="字幕链路" value={`${asrLabels[draft.asrProvider]} + ${subtitleLabels[draft.subtitleMode]}`} />
              <SummaryRow label="导出规格" value={`${draft.exportResolution} · ${draft.videoSpeed}x`} />
              <SummaryRow label="音频" value={draft.bgmEnabled ? `BGM ${Math.round(draft.bgmVolume * 100)}% / 原声 ${Math.round(draft.originalVolume * 100)}%` : "无 BGM"} />
            </div>
          </div>

          <div className="rounded-lg border border-slate-200 bg-white p-5">
            <h2 className="text-sm font-semibold text-slate-900">依赖检查</h2>
            <div className="mt-4 space-y-3">
              <DependencyRow label="VLM API Key" ok={!needsVlmKey || Boolean(draft.apiKey.trim())} inactive={!needsVlmKey} />
              <DependencyRow label="ASR API Key" ok={Boolean(draft.asrApiKey.trim())} />
              <DependencyRow label="火山 TOS" ok={tosReady} inactive={!needsTos} />
              <DependencyRow label="LLM Key" ok={llmReady} inactive={!draft.enableLlmAnalysis} />
            </div>
            <div className="mt-5 rounded-lg bg-slate-50 p-3 text-xs leading-5 text-slate-500">
              设置保存在浏览器 localStorage。上传时非敏感配置写入 settings.json，敏感字段写入 secrets.json。
            </div>
          </div>
        </aside>
      </main>
    </>
  );
}

const fieldClassName =
  "h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-800 outline-none transition focus:border-blue-400 disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-400";

function SettingsCard({
  id,
  title,
  desc,
  badge,
  children,
}: {
  id: string;
  title: string;
  desc: string;
  badge?: string;
  children: React.ReactNode;
}) {
  return (
    <section id={id} className="scroll-mt-6 rounded-lg border border-slate-200 bg-white">
      <div className="flex items-start justify-between gap-4 border-b border-slate-100 px-5 py-4">
        <div>
          <h2 className="text-sm font-semibold text-slate-950">{title}</h2>
          <p className="mt-1 text-xs leading-5 text-slate-500">{desc}</p>
        </div>
        {badge && <span className="shrink-0 rounded-full bg-blue-50 px-2.5 py-1 text-xs font-medium text-blue-700">{badge}</span>}
      </div>
      <div className="p-5">{children}</div>
    </section>
  );
}

function PresetCard({
  title,
  desc,
  selected,
  tags,
  onClick,
}: {
  title: string;
  desc: string;
  selected: boolean;
  tags: string[];
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "rounded-lg border p-4 text-left transition",
        selected ? "border-blue-300 bg-blue-50 ring-2 ring-blue-100" : "border-slate-200 bg-white hover:bg-slate-50",
      )}
    >
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-slate-950">{title}</h3>
        <span className={cn("grid h-5 w-5 place-items-center rounded-full border", selected ? "border-blue-600 bg-blue-600 text-white" : "border-slate-300")}>
          {selected && <Check size={13} />}
        </span>
      </div>
      <p className="mt-2 text-xs leading-5 text-slate-500">{desc}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {tags.map((tag) => (
          <span key={tag} className="rounded-full bg-white px-2 py-1 text-xs font-medium text-slate-600 ring-1 ring-slate-200">
            {tag}
          </span>
        ))}
      </div>
    </button>
  );
}

function OptionCard({
  title,
  desc,
  selected,
  onClick,
}: {
  title: string;
  desc: string;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "rounded-lg border p-4 text-left transition",
        selected ? "border-blue-300 bg-blue-50" : "border-slate-200 bg-white hover:bg-slate-50",
      )}
    >
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-slate-950">{title}</h3>
        {selected && <span className="rounded-full bg-blue-600 px-2 py-0.5 text-xs font-medium text-white">当前</span>}
      </div>
      <p className="mt-2 text-xs leading-5 text-slate-500">{desc}</p>
    </button>
  );
}

function Field({
  label,
  hint,
  className,
  children,
}: {
  label: string;
  hint?: string;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <label className={cn("block", className)}>
      <span className="mb-1.5 flex items-center justify-between gap-3 text-xs">
        <span className="font-medium text-slate-600">{label}</span>
        {hint && <span className="text-slate-400">{hint}</span>}
      </span>
      {children}
    </label>
  );
}

function SegmentedControl({
  value,
  onChange,
  options,
}: {
  value: string;
  onChange: (value: string) => void;
  options: [string, string][];
}) {
  return (
    <div className="grid gap-1 rounded-lg bg-slate-100 p-1 sm:grid-flow-col sm:auto-cols-fr">
      {options.map(([optionValue, label]) => (
        <button
          key={optionValue}
          onClick={() => onChange(optionValue)}
          className={cn(
            "rounded-md px-3 py-2 text-sm font-medium transition",
            value === optionValue ? "bg-white text-blue-700 shadow-sm" : "text-slate-500 hover:text-slate-800",
          )}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

function ToggleCard({
  title,
  desc,
  checked,
  disabled,
  onChange,
}: {
  title: string;
  desc: string;
  checked: boolean;
  disabled?: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <div className={cn("flex items-center justify-between gap-4 rounded-lg bg-slate-50 px-4 py-3", disabled && "opacity-60")}>
      <div className="min-w-0">
        <div className="text-sm font-medium text-slate-800">{title}</div>
        <p className="mt-1 text-xs leading-5 text-slate-500">{desc}</p>
      </div>
      <button
        onClick={() => !disabled && onChange(!checked)}
        disabled={disabled}
        className={cn("h-6 w-11 shrink-0 rounded-full p-0.5 transition-colors", checked ? "bg-blue-600" : "bg-slate-300", disabled && "cursor-not-allowed")}
        aria-label={title}
      >
        <span className={cn("block h-5 w-5 rounded-full bg-white transition-transform", checked && "translate-x-5")} />
      </button>
    </div>
  );
}

function RangeField({
  label,
  value,
  max,
  onChange,
}: {
  label: string;
  value: number;
  max: number;
  onChange: (value: number) => void;
}) {
  return (
    <label className="block rounded-lg bg-slate-50 p-4">
      <span className="mb-2 flex items-center justify-between text-xs">
        <span className="font-medium text-slate-600">{label}</span>
        <span className="font-semibold text-slate-800">{Math.round(value * 100)}%</span>
      </span>
      <input
        type="range"
        min={0}
        max={max}
        step={0.05}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
        className="w-full"
      />
    </label>
  );
}

function NumberField({
  label,
  value,
  fallback,
  onChange,
}: {
  label: string;
  value: number;
  fallback: number;
  onChange: (value: number) => void;
}) {
  return (
    <Field label={label}>
      <input value={String(value)} onChange={(event) => onChange(Number(event.target.value) || fallback)} className={fieldClassName} />
    </Field>
  );
}

function Notice({ text }: { text: string }) {
  return (
    <div className="mt-4 flex gap-3 rounded-lg border border-blue-100 bg-blue-50 p-4 text-sm leading-6 text-blue-800">
      <Info className="mt-0.5 h-4 w-4 shrink-0" />
      <span>{text}</span>
    </div>
  );
}

function MetricBox({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="text-xs font-medium text-slate-500">{label}</div>
      <div className="mt-2 text-xl font-semibold text-slate-950">{value}</div>
      <div className="mt-1 text-xs text-slate-400">{hint}</div>
    </div>
  );
}

function SummaryRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4 py-3">
      <span className="text-slate-500">{label}</span>
      <span className="text-right font-medium text-slate-900">{value}</span>
    </div>
  );
}

function DependencyRow({ label, ok, inactive }: { label: string; ok: boolean; inactive?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-3 text-sm">
      <span className={inactive ? "text-slate-400" : "text-slate-700"}>{label}</span>
      <span
        className={cn(
          "rounded-full px-2.5 py-1 text-xs font-medium",
          inactive ? "bg-slate-100 text-slate-500" : ok ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700",
        )}
      >
        {inactive ? "未启用" : ok ? "已配置" : "需确认"}
      </span>
    </div>
  );
}
