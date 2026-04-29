import { useMemo, useState, type PointerEvent } from "react";
import { Check, Info, Move, Save, SlidersHorizontal, X } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  DEFAULT_API_BASES,
  DEFAULT_MODELS,
  useSettingsStore,
  type AsrProvider,
  type ChangeDetectionFusionMode,
  type ChangeDetectionSensitivity,
  type CommerceImageQuality,
  type CommerceImageSize,
  type CoverStrategy,
  type ExportMode,
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
  type VlmProvider,
} from "@/stores/settingsStore";
import { Chip, Header } from "../shared";

type SettingsDraft = Settings;

const sectionTabs = ["处理预设", "AI 服务", "转写服务", "字幕设置", "敏感词过滤", "切分策略", "导出与音频", "高级参数"];

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
  karaoke: "卡拉 OK 字幕",
};

const subtitlePositionLabels: Record<SubtitlePosition, string> = {
  top: "顶部",
  middle: "中部",
  bottom: "底部",
  custom: "自定义",
};

const subtitleTemplateLabels: Record<SubtitleTemplate, string> = {
  clean: "简洁",
  ecommerce: "电商",
  bold: "加粗",
  karaoke: "卡拉 OK",
};

const initialDraft = (state: ReturnType<typeof useSettingsStore.getState>): SettingsDraft => {
  const settings: Partial<ReturnType<typeof useSettingsStore.getState>> = { ...state };
  delete settings.setSettings;
  delete settings.reset;
  return settings as Settings;
};

const isVolcengineAsr = (provider: AsrProvider) => provider === "volcengine" || provider === "volcengine_vc";

export function AdminSettingsPage() {
  const settings = useSettingsStore();
  const [draft, setDraft] = useState<SettingsDraft>(() => initialDraft(useSettingsStore.getState()));
  const [expandedAdvanced, setExpandedAdvanced] = useState(true);
  const [activeSection, setActiveSection] = useState(0);
  const [sensitiveWordInput, setSensitiveWordInput] = useState("");
  const [hoveredSubtitlePreset, setHoveredSubtitlePreset] = useState<SubtitlePosition | null>(null);

  const savedSnapshot = useMemo(() => JSON.stringify(initialDraft(settings)), [settings]);
  const draftSnapshot = useMemo(() => JSON.stringify(draft), [draft]);
  const hasUnsavedChanges = savedSnapshot !== draftSnapshot;

  const updateDraft = (partial: Partial<SettingsDraft>) => {
    setDraft((current) => ({ ...current, ...partial }));
  };

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

          {activeSection === 0 && (
          <SettingsCard
            id="settings-section-0"
            title="处理预设"
            desc="先选择本次剪辑目标，再微调下方参数。预设只更新草稿，保存后才会生效。"
            badge="推荐先选"
          >
            <div className="grid gap-3 md:grid-cols-2">
              <PresetCard
                title="高质量字幕版"
                desc="火山 VC + 卡拉 OK 字幕 + BGM，适合正式交付和公开视频。"
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
          )}

          {activeSection === 1 && (
          <>
          <SettingsCard
            id="settings-section-1"
            title="剪辑 VLM 服务"
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
            id="settings-section-1-commerce"
            title="AI 商品素材"
            desc="独立用于片段封面识图、抖音/淘宝文案和 gpt-image-2 商品图生成，不影响剪辑流水线。"
            badge="独立配置"
          >
              <div className="space-y-4">
                <div className="rounded-lg border border-slate-200 bg-white p-4">
                  <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <h3 className="text-sm font-semibold text-slate-950">Gemini 商品识图</h3>
                      <p className="mt-1 text-xs leading-5 text-slate-500">读取片段封面，识别商品品类、颜色、版型、可见卖点和不确定字段。</p>
                    </div>
                    <span className="rounded-full bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-700">识图 / 文案前置</span>
                  </div>
                  <div className="grid gap-4 md:grid-cols-2">
                    <Field label="Gemini API Base" hint="建议只填域名，不带 /v1 路径">
                      <input
                        value={draft.commerceGeminiApiBase}
                        onChange={(event) => updateDraft({ commerceGeminiApiBase: event.target.value })}
                        className={fieldClassName}
                        placeholder="https://generativelanguage.googleapis.com"
                      />
                    </Field>
                    <Field label="Gemini 识图模型">
                      <input
                        value={draft.commerceGeminiModel}
                        onChange={(event) => updateDraft({ commerceGeminiModel: event.target.value })}
                        className={fieldClassName}
                        placeholder="gemini-3-flash-preview"
                      />
                    </Field>
                    <Field label="Gemini API Key" hint="用于封面识图和商品结构化分析" className="md:col-span-2">
                      <input
                        type="password"
                        value={draft.commerceGeminiApiKey}
                        onChange={(event) => updateDraft({ commerceGeminiApiKey: event.target.value })}
                        className={fieldClassName}
                      />
                    </Field>
                    <NumberField
                      label="Gemini 超时 (秒)"
                      value={draft.commerceGeminiTimeoutSeconds}
                      min={30}
                      max={600}
                      onChange={(commerceGeminiTimeoutSeconds) => updateDraft({ commerceGeminiTimeoutSeconds })}
                    />
                  </div>
                </div>

                <div className="rounded-lg border border-slate-200 bg-white p-4">
                  <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <h3 className="text-sm font-semibold text-slate-950">OpenAI Image 生图</h3>
                      <p className="mt-1 text-xs leading-5 text-slate-500">基于商品识别结果和片段封面，生成 AI 模特图与淘宝详情页示例图。</p>
                    </div>
                    <span className="rounded-full bg-blue-50 px-2 py-1 text-xs font-medium text-blue-700">gpt-image-2</span>
                  </div>
                  <div className="grid gap-4 md:grid-cols-2">
                    <Field label="OpenAI Image API Base">
                      <input
                        value={draft.commerceImageApiBase}
                        onChange={(event) => updateDraft({ commerceImageApiBase: event.target.value })}
                        className={fieldClassName}
                        placeholder="https://api.openai.com/v1"
                      />
                    </Field>
                    <Field label="图片模型">
                      <input
                        value={draft.commerceImageModel}
                        onChange={(event) => updateDraft({ commerceImageModel: event.target.value })}
                        className={fieldClassName}
                        placeholder="gpt-image-2"
                      />
                    </Field>
                    <Field label="OpenAI Image API Key" hint="用于 AI 模特图和详情页示例图" className="md:col-span-2">
                      <input
                        type="password"
                        value={draft.commerceImageApiKey}
                        onChange={(event) => updateDraft({ commerceImageApiKey: event.target.value })}
                        className={fieldClassName}
                      />
                    </Field>
                    <Field label="默认图片尺寸">
                      <select
                        value={draft.commerceImageSize}
                        onChange={(event) => updateDraft({ commerceImageSize: event.target.value as CommerceImageSize })}
                        className={fieldClassName}
                      >
                        <option value="2K">2K 高清图（默认）</option>
                        <option value="1024x1024">1024x1024 方图</option>
                        <option value="1024x1536">1024x1536 模特竖图</option>
                        <option value="1536x1024">1536x1024 横图</option>
                        <option value="2048x2048">2048x2048 高清方图</option>
                        <option value="2160x3840">2160x3840 详情长图</option>
                      </select>
                    </Field>
                    <Field label="默认生成质量" hint="gpt-image-2 默认使用自动质量">
                      <select
                        value={draft.commerceImageQuality}
                        onChange={(event) => updateDraft({ commerceImageQuality: event.target.value as CommerceImageQuality })}
                        className={fieldClassName}
                      >
                        <option value="auto">自动</option>
                        <option value="low">低</option>
                        <option value="medium">中</option>
                        <option value="high">高</option>
                      </select>
                    </Field>
                    <NumberField
                      label="图片生成超时 (秒)"
                      value={draft.commerceImageTimeoutSeconds}
                      min={60}
                      max={1200}
                      onChange={(commerceImageTimeoutSeconds) => updateDraft({ commerceImageTimeoutSeconds })}
                    />
                  </div>
                </div>
              </div>
          </SettingsCard>
          </>
          )}

          {activeSection === 2 && (
          <>
          <SettingsCard
            id="settings-section-2-asr"
            title="ASR 转写服务"
            desc="选择语音转写引擎和凭证。ASR 决定字幕时间轴质量，卡拉 OK 字幕推荐火山 VC。"
            badge={draft.asrProvider === "volcengine_vc" ? "火山 VC 推荐" : undefined}
          >
            <div className="grid gap-3 md:grid-cols-3">
              <OptionCard
                title="火山 VC 字幕"
                desc="剪映引擎分句，真实节奏时间戳，适合卡拉 OK 字幕。"
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
                desc="成本较低，基础字幕可用，不推荐卡拉 OK 跳字。"
                selected={draft.asrProvider === "dashscope"}
                onClick={() => updateDraft({ asrProvider: "dashscope" })}
              />
            </div>
            <div className="mt-4 grid gap-4 md:grid-cols-2">
              <Field label="ASR API Key" className="md:col-span-2">
                <input
                  type="password"
                  value={draft.asrApiKey}
                  onChange={(event) => updateDraft({ asrApiKey: event.target.value })}
                  className={fieldClassName}
                />
              </Field>
            </div>
          </SettingsCard>

            {needsTos && (
              <SettingsCard
                id="settings-section-2-tos"
                title="火山存储配置"
                desc="火山标准版和 VC 字幕需要 TOS 上传音频。敏感字段上传时会写入 secrets.json。"
                badge="TOS"
              >
                <div className="grid gap-4 md:grid-cols-2">
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
              </SettingsCard>
            )}
          </>
          )}

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

const subtitlePresetMeta: Record<SubtitlePosition, { label: string; y: number; desc: string }> = {
  top: { label: "顶部", y: 12, desc: "适合商品画面在下方" },
  middle: { label: "中部", y: 50, desc: "适合画面上下都较干净" },
  bottom: { label: "底部", y: 88, desc: "默认位置，适合口播画面" },
  custom: { label: "自定义", y: 72, desc: "拖动预览字幕记录坐标" },
};

function SubtitlePositionEditor({
  disabled,
  position,
  customY,
  fontSize,
  hoveredPreset,
  onHoverPreset,
  onPresetChange,
  onCustomYChange,
  onPreviewPointer,
}: {
  disabled: boolean;
  position: SubtitlePosition;
  customY: number;
  fontSize: number;
  hoveredPreset: SubtitlePosition | null;
  onHoverPreset: (position: SubtitlePosition | null) => void;
  onPresetChange: (position: SubtitlePosition) => void;
  onCustomYChange: (value: number) => void;
  onPreviewPointer: (event: PointerEvent<HTMLDivElement>) => void;
}) {
  const effectiveY = position === "custom" ? customY : subtitlePresetMeta[position].y;
  const previewPosition = hoveredPreset ?? position;
  const previewY = previewPosition === "custom" ? effectiveY : subtitlePresetMeta[previewPosition].y;

  return (
    <div className={cn("rounded-lg border border-slate-200 bg-slate-50 p-4", disabled && "opacity-60")}>
      <div className="grid gap-5 lg:grid-cols-[280px_minmax(0,1fr)]">
        <div className="min-w-0">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h3 className="text-sm font-semibold text-slate-950">字幕位置调整</h3>
              <p className="mt-1 text-xs leading-5 text-slate-500">左侧设置位置，右侧拖动视频预览中的字幕条。</p>
            </div>
            <span className="shrink-0 rounded-full bg-blue-50 px-2 py-1 text-xs font-medium text-blue-700">Y {effectiveY}%</span>
          </div>

          <div className="relative mt-4">
            <div className="grid grid-cols-2 gap-1 rounded-lg bg-slate-100 p-1">
              {(Object.keys(subtitlePresetMeta) as SubtitlePosition[]).map((item) => (
                <button
                  key={item}
                  disabled={disabled}
                  onMouseEnter={() => onHoverPreset(item)}
                  onMouseLeave={() => onHoverPreset(null)}
                  onClick={() => onPresetChange(item)}
                  className={cn(
                    "rounded-md px-2 py-2 text-xs font-medium transition",
                    position === item ? "bg-white text-blue-700 shadow-sm" : "text-slate-500 hover:text-slate-800",
                    disabled && "cursor-not-allowed",
                  )}
                >
                  {subtitlePresetMeta[item].label}
                </button>
              ))}
            </div>
            {hoveredPreset && (
              <div className="absolute left-0 top-24 z-20 w-36 rounded-lg border border-slate-200 bg-white p-2 shadow-lg">
                <MiniSubtitlePreview y={subtitlePresetMeta[hoveredPreset].y} />
                <div className="mt-1 text-center text-[11px] font-medium text-slate-600">{subtitlePresetMeta[hoveredPreset].desc}</div>
              </div>
            )}
          </div>

          <div className="mt-4">
            <RangeField label="垂直位置" value={effectiveY / 100} max={1} onChange={(value) => onCustomYChange(Math.round(value * 100))} />
          </div>
          <div className="mt-3 grid gap-2 text-xs">
            <div className="rounded-lg bg-white p-2 ring-1 ring-slate-200">
              <div className="text-slate-400">字幕位置</div>
              <div className="mt-1 font-medium text-slate-800">{subtitlePositionLabels[position]}</div>
            </div>
            <div className="rounded-lg bg-white p-2 ring-1 ring-slate-200">
              <div className="text-slate-400">自定义纵向坐标</div>
              <div className="mt-1 font-medium text-slate-800">{position === "custom" ? `${effectiveY}%` : "未启用"}</div>
            </div>
          </div>
        </div>

        <div className="min-w-0">
          <div
            className={cn("relative mx-auto aspect-[9/16] max-h-[430px] overflow-hidden rounded-lg border border-slate-200 bg-slate-900", !disabled && "cursor-grab active:cursor-grabbing")}
            onPointerDown={(event) => {
              if (disabled) return;
              event.currentTarget.setPointerCapture(event.pointerId);
              onPreviewPointer(event);
            }}
            onPointerMove={(event) => {
              if (disabled || !event.currentTarget.hasPointerCapture(event.pointerId)) return;
              onPreviewPointer(event);
            }}
            onPointerUp={(event) => {
              if (event.currentTarget.hasPointerCapture(event.pointerId)) {
                event.currentTarget.releasePointerCapture(event.pointerId);
              }
            }}
          >
            <img
              src="/images/subtitle-preview-live-demo.png"
              alt=""
              className="absolute inset-0 h-full w-full object-cover"
              draggable={false}
            />
            <div className="absolute inset-x-0 bottom-0 h-1/3 bg-gradient-to-t from-black/35 to-transparent" />
            {[12, 50, 88].map((line) => (
              <div key={line} className="absolute left-0 right-0 border-t border-white/15" style={{ top: `${line}%` }} />
            ))}
            <div
              className="absolute left-1/2 inline-flex -translate-x-1/2 -translate-y-1/2 items-center gap-2 rounded-lg border border-blue-300 bg-black/55 px-3 py-1.5 text-center text-sm font-semibold text-white shadow-lg"
              style={{
                top: `${previewY}%`,
                fontSize: `${Math.min(Math.max(fontSize, 24), 120) / 4}px`,
              }}
            >
              <Move size={14} />
              这款连衣裙显瘦又好搭
            </div>
            <div className="absolute left-1/2 rounded-full bg-blue-600 px-2 py-0.5 text-[11px] font-medium text-white" style={{ top: `calc(${previewY}% + 22px)`, transform: "translateX(-50%)" }}>
              X 50%, Y {previewY}%
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function MiniSubtitlePreview({ y }: { y: number }) {
  return (
    <div className="relative mx-auto aspect-[9/16] h-24 overflow-hidden rounded-md bg-slate-900">
      <div className="absolute inset-0 bg-gradient-to-b from-slate-600 to-slate-900" />
      <div className="absolute left-1/2 h-1.5 w-16 -translate-x-1/2 rounded-full bg-white" style={{ top: `${y}%` }} />
    </div>
  );
}

function Field({
  label,
  hint,
  tooltip,
  className,
  children,
}: {
  label: string;
  hint?: string;
  tooltip?: string;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <label className={cn("block", className)}>
      <span className="mb-1.5 flex items-center justify-between gap-3 text-xs">
        <span className="flex items-center gap-1.5 font-medium text-slate-600">
          {label}
          {tooltip && <Tooltip text={tooltip} />}
        </span>
        {hint && <span className="text-slate-400">{hint}</span>}
      </span>
      {children}
    </label>
  );
}

function Tooltip({ text }: { text: string }) {
  return (
    <span className="group relative inline-flex">
      <Info size={13} className="cursor-help text-slate-400" aria-hidden="true" />
      <span
        role="tooltip"
        className="pointer-events-none absolute left-1/2 top-5 z-20 hidden w-64 -translate-x-1/2 rounded-lg border border-slate-200 bg-white p-3 text-xs font-normal leading-5 text-slate-600 shadow-lg group-hover:block group-focus-within:block"
      >
        {text}
      </span>
    </span>
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
  min,
  max,
  tooltip,
  onChange,
}: {
  label: string;
  value: number;
  min?: number;
  max?: number;
  tooltip?: string;
  onChange: (value: number) => void;
}) {
  return (
    <Field label={label} tooltip={tooltip}>
      <input
        type="number"
        step="any"
        min={min}
        max={max}
        value={String(value)}
        onChange={(event) => {
          const nextValue = event.target.value;
          if (nextValue === "") return;
          const parsed = Number(nextValue);
          if (Number.isFinite(parsed)) onChange(parsed);
        }}
        className={fieldClassName}
      />
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
