import {
  DEFAULT_API_BASES,
  DEFAULT_MODELS,
  type CommerceImageQuality,
  type CommerceImageSize,
  type ExportMode,
  type VlmProvider,
} from "@/stores/settingsStore";
import {
  Field,
  Notice,
  NumberField,
  OptionCard,
  PresetCard,
  SecretInput,
  SegmentedControl,
  SettingsCard,
  fieldClassName,
} from "./SettingsControls";
import type { SettingsDraft, UpdateSettingsDraft } from "./types";

export function PresetSection({
  draft,
  onApplyPreset,
}: {
  draft: SettingsDraft;
  onApplyPreset: (preset: "quality" | "fast" | "debug" | "plain") => void;
}) {
  return (
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
          onClick={() => onApplyPreset("quality")}
        />
        <PresetCard
          title="快速低成本版"
          desc="跳过 VLM，使用基础字幕，适合快速预览切片结果。"
          selected={draft.exportMode === "no_vlm" && draft.subtitleMode === "basic"}
          tags={["速度快", "成本低"]}
          onClick={() => onApplyPreset("fast")}
        />
        <PresetCard
          title="全量候选调试版"
          desc="导出所有候选片段，用于排查召回不足或误切问题。"
          selected={draft.exportMode === "all_candidates"}
          tags={["调试", "候选全切"]}
          onClick={() => onApplyPreset("debug")}
        />
        <PresetCard
          title="纯切片无字幕版"
          desc="关闭字幕和 BGM，只导出原声片段，适合二次剪辑。"
          selected={draft.subtitleMode === "off" && !draft.bgmEnabled}
          tags={["无字幕", "无混音"]}
          onClick={() => onApplyPreset("plain")}
        />
      </div>
    </SettingsCard>
  );
}

export function AiServicesSection({
  draft,
  needsVlmKey,
  updateDraft,
}: {
  draft: SettingsDraft;
  needsVlmKey: boolean;
  updateDraft: UpdateSettingsDraft;
}) {
  return (
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
              <SecretInput value={draft.apiKey} onChange={(apiKey) => updateDraft({ apiKey })} />
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
                <SecretInput
                  value={draft.commerceGeminiApiKey}
                  onChange={(commerceGeminiApiKey) => updateDraft({ commerceGeminiApiKey })}
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
                <SecretInput
                  value={draft.commerceImageApiKey}
                  onChange={(commerceImageApiKey) => updateDraft({ commerceImageApiKey })}
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
  );
}

export function TranscriptionSection({
  draft,
  needsTos,
  updateDraft,
}: {
  draft: SettingsDraft;
  needsTos: boolean;
  updateDraft: UpdateSettingsDraft;
}) {
  return (
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
            <SecretInput value={draft.asrApiKey} onChange={(asrApiKey) => updateDraft({ asrApiKey })} />
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
              <SecretInput value={draft.tosSk} onChange={(tosSk) => updateDraft({ tosSk })} />
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
  );
}
