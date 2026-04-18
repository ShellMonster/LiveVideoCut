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
- ASR：当前主链路使用 `DashScope paraformer-v2`（阿里云百炼云端 API，¥0.288/小时，直接传 MP4，返回逐字时间戳）


## 当前 Docker 端口

以当前仓库里的 `docker-compose.yml` 为准：

- 前端：http://127.0.0.1:5537
- 后端：http://127.0.0.1:5538
- Redis：6379


## 用户侧主流程

### 1. 前端设置

用户先在设置弹窗里配置：

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
- 生成缩略图
- 写 `clip_xxx_meta.json`


## 当前字幕链路（非常重要）

### 基础事实

- `basic`：生成普通 SRT
- `karaoke`：生成 ASS 并烧录
- 当前简体转换已接入
- 当前 DashScope paraformer-v2 已输出字符级时间戳（words: [{text, begin_time, end_time}]）
- `transcript.json` 中保留 `words`

### 当前 karaoke 的实现方式

当前实现不是简单整句字幕，而是：

- 逐词/逐字时间高亮
- 当前词/字会额外叠加高亮对白
- 当前高亮词/字会带轻量放大动画

### 当前已验证的字号

最新一版已经把字号翻倍：

- 普通字幕：`60`
- 当前高亮字幕：`72`

当前真实任务复跑后，后续 clip 也能看到更明显的底部字幕，不再只有第一个 clip 才明显。


## 关键文件

### 后端

- `backend/app/api/upload.py`
- `backend/app/api/tasks.py`
- `backend/app/api/clips.py`
- `backend/app/api/settings.py`
- `backend/app/tasks/pipeline.py`
- `backend/app/services/dashscope_asr_client.py`
- `backend/app/services/transcript_merger.py`
- `backend/app/services/srt_generator.py`
- `backend/app/services/ffmpeg_builder.py`
- `backend/app/services/vlm_confirmor.py`
- `backend/app/services/segment_validator.py`
- `backend/app/services/clothing_segmenter.py`
- `backend/app/services/clothing_change_detector.py`

### 前端

- `frontend/src/App.tsx`
- `frontend/src/components/UploadZone.tsx`
- `frontend/src/components/SettingsModal.tsx`
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


## 当前协作规则

### 改代码前

- 优先先读 `pipeline.py`、`settings.py`、`UploadZone.tsx`、`SettingsModal.tsx`
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


## 已知注意点

- 当前主链路使用 DashScope paraformer-v2（阿里云百炼云端 API），之前用的 SenseVoice / faster-whisper 已删除
- `subtitle_mode=karaoke` 走的是 ASS，不是普通 SRT
- karaoke 的 base 层（`\kf` 逐字高亮）和 overlay 层（逐字跳动）通过 gap filler 机制保持时间同步
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
