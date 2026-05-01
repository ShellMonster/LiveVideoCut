import { useEffect, useMemo, useState, type PointerEvent } from "react";
import { Save, SlidersHorizontal, X } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  diffSettingsToPayload,
  payloadToSettings,
  useSettingsStore,
  type AsrProvider,
  type ChangeDetectionFusionMode,
  type ChangeDetectionSensitivity,
  type CoverStrategy,
  type ExportResolution,
  type FFmpegPreset,
  type FillerFilterMode,
  type LlmType,
  type SensitiveFilterMode,
  type SensitiveMatchMode,
  type Settings,
  type SubtitleMode,
  type SubtitlePosition,
  type SubtitleTemplate,
  type SettingsPayload,
} from "@/stores/settingsStore";
import { useToastStore } from "@/stores/toastStore";
import { API_BASE, fetchJson, sendJson } from "../api";
import { Chip, Header } from "../shared";
import {
  DependencyRow,
  Field,
  MetricBox,
  NumberField,
  OptionCard,
  RangeField,
  SecretInput,
  SegmentedControl,
  SettingsCard,
  SubtitlePositionEditor,
  SummaryRow,
  ToggleCard,
  fieldClassName,
} from "../settings/SettingsControls";
import { asrLabels, exportModeLabels, sectionTabs, subtitleLabels, subtitleTemplateLabels } from "../settings/labels";
import { AiServicesSection, PresetSection, TranscriptionSection } from "../settings/SettingsSections";
import type { SettingsDraft } from "../settings/types";

const initialDraft = (state: ReturnType<typeof useSettingsStore.getState>): SettingsDraft => {
  const settings: Partial<ReturnType<typeof useSettingsStore.getState>> = { ...state };
  delete settings.setSettings;
  delete settings.reset;
  return settings as Settings;
};

const isVolcengineAsr = (provider: AsrProvider) => provider === "volcengine" || provider === "volcengine_vc";

export function AdminSettingsPage() {
  const settings = useSettingsStore();
  const showToast = useToastStore((state) => state.showToast);
  const [draft, setDraft] = useState<SettingsDraft>(() => initialDraft(useSettingsStore.getState()));
  const [loadingSettings, setLoadingSettings] = useState(true);
  const [savingSettings, setSavingSettings] = useState(false);
  const [expandedAdvanced, setExpandedAdvanced] = useState(true);
  const [activeSection, setActiveSection] = useState(0);
  const [sensitiveWordInput, setSensitiveWordInput] = useState("");
  const [hoveredSubtitlePreset, setHoveredSubtitlePreset] = useState<SubtitlePosition | null>(null);

  const settingsBase = useMemo(() => initialDraft(settings), [settings]);
  const settingsDiff = useMemo(() => diffSettingsToPayload(settingsBase, draft), [settingsBase, draft]);
  const hasUnsavedChanges = Object.keys(settingsDiff).length > 0;

  const updateDraft = (partial: Partial<SettingsDraft>) => {
    setDraft((current) => ({ ...current, ...partial }));
  };

  useEffect(() => {
    const controller = new AbortController();
    fetchJson<SettingsPayload>(`${API_BASE}/api/settings/current`, controller.signal)
      .then((payload) => {
        const loaded = payloadToSettings(payload);
        settings.setSettings(loaded);
        setDraft(loaded);
      })
      .catch(() => {
        showToast("读取全局设置失败，已使用浏览器本地设置", "error");
      })
      .finally(() => setLoadingSettings(false));
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const addSensitiveWord = (rawValue: string) => {
    const value = rawValue.trim();
    if (!value || draft.sensitiveWords.includes(value)) return;
    updateDraft({ sensitiveWords: [...draft.sensitiveWords, value] });
    setSensitiveWordInput("");
  };

  const removeSensitiveWord = (word: string) => {
    updateDraft({ sensitiveWords: draft.sensitiveWords.filter((item) => item !== word) });
  };

  const setSubtitlePreset = (subtitlePosition: SubtitlePosition) => {
    updateDraft({
      subtitlePosition,
      customPositionY: subtitlePosition === "custom" ? draft.customPositionY ?? 72 : draft.customPositionY,
    });
  };

  const updateSubtitleYFromPointer = (event: PointerEvent<HTMLDivElement>) => {
    if (draft.subtitleMode === "off") return;
    const rect = event.currentTarget.getBoundingClientRect();
    const y = Math.round(((event.clientY - rect.top) / rect.height) * 100);
    updateDraft({
      subtitlePosition: "custom",
      customPositionY: Math.min(92, Math.max(8, y)),
    });
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

  const saveSettings = async () => {
    setSavingSettings(true);
    try {
      const saved = await sendJson<SettingsPayload>(
        `${API_BASE}/api/settings/current`,
        settingsDiff,
        "PUT",
      );
      const next = payloadToSettings(saved);
      settings.setSettings(next);
      setDraft(next);
      showToast("设置已保存", "success");
    } catch {
      showToast("保存设置失败", "error");
    } finally {
      setSavingSettings(false);
    }
  };

  const resetSettings = async () => {
    setSavingSettings(true);
    try {
      const saved = await sendJson<SettingsPayload>(`${API_BASE}/api/settings/reset`, {}, "POST");
      const next = payloadToSettings(saved);
      settings.setSettings(next);
      setDraft(next);
      showToast("设置已恢复默认", "success");
    } catch {
      settings.reset();
      setDraft(initialDraft(useSettingsStore.getState()));
      showToast("后端恢复失败，已恢复浏览器本地默认", "error");
    } finally {
      setSavingSettings(false);
    }
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
              disabled={savingSettings || !hasUnsavedChanges}
              className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-300"
            >
              <Save size={16} />
              {savingSettings ? "保存中" : "保存设置"}
            </button>
          </>
        }
      />

      <main className="grid gap-5 p-6 xl:grid-cols-[minmax(0,1fr)_340px]">
        {loadingSettings && (
          <div className="xl:col-span-2 rounded-lg border border-blue-100 bg-blue-50 px-4 py-3 text-sm text-blue-700">
            正在读取后端全局设置
          </div>
        )}
        <section className="min-w-0 space-y-5">
          <div className="flex flex-wrap gap-2 rounded-lg border border-slate-200 bg-white p-2">
            {sectionTabs.map((tab, index) => (
              <button
                key={tab}
                onClick={() => setActiveSection(index)}
                className={cn(
                  "rounded-md px-3 py-2 text-sm font-medium hover:bg-slate-50",
                  activeSection === index ? "bg-blue-50 text-blue-700" : "text-slate-600 hover:text-slate-950",
                )}
              >
                {tab}
              </button>
            ))}
          </div>

          {activeSection === 0 && <PresetSection draft={draft} onApplyPreset={applyPreset} />}

          {activeSection === 1 && <AiServicesSection draft={draft} needsVlmKey={needsVlmKey} updateDraft={updateDraft} />}

          {activeSection === 2 && <TranscriptionSection draft={draft} needsTos={needsTos} updateDraft={updateDraft} />}

          {activeSection === 3 && (
          <SettingsCard
            id="settings-section-2-subtitle"
            title="字幕样式与位置"
            desc="控制字幕模式、样式模板、语气词处理和画面中的字幕坐标。"
          >
            <div className="grid gap-4 md:grid-cols-3">
              <Field label="字幕模式">
                <select
                  value={draft.subtitleMode}
                  onChange={(event) => updateDraft({ subtitleMode: event.target.value as SubtitleMode })}
                  className={fieldClassName}
                >
                  <option value="off">关闭</option>
                  <option value="basic">基础字幕</option>
                  <option value="styled">样式字幕</option>
                  <option value="karaoke">{subtitleLabels.karaoke}</option>
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
              <Field label="字幕模板">
                <select
                  value={draft.subtitleTemplate}
                  onChange={(event) => updateDraft({ subtitleTemplate: event.target.value as SubtitleTemplate })}
                  className={fieldClassName}
                  disabled={draft.subtitleMode === "off"}
                >
                  <option value="clean">{subtitleTemplateLabels.clean}</option>
                  <option value="ecommerce">{subtitleTemplateLabels.ecommerce}</option>
                  <option value="bold">{subtitleTemplateLabels.bold}</option>
                  <option value="karaoke">{subtitleTemplateLabels.karaoke}</option>
                </select>
              </Field>
            </div>
            <div className="mt-4 grid gap-4 md:grid-cols-2">
              <NumberField
                label="普通字幕字号"
                value={draft.subtitleFontSize}
                min={24}
                max={120}
                tooltip="用于基础字幕、样式字幕，以及卡拉 OK 字幕的普通白字层。只影响新上传任务。"
                onChange={(subtitleFontSize) => updateDraft({ subtitleFontSize: Math.round(subtitleFontSize) })}
              />
              <NumberField
                label="高亮字幕字号"
                value={draft.subtitleHighlightFontSize}
                min={24}
                max={144}
                tooltip="用于卡拉 OK 逐字高亮和弹跳层。通常比普通字号略大；非卡拉 OK 模式不会使用。"
                onChange={(subtitleHighlightFontSize) => updateDraft({ subtitleHighlightFontSize: Math.round(subtitleHighlightFontSize) })}
              />
            </div>
            <div className="mt-4">
              <SubtitlePositionEditor
                disabled={draft.subtitleMode === "off"}
                position={draft.subtitlePosition}
                customY={draft.customPositionY ?? 72}
                fontSize={draft.subtitleFontSize}
                hoveredPreset={hoveredSubtitlePreset}
                onHoverPreset={setHoveredSubtitlePreset}
                onPresetChange={setSubtitlePreset}
                onCustomYChange={(customPositionY) => updateDraft({ subtitlePosition: "custom", customPositionY })}
                onPreviewPointer={updateSubtitleYFromPointer}
              />
            </div>
          </SettingsCard>
          )}

          {activeSection === 4 && (
          <SettingsCard
            id="settings-section-2-sensitive"
            title="敏感词过滤"
            desc="维护违规词库，命中后按字幕句段裁剪视频，或直接跳过整条片段。"
            badge={draft.sensitiveFilterEnabled ? "已启用" : "未启用"}
          >
            <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
              <div>
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h3 className="text-sm font-semibold text-slate-950">启用状态</h3>
                    <p className="mt-1 text-xs leading-5 text-slate-500">关闭时保留词库，但新任务不会应用过滤。</p>
                  </div>
                  <button
                    onClick={() => updateDraft({ sensitiveFilterEnabled: !draft.sensitiveFilterEnabled })}
                    className={cn("h-6 w-11 shrink-0 rounded-full p-0.5 transition-colors", draft.sensitiveFilterEnabled ? "bg-blue-600" : "bg-slate-300")}
                    aria-label="启用敏感词过滤"
                  >
                    <span className={cn("block h-5 w-5 rounded-full bg-white transition-transform", draft.sensitiveFilterEnabled && "translate-x-5")} />
                  </button>
                </div>

                <div className="mt-4 grid gap-4 md:grid-cols-2">
                  <Field label="处理方式" tooltip="裁掉命中句段会保留 clip 其余内容；整条片段不导出适合更严格的合规策略。">
                    <SegmentedControl
                      value={draft.sensitiveFilterMode}
                      onChange={(sensitiveFilterMode) => updateDraft({ sensitiveFilterMode: sensitiveFilterMode as SensitiveFilterMode })}
                      options={[
                        ["video_segment", "裁掉命中句段"],
                        ["drop_clip", "整条不导出"],
                      ]}
                    />
                  </Field>
                  <Field label="匹配方式" tooltip="包含匹配适合中文敏感词；精确匹配只在整句字幕完全等于词条时命中。">
                    <SegmentedControl
                      value={draft.sensitiveMatchMode}
                      onChange={(sensitiveMatchMode) => updateDraft({ sensitiveMatchMode: sensitiveMatchMode as SensitiveMatchMode })}
                      options={[
                        ["contains", "包含匹配"],
                        ["exact", "精确匹配"],
                      ]}
                    />
                  </Field>
                </div>

                <Field label="敏感词库" hint={`${draft.sensitiveWords.length} 个词`} className="mt-4">
                  <div className="min-h-24 rounded-lg border border-slate-200 bg-slate-50 p-3">
                    <div className="flex flex-wrap gap-2">
                      {draft.sensitiveWords.map((word) => (
                        <span key={word} className="inline-flex items-center gap-1 rounded-full bg-white px-2.5 py-1 text-xs font-medium text-slate-700 ring-1 ring-slate-200">
                          {word}
                          <button onClick={() => removeSensitiveWord(word)} className="text-slate-400 hover:text-red-500" aria-label={`删除 ${word}`}>
                            <X size={12} />
                          </button>
                        </span>
                      ))}
                      <input
                        value={sensitiveWordInput}
                        onChange={(event) => setSensitiveWordInput(event.target.value)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter" || event.key === ",") {
                            event.preventDefault();
                            addSensitiveWord(sensitiveWordInput);
                          }
                        }}
                        onBlur={() => addSensitiveWord(sensitiveWordInput)}
                        placeholder="输入词后回车添加"
                        className="min-w-40 flex-1 bg-transparent px-1 py-1 text-sm text-slate-700 outline-none placeholder:text-slate-400"
                      />
                    </div>
                  </div>
                </Field>
                <div className="mt-3 flex flex-wrap gap-2 text-xs">
                  <span className="rounded-full bg-blue-50 px-2 py-1 font-medium text-blue-700">随任务保存</span>
                  <span className="rounded-full bg-amber-50 px-2 py-1 font-medium text-amber-700">需要 ASR</span>
                  <span className="rounded-full bg-slate-100 px-2 py-1 font-medium text-slate-600">只影响新任务</span>
                </div>
              </div>

              <div className="rounded-lg bg-slate-50 p-4 text-xs leading-5 text-slate-500">
                <div className="font-semibold text-slate-700">处理说明</div>
                <p className="mt-2">
                  裁掉命中句段会保留 clip 其它内容；整条不导出适合更严格的合规策略。敏感词依赖 transcript，所以开启后即使字幕关闭也会触发 ASR。
                </p>
              </div>
            </div>
          </SettingsCard>
          )}

          {activeSection === 5 && (
          <>
          <SettingsCard
            id="settings-section-3-granularity"
            title="切分粒度"
            desc="控制商品讨论段最终按单品还是整套穿搭导出。"
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
          </SettingsCard>

          <SettingsCard
            id="settings-section-3-visual"
            title="视觉换衣检测"
            desc="控制视觉信号如何判定换衣节点。默认沿用旧逻辑，加权投票更适合减少光照和抖动误切。"
          >
            <div className="grid gap-4 md:grid-cols-2">
              <Field
                label="换衣信号融合"
                tooltip="默认沿用旧逻辑：任一视觉信号触发就进入换衣检测。加权投票会综合品类、上身 HSV、下身 HSV、纹理和全局 HSV，通常更抗光照变化和摄像头抖动。"
              >
                <SegmentedControl
                  value={draft.changeDetectionFusionMode}
                  onChange={(changeDetectionFusionMode) =>
                    updateDraft({ changeDetectionFusionMode: changeDetectionFusionMode as ChangeDetectionFusionMode })
                  }
                  options={[
                    ["any_signal", "任一信号"],
                    ["weighted_vote", "加权投票"],
                  ]}
                />
              </Field>
              <Field
                label="换衣检测敏感度"
                tooltip="只影响加权投票模式。保守会减少误切但可能漏掉弱变化；灵敏会提高召回但更容易把光照或遮挡变化切出来。"
              >
                <SegmentedControl
                  value={draft.changeDetectionSensitivity}
                  onChange={(changeDetectionSensitivity) =>
                    updateDraft({ changeDetectionSensitivity: changeDetectionSensitivity as ChangeDetectionSensitivity })
                  }
                  options={[
                    ["conservative", "保守"],
                    ["balanced", "均衡"],
                    ["sensitive", "灵敏"],
                  ]}
                />
              </Field>
            </div>
          </SettingsCard>

          <SettingsCard
            id="settings-section-3-text"
            title="文本边界与精修"
            desc="用 ASR 句子和 LLM 文本分析校正片段边界，减少半句话和商品边界错位。"
          >
            <div className="space-y-3">
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
                    <SecretInput value={draft.llmApiKey} onChange={(llmApiKey) => updateDraft({ llmApiKey })} />
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
          </>
          )}

          {activeSection === 6 && (
          <>
          <SettingsCard
            id="settings-section-4-video"
            title="视频导出"
            desc="控制分辨率、封面策略、编码速度和视频倍速。"
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
              <Field
                label="FFmpeg 编码速度"
                tooltip="veryfast 导出更快、文件可能略大；fast 是当前默认；medium 更慢，通常只在特别追求压缩率时使用。"
              >
                <SegmentedControl
                  value={draft.ffmpegPreset}
                  onChange={(ffmpegPreset) => updateDraft({ ffmpegPreset: ffmpegPreset as FFmpegPreset })}
                  options={[
                    ["veryfast", "很快"],
                    ["fast", "默认"],
                    ["medium", "压缩优先"],
                  ]}
                />
              </Field>
              <NumberField
                label="FFmpeg CRF"
                value={draft.ffmpegCrf}
                min={18}
                max={32}
                tooltip="画质/体积参数，数值越低画质越高、文件越大。23 是当前默认，建议保持 20-26。"
                onChange={(ffmpegCrf) => updateDraft({ ffmpegCrf })}
              />
              <Field label="视频倍速" hint="先烧字幕再变速" className="md:col-span-2">
                <SegmentedControl
                  value={String(draft.videoSpeed)}
                  onChange={(videoSpeed) => updateDraft({ videoSpeed: Number(videoSpeed) as SettingsDraft["videoSpeed"] })}
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
              </Field>
            </div>
          </SettingsCard>

          <SettingsCard
            id="settings-section-4-audio"
            title="音频与 BGM"
            desc="控制是否自动选曲，以及 BGM 与原声的混音比例。"
            badge={draft.bgmEnabled ? "BGM 已启用" : "BGM 关闭"}
          >
            <div className="space-y-3">
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
          </>
          )}

          {activeSection === 7 && (
          <>
          <SettingsCard
            id="settings-section-5-overview"
            title="高级参数概览"
            desc="默认展示关键数值。需要排查召回、误切或性能问题时再展开分组表单。"
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
          </SettingsCard>

          {expandedAdvanced && (
            <>
              <SettingsCard
                id="settings-section-5-core"
                title="检测基础阈值"
                desc="影响候选召回的基础检测参数。调低通常更敏感，调高通常更保守。"
              >
                <div className="grid gap-4 md:grid-cols-2">
                <NumberField label="场景检测阈值" value={draft.sceneThreshold} onChange={(sceneThreshold) => updateDraft({ sceneThreshold })} />
                <NumberField label="抽帧帧率 (fps)" value={draft.frameSampleFps} onChange={(frameSampleFps) => updateDraft({ frameSampleFps })} />
                <NumberField
                  label="最小片段时长 (秒)"
                  value={draft.minSegmentDurationSeconds}
                  onChange={(minSegmentDurationSeconds) => updateDraft({ minSegmentDurationSeconds })}
                />
                <NumberField label="去重窗口 (秒)" value={draft.dedupeWindowSeconds} onChange={(dedupeWindowSeconds) => updateDraft({ dedupeWindowSeconds })} />
                </div>
              </SettingsCard>

              <SettingsCard
                id="settings-section-5-recall"
                title="召回与候选合并"
                desc="限制候选数量、回讲召回和相邻片段合并，主要影响导出数量。"
              >
                <div className="grid gap-4 md:grid-cols-2">
                <NumberField label="最大候选数" value={draft.maxCandidateCount} onChange={(maxCandidateCount) => updateDraft({ maxCandidateCount })} />
                <NumberField
                  label="召回冷却时间 (秒)"
                  value={draft.recallCooldownSeconds}
                  onChange={(recallCooldownSeconds) => updateDraft({ recallCooldownSeconds })}
                />
                <NumberField label="合并数量" value={draft.mergeCount} onChange={(mergeCount) => updateDraft({ mergeCount })} />
                <ToggleCard
                  title="允许回讲商品"
                  desc="同一商品被主播回讲时允许再次生成候选。"
                  checked={draft.allowReturnedProduct}
                  onChange={(allowReturnedProduct) => updateDraft({ allowReturnedProduct })}
                />
                </div>
              </SettingsCard>

              <SettingsCard
                id="settings-section-5-yolo"
                title="服装检测门限"
                desc="控制服装检测框进入后续 HSV/纹理分析的最低置信度。"
              >
                <div className="grid gap-4 md:grid-cols-2">
                <NumberField
                  label="服装 YOLO 置信度"
                  value={draft.clothingYoloConfidence}
                  min={0.05}
                  max={0.8}
                  tooltip="服装检测框的最低置信度。提高到 0.35-0.4 可减少杂乱画面中的低质量框，但可能降低小件服装召回。"
                  onChange={(clothingYoloConfidence) => updateDraft({ clothingYoloConfidence })}
                />
                </div>
              </SettingsCard>
            </>
          )}
          </>
          )}
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
              <DependencyRow label="商品素材 Gemini" ok={Boolean(draft.commerceGeminiApiKey.trim())} />
              <DependencyRow label="商品素材生图" ok={Boolean(draft.commerceImageApiKey.trim())} />
            </div>
            <div className="mt-5 rounded-lg bg-slate-50 p-3 text-xs leading-5 text-slate-500">
              设置优先保存在后端 SQLite，全局配置读取顺序为 SQLite、环境变量、代码默认值。上传时会固化到任务 settings.json 和 secrets.json。
            </div>
          </div>
        </aside>
      </main>
    </>
  );
}
