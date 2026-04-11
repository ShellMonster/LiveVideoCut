import { useState } from "react";
import { Settings } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { useSettingsStore } from "@/stores/settingsStore";

export function SettingsModal() {
  const [open, setOpen] = useState(false);
  const { apiKey, apiBase, model, funasrMode, setSettings } = useSettingsStore();

  const [draft, setDraft] = useState({ apiKey, apiBase, model, funasrMode });
  const [error, setError] = useState<string | null>(null);

  const handleOpen = () => {
    setDraft({ apiKey, apiBase, model, funasrMode });
    setError(null);
    setOpen(true);
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
        <DialogContent>
          <DialogHeader>
            <DialogTitle>VLM / FunASR Settings</DialogTitle>
            <DialogDescription>
              Configure the VLM API and FunASR transcription mode.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div>
              <label htmlFor="api-key" className="mb-1 block text-sm font-medium text-slate-700">
                VLM API Key
              </label>
              <input
                id="api-key"
                type="password"
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
                value={draft.apiKey}
                onChange={(e) => setDraft({ ...draft, apiKey: e.target.value })}
                placeholder="sk-..."
              />
            </div>

            <div>
              <label htmlFor="api-base" className="mb-1 block text-sm font-medium text-slate-700">
                API Base URL
              </label>
              <input
                id="api-base"
                type="text"
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
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
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
                value={draft.model}
                onChange={(e) => setDraft({ ...draft, model: e.target.value })}
              />
            </div>

            <div>
              <label htmlFor="funasr-mode" className="mb-1 block text-sm font-medium text-slate-700">
                FunASR Mode
              </label>
              <select
                id="funasr-mode"
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
                value={draft.funasrMode}
                onChange={(e) =>
                  setDraft({ ...draft, funasrMode: e.target.value as "local" | "remote" })
                }
              >
                <option value="local">Local Docker</option>
                <option value="remote">Remote API</option>
              </select>
            </div>

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
