# Livestream Segmentation + VLM Switch + Subtitle Modes Implementation Plan

> **Summary**: Upgrade the current livestream clipping pipeline so segmentation quality improves materially, VLM provider/model can switch between Qwen-VL and GLM-5V, and subtitle behavior becomes settings-driven rather than hardcoded.
> **Deliverables**:
> - Task-scoped settings snapshot persisted with each upload
> - Configurable segmentation controls and VLM strategy controls in UI + backend
> - Qwen-VL / GLM-5V selectable provider path
> - Subtitle modes (`off/basic/styled/karaoke`) exposed in settings
> - Safe defaults that preserve current working export path
> **Effort**: Large
> **Parallel**: YES - 3 waves
> **Critical Path**: task-scoped settings → segmentation/VLM parameterization → subtitle mode plumbing → UI exposure

## Context

### Original Request
- 写一个单一实施方案
- 把候选召回、VLM、后处理、字幕方案都写进计划
- Qwen 和 GLM 做成设置里二选一
- 前端设置里要有对应开关和 API Key / Base / Model 输入

### Current Project Reality
- Current pipeline is **hybrid**, not pure local:
  - Local: FashionSigLIP, faster-whisper, FFmpeg
  - Cloud: Qwen-VL via DashScope
- Current first usable version can already export clips, but segmentation under-recalls and subtitle burn is only robust through fallback-to-no-subtitles.
- Current settings are frontend-only `localStorage` values (`apiKey/apiBase/model/funasrMode`) and do **not** flow through the task pipeline.

### Metis Review (gaps addressed)
- Must define **task-scoped settings snapshot** vs global settings behavior
- Must keep **provider switching limited to OpenAI-compatible providers** in first implementation
- Must define **subtitle mode downgrade chain** so export never blocks
- Must validate all numeric settings with explicit ranges/defaults on backend
- Must avoid scope creep into OCR/UI recall, auto model routing, or subtitle editor work

## Work Objectives

### Core Objective
Turn the current hardcoded segmentation/VLM/subtitle pipeline into a settings-driven system that improves product recall without breaking the currently working export path.

### Deliverables
- Backend task settings snapshot persisted per upload
- Segmentation controls:
  - scene threshold
  - frame sample fps
  - recall cooldown seconds
  - candidate looseness / threshold mode
  - min segment duration
  - dedupe window seconds
  - allow returned product
- VLM controls:
  - provider select (`qwen`, `glm`)
  - api key / api base / model
  - review strictness (`strict/standard/loose`)
  - review mode (`adjacent_frames`, `segment_multiframe`)
  - max candidate count
- Subtitle controls:
  - mode (`off/basic/styled/karaoke`)
  - position (`bottom/middle/custom`)
  - template (`clean/ecommerce/bold/karaoke`)
- Provider adapter path for GLM-5V via OpenAI-compatible chat completions

### Definition of Done
- A new upload stores its full settings snapshot under the task directory and only that snapshot is used during processing.
- Adjusting segmentation controls changes `candidates.json` / `confirmed_segments.json` / `enriched_segments.json` counts in a traceable way.
- User can choose Qwen-VL or GLM-5V in settings; backend validates both via the same OpenAI-compatible pattern.
- Subtitle mode selection affects export behavior without breaking clip generation.
- Existing “fallback to no-subtitle export still succeeds” remains true.

### Must Have
- No OCR/UI recall in this phase
- No breaking of current faster-whisper local path
- No blocking export if styled/karaoke subtitle mode fails
- Qwen remains default provider unless user explicitly switches

### Must NOT Have
- No auto provider routing by price
- No subtitle animation editor UI
- No provider-specific fork explosion in core business logic
- No runtime reading of mutable frontend settings after task start

## Configuration Ownership Model

### Rule
Settings have **two layers**:
- **Global UI defaults**: persisted in frontend localStorage
- **Task snapshot**: frozen copy written at upload time, used by backend pipeline

### Required Behavior
- Editing settings only affects **new** uploads
- In-flight tasks keep using their captured snapshot
- Backend pipeline must never read frontend localStorage concepts directly

### Task Snapshot File
- Persist to task directory as `settings.json`
- Include all segmentation/VLM/subtitle parameters plus defaults actually resolved
- `settings.json` is the only runtime truth source for all post-upload pipeline stages

## Validation Ranges and Defaults

### Default Source of Truth
- Backend settings schema is the single source of truth for defaults and numeric ranges
- Frontend store mirrors these defaults for UX only and must not diverge semantically

### Segmentation Defaults
- `scene_threshold`: default `27.0`, range `10.0-60.0`
- `frame_sample_fps`: default `2`, range `1-5`
- `recall_cooldown_seconds`: default `15`, range `0-60`
- `candidate_looseness`: enum `strict|standard|loose`, default `standard`
- `min_segment_duration_seconds`: default `25`, range `5-120`
- `dedupe_window_seconds`: default `90`, range `0-600`
- `allow_returned_product`: default `true`

### VLM Defaults
- `vlm_provider`: default `qwen`
- `api_base` default for qwen: `https://dashscope.aliyuncs.com/compatible-mode/v1`
- `model` default for qwen: `qwen-vl-plus`
- `glm` default model: `glm-5v-turbo`
- `review_strictness`: default `standard`
- `review_mode`: default `segment_multiframe`
- `max_candidate_count`: default `20`, range `1-100`

### Subtitle Defaults
- `subtitle_mode`: default `off`
- `subtitle_position`: default `bottom`
- `subtitle_template`: default `clean`
- `custom_position_y`: optional, range `0-100` percent if used

## Provider Decision: Qwen vs GLM

### Current Assessment
- **Qwen-VL** and **GLM-5V** are both viable OpenAI-compatible multimodal providers for this project.
- GLM can be integrated through the same `chat.completions` style abstraction.
- GLM is currently more expensive than Qwen for this workload, while the current bottleneck is not model capability but candidate recall and confirmation strategy.

### Plan Decision
- Implement **provider switchability** in this phase
- Keep **Qwen as default**
- Add **GLM-5V as optional challenger**, not default

## Subtitle Strategy Contract

### Modes
- `off`: export video without subtitle burn
- `basic`: current SRT-based attempt, but fallback to no-subtitle export if FFmpeg subtitle stage fails
- `styled`: generate styled subtitle asset (ASS-capable path) with fallback to `basic`, then `off`
- `karaoke`: timed highlight path (word/phrase level), fallback to `styled`, then `basic`, then `off`

### Guardrail
Any subtitle failure must still allow clip export to succeed.

## File Map

### Frontend files to modify
- `frontend/src/stores/settingsStore.ts`
- `frontend/src/components/SettingsModal.tsx`
- `frontend/src/components/UploadZone.tsx`
- `frontend/src/App.tsx`

### Backend API/config files to modify
- `backend/app/api/settings.py`
- `backend/app/api/upload.py`
- `backend/app/main.py`

### Backend pipeline/logic files to modify
- `backend/app/tasks/pipeline.py`
- `backend/app/services/adaptive_similarity.py`
- `backend/app/services/scene_detector.py`
- `backend/app/services/segment_validator.py`
- `backend/app/services/vlm_client.py`
- `backend/app/services/vlm_confirmor.py`
- `backend/app/services/vlm_parser.py` (if provider normalization is needed)
- `backend/app/services/srt_generator.py`
- `backend/app/services/ffmpeg_builder.py`

### Test files to add or modify
- `backend/tests/test_pipeline_config.py`
- `backend/tests/test_pipeline_orchestration.py`
- `backend/tests/test_segment_validator.py`
- `backend/tests/test_ffmpeg_builder.py`
- new: `backend/tests/test_settings_schema.py`
- new: `backend/tests/test_vlm_provider_switch.py`
- new: `backend/tests/test_segment_multiframe_review.py`

## Implementation Waves

### Wave 1 — Settings skeleton and task snapshot

#### Task 1: Expand frontend settings model
**Files**
- Modify: `frontend/src/stores/settingsStore.ts`
- Modify: `frontend/src/components/SettingsModal.tsx`

- [x] Add new settings shape for segmentation, VLM strategy, and subtitle modes
- [x] Add defaults matching the ranges in this plan
- [x] Add grouped UI sections: Segmentation / VLM / Subtitle
- [x] Preserve existing API key/base/model inputs
- [x] Add provider select: `qwen | glm`
- [x] Add subtitle mode and subtitle position/template controls

**Acceptance criteria**
- User can open settings and see all new controls
- Saving persists values to localStorage

#### Task 2: Backend settings schema and validation
**Files**
- Modify: `backend/app/api/settings.py`
- Modify: `backend/app/main.py`
- Add: `backend/tests/test_settings_schema.py`

- [x] Replace current minimal `SettingsRequest` with full typed schema
- [x] Add range validation for all numeric fields
- [x] Add provider/model compatibility checks
- [x] Keep `/api/settings/validate` working for Qwen and GLM
- [x] Make backend schema the sole default-value source for runtime settings

**Acceptance criteria**
- Invalid values return structured validation failures
- Valid Qwen and GLM payloads pass schema validation

#### Task 3: Task-scoped settings snapshot
**Files**
- Modify: `backend/app/api/upload.py`
- Modify: `backend/app/tasks/pipeline.py`

- [x] Upload endpoint accepts settings payload alongside file
- [x] Upload endpoint uses multipart form with a `settings_json` field plus file payload
- [x] Resolved settings are written into task directory `settings.json`
- [x] Pipeline stages read task-local `settings.json`, not mutable frontend/global state, except as final fallback when snapshot is absent

**Acceptance criteria**
- Each task directory contains `settings.json`
- Changing UI settings affects only future uploads

### Wave 2 — Segmentation and VLM quality upgrade

#### Task 4: Make segmentation controls configurable
**Files**
- Modify: `backend/app/services/scene_detector.py`
- Modify: `backend/app/services/adaptive_similarity.py`
- Modify: `backend/app/tasks/pipeline.py`

- [x] Thread `scene_threshold`, `frame_sample_fps`, `recall_cooldown_seconds`, and `candidate_looseness` through the pipeline
- [x] Replace hardcoded `60s` cooldown with task settings
- [x] Replace fixed sample rate with settings-controlled sample rate

**Acceptance criteria**
- Same video with different settings produces different candidate counts in a traceable way
- Lower cooldown / higher fps increases recall without code edits

#### Task 5: Change VLM review from adjacent-point to segment-multiframe
**Files**
- Modify: `backend/app/services/vlm_confirmor.py`
- Modify: `backend/app/services/vlm_client.py`
- Add: `backend/tests/test_segment_multiframe_review.py`

- [x] Add `review_mode` support
- [x] Implement `segment_multiframe` by sampling start/middle/end frames for a candidate segment
- [x] Keep `adjacent_frames` as compatibility mode
- [x] Add `review_strictness` knobs to prompt construction or decision thresholds

**Acceptance criteria**
- Backend can run with either adjacent or multiframe review mode
- Default mode is `segment_multiframe`
- Confirmed segment count does not depend on only one point frame anymore

#### Task 6: Provider switch: Qwen vs GLM
**Files**
- Modify: `backend/app/services/vlm_client.py`
- Modify: `backend/app/tasks/pipeline.py`
- Add: `backend/tests/test_vlm_provider_switch.py`

- [x] Normalize provider settings into one OpenAI-compatible client factory
- [x] Support provider-specific default base URLs and models
- [x] Keep a shared image_url-based message path
- [x] Log which provider/model each task used
- [x] Restrict first implementation to OpenAI-compatible providers only

**Acceptance criteria**
- User can choose Qwen or GLM in settings
- Validation passes for both providers
- Default remains Qwen

### Wave 3 — Post-processing and subtitle modes

#### Task 7: Make post-processing compression configurable
**Files**
- Modify: `backend/app/services/segment_validator.py`
- Modify: `backend/app/tasks/pipeline.py`

- [ ] Make `min_segment_duration_seconds` configurable
- [ ] Make `dedupe_window_seconds` configurable
- [ ] Implement `allow_returned_product` semantics so return visits are not dropped when enabled

**Acceptance criteria**
- Short valid product sections survive when user lowers min duration
- Return-product behavior is controlled by setting, not hardcoded

#### Task 8: Subtitle mode plumbing
**Files**
- Modify: `backend/app/services/srt_generator.py`
- Modify: `backend/app/services/ffmpeg_builder.py`
- Modify: `backend/app/tasks/pipeline.py`

- [ ] Route export behavior based on `subtitle_mode`
- [ ] `off`: do not generate/burn subtitle assets
- [ ] `basic`: current SRT path with safe fallback to no subtitles
- [ ] `styled`: in phase 1, provide schema, task snapshot plumbing, and downgrade contract to `basic/off`
- [ ] `karaoke`: in phase 1, provide schema, task snapshot plumbing, and downgrade contract through `styled/basic/off`
- [ ] Thread subtitle position/template settings into selected export path

**Acceptance criteria**
- Subtitle mode is reflected in export behavior
- Export never blocks on subtitle failures

#### Task 9: Frontend upload path uses full settings payload
**Files**
- Modify: `frontend/src/components/UploadZone.tsx`

- [ ] Upload request includes current settings payload
- [ ] UI shows active provider/subtitle mode context on current task

**Acceptance criteria**
- Backend task uses the exact settings visible in UI at upload time

## Acceptance Scenarios

### Scenario A — Segmentation tuning
- Upload same video twice
- Run once with strict/default settings and once with loose settings
- Expect candidate count and final segment count for loose settings to be greater or equal to strict settings

### Scenario B — Provider switch
- Validate Qwen settings
- Validate GLM settings
- Upload two tasks, one with each provider
- Expect task snapshots to reflect chosen provider/model

### Scenario C — Subtitle mode degradation chain
- `off` exports clip with no subtitle attempt
- `basic` attempts SRT burn, falls back to no subtitles if FFmpeg rejects subtitle filter
- `styled` and `karaoke` do not block export; in phase 1 they may behave as downgraded modes, but export must still succeed

### Must-Have Regression Scenarios
- Runtime settings sourced from `task/settings.json` preserve current working pipeline behavior under defaults
- Basic subtitle fallback to no-subtitle export still succeeds
- Existing point-to-segment expansion remains intact under default settings

### Scenario D — Returned product handling
- Use a video where the same product reappears later
- Expect `allow_returned_product=true` to preserve both sections
- Expect `allow_returned_product=false` + dedupe window to collapse them when within threshold

## Key Risks and Guardrails

- **Risk**: Settings become decorative and do not affect runtime
  - **Guardrail**: task-local `settings.json` required for every upload
- **Risk**: GLM provider introduces response-shape drift
  - **Guardrail**: keep provider behind shared OpenAI-compatible client contract; add provider-specific normalization only where needed
- **Risk**: Subtitle modes block export
  - **Guardrail**: strict downgrade chain from karaoke → styled → basic → off
- **Risk**: Too many segmentation knobs create unbounded candidate counts
  - **Guardrail**: enforce `max_candidate_count` and numeric validation ranges

## Out of Scope

- OCR/UI recall pipeline
- Automatic provider selection by price
- Subtitle animation editor
- Full ASS/karaoke implementation details beyond settings contract and downgrade path
- Historical task management / configuration history UI

## Success Criteria

- Users can tune segmentation without code changes
- Users can switch Qwen/GLM from settings with explicit API key/base/model fields
- Users can choose subtitle mode levels from settings
- Current first usable clip-export path keeps working
- The project remains runnable on the existing M4 MacBook Air + Docker 8G memory budget
