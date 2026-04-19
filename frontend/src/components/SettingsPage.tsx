import { useState } from "react";
import { ArrowLeft } from "lucide-react";
import {
  DEFAULT_API_BASES,
  DEFAULT_MODELS,
  useSettingsStore,
  type Settings as SettingsValues,
  type ReviewMode,
  type ExportMode,
  type StrictnessMode,
  type SubtitleMode,
  type SubtitlePosition,
  type SubtitleTemplate,
  type VlmProvider,
  type AsrProvider,
  type FillerFilterMode,
  type CoverStrategy,
  type VideoSpeed,
  type LlmType,
  type ExportResolution,
} from "@/stores/settingsStore";
import { useToastStore } from "@/stores/toastStore";

const inputClassName =
  "w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none";

const sectionClassName = "space-y-4 rounded-lg border border-slate-200 bg-slate-50/60 p-4";

function Section({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <section className={sectionClassName}>
      <div>
        <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
        <p className="mt-1 text-xs text-slate-500">{description}</p>
      </div>
      {children}
    </section>
  );
}

function applyProviderDefaults(provider: VlmProvider, draft: SettingsValues): SettingsValues {
  return {
    ...draft,
    provider,
    apiBase: DEFAULT_API_BASES[provider],
    model: DEFAULT_MODELS[provider],
  };
}

interface SettingsPageProps {
  onBack: () => void;
}

export function SettingsPage({ onBack }: SettingsPageProps) {
  const [error, setError] = useState<string | null>(null);
  const {
    enableVlm,
    exportMode,
    provider,
    apiKey,
    apiBase,
    model,
    reviewStrictness,
    reviewMode,
    sceneThreshold,
    frameSampleFps,
    recallCooldownSeconds,
    candidateLooseness,
    minSegmentDurationSeconds,
    dedupeWindowSeconds,
    mergeCount,
    allowReturnedProduct,
    maxCandidateCount,
    subtitleMode,
    subtitlePosition,
    subtitleTemplate,
    funasrMode,
    asrProvider,
    fillerFilterMode,
    coverStrategy,
    videoSpeed,
    asrApiKey,
    tosAk,
    tosSk,
    tosBucket,
    tosRegion,
    tosEndpoint,
    enableLlmAnalysis,
    llmApiKey,
    llmApiBase,
    llmModel,
    llmType,
    exportResolution,
    setSettings,
  } = useSettingsStore();

  const [draft, setDraft] = useState({
    enableVlm,
    exportMode,
    provider,
    apiKey,
    apiBase,
    model,
    reviewStrictness,
    reviewMode,
    sceneThreshold,
    frameSampleFps,
    recallCooldownSeconds,
    candidateLooseness,
    minSegmentDurationSeconds,
    dedupeWindowSeconds,
    mergeCount,
    allowReturnedProduct,
    maxCandidateCount,
    subtitleMode,
    subtitlePosition,
    subtitleTemplate,
    funasrMode,
    asrProvider,
    fillerFilterMode,
    coverStrategy,
    videoSpeed,
    asrApiKey,
    tosAk,
    tosSk,
    tosBucket,
    tosRegion,
    tosEndpoint,
    enableLlmAnalysis,
    llmApiKey,
    llmApiBase,
    llmModel,
    llmType,
    exportResolution,
  });

  const showToast = useToastStore((state) => state.showToast);

  const updateNumber = (key: keyof typeof draft, value: string) => {
    const nextValue = Number(value);
    setDraft({
      ...draft,
      [key]: Number.isNaN(nextValue) ? 0 : nextValue,
    });
  };

  const handleSave = () => {
    if (draft.exportMode === "smart" && !draft.apiKey.trim()) {
      const message = "VLM 已启用，请先输入 API 密钥";
      setError(message);
      showToast(message, "error");
      return;
    }
    setSettings(draft);
    setError(null);
    showToast("设置已保存", "success");
    onBack();
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <nav className="sticky top-0 z-10 border-b border-slate-200 bg-white/80 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-2xl items-center gap-3 px-4 sm:px-6">
          <button
            className="flex items-center gap-1 rounded-md px-2 py-1 text-sm text-slate-600 hover:bg-slate-100 hover:text-slate-900"
            onClick={onBack}
          >
            <ArrowLeft size={16} />
            返回
          </button>
          <h1 className="text-sm font-semibold text-slate-900">流程设置</h1>
        </div>
      </nav>

      <div className="mx-auto max-w-2xl space-y-4 px-4 py-6 sm:px-6">
        <Section
          title="分段设置"
          description="调整候选片段在进入 VLM 复核前的召回与压缩方式。"
        >
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <label htmlFor="scene-threshold" className="mb-1 block text-sm font-medium text-slate-700">
                场景阈值
              </label>
              <input
                id="scene-threshold"
                type="number"
                min={10}
                max={60}
                step="0.5"
                className={inputClassName}
                value={draft.sceneThreshold}
                onChange={(e) => updateNumber("sceneThreshold", e.target.value)}
              />
            </div>

            <div>
              <label htmlFor="frame-sample-fps" className="mb-1 block text-sm font-medium text-slate-700">
                采样帧率 FPS
              </label>
              <input
                id="frame-sample-fps"
                type="number"
                min={0.25}
                max={5}
                step="0.25"
                className={inputClassName}
                value={draft.frameSampleFps}
                onChange={(e) => updateNumber("frameSampleFps", e.target.value)}
              />
            </div>

            <div>
              <label htmlFor="recall-cooldown" className="mb-1 block text-sm font-medium text-slate-700">
                召回冷却时间（秒）
              </label>
              <input
                id="recall-cooldown"
                type="number"
                min={0}
                max={60}
                step="1"
                className={inputClassName}
                value={draft.recallCooldownSeconds}
                onChange={(e) => updateNumber("recallCooldownSeconds", e.target.value)}
              />
            </div>

            <div>
              <label htmlFor="candidate-looseness" className="mb-1 block text-sm font-medium text-slate-700">
                候选宽松度
              </label>
              <select
                id="candidate-looseness"
                className={inputClassName}
                value={draft.candidateLooseness}
                onChange={(e) =>
                  setDraft({ ...draft, candidateLooseness: e.target.value as StrictnessMode })
                }
              >
                <option value="strict">严格</option>
                <option value="standard">标准</option>
                <option value="loose">宽松</option>
              </select>
            </div>

            <div>
              <label htmlFor="min-segment-duration" className="mb-1 block text-sm font-medium text-slate-700">
                最短片段时长（秒）
              </label>
              <input
                id="min-segment-duration"
                type="number"
                min={5}
                max={120}
                step="1"
                className={inputClassName}
                value={draft.minSegmentDurationSeconds}
                onChange={(e) => updateNumber("minSegmentDurationSeconds", e.target.value)}
              />
            </div>

            <div>
              <label htmlFor="dedupe-window" className="mb-1 block text-sm font-medium text-slate-700">
                去重窗口（秒）
              </label>
              <input
                id="dedupe-window"
                type="number"
                min={0}
                max={600}
                step="1"
                className={inputClassName}
                value={draft.dedupeWindowSeconds}
                onChange={(e) => updateNumber("dedupeWindowSeconds", e.target.value)}
              />
            </div>

            <div>
              <label htmlFor="merge-count" className="mb-1 block text-sm font-medium text-slate-700">
                片段合并数
              </label>
              <input
                id="merge-count"
                type="number"
                min={1}
                max={10}
                step="1"
                className={inputClassName}
                value={draft.mergeCount}
                onChange={(e) => updateNumber("mergeCount", e.target.value)}
              />
            </div>

            <div>
              <label htmlFor="filler-filter-mode" className="mb-1 block text-sm font-medium text-slate-700">
                语气词过滤
              </label>
              <select
                id="filler-filter-mode"
                className={inputClassName}
                value={draft.fillerFilterMode}
                onChange={(e) => setDraft({ ...draft, fillerFilterMode: e.target.value as FillerFilterMode })}
              >
                <option value="off">关闭</option>
                <option value="subtitle">过滤字幕（仅去除字幕中的语气词）</option>
                <option value="video">过滤视频片段（裁掉语气词对应的短视频段）</option>
              </select>
            </div>

            <div>
              <label htmlFor="cover-strategy" className="mb-1 block text-sm font-medium text-slate-700">
                封面策略
              </label>
              <select
                id="cover-strategy"
                className={inputClassName}
                value={draft.coverStrategy}
                onChange={(e) => setDraft({ ...draft, coverStrategy: e.target.value as CoverStrategy })}
              >
                <option value="content_first">内容优先（突出商品）</option>
                <option value="person_first">主播优先（突出主播）</option>
              </select>
            </div>

            <div>
              <label htmlFor="video-speed" className="mb-1 block text-sm font-medium text-slate-700">
                视频倍速
              </label>
              <select
                id="video-speed"
                className={inputClassName}
                value={draft.videoSpeed}
                onChange={(e) => setDraft({ ...draft, videoSpeed: parseFloat(e.target.value) as VideoSpeed })}
              >
                <option value="0.5">0.5x</option>
                <option value="0.75">0.75x</option>
                <option value="1">1x（原速）</option>
                <option value="1.25">1.25x</option>
                <option value="1.5">1.5x</option>
                <option value="1.75">1.75x</option>
                <option value="2">2x</option>
                <option value="3">3x</option>
              </select>
            </div>

            <div>
              <label htmlFor="export-resolution" className="mb-1 block text-sm font-medium text-slate-700">
                导出分辨率
              </label>
              <select
                id="export-resolution"
                className={inputClassName}
                value={draft.exportResolution}
                onChange={(e) => setDraft({ ...draft, exportResolution: e.target.value as ExportResolution })}
              >
                <option value="1080p">1080P（默认）</option>
                <option value="4k">4K</option>
                <option value="original">保持原始</option>
              </select>
            </div>
          </div>
        </Section>

        <Section
          title="VLM 设置"
          description="选择导出走哪条流程线，再决定是否需要 VLM 复核与相关参数。"
        >
          <div className="grid gap-4 md:grid-cols-2">
            <div className="md:col-span-2">
              <label htmlFor="export-mode" className="mb-1 block text-sm font-medium text-slate-700">
                导出模式
              </label>
              <select
                id="export-mode"
                className={inputClassName}
                value={draft.exportMode}
                onChange={(e) => {
                  const nextExportMode = e.target.value as ExportMode;
                  setDraft({
                    ...draft,
                    exportMode: nextExportMode,
                    enableVlm: nextExportMode === "smart",
                  });
                }}
              >
                <option value="smart">智能模式</option>
                <option value="no_vlm">跳过 VLM</option>
                <option value="all_candidates">候选全切</option>
                <option value="all_scenes">场景全切</option>
              </select>
            </div>

            <div>
              <label htmlFor="provider" className="mb-1 block text-sm font-medium text-slate-700">
                提供方
              </label>
              <select
                id="provider"
                className={inputClassName}
                value={draft.provider}
                onChange={(e) =>
                  setDraft(applyProviderDefaults(e.target.value as VlmProvider, draft))
                }
              >
                <option value="qwen">Qwen</option>
                <option value="glm">GLM</option>
              </select>
            </div>

            <div>
              <label htmlFor="review-strictness" className="mb-1 block text-sm font-medium text-slate-700">
                VLM 严格度
              </label>
              <select
                id="review-strictness"
                className={inputClassName}
                value={draft.reviewStrictness}
                onChange={(e) =>
                  setDraft({ ...draft, reviewStrictness: e.target.value as StrictnessMode })
                }
                disabled={draft.exportMode !== "smart"}
              >
                <option value="strict">严格</option>
                <option value="standard">标准</option>
                <option value="loose">宽松</option>
              </select>
            </div>

            <div className="md:col-span-2">
              <label htmlFor="api-key" className="mb-1 block text-sm font-medium text-slate-700">
                VLM API 密钥
              </label>
              <input
                id="api-key"
                type="password"
                className={inputClassName}
                value={draft.apiKey}
                onChange={(e) => setDraft({ ...draft, apiKey: e.target.value })}
                placeholder="sk-..."
                disabled={draft.exportMode !== "smart"}
              />
            </div>

            <div className="md:col-span-2">
              <label htmlFor="api-base" className="mb-1 block text-sm font-medium text-slate-700">
                API 基础地址
              </label>
              <input
                id="api-base"
                type="text"
                className={inputClassName}
                value={draft.apiBase}
                onChange={(e) => setDraft({ ...draft, apiBase: e.target.value })}
              />
            </div>

            <div>
              <label htmlFor="model" className="mb-1 block text-sm font-medium text-slate-700">
                模型
              </label>
              <input
                id="model"
                type="text"
                className={inputClassName}
                value={draft.model}
                onChange={(e) => setDraft({ ...draft, model: e.target.value })}
              />
            </div>

            <div>
              <label htmlFor="review-mode" className="mb-1 block text-sm font-medium text-slate-700">
                复核模式
              </label>
              <select
                id="review-mode"
                className={inputClassName}
                value={draft.reviewMode}
                onChange={(e) => setDraft({ ...draft, reviewMode: e.target.value as ReviewMode })}
              >
                <option value="adjacent_frames">相邻帧</option>
                <option value="segment_multiframe">片段多帧</option>
              </select>
            </div>

            <div>
              <label htmlFor="max-candidate-count" className="mb-1 block text-sm font-medium text-slate-700">
                最大候选数量
              </label>
              <input
                id="max-candidate-count"
                type="number"
                min={1}
                max={100}
                step="1"
                className={inputClassName}
                value={draft.maxCandidateCount}
                onChange={(e) => updateNumber("maxCandidateCount", e.target.value)}
              />
            </div>

            <div>
              <label htmlFor="funasr-mode" className="mb-1 block text-sm font-medium text-slate-700">
                FunASR 模式
              </label>
              <select
                id="funasr-mode"
                className={inputClassName}
                value={draft.funasrMode}
                onChange={(e) =>
                  setDraft({ ...draft, funasrMode: e.target.value as "local" | "remote" })
                }
              >
                <option value="local">本地 Docker</option>
                <option value="remote">远程 API</option>
              </select>
            </div>
          </div>
        </Section>

        <Section
          title="语音识别设置"
          description="选择语音转写（ASR）的服务提供方。"
        >
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <label htmlFor="asr-provider" className="mb-1 block text-sm font-medium text-slate-700">
                ASR 提供方
              </label>
              <select
                id="asr-provider"
                className={inputClassName}
                value={draft.asrProvider}
                onChange={(e) =>
                  setDraft({ ...draft, asrProvider: e.target.value as AsrProvider })
                }
              >
                <option value="volcengine_vc">火山 VC 字幕（推荐 · 剪映分句+逐字同步最佳）</option>
                <option value="volcengine">火山豆包大模型（真实时间戳，分句偏长）</option>
                <option value="dashscope">阿里云 DashScope（最便宜，逐字匀速不适合跳字）</option>
              </select>
            </div>

            {(draft.asrProvider === "volcengine" || draft.asrProvider === "volcengine_vc") && (
              <>
                <div className="md:col-span-2">
                  <label htmlFor="asr-api-key" className="mb-1 block text-sm font-medium text-slate-700">
                    火山引擎 API Key
                  </label>
                  <input
                    id="asr-api-key"
                    type="password"
                    className={inputClassName}
                    value={draft.asrApiKey}
                    onChange={(e) => setDraft({ ...draft, asrApiKey: e.target.value })}
                    placeholder="火山引擎控制台获取的 API Key"
                  />
                </div>
                <div className="md:col-span-2 mt-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2">
                  <p className="text-xs font-medium text-amber-800">TOS 对象存储配置（bigmodel / VC 字幕均需通过 TOS 传音频）</p>
                </div>
                <div className="md:col-span-2">
                  <label htmlFor="tos-ak" className="mb-1 block text-sm font-medium text-slate-700">
                    TOS Access Key
                  </label>
                  <input
                    id="tos-ak"
                    type="password"
                    className={inputClassName}
                    value={draft.tosAk}
                    onChange={(e) => setDraft({ ...draft, tosAk: e.target.value })}
                    placeholder="火山引擎 TOS 的 AK"
                  />
                </div>
                <div className="md:col-span-2">
                  <label htmlFor="tos-sk" className="mb-1 block text-sm font-medium text-slate-700">
                    TOS Secret Key
                  </label>
                  <input
                    id="tos-sk"
                    type="password"
                    className={inputClassName}
                    value={draft.tosSk}
                    onChange={(e) => setDraft({ ...draft, tosSk: e.target.value })}
                    placeholder="火山引擎 TOS 的 SK"
                  />
                </div>
                <div>
                  <label htmlFor="tos-bucket" className="mb-1 block text-sm font-medium text-slate-700">
                    TOS 桶名称
                  </label>
                  <input
                    id="tos-bucket"
                    type="text"
                    className={inputClassName}
                    value={draft.tosBucket}
                    onChange={(e) => setDraft({ ...draft, tosBucket: e.target.value })}
                    placeholder="mp3-srt"
                  />
                </div>
                <div>
                  <label htmlFor="tos-region" className="mb-1 block text-sm font-medium text-slate-700">
                    TOS 区域
                  </label>
                  <input
                    id="tos-region"
                    type="text"
                    className={inputClassName}
                    value={draft.tosRegion}
                    onChange={(e) => setDraft({ ...draft, tosRegion: e.target.value })}
                    placeholder="cn-beijing"
                  />
                </div>
                <div className="md:col-span-2">
                  <label htmlFor="tos-endpoint" className="mb-1 block text-sm font-medium text-slate-700">
                    TOS Endpoint
                  </label>
                  <input
                    id="tos-endpoint"
                    type="text"
                    className={inputClassName}
                    value={draft.tosEndpoint}
                    onChange={(e) => setDraft({ ...draft, tosEndpoint: e.target.value })}
                    placeholder="tos-cn-beijing.volces.com"
                  />
                </div>
              </>
            )}
          </div>
        </Section>

        <Section
          title="LLM 文本分析"
          description="配置用于文本分析的大模型服务，通过字幕文本识别换品边界，与视觉检测结合提高分段准确度。"
        >
          <div className="grid gap-4 md:grid-cols-2">
            <div className="col-span-full">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={draft.enableLlmAnalysis}
                  onChange={(e) => setDraft({ ...draft, enableLlmAnalysis: e.target.checked })}
                  className="h-4 w-4 rounded border-slate-300 text-slate-900 focus:ring-slate-500"
                />
                <span className="text-sm font-medium text-slate-700">启用 LLM 文本分析</span>
              </label>
            </div>

            <div className="md:col-span-2">
              <label htmlFor="llm-api-key" className="mb-1 block text-sm font-medium text-slate-700">
                LLM API 密钥
              </label>
              <input
                id="llm-api-key"
                type="password"
                className={inputClassName}
                value={draft.llmApiKey}
                onChange={(e) => setDraft({ ...draft, llmApiKey: e.target.value })}
                placeholder="sk-..."
                disabled={!draft.enableLlmAnalysis}
              />
            </div>

            <div className="md:col-span-2">
              <label htmlFor="llm-api-base" className="mb-1 block text-sm font-medium text-slate-700">
                API 基础地址
              </label>
              <input
                id="llm-api-base"
                type="text"
                className={inputClassName}
                value={draft.llmApiBase}
                onChange={(e) => setDraft({ ...draft, llmApiBase: e.target.value })}
                placeholder="https://api.openai.com/v1"
                disabled={!draft.enableLlmAnalysis}
              />
            </div>

            <div>
              <label htmlFor="llm-model" className="mb-1 block text-sm font-medium text-slate-700">
                模型
              </label>
              <input
                id="llm-model"
                type="text"
                className={inputClassName}
                value={draft.llmModel}
                onChange={(e) => setDraft({ ...draft, llmModel: e.target.value })}
                placeholder="gpt-4o-mini"
                disabled={!draft.enableLlmAnalysis}
              />
            </div>
          </div>
        </Section>

        <Section
          title="字幕设置"
          description="选择片段字幕的生成方式，待后端接入后默认生效。"
        >
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <label htmlFor="subtitle-mode" className="mb-1 block text-sm font-medium text-slate-700">
                字幕模式
              </label>
              <select
                id="subtitle-mode"
                className={inputClassName}
                value={draft.subtitleMode}
                onChange={(e) => setDraft({ ...draft, subtitleMode: e.target.value as SubtitleMode })}
              >
                <option value="off">关闭</option>
                <option value="basic">基础</option>
                <option value="styled">样式化</option>
                <option value="karaoke">卡拉 OK</option>
              </select>
            </div>

            <div>
              <label htmlFor="subtitle-position" className="mb-1 block text-sm font-medium text-slate-700">
                字幕位置
              </label>
              <select
                id="subtitle-position"
                className={inputClassName}
                value={draft.subtitlePosition}
                onChange={(e) =>
                  setDraft({ ...draft, subtitlePosition: e.target.value as SubtitlePosition })
                }
              >
                <option value="bottom">底部</option>
                <option value="middle">中间</option>
                <option value="custom">自定义</option>
              </select>
            </div>

            <div>
              <label htmlFor="subtitle-template" className="mb-1 block text-sm font-medium text-slate-700">
                字幕模板
              </label>
              <select
                id="subtitle-template"
                className={inputClassName}
                value={draft.subtitleTemplate}
                onChange={(e) =>
                  setDraft({ ...draft, subtitleTemplate: e.target.value as SubtitleTemplate })
                }
              >
                <option value="clean">简洁</option>
                <option value="ecommerce">电商</option>
                <option value="bold">加粗</option>
                <option value="karaoke">卡拉 OK</option>
              </select>
            </div>
          </div>
        </Section>

        <Section
          title="LLM 分析设置"
          description="配置用于商品分析的大语言模型（LLM）API。"
        >
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <label htmlFor="llm-type" className="mb-1 block text-sm font-medium text-slate-700">
                LLM 类型
              </label>
              <select
                id="llm-type"
                className={inputClassName}
                value={draft.llmType}
                onChange={(e) =>
                  setDraft({ ...draft, llmType: e.target.value as LlmType })
                }
              >
                <option value="openai">OpenAI 兼容</option>
                <option value="gemini">Gemini</option>
              </select>
            </div>

            <div>
              <label htmlFor="enable-llm-analysis" className="mb-1 block text-sm font-medium text-slate-700">
                启用 LLM 分析
              </label>
              <select
                id="enable-llm-analysis"
                className={inputClassName}
                value={draft.enableLlmAnalysis ? "true" : "false"}
                onChange={(e) =>
                  setDraft({ ...draft, enableLlmAnalysis: e.target.value === "true" })
                }
              >
                <option value="false">关闭</option>
                <option value="true">开启</option>
              </select>
            </div>

            <div className="md:col-span-2">
              <label htmlFor="llm-api-key" className="mb-1 block text-sm font-medium text-slate-700">
                LLM API 密钥
              </label>
              <input
                id="llm-api-key"
                type="password"
                className={inputClassName}
                value={draft.llmApiKey}
                onChange={(e) => setDraft({ ...draft, llmApiKey: e.target.value })}
                placeholder="sk-..."
              />
            </div>

            <div className="md:col-span-2">
              <label htmlFor="llm-api-base" className="mb-1 block text-sm font-medium text-slate-700">
                LLM API 基础地址
              </label>
              <input
                id="llm-api-base"
                type="text"
                className={inputClassName}
                value={draft.llmApiBase}
                onChange={(e) => setDraft({ ...draft, llmApiBase: e.target.value })}
                placeholder="https://api.openai.com/v1"
              />
            </div>

            <div className="md:col-span-2">
              <label htmlFor="llm-model" className="mb-1 block text-sm font-medium text-slate-700">
                LLM 模型
              </label>
              <input
                id="llm-model"
                type="text"
                className={inputClassName}
                value={draft.llmModel}
                onChange={(e) => setDraft({ ...draft, llmModel: e.target.value })}
                placeholder="gpt-4o-mini"
              />
            </div>
          </div>
        </Section>

        {error && <p className="text-sm text-red-600">{error}</p>}
      </div>

      <div className="sticky bottom-0 border-t border-slate-200 bg-white/80 backdrop-blur">
        <div className="mx-auto flex max-w-2xl justify-end gap-3 px-4 py-3 sm:px-6">
          <button
            className="rounded-md px-4 py-2 text-sm text-slate-600 hover:bg-slate-100"
            onClick={onBack}
          >
            取消
          </button>
          <button
            className="save-btn rounded-md bg-slate-900 px-4 py-2 text-sm text-white hover:bg-slate-800"
            onClick={handleSave}
          >
            保存
          </button>
        </div>
      </div>
    </div>
  );
}
