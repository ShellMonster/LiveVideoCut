import { useState } from "react";
import { Settings } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import {
  useSettingsStore,
  type ReviewMode,
  type StrictnessMode,
  type SubtitleMode,
  type SubtitlePosition,
  type SubtitleTemplate,
  type VlmProvider,
} from "@/stores/settingsStore";

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

export function SettingsModal() {
  const [open, setOpen] = useState(false);
  const {
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
    allowReturnedProduct,
    maxCandidateCount,
    subtitleMode,
    subtitlePosition,
    subtitleTemplate,
    funasrMode,
    setSettings,
  } = useSettingsStore();

  const [draft, setDraft] = useState({
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
    allowReturnedProduct,
    maxCandidateCount,
    subtitleMode,
    subtitlePosition,
    subtitleTemplate,
    funasrMode,
  });
  const [error, setError] = useState<string | null>(null);

  const handleOpen = () => {
    setDraft({
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
      allowReturnedProduct,
      maxCandidateCount,
      subtitleMode,
      subtitlePosition,
      subtitleTemplate,
      funasrMode,
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
    if (!draft.apiKey.trim()) {
      setError("API Key is required");
      return;
    }
    setSettings(draft);
    setError(null);
    setOpen(false);
  };

  return (
    <>
      <button
        className="settings-btn fixed right-4 top-4 rounded-lg p-2 text-slate-500 hover:bg-slate-100 hover:text-slate-700"
        onClick={handleOpen}
        aria-label="Settings"
      >
        <Settings size={20} />
      </button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[85vh] max-w-2xl overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Pipeline Settings</DialogTitle>
            <DialogDescription>
              Configure segmentation, VLM review, and subtitle defaults for new uploads.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <Section
              title="Segmentation"
              description="Tune how candidate segments are recalled and compressed before VLM review."
            >
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <label htmlFor="scene-threshold" className="mb-1 block text-sm font-medium text-slate-700">
                    Scene Threshold
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
                    Frame Sample FPS
                  </label>
                  <input
                    id="frame-sample-fps"
                    type="number"
                    min={1}
                    max={5}
                    step="1"
                    className={inputClassName}
                    value={draft.frameSampleFps}
                    onChange={(e) => updateNumber("frameSampleFps", e.target.value)}
                  />
                </div>

                <div>
                  <label htmlFor="recall-cooldown" className="mb-1 block text-sm font-medium text-slate-700">
                    Recall Cooldown (seconds)
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
                    Candidate Looseness
                  </label>
                  <select
                    id="candidate-looseness"
                    className={inputClassName}
                    value={draft.candidateLooseness}
                    onChange={(e) =>
                      setDraft({ ...draft, candidateLooseness: e.target.value as StrictnessMode })
                    }
                  >
                    <option value="strict">Strict</option>
                    <option value="standard">Standard</option>
                    <option value="loose">Loose</option>
                  </select>
                </div>

                <div>
                  <label htmlFor="min-segment-duration" className="mb-1 block text-sm font-medium text-slate-700">
                    Min Segment Duration (seconds)
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
                    Dedupe Window (seconds)
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
              </div>

              <label className="flex items-center justify-between gap-4 rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700">
                <div>
                  <span className="font-medium text-slate-900">Allow Returned Product</span>
                  <p className="mt-0.5 text-xs text-slate-500">
                    Keep segments where the same product returns later in the stream.
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
              title="VLM"
              description="Keep the existing API credentials while adding provider and review strategy controls."
            >
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <label htmlFor="provider" className="mb-1 block text-sm font-medium text-slate-700">
                    Provider
                  </label>
                  <select
                    id="provider"
                    className={inputClassName}
                    value={draft.provider}
                    onChange={(e) => setDraft({ ...draft, provider: e.target.value as VlmProvider })}
                  >
                    <option value="qwen">Qwen</option>
                    <option value="glm">GLM</option>
                  </select>
                </div>

                <div>
                  <label htmlFor="review-strictness" className="mb-1 block text-sm font-medium text-slate-700">
                    Review Strictness
                  </label>
                  <select
                    id="review-strictness"
                    className={inputClassName}
                    value={draft.reviewStrictness}
                    onChange={(e) =>
                      setDraft({ ...draft, reviewStrictness: e.target.value as StrictnessMode })
                    }
                  >
                    <option value="strict">Strict</option>
                    <option value="standard">Standard</option>
                    <option value="loose">Loose</option>
                  </select>
                </div>

                <div className="md:col-span-2">
                  <label htmlFor="api-key" className="mb-1 block text-sm font-medium text-slate-700">
                    VLM API Key
                  </label>
                  <input
                    id="api-key"
                    type="password"
                    className={inputClassName}
                    value={draft.apiKey}
                    onChange={(e) => setDraft({ ...draft, apiKey: e.target.value })}
                    placeholder="sk-..."
                  />
                </div>

                <div className="md:col-span-2">
                  <label htmlFor="api-base" className="mb-1 block text-sm font-medium text-slate-700">
                    API Base URL
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
                    Model
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
                    Review Mode
                  </label>
                  <select
                    id="review-mode"
                    className={inputClassName}
                    value={draft.reviewMode}
                    onChange={(e) => setDraft({ ...draft, reviewMode: e.target.value as ReviewMode })}
                  >
                    <option value="adjacent_frames">Adjacent Frames</option>
                    <option value="segment_multiframe">Segment Multi-frame</option>
                  </select>
                </div>

                <div>
                  <label htmlFor="max-candidate-count" className="mb-1 block text-sm font-medium text-slate-700">
                    Max Candidate Count
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
                    FunASR Mode
                  </label>
                  <select
                    id="funasr-mode"
                    className={inputClassName}
                    value={draft.funasrMode}
                    onChange={(e) =>
                      setDraft({ ...draft, funasrMode: e.target.value as "local" | "remote" })
                    }
                  >
                    <option value="local">Local Docker</option>
                    <option value="remote">Remote API</option>
                  </select>
                </div>
              </div>
            </Section>

            <Section
              title="Subtitle"
              description="Choose how clip subtitles should be generated when later backend wiring lands."
            >
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <label htmlFor="subtitle-mode" className="mb-1 block text-sm font-medium text-slate-700">
                    Subtitle Mode
                  </label>
                  <select
                    id="subtitle-mode"
                    className={inputClassName}
                    value={draft.subtitleMode}
                    onChange={(e) => setDraft({ ...draft, subtitleMode: e.target.value as SubtitleMode })}
                  >
                    <option value="off">Off</option>
                    <option value="basic">Basic</option>
                    <option value="styled">Styled</option>
                    <option value="karaoke">Karaoke</option>
                  </select>
                </div>

                <div>
                  <label htmlFor="subtitle-position" className="mb-1 block text-sm font-medium text-slate-700">
                    Subtitle Position
                  </label>
                  <select
                    id="subtitle-position"
                    className={inputClassName}
                    value={draft.subtitlePosition}
                    onChange={(e) =>
                      setDraft({ ...draft, subtitlePosition: e.target.value as SubtitlePosition })
                    }
                  >
                    <option value="bottom">Bottom</option>
                    <option value="middle">Middle</option>
                    <option value="custom">Custom</option>
                  </select>
                </div>

                <div>
                  <label htmlFor="subtitle-template" className="mb-1 block text-sm font-medium text-slate-700">
                    Subtitle Template
                  </label>
                  <select
                    id="subtitle-template"
                    className={inputClassName}
                    value={draft.subtitleTemplate}
                    onChange={(e) =>
                      setDraft({ ...draft, subtitleTemplate: e.target.value as SubtitleTemplate })
                    }
                  >
                    <option value="clean">Clean</option>
                    <option value="ecommerce">Ecommerce</option>
                    <option value="bold">Bold</option>
                    <option value="karaoke">Karaoke</option>
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
              Cancel
            </button>
            <button
              className="save-btn rounded-md bg-slate-900 px-4 py-2 text-sm text-white hover:bg-slate-800"
              onClick={handleSave}
            >
              Save
            </button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
