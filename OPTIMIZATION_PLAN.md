# 全管线优化方案

基于对项目各节点的调研（FFmpeg 视频处理、ASR 转写、换衣检测、字幕生成、Celery 管线、商品匹配），整理出 P0-P3 四个优先级的优化方案。

## P0 — 已实施（零风险，即改即生效）

| # | 优化 | 改动文件 | 效果 |
|---|------|---------|------|
| 1 | **`_build_trim_concat_command` 加 `-ss` input seeking** | `ffmpeg_builder.py` | FFmpeg 从 `-ss` 位置开始解码而非从头读，filler_mode=video 路径跳帧更快 |
| 2 | **封面提取加 `-an`** | `ffmpeg_builder.py`, `cover_selector.py` | 提取封面时跳过音频解码，每次提取省 ~50ms + 避免 audio stream probe |
| 3 | **ASS 字幕加 `shaping=simple`** | `ffmpeg_builder.py` | libass 使用简单文本塑形替代复杂 OpenType 塑形，降低 CPU 开销 |
| 4 | **Docker 加 `shm_size: 512mb` + `nofile: 65536`** | `docker-compose.yml` | 避免多 FFmpeg 实例并发时 `/dev/shm` 不足导致帧缓存失败；提升文件描述符上限避免 YOLO/MediaPipe ONNX Runtime 多线程时 fd 耗尽 |
| 5 | **Celery `max-tasks-per-child` 10→100** | `docker-compose.yml` | 减少进程回收频率，避免频繁重启 worker 的开销（10 太激进，300MB/task 的内存增长在 100 task 内不会超限） |
| 6 | **变速加 `aresample=async=1` + `-fflags +genpts`** | `ffmpeg_builder.py` | `aresample=async=1` 在 atempo 后自动补偿时间戳漂移，避免变速后音频不同步；`-fflags +genpts` 确保 concat 后 PTS 连续 |

### 注意事项

- P0-1（`-ss` seeking）改变了 `_build_trim_concat_command` 中 trim/atrim 的时间戳语义：从绝对时间改为相对 `-ss` 偏移的相对时间。不影响 `build_cut_command` 的普通路径（已有 `-ss`）。
- P0-3（`shaping=simple`）对中文 CJK 字幕效果无明显影响，仅影响复杂连字（如阿拉伯文）。中文场景完全安全。
- P0-4（`shm_size`）需要在 `docker compose up -d` 后生效，不影响构建。
- P0-5（`max-tasks-per-child=100`）配合 `--max-memory-per-child=3000000`（3GB）双保险，内存超限仍会回收。


## P1 — 推荐后续实施（低风险，需测试验证）

| # | 优化 | 改动范围 | 预期效果 | 风险 |
|---|------|---------|---------|------|
| 1 | **FFmpeg preset `fast` → `veryfast`** | `ffmpeg_builder.py` | 编码速度提升 ~30%，文件略大（CRF 23 下约 +5-10%），适合短视频场景 | 画质略降，可接受 |
| 2 | **CPS 约束（Characters Per Second）** | `srt_generator.py` | 限制字幕每秒显示字符数（建议 15-20 CPS），避免语速快的段落字幕一闪而过 | 可能需要分句重切 |
| 3 | **ASR 时间戳平滑** | `transcript_merger.py` | 对 DashScope 的匀速伪时间戳做加权平滑（参考 volcengine_vc 的节奏模式），改善 basic/styled 模式下的字幕节奏 | 不影响 karaoke（推荐用 vc） |
| 4 | **YOLOv8n → YOLO11n** | `clothing_segmenter.py`, 模型文件 | YOLO11n 比 YOLOv8n 在同等速度下 mAP 高 ~3-5%，无需重新训练，直接加载 ONNX | 需验证 46 类兼容性 |
| 5 | **OpenVINO INT8 量化** | `clothing_segmenter.py`, Dockerfile | 将 YOLO/MediaPipe ONNX 模型用 OpenVINO INT8 量化，推理速度提升 2-3x，内存减半 | 需安装 openvino 包，Docker 镜像增 ~300MB |
| 6 | **TF-IDF 商品匹配** | `product_matcher.py` | 用 TF-IDF + cosine similarity 替代当前关键词匹配，提升商品名召回率 | 需验证匹配准确率 |
| 7 | **Redis 进度追踪** | `pipeline.py`, `tasks.py` | 将 state.json 进度写入 Redis（当前是文件 I/O），减少磁盘读写 | 需改 WebSocket 读取逻辑 |

### 实施建议

- P1-1（veryfast）最简单，改一个字符串，建议优先。
- P1-4（YOLO11n）需要验证模型兼容性，建议用 Ultralytics 导出 46 类 ONNX 后跑对比测试。
- P1-5（OpenVINO）收益最大但改动最多，建议独立分支验证。


## P2 — 中期优化（中等风险，需架构改动）

| # | 优化 | 改动范围 | 预期效果 | 说明 |
|---|------|---------|---------|------|
| 1 | **Scene-VLM Context-Focus Window** | `vlm_confirmor.py` | VLM 确认时只传换衣节点 ±5s 的帧（而非整个场景），减少 token 消耗 50-70% | 需要精确定位帧范围 |
| 2 | **Embedding 第三路信号** | 新增 `embedding_service.py` | 用 CLIP/SigLIP embedding 计算相邻帧语义相似度，作为换衣检测的第三路信号（替代 HSV 兜底） | 需要引入 sentence-transformers |
| 3 | **Karaoke 280ms 动画时长** | `srt_generator.py` | 将弹跳动画从 200ms 延长到 280ms，使视觉节奏更自然 | 需调整三段动画比例 |
| 4 | **Celery Canvas 并行阶段** | `pipeline.py` | 将 visual_prescreen 的抽帧和换衣检测拆为 Canvas chain，抽帧完成后立即开始检测（而非抽完再检测） | 需要重构 pipeline 编排 |
| 5 | **4K→1080p 预处理** | `pipeline.py`, `ffmpeg_builder.py` | 如果输入视频 > 1080p，先缩放到 1080p 再处理，减少后续所有阶段的计算量 | 需要检测分辨率逻辑 |

### 实施建议

- P2-1（VLM Context-Focus）ROI 最高，能显著降低 API 成本。
- P2-4（Celery Canvas）改动较大但能提升整体吞吐量。


## P3 — 长期优化（高风险，需重大改动）

| # | 优化 | 改动范围 | 预期效果 | 说明 |
|---|------|---------|---------|------|
| 1 | **Grounding DINO 替代 YOLO** | `clothing_segmenter.py`, Dockerfile | 用 Grounding DINO 做开放词汇目标检测，不再受限于 46 类，可检测任意商品描述 | 需 GPU 或高性能 CPU，模型 ~600MB |
| 2 | **Intel QSV/NVIDIA NVENC 硬件编码** | `ffmpeg_builder.py`, Dockerfile | 用硬件编码替代 libx264 软编码，编码速度提升 5-10x | 需要特定硬件支持，Docker 内需设备映射 |
| 3 | **Queue 分区** | `docker-compose.yml`, `pipeline.py` | 将长任务（ASR/VLM）和短任务（FFmpeg）分到不同 Celery queue，避免短任务被长任务阻塞 | 需要多 worker 实例 |
| 4 | **Rubberband 音频变速** | `ffmpeg_builder.py`, Dockerfile | 用 rubberband 替代 atempo 做音频变速，音质更好（尤其 >2x 时） | 需安装 librubberband |

### 实施建议

- P3 仅在当前方案遇到瓶颈时考虑。
- P3-2（硬件编码）如果有 NVIDIA GPU 环境可以优先。
- P3-1（Grounding DINO）需要评估 CPU 性能是否够用。


## 调研来源

- FFmpeg 性能优化：官方 wiki（x264 tuning, seeking, concat filter）、Superuser/StackOverflow 社区经验
- ASR 最佳实践：DashScope / 火山引擎官方文档、语音处理社区经验
- Celery 生产配置：Celery 官方文档、AWS 生产部署指南
- 换衣检测：YOLO11 / Fashionpedia / DeepFashion2 / Grounding DINO 论文与开源实现
- 商品匹配：TF-IDF / BM25 / Embedding-based matching 业界实践
