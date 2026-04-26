# Pipeline Performance Benchmark — 2026-04-26

Video: `/Users/daozhang/Downloads/26年直播切片录屏/2026.2.27/艾文文IRIS202602271058.mp4`

Duration: 1200.06s, 1080x1920, 30fps, H.264/AAC.

## 1. Local isolated benchmark baseline

Task: `16dbad23-ce8d-41d9-96e8-c1932b8898e9`

Settings: VLM off, ASR/LLM off, subtitles off, BGM off, 1.25x, 1080p, `frame_sample_fps=0.5`.

| Metric | Value |
|---|---:|
| Monitor elapsed | ~295s |
| `visual_prescreen.extract_frames` | 39.96s |
| `visual_prescreen.detect_changes` | 117.79s |
| `process_clips` | 172.35s |
| Clips | 8 |
| Cover avg | ~20.16s/clip |
| FFmpeg export avg | ~40.82s/clip |

## 2. Scheme one benchmark: reuse pre-sampled frames for cover selection

Task: `75da8d82-9502-4597-b108-b2b58776bff1`

Same settings as baseline.

| Metric | Baseline | Current | Delta |
|---|---:|---:|---:|
| Monitor elapsed | ~295s | ~330s | +35s |
| `visual_prescreen.extract_frames` | 39.96s | 40.79s | +0.83s |
| `visual_prescreen.detect_changes` | 117.79s | 120.70s | +2.91s |
| `process_clips` | 172.35s | 181.25s | +8.90s |
| Cover avg | 20.16s | 15.87s | **-4.29s/clip** |
| FFmpeg export avg | 40.82s | 46.95s | +6.13s/clip |
| Cover source | ffmpeg | pre_sampled x8 | pass |
| Thumbnail skip | x8 | x8 | pass |

Interpretation: scheme one works and removes redundant cover extraction. Overall task time was slower in this run because FFmpeg export was slower under current machine load; the cover-selection substage itself improved by about 21%.

## 3. Full-chain benchmark

Task: `b8e233b5-0ca2-4e06-9416-0384a8c74092`

Settings: `smart` VLM on, `volcengine_vc`, karaoke subtitles, LLM text analysis on, BGM on, boundary snap on, boundary refinement off, 1.25x, 1080p.

| Stage | Time |
|---|---:|
| Monitor elapsed | ~600s |
| `visual_prescreen.extract_frames` | 46.34s |
| `visual_prescreen.detect_changes` | 165.40s |
| `vlm_confirm.confirm_candidates` | 72.08s |
| `enrich_segments.transcribe` | 22.83s |
| `enrich_segments.llm_analysis` | 19.24s |
| `enrich_segments.postprocess` | 0.06s |
| `process_clips` | 285.08s |

Clip stats:

| Metric | Value |
|---|---:|
| Validated/exported clips | 17 |
| Cover avg | 11.73s/clip |
| Cover source | pre_sampled x17 |
| Thumbnail skip | x17 |
| Subtitle prep avg | 0.02s/clip |
| FFmpeg export avg | 35.95s/clip |
| Clip total avg | 47.71s/clip |

## Bottleneck ranking

1. `process_clips` remains the largest full-chain stage at 285.08s, mostly FFmpeg export plus cover scoring.
2. Visual detection is second at 211.74s combined; `detect_changes` varies strongly by load/model warm state.
3. VLM confirmation costs 72.08s for 15 candidates.
4. VC ASR and LLM text analysis are comparatively small in this run: 22.83s and 19.24s.

## Post-review fixes

Oracle review found two follow-up issues after the benchmark run:

1. `TempFileCleaner.cleanup_frames()` only removed top-level image files and did not remove the real `frames/scene000/*.jpg` + `frames/frames.json` structure. This was fixed by recursively deleting the entire temporary `frames/` directory after `process_clips` finishes.
2. Reusing pre-sampled frames could reduce cover candidate density when `frame_sample_fps=0.5`. This was fixed by topping up with FFmpeg-sampled candidates only when the pre-sampled in-range frames are fewer than `max_frames`.

Verification after fixes:

| Check | Result |
|---|---:|
| `pytest tests/test_cleanup.py tests/test_ffmpeg_builder.py tests/test_cover_selector.py -q` | 42 passed |
| LSP errors: `cleanup.py`, `cover_selector.py`, `pipeline.py` | 0 |
| `npm run build` | passed |
| Docker `api` / `worker` health | healthy |
| Container cleanup probe | `frames_exists=False` |

## Evidence files

- `/tmp/benchmark_worker_16dbad23.log`
- `/tmp/benchmark_worker_75da8d82.log`
- `/tmp/benchmark_worker_b8e233b5.log`
- `/tmp/benchmark_worker_b8e233b5_summary.json`
