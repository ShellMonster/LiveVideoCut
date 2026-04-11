# Learnings — live-stream-clipper

## 2026-04-09 Session Start
- Project: 直播视频AI切片工具 (Live Stream Clipper)
- Tech stack: React+shadcn/ui + FastAPI+Celery+Redis + ONNX Runtime + PySceneDetect + FashionSigLIP + Qwen-VL-Plus + FunASR + FFmpeg
- Key constraint: NO PyTorch, NO MoviePy, NO `-c copy`, NO CLIP ViT-B/32
- FashionSigLIP outputs 768-dim vectors (not 512 like CLIP)
- Adaptive threshold 0.78-0.82 with sliding window 5 frames
- 60s cooldown period between detected switches
- FunASR: 30min chunks + 3-5s overlap + independent process per chunk
- Qwen-VL-Plus: no native JSON mode, need regex extraction + parsing tolerance
- Conflict resolution: VLM > FashionSigLIP > ASR
- Docker image target: ~500MB (ONNX Runtime, not PyTorch 8GB)

## Task 1: Project Scaffold (2026-04-10)

### Environment
- Python 3.12.9 on macOS (arm64) — used instead of 3.11 for local venv, Dockerfile still targets 3.11-slim
- Node 20 with Vite 8.0.8
- Tailwind CSS v4 uses `@tailwindcss/vite` plugin (no tailwind.config.js needed)
- shadcn/ui v4 uses `base-nova` style, requires `clsx` + `tailwind-merge` + `lucide-react`

### Gotchas
- TypeScript 7.0 deprecates `baseUrl` — must add `"ignoreDeprecations": "6.0"` to tsconfig
- shadcn/ui init needs `baseUrl` + `paths` in root `tsconfig.json` (not just tsconfig.app.json)
- shadcn/ui init may timeout on dependency install — manually create `src/lib/utils.ts` with `cn()` helper
- pytest-asyncio warns about unset `asyncio_default_fixture_loop_scope` — non-blocking

### Key Decisions
- Backend venv at `backend/venv/` (gitignored)
- Frontend uses Tailwind CSS v4 (CSS-first config, no JS config file)
- nginx.conf proxies `/api` to backend service
- Test video: 333KB, 30s blue screen + 440Hz sine tone

## Task 2: Upload API + UI (2026-04-10)

### Gotchas
- Fake files (all-zero bytes) cause ffprobe to return non-zero exit code, not empty output — tests for "no audio" / "no video" must match generic ValidationError, not specific message
- `file.size` on UploadFile may be None — need `or 0` fallback
- Celery task stub needs `@celery_app.task(bind=True)` for future `self.update_state()` support
- Frontend XHR upload progress requires `xhr.upload.onprogress`, not `xhr.onprogress`

### Key Decisions
- Upload saves to `uploads/{task_id}/original.mp4` — flat structure, one dir per task
- Validation order: extension → size → save → codec → audio → metadata (fail fast before I/O)
- UploadZone uses XHR instead of fetch for progress tracking
- Zustand store tracks full lifecycle: idle → uploading → processing → done/error

## Task 3: WebSocket Progress System (2026-04-10)

### Key Decisions
- TaskStateMachine is a pure class with optional task_dir for persistence — decoupled from FastAPI
- State transitions validated via VALID_TRANSITIONS dict; ERROR is always valid from any state
- WebSocket polls state.json every 500ms and sends updates only on state change
- WebSocket auto-closes on COMPLETED or ERROR terminal states
- Frontend useWebSocket hook auto-reconnects on non-4040 close codes with 3s delay
- ProgressBar uses step indicators with Chinese labels matching backend state names

### Gotchas
- React 19 + TypeScript 6: `useRef<T>()` without initial value is a type error — must pass `undefined`
- `VALID_TRANSITIONS` dict doesn't include COMPLETED as a key (it's a terminal state) — `get_states()` must append it
- WebSocket close code 4040 used as custom "task not found" signal
- `asyncio.wait_for(websocket.receive_text(), timeout=0.01)` used to check client disconnect without blocking the poll loop

## Task 4: Settings UI — VLM/FunASR配置弹窗

### What was done
- Created `settingsStore.ts` — Zustand store with localStorage persistence (key: `clipper-settings`)
- Created `ui/dialog.tsx` — lightweight Dialog component (no @radix-ui dependency needed)
- Created `SettingsModal.tsx` — gear icon button + modal with form fields (apiKey, apiBase, model, funasrMode)
- Created `backend/app/api/settings.py` — `POST /api/settings/validate` using OpenAI SDK to verify API key
- Registered settings router in `main.py`

### Key decisions
- Hand-rolled Dialog instead of adding @radix-ui/react-dialog to keep dependencies minimal
- localStorage persistence done manually in store (no zustand/middleware needed for this simple case)
- Backend validate endpoint uses `openai` SDK with `max_tokens=1` for minimal cost validation
- SettingsModal uses draft state pattern — edits don't affect store until Save is clicked

### Files created/modified
- NEW: `frontend/src/stores/settingsStore.ts`
- NEW: `frontend/src/components/ui/dialog.tsx`
- NEW: `frontend/src/components/SettingsModal.tsx`
- NEW: `backend/app/api/settings.py`
- MOD: `backend/app/main.py` (added settings router)

## Task 5: First-Level Pipeline — Scene Detection + Visual Prescreen (2026-04-10)

### What was done
- Created `SceneDetector` — PySceneDetect ContentDetector(threshold=27.0), merges scenes <2s, handles no-scene-change edge case
- Created `FrameExtractor` — ffmpeg subprocess at 1fps within scene regions, saves frames.json
- Created `FashionSigLIPEncoder` — ONNX Runtime with mock_mode fallback (deterministic random via md5 seed), 768-dim vectors
- Created `AdaptiveSimilarityAnalyzer` — cosine similarity → sliding window(5) → adaptive threshold(90th pct * 0.9, clamped [0.78,0.82]) → 60s cooldown
- Updated `pipeline.py` with `visual_prescreen` Celery task (UPLOADED → EXTRACTING_FRAMES → SCENE_DETECTING → VISUAL_SCREENING)
- 37 new tests, all 79 tests pass

### Key decisions
- Mock mode uses `np.random.RandomState(md5_hash(path))` for deterministic vectors — same image always produces same vector
- Pipeline imports are at module level for services, but `json`/`Path` imported inside task function to match existing pattern
- Scene merging: short scenes (<2s) merge with previous, not next — simpler logic, preserves scene boundaries
- Sliding window uses `mode='valid'` — output is shorter by (window_size-1), offset maps back to original frame indices

### Gotchas
- PySceneDetect `open_video()` returns a video object with `.duration.get_seconds()` for total duration
- `scene_manager.get_scene_list()` returns list of tuples `(FrameTimecode, FrameTimecode)` — use `.get_seconds()` on each
- ffmpeg `-ss` before `-i` does fast seek (keyframe-based), `-to` is relative to seeked position
- `np.convolve(mode='valid')` output length = `len(input) - len(kernel) + 1`
