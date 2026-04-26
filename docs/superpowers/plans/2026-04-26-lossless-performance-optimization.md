# Lossless Performance Optimization Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce avoidable runtime overhead without changing clipping quality, subtitle output, visual detection thresholds, ASR/VLM/LLM behavior, or FFmpeg quality settings.

**Architecture:** Keep all algorithmic decisions unchanged. Optimize waste around observability, duplicate FFmpeg thumbnail extraction, cover frame sampling process count, frontend state churn, and history page request/image behavior.

**Tech Stack:** Python/FastAPI/Celery/OpenCV/FFmpeg, React/TypeScript/Zustand/Vite.

---

### Task 1: Backend cover extraction and thumbnail reuse

**Files:**
- Modify: `backend/app/services/cover_selector.py`
- Modify: `backend/app/services/ffmpeg_builder.py`
- Modify: `backend/app/tasks/pipeline.py`
- Test: `backend/tests/test_ffmpeg_builder.py`
- Test: `backend/tests/test_cover_selector.py`

- [ ] Add failing tests for batch cover frame extraction and thumbnail skip.
- [ ] Implement single-FFmpeg cover candidate extraction while preserving timestamps and scoring.
- [ ] Return/save the selected cover frame so thumbnail extraction can be skipped when already present.
- [ ] Add lightweight timing logs around cover selection and FFmpeg export.
- [ ] Run related backend tests.

### Task 2: Frontend state churn and history page lightweight optimization

**Files:**
- Modify: `frontend/src/stores/taskStore.ts`
- Modify: `frontend/src/hooks/useWebSocket.ts`
- Modify: `frontend/src/components/HistoryPage.tsx`

- [ ] Add equality guards to task store setters.
- [ ] Avoid redundant WebSocket-driven state writes.
- [ ] Add AbortController to history list/count requests.
- [ ] Cache expanded task clips in memory during the page session.
- [ ] Add lazy/async image loading to history thumbnails.
- [ ] Run frontend typecheck/build.

### Task 3: Verification

**Files:**
- Validate modified backend and frontend files.

- [ ] Run backend targeted pytest.
- [ ] Run frontend build/typecheck.
- [ ] Run diagnostics on modified files where available.
- [ ] Report verification results and remaining real-video validation need.
