# CLAUDE.md

## 项目定位

这是一个“直播视频 AI 智能剪辑”项目：

- 输入：一段直播录像 MP4
- 输出：一组可预览、可下载的短视频片段（clips）
- 目标：把直播里适合单独传播的商品讲解片段自动切出来，并带上烧录字幕


## 当前真实架构

不要只看 README，当前代码的真实运行架构如下：

- 前端：React + TypeScript + Vite + Tailwind
- 后端 API：FastAPI
- 异步任务：Celery
- 队列/状态：Redis
- 视频处理：FFmpeg
- 换衣检测：ClothingChangeDetector（三信号联合：YOLO 46类检测 + MediaPipe 像素分割 + HSV 直方图兜底）
- VLM：Qwen / GLM（二选一）
- ASR：当前支持四个 ASR provider：
  - `dashscope`：DashScope paraformer-v2（阿里云百炼，直接传 MP4，返回逐字时间戳）
  - `volcengine`：火山引擎大模型 ASR 标准版（submit+poll 模式，需 TOS 上传音频）
  - `volcengine_flash`：火山引擎大模型 ASR 极速版（一次请求返回，`transcribe_auto` 方法会优先尝试 flash 再回退标准版）
  - `volcengine_vc`：火山引擎音视频字幕生成 VC（剪映引擎分句，submit+poll，需 TOS + API Key）


## 当前 Docker 端口

以当前仓库里的 `docker-compose.yml` 为准：

- 前端：http://127.0.0.1:5537
- 后端：http://127.0.0.1:5538
- Redis：6379


## 用户侧主流程

### 1. 前端设置

用户先在独立设置页面（不是弹窗）里配置：

- `enable_vlm`：是否开启 VLM
- `export_mode`：导出模式
  - `smart`
  - `no_vlm`
  - `all_candidates`
  - `all_scenes`
- `vlm_provider`：`qwen` / `glm`
- `api_base` / `model`
- 分段参数（scene threshold、dedupe、min duration 等）
- 字幕参数：
  - `subtitle_mode`: `off` / `basic` / `styled` / `karaoke`
  - `subtitle_position`
  - `subtitle_template`
- 语气词过滤：`filter_filler_mode`：`off` / `subtitle` / `video`
  - `off`：不过滤（默认）
  - `subtitle`：仅从字幕中删除语气词
  - `video`：从字幕删除语气词 + 裁剪掉语气词对应的短视频段
- 封面策略：`cover_strategy`：`content_first` / `person_first`
  - `content_first`（默认）：优先选择突出商品/服装的帧作为封面
  - `person_first`：优先选择突出主播人脸的帧作为封面
- 视频倍速：`video_speed`：0.5 / 0.75 / 1.25（默认）/ 1.5 / 1.75 / 2 / 3
  - FFmpeg 滤镜顺序：先烧录字幕再变速，字幕与语音时序保持一致
  - 视频：`setpts=PTS/{speed}`，音频：`atempo` 链（>2x 时链式拼接）

这些设置保存在前端 Zustand store + localStorage 中，只影响之后新上传的任务。

### 2. 上传

前端上传时会把：

- 视频文件
- `settings_json`

一起提交到 `POST /api/upload`。

后端会：

- 校验格式、大小、编码、音频流
- 把原视频保存到 `uploads/<task_id>/original.mp4`
- 把元数据写到 `meta.json`
- 把设置写到 `settings.json`
- 启动 Celery 流水线

### 3. 任务进度

前端通过 WebSocket 连接 `/ws/tasks/{task_id}` 获取进度。

后端不是直接查 Celery 状态，而是读取 `uploads/<task_id>/state.json`。前端会显示：

- 上传中
- 处理中
- 已完成
- 失败

### 4. 结果展示

任务完成后，前端请求 `/api/tasks/{task_id}/clips` 获取片段列表，展示：

- 视频片段
- 缩略图
- 时长
- 商品名
- 下载入口


## 后端流水线真实顺序

当前主编排在：`backend/app/tasks/pipeline.py`

整体顺序是：

1. `visual_prescreen`
2. `vlm_confirm`
3. `enrich_segments`
4. `process_clips`

### 1) visual_prescreen

做这些事：

- FFmpeg 抽帧（默认 0.5fps）
- 用 ClothingChangeDetector（三信号联合：YOLO 品类变化 + MediaPipe 衣服 mask 内 HSV + 全帧 HSV 兜底）检测换衣节点
- 产出 `candidates.json` 和 `scenes.json`

### 2) vlm_confirm

根据导出模式决定是否走 VLM：

- `smart`：走 VLM 确认
- `no_vlm`：跳过 VLM
- `all_candidates`：导出所有候选
- `all_scenes`：导出所有场景

### 3) enrich_segments

做这些事：

- 整体转写，写出 `transcript.json`
- 商品名匹配
- 分段合法性校验
- 产出 `enriched_segments.json`

### 4) process_clips

这是最终导出阶段，会：

- 为每个 clip 重新从 `transcript.json` 裁对应字幕
- 生成 `.srt` 或 `.ass`
- 调用 FFmpeg 烧录字幕并导出 mp4
- 封面选择：根据 `cover_strategy` 从 clip 中均匀采样最多 30 帧，评分选出最佳封面
- 生成缩略图（保存到 `covers/clip_xxx.jpg`）
- 写 `clip_xxx_meta.json`

**并发处理**：使用 `ThreadPoolExecutor` 并行处理多个 clip，并发数由 `resource_detector.py` 根据容器 cgroup 资源动态计算（4GB 容器默认 2 workers）


## 并发处理与性能优化（resource_detector.py）

### 资源检测

`resource_detector.py` 在 Docker 容器内通过 cgroup v2 实时检测资源：
- CPU：读 `/sys/fs/cgroup/cpu.max`
- 内存：读 `/sys/fs/cgroup/memory.max`
- 计算公式：`clip_workers = min(cpu_cores, (mem - 2.0GB) / 0.6GB, 2)`

### process_clips 并行策略

- 使用 `ThreadPoolExecutor`（不是 ProcessPoolExecutor — Celery prefork worker 是 daemon 进程，不允许再 fork）
- 每个 thread 启动 FFmpeg 子进程，GIL 在 subprocess.run() 期间释放
- 并行数 > 1 且 segments > 1 时并行，否则串行 fallback

### FFmpeg 优化

每个 FFmpeg 实例加了以下优化参数（在 `ffmpeg_builder.py` 的 `build_cut_command` 中）：
- `-x264opts rc-lookahead=5:bframes=1:ref=1` — 降低编码缓冲区，每实例省 ~100MB
- `-threads 4 -filter_threads 2` — 限制线程数，避免内存膨胀
- `-movflags +faststart` — MP4 元数据前置，支持流式播放

### Celery Worker 配置

docker-compose.yml 中 worker 启动参数：
- `--concurrency=1` — 单进程，为 FFmpeg 留资源（AWS 生产指南推荐）
- `--max-tasks-per-child=10` — 处理 10 个任务后回收进程（避免内存高水位泄漏）
- `--max-memory-per-child=3000000` — 3GB 内存上限后回收（4GB 容器的 75%）
- `--prefetch-multiplier=1` — 只拉取 1 个任务（长耗时任务必须设 1）
- `-Ofair` — 公平调度

### 实测数据（20 分钟直播视频，9 clips）

| 阶段 | 串行 | 并行 2w + FFmpeg 优化 | 改善 |
|------|------|---------------------|------|
| process_clips | 276s | **195s** | **-29%** |
| visual_prescreen | 336s | 269s | 不稳定（受系统负载影响） |


## 语气词过滤（filler_filter.py）

三级词表：

- `FILLER_SAFE`（29词）— 安全删除，任何位置都可过滤
- `FILLER_SENTENCE_EDGE`（9词）— 只在句首/句尾过滤
- `FILLER_ALL`（38词）— 全量词表

两种模式：

- `subtitle`：调用 `filter_subtitle_words()` 从 words[] 删语气词，重建 text，空句整删
- `video`：除字幕过滤外，还调用 `compute_filler_cut_ranges()` 计算裁剪时间点（合并相邻 filler、加 padding、限非 filler 边界），传给 FFmpeg 的 `_build_trim_concat_command` 裁掉语气词短视频段

### 语气词视频裁剪（_build_trim_concat_command）

当 `filter_filler_mode=video` 且有 ASR 数据时，`build_cut_command` 委托给 `_build_trim_concat_command`：
1. 将 `filler_cut_ranges`（要删除的段）反转为 `keep_ranges`（要保留的段）
2. 对每个 keep range 用 FFmpeg `trim/atrim` 提取，`setpts=PTS-STARTPTS` 重置时间戳
3. `concat=n=N:v=1:a=1` 拼接所有保留段
4. 在拼接后的视频上烧字幕、变速、混 BGM
5. 整个过程单条 FFmpeg 命令，无中间临时文件


## 封面选择策略（cover_selector.py）

从 clip 中均匀采样最多 30 帧进行评分，选最佳帧作为缩略图。

### 评分算法

**质量分**（所有策略都会算，作为乘法基数）：
- 清晰度（Laplacian variance）50% + 对比度（std dev）30% + 亮度（钟形曲线 ideal=130）20%

**语义分**（按策略选择）：
- `content_first`（默认）：商品 bbox 面积比(cap 0.5) 35% + 置信度 25% + 三分法距离 20% + 局部清晰度 20%
- `person_first`：人脸面积比 40% + 中心距 25% + 人脸置信度 20% + 清晰度 15%

**最终得分** = 语义分 × 质量分。无信号时 fallback 到 clip 中点。

### 依赖模型

- `content_first` 复用已有 YOLO 46类 ONNX（通过 ClothingSegmenter.detect_clothing_items）
- `person_first` 用 MediaPipe FaceDetection（已有依赖 mediapipe>=0.10.14）


## 当前字幕链路（非常重要）

### 基础事实

- `basic`：生成普通 SRT
- `karaoke`：生成 ASS 并烧录
- 当前简体转换已接入
- 当前 DashScope paraformer-v2 已输出字符级时间戳（words: [{text, begin_time, end_time}]）
- `transcript.json` 中保留 `words`
- SRT/ASS 文件不再清理，处理完会保留在 `clips/` 目录下

### 当前 karaoke 的实现方式

当前实现不是简单整句字幕，而是：

- 逐词/逐字时间高亮
- 当前词/字会额外叠加高亮对白
- 当前高亮词/字带三段弹跳动画（0→60ms 放大130% → 60→120ms 回弹105% → 120→200ms 稳定100%）

### 时序改进（解决"匀速感"和"跳句"问题）

1. **最小视觉间隙**：`_ensure_non_overlapping()` 强制 80ms 最小间隙（`min_gap=0.08`），被截断的 segment 同步修剪 words 列表并重建 text，标记 `_truncated`
2. **淡出效果**：被截断的 segment 加 `{\fad(0,200)}` 淡出，避免突然消失
3. **加权分字**：多字 word 用加权分配（首字 1.3x、末字 0.7x、中间 1.0x）模拟自然语音起始强调，而非均分
4. **间隙修剪同步**：截断 segment 时同步修剪 words 列表，确保 `\kf` 总时长与实际显示时长一致

### 当前已验证的字号

- 普通字幕：`60`
- 当前高亮字幕：`72`


## 关键文件

### 后端

- `backend/app/api/upload.py`
- `backend/app/api/tasks.py`
- `backend/app/api/clips.py`
- `backend/app/api/settings.py`
- `backend/app/tasks/pipeline.py`
- `backend/app/services/dashscope_asr_client.py`
- `backend/app/services/volcengine_asr_client.py`
- `backend/app/services/volcengine_vc_client.py`
- `backend/app/services/transcript_merger.py`
- `backend/app/services/srt_generator.py`
- `backend/app/services/ffmpeg_builder.py`
- `backend/app/services/vlm_confirmor.py`
- `backend/app/services/segment_validator.py`
- `backend/app/services/clothing_segmenter.py`
- `backend/app/services/clothing_change_detector.py`
- `backend/app/services/filler_filter.py`
- `backend/app/services/cover_selector.py`
- `backend/app/services/resource_detector.py`

### 前端

- `frontend/src/App.tsx`
- `frontend/src/components/UploadZone.tsx`
- `frontend/src/components/SettingsPage.tsx`
- `frontend/src/components/ToastViewport.tsx`
- `frontend/src/hooks/useWebSocket.ts`
- `frontend/src/stores/settingsStore.ts`
- `frontend/src/stores/taskStore.ts`
- `frontend/src/stores/toastStore.ts`


## 输出目录约定

每个任务都落在：

- `uploads/<task_id>/original.mp4`
- `uploads/<task_id>/meta.json`
- `uploads/<task_id>/settings.json`
- `uploads/<task_id>/transcript.json`
- `uploads/<task_id>/candidates.json`
- `uploads/<task_id>/enriched_segments.json`
- `uploads/<task_id>/clips/clip_xxx.mp4`
- `uploads/<task_id>/clips/clip_xxx_meta.json`
- `uploads/<task_id>/covers/clip_xxx.jpg`


## 当前协作规则

### 改代码前

- 优先先读 `pipeline.py`、`settings.py`、`UploadZone.tsx`、`SettingsPage.tsx`
- 涉及字幕，一定先看 `srt_generator.py` 和 `ffmpeg_builder.py`
- 不要只参考 README，必须以真实代码为准

### 调试时

- 先确认问题发生在：
  - 候选生成
  - VLM 确认
  - transcript 生成
  - 字幕切片
  - FFmpeg 烧录
- 不要跳过真实视频复验

### 修改后最少验证

至少做这三类验证：

1. 相关 pytest
2. 相关文件诊断 / 类型检查
3. 真实 Docker 链路复跑一次

字幕、导出、任务编排这类改动，不做真实复跑不算完成。


## 常用命令

### 启动 / 重建

```bash
docker compose up -d
docker compose build api worker
docker compose up -d api worker
docker compose ps
```

### 看日志

```bash
docker compose logs -f api
docker compose logs -f worker
```

### 后端测试

```bash
cd backend
pytest tests/test_srt_generator.py tests/test_ffmpeg_builder.py
```


## ASR 效果对比（实测结论）

用同一段 20 分钟直播视频，karaoke 字幕模式下对比：

| ASR Provider | 分句数 | 平均句长 | Karaoke 效果 |
|---|---|---|---|
| `dashscope` (paraformer-v2) | 267 | 4.5s | ❌ 最差 — 逐字时间戳是伪时间戳（匀速 0.272s/字），跳字完全不同步 |
| `volcengine` (BigModel 标准版) | 403 | 2.7s | ⚠️ 还行 — 真实时间戳同步好，但中文无词边界感知会拆词折行（如"雪/纺"分两行） |
| `volcengine_vc` (VC 字幕) | 796 | 1.5s | ✅ 最好 — 剪映引擎智能分句 + 真实语音节奏时间戳，句尾字自然拖长 |

**结论：`volcengine_vc` 是当前最佳 ASR 选择，推荐设为默认。**

DashScope paraformer-v2 的逐字时间戳是均匀分配的伪时间戳，不是真实语音节奏，这导致 karaoke 跳字完全不同步。这是 API 本身的限制，不是我们能修的。

## ASR 价格对比

| ASR Provider | 后付费 | 预付费 | 免费额度 |
|---|---|---|---|
| DashScope paraformer-v2 | ~¥0.29/小时 | — | 有 |
| 火山 BigModel 标准版 | ¥2.3/小时 | ¥2,000/千小时 | 20 小时 |
| 火山 BigModel 极速版 | ¥4.5/小时 | — | 20 小时 |
| 火山 VC 字幕 | ¥6.5/小时 | ¥2,500/500小时 | 20 小时 |

VC 贵 3 倍但效果最好，适合对字幕质量有要求的场景。

## 已知注意点

- 当前推荐 ASR 为 `volcengine_vc`（效果最好），`dashscope` 和 `volcengine` 均可作为备选
- 之前用的 SenseVoice / faster-whisper 已删除
- 火山引擎 ASR 已接入两种模式：标准版（submit+poll）和极速版 flash（单次请求），`transcribe_auto` 会优先 flash 再回退标准版
- 火山引擎 VC 使用剪映引擎分句，submit+poll 模式，需 TOS 上传音频 + API Key（与 BigModel 共用同一个 key）
- DashScope paraformer-v2 的逐字时间戳是匀速伪时间戳（~0.272s/字），不适合 karaoke 跳字，只适合 basic/styled 字幕
- `subtitle_mode=karaoke` 走的是 ASS，不是普通 SRT
- karaoke 的 base 层（`\kf` 逐字高亮）和 overlay 层（逐字跳动）通过 gap filler 机制保持时间同步
- SRT/ASS 文件不再清理（`cleanup_srt` 已注释掉），处理完会保留在 `clips/` 目录下方便调试
- 某些问题表面看像"后续 clip 没字幕"，实际可能只是字幕太小、太靠底，需要先抽帧确认
- 现在已经把字幕字号放大，但如果用户还想要更夸张的综艺感，需要继续加强动画而不是只调字号
- 换衣检测依赖两个本地模型文件（位于 `backend/assets/models/`）：
  - `selfie_multiclass_256x256.tflite`（MediaPipe，16MB，6类像素分割，class 4 = clothes）
  - `yolov8n-fashionpedia.onnx`（YOLO，12MB，46类服装检测）
  - Docker 构建时通过 `COPY assets/` 打包进镜像
  - 模型来源：MediaPipe 从 Google GCS 下载，YOLO 从 HuggingFace `louisJLN/yolo8-fashionpedia` 下载（国内需代理）
- `frame_sample_fps` 默认值已改为 `0.5`（float 类型），原来 `2` 导致帧数过多、处理慢且容易 OOM
- 换衣检测的帧分析会在处理前 resize 到 640px 以降低内存占用
- 新增依赖 `mediapipe>=0.10.14`（在 requirements.txt 中）
