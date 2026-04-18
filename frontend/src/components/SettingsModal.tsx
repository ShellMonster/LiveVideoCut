import { useState } from "react";
import { Settings as SettingsIcon } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
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

export function SettingsModal() {
  const [open, setOpen] = useState(false);
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
    asrApiKey,
    tosAk,
    tosSk,
    tosBucket,
    tosRegion,
    tosEndpoint,
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
    asrApiKey,
    tosAk,
    tosSk,
    tosBucket,
    tosRegion,
    tosEndpoint,
  });
  const showToast = useToastStore((state) => state.showToast);

  const handleOpen = () => {
    setDraft({
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
    asrApiKey,
    tosAk,
    tosSk,
    tosBucket,
    tosRegion,
    tosEndpoint,
  });
    setError(null);
    setOpen(true);
  };

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
    setOpen(false);
    showToast("设置已保存", "success");
  };

  return (
    <>
        <button
          className="settings-btn fixed right-4 top-4 rounded-lg p-2 text-slate-500 hover:bg-slate-100 hover:text-slate-700"
          onClick={handleOpen}
          aria-label="设置"
        >
        <SettingsIcon size={20} />
      </button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[85vh] max-w-2xl overflow-y-auto">
          <DialogHeader>
            <DialogTitle>流程设置</DialogTitle>
            <DialogDescription>
              配置分段、VLM 复核和新上传任务的默认字幕参数。
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
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
              </div>

              <label className="flex items-center justify-between gap-4 rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700">
                <div>
                  <span className="font-medium text-slate-900">允许商品再次出现</span>
                  <p className="mt-0.5 text-xs text-slate-500">
                    保留同一商品在直播后续再次出现的片段。
                  </p>
                </div>
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded border-slate-300 text-slate-900 focus:ring-slate-500"
                  checked={draft.allowReturnedProduct}
                  onChange={(e) => setDraft({ ...draft, allowReturnedProduct: e.target.checked })}
                />
              </label>
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
                    <option value="dashscope">阿里云 DashScope</option>
                    <option value="volcengine">火山引擎 豆包</option>
                  </select>
                </div>

                {draft.asrProvider === "volcengine" && (
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
                      <p className="text-xs font-medium text-amber-800">TOS 对象存储配置（bigmodel ASR 需要通过 TOS 传音频）</p>
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

            {error && <p className="text-sm text-red-600">{error}</p>}
          </div>

          <div className="mt-6 flex justify-end gap-3">
            <button
              className="rounded-md px-4 py-2 text-sm text-slate-600 hover:bg-slate-100"
              onClick={() => setOpen(false)}
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
        </DialogContent>
      </Dialog>
    </>
  );
}
