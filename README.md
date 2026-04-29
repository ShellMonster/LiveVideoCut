# 直播视频 AI 智能剪辑

一键将直播录像自动拆分为商品讲解短视频片段，支持烧录字幕、karaoke 逐字高亮、语气词/敏感词过滤、字幕位置拖拽调整、智能封面选择、BGM 自动选曲和视频变速。上传 MP4，AI 自动识别换衣节点、转写语音、匹配商品名、导出短视频。

![产品流程图](docs/images/product-flow.png)

## 快速开始

### 前置条件

- Docker + Docker Compose
- 16GB 内存 + 8 核 CPU（Worker 限制 4GB，无需 GPU）

### 部署

```bash
git clone <repo-url> && cd 直播视频剪辑_GLM
cp .env.example .env
# 编辑 .env，填入 API Key
docker compose up -d
```

- 前端：http://127.0.0.1:5537
- 后端 API 文档：http://127.0.0.1:5538/docs

### 获取 API Key

| 服务 | 用途 | 获取地址 |
|------|------|----------|
| 阿里云 DashScope | VLM (Qwen) / ASR | [DashScope 控制台](https://dashscope.console.aliyun.com/) |
| 智谱开放平台 | VLM (GLM) | [智谱开放平台](https://open.bigmodel.cn/) |
| 火山引擎 | ASR (BigModel / VC) | [火山引擎控制台](https://console.volcengine.com/) |

## 用户流程

从上传到拿到成片，完整流程分五步：

1. **配置设置** — 在设置页配置 VLM / ASR / 字幕 / 切分等参数。设置保存在浏览器 localStorage 中，只影响之后新上传的任务，已有任务不受影响。页面按业务分 8 个页签（处理预设、AI 服务、转写服务、字幕设置、敏感词过滤、切分策略、导出与音频、高级参数），枚举值全部中文展示。

2. **上传视频** — 拖拽上传 MP4 文件，选择预设（高质量字幕版 / 快速低成本版 / 全量候选调试版 / 只切不烧字幕版）或自定义参数。后端校验格式、大小、编码和音频流后启动四阶段流水线。上传页同时展示 4 种预设的参数差异，方便非技术用户快速选择。

3. **实时进度** — 通过 WebSocket 推送四阶段处理进度：抽帧检测 → VLM 确认 → 转写融合 → 导出剪辑。任务队列页面可查看阶段 checklist、Worker 资源占用（CPU / 内存 / Redis）和实时日志。处理中任务 5 秒轮询，全部完成后自动切换到 30 秒。

4. **审核片段** — 卡片式浏览所有剪辑结果。右侧复核抽屉支持字幕草稿编辑（文本覆盖 + 起止秒调整）、approve / skip / reprocess 操作，以及单片段重导出。字幕覆盖保存在 `review.json` 中，不修改原始 ASR 数据，保持可追溯。修改字幕后点击重导出即可生成新片段。

5. **下载 / 分享** — 单个下载或批量 ZIP 打包（单次最多 20 个片段）。还可进入 AI 商品素材工作台，用 Gemini 识图 + OpenAI Image 生成模特图、淘宝详情页示例等电商素材。资产浏览器支持跨项目浏览所有片段，按状态和时长筛选。

## 功能特点

- **换衣检测** — 五信号联合（YOLO 46类 + MediaPipe + HSV × 3 + ORB 纹理），支持多信号独立 EMA 或加权投票融合
- **多 ASR 支持** — 火山 VC 字幕（推荐）、火山 BigModel、阿里 DashScope
- **VLM 二次确认** — 支持 Qwen / GLM，按导出模式决定是否参与
- **LLM 文本分析** — 用 LLM 识别换品边界，与视觉检测信号两层树融合
- **字幕烧录** — 四种模式：off / basic / styled / karaoke（逐字高亮 + 弹跳动画），支持预设按钮、拖拽坐标和字号调整
- **设置分块** — AI、转写、字幕、敏感词、切分、导出和高级参数按业务拆分，关键枚举值前端中文展示，减少长表单挤压
- **智能封面** — 商品优先 / 主播优先双策略，COCO YOLO 遮挡检测
- **BGM 自动选曲** — 双库架构（内置 + 用户上传），按商品类型自动匹配
- **语气词过滤** — 三级词表（38词），可仅过滤字幕或同时裁剪视频段
- **敏感词过滤** — 用户自定义词库，包含/精确两种匹配，命中字幕句可裁掉视频段或跳过整个 clip
- **视频变速** — 0.5x ~ 3x，先烧字幕再变速
- **AI 商品素材** — 独立工作台，Gemini 商品识图 + 平台文案 + OpenAI Image 模特图/详情图
- **片段审核** — 字幕草稿覆盖、approve/skip/reprocess、单片段重导出
- **任务诊断** — 指标卡、漏斗图、事件日志、异常建议、artifacts 导出
- **实时进度** — WebSocket 推送，前端实时展示处理阶段

## 处理管线

后端流水线分四个阶段，由 Celery 编排（`backend/app/tasks/pipeline.py`）：

| 阶段 | 模块 | 输入 | 输出 | 说明 |
|------|------|------|------|------|
| Stage 1 | `visual_prescreen` | 原始 MP4 | `candidates.json` | FFmpeg 0.5fps 抽帧 + 五信号联合换衣检测（YOLO 46类 + MediaPipe + HSV × 3 + ORB 纹理），失败帧标记为缺失信号并跳过候选判断 |
| Stage 2 | `vlm_confirm` | 候选帧 | `segments.json` | VLM 二次确认（Qwen / GLM），按导出模式决定是否参与 |
| Stage 3 | `enrich_segments` | 视觉分段 | `enriched_segments.json` + `transcript.json` | ASR 转写 + LLM 文本边界识别 + 两层树信号融合 + 句边界对齐 |
| Stage 4 | `process_clips` | 分段 + 字幕 | `clips/*.mp4` | FFmpeg 烧录字幕 + BGM 混音 + 封面选择 + 敏感词/语气词裁剪，ThreadPoolExecutor 并行导出 |

导出模式说明：

| 模式 | 行为 |
|------|------|
| `smart` | VLM 确认后导出（推荐，平衡精度和成本） |
| `no_vlm` | 跳过 VLM，直接按视觉候选导出（无需 VLM API Key） |
| `all_candidates` | 导出所有候选片段（调试用，不消耗 VLM） |
| `all_scenes` | 导出所有场景（调试用，产出最多片段） |

信号融合架构（Stage 3 内部）：

- Level 0（Outfit Period）：视觉 candidates 定义换装区间，每个 visual candidate 是两个 outfit period 的边界
- Level 1（Product Discussion）：LLM text boundaries 按最大重叠度嵌套进 Level 0 区间
- 切分粒度由 `segment_granularity` 控制：`single_item` 展平到 Level 1（每件单品一个视频），`outfit` 展平到 Level 0（整套搭配一个视频）
- 无视觉信号时退化为单层（整个视频是一个 outfit period），无 LLM 信号时退化为单层（每个 visual candidate 自成一个 segment）

## ASR 选型指南

### 效果对比

同一条 20 分钟直播视频，karaoke 字幕模式实测：

| ASR Provider | 分句数 | 平均句长 | Karaoke 效果 |
|---|---|---|---|
| `dashscope` (paraformer-v2) | 267 | 4.5s | ❌ 最差 — 逐字时间戳是伪时间戳（匀速 0.272s/字），跳字完全不同步 |
| `volcengine` (BigModel 标准版) | 403 | 2.7s | ⚠️ 还行 — 真实时间戳同步好，但中文无词边界感知会拆词折行（如"雪/纺"分两行） |
| `volcengine_vc` (VC 字幕) | 796 | 1.5s | ✅ 最好 — 剪映引擎智能分句 + 真实语音节奏时间戳，句尾字自然拖长 |

结论：`volcengine_vc` 是当前最佳选择，karaoke 字幕必须选它；basic 字幕可用 `dashscope` 最便宜。DashScope 的逐字时间戳是 API 层面均匀分配的伪时间戳，不是真实语音节奏，这导致 karaoke 跳字不同步，是 API 本身的限制。

### 价格对比

| ASR Provider | 后付费 | 预付费 | 免费额度 |
|---|---|---|---|
| DashScope paraformer-v2 | ~¥0.29/小时 | — | 有 |
| 火山 BigModel 标准版 | ¥2.3/小时 | ¥2,000/千小时 | 20 小时 |
| 火山 BigModel 极速版 | ¥4.5/小时 | — | 20 小时 |
| 火山 VC 字幕 | ¥6.5/小时 | ¥2,500/500小时 | 20 小时 |

VC 贵 3 倍但效果最好，适合对字幕质量有要求的场景。

## 字幕模式

| 模式 | 格式 | 效果 | 适用场景 |
|------|------|------|----------|
| `off` | 无 | 不烧录字幕 | 纯净画面输出 |
| `basic` | SRT | 普通白字字幕 | 快速低成本 |
| `styled` | SRT + force_style | 带样式字幕（可调字号/位置） | 品牌定制 |
| `karaoke` | ASS | 逐字高亮 + 弹跳动画（0→60ms 放大130% → 60→120ms 回弹 → 稳定） | 短视频传播（推荐） |

karaoke 模式推荐搭配 `volcengine_vc` ASR。其他 ASR 的逐字时间戳不够精确，会导致跳字不同步。

字幕位置支持四种预设（top / middle / bottom）和自定义模式（拖拽调整纵向百分比）。普通字幕和高亮字幕字号可分别设置，默认普通层 60，高亮层 72。

karaoke 的 ASS 字幕通过两层实现：底层 `\kf` 逐字高亮 + 顶层逐字弹跳动画。时序方面做了多项改进：80ms 最小视觉间隙防止重叠、被截断句淡出效果、多字 word 加权分配（首字 1.3x，末字 0.7x）模拟自然语音节奏。

语气词过滤和敏感词过滤在导出阶段（Stage 4）执行：

- **语气词**（三级词表共 38 词）：`subtitle` 模式仅从字幕中删除，`video` 模式同时裁掉语气词对应的视频段（单条 FFmpeg trim+concat，无临时文件）
- **敏感词**（用户自定义词库，最多 200 词）：`contains` 包含匹配 / `exact` 精确匹配；`video_segment` 裁掉命中句的视频段，`drop_clip` 直接跳过整个 clip

## 设置参考

设置页按业务分 8 个页签。以下列出最常用的设置项。

### AI 服务

| 设置 | 说明 | 默认值 |
|------|------|--------|
| VLM 导出模式 | smart / no_vlm / all_candidates / all_scenes | `smart` |
| VLM Provider | qwen / glm | `qwen` |
| LLM 文本分析 | 用 LLM 识别换品边界，与视觉信号融合 | 关闭 |

### 转写服务

| 设置 | 说明 | 默认值 |
|------|------|--------|
| ASR Provider | dashscope / volcengine / volcengine_vc | `volcengine_vc` |

### 字幕设置

| 设置 | 说明 | 默认值 |
|------|------|--------|
| 字幕模式 | off / basic / styled / karaoke | `karaoke` |
| 字幕位置 | top / middle / bottom / custom | `bottom` |
| 普通字号 | 24-120 | `60` |
| 高亮字号（karaoke） | 24-144 | `72` |

### 敏感词过滤

| 设置 | 说明 | 默认值 |
|------|------|--------|
| 开启过滤 | 是否启用敏感词过滤 | 关闭 |
| 匹配模式 | contains（包含）/ exact（精确） | `contains` |
| 处理方式 | video_segment（裁掉命中段）/ drop_clip（跳过整个 clip） | `video_segment` |

### 切分策略

| 设置 | 说明 | 默认值 |
|------|------|--------|
| 切分粒度 | single_item（每件单品）/ outfit（整套搭配） | `single_item` |
| 句边界对齐 | 将 clip 起止对齐到 ASR 句边界，避免截断半句话 | 开启 |

### 导出与音频

| 设置 | 说明 | 默认值 |
|------|------|--------|
| 导出分辨率 | 1080p / 4k / original | `1080p` |
| 视频倍速 | 0.5x ~ 3x | `1.25x` |
| 封面策略 | content_first / person_first | `content_first` |
| BGM | 开启/关闭 + 音量调节 | 开启, 0.25 |

### 高级参数

| 设置 | 说明 | 默认值 |
|------|------|--------|
| 换衣检测融合 | any_signal / weighted_vote | `any_signal` |
| 换衣检测灵敏度 | conservative / balanced / sensitive（仅 weighted_vote 模式生效） | `balanced` |
| FFmpeg preset | veryfast / fast / medium | `fast` |
| FFmpeg CRF | 18-32（越小画质越好，文件越大） | `23` |
| LLM 边界精修 | 用 LLM 审查片段起止边界（需开启 LLM 文本分析） | 关闭 |

所有设置保存在浏览器 localStorage 中，只影响之后新上传的任务。

### AI 商品素材

AI 商品素材配置位于设置页的 AI 服务页签内，独立于剪辑 VLM / LLM：

| 设置 | 说明 | 默认值 |
|------|------|--------|
| Gemini API | 商品识图 + 平台文案（抖音/淘宝） | gemini-3-flash-preview |
| OpenAI Image | 模特图 + 详情页示例（gpt-image-2） | 2K (2048x2048) |

商品素材工作台从片段资产页新标签打开，支持 Gemini 商品识别、平台文案生成、OpenAI Image 模特图/详情图生成，每张图可独立重试。

## 项目结构

```
直播视频剪辑_GLM/
├── backend/                  # FastAPI 后端
│   ├── app/api/              # REST API 端点（上传、任务、片段、音乐库）
│   ├── app/services/         # 核心业务（换衣检测、ASR、VLM、FFmpeg、字幕、BGM）
│   ├── app/tasks/            # Celery 流水线编排 & 四阶段模块
│   ├── assets/               # ML 模型、字体、BGM 曲库、水印
│   └── tests/                # 测试文件
├── frontend/                 # React + TypeScript + Vite
│   └── src/
│       ├── components/       # UI 组件 & 9 个页面
│       ├── hooks/            # WebSocket、TanStack Query hooks
│       └── stores/           # Zustand 状态管理
├── docs/images/              # 架构图 & 流程图
├── docker-compose.yml        # 容器编排（4 services）
└── .env.example              # 环境变量模板
```

<details>
<summary>📁 查看完整目录结构</summary>

```
直播视频剪辑_GLM/
├── docker-compose.yml                                # 容器编排（4 services）
├── .env.example                                     # 环境变量模板
├── CLAUDE.md                                        # 项目真实状态文档
├── AGENTS.md                                        # AI 协作规范
├── docs/
│   └── images/
│       ├── product-flow.png                         # 产品流程图
│       └── technical-architecture.png               # 技术架构图
├── backend/
│   ├── Dockerfile                                   # Python 3.11 + FFmpeg 多阶段构建
│   ├── requirements.txt                             # Python 依赖
│   ├── assets/
│   │   ├── fonts/                                   # 字幕字体
│   │   ├── models/
│   │   │   ├── selfie_multiclass_256x256.tflite     # MediaPipe 6类像素分割
│   │   │   ├── yolov8n-fashionpedia.onnx            # YOLO 46类服装检测
│   │   │   └── yolov8n.onnx                         # COCO YOLO 80类（封面遮挡检测）
│   │   ├── bgm/
│   │   │   ├── bgm_library.json                     # 音乐库索引（mood/category 映射）
│   │   │   └── *.mp3                                # 内置背景音乐
│   │   ├── default_bgm.mp3                          # 默认 BGM fallback
│   │   └── watermark.png                            # 水印图片
│   ├── app/
│   │   ├── main.py                                  # FastAPI 入口，注册路由和异常处理
│   │   ├── config.py                                # 共享配置常量（上传目录、Provider 枚举等）
│   │   ├── api/
│   │   │   ├── health.py                            # 健康检查端点
│   │   │   ├── upload.py                            # 视频上传（流式写入 + 校验）
│   │   │   ├── tasks.py                             # 任务路由（CRUD + WebSocket + 诊断 + 审核 + 重试）
│   │   │   ├── task_helpers.py                      # 任务摘要 / 诊断 / 复核 payload 组装工具（显式接收上传目录）
│   │   │   ├── clips.py                             # 片段列表 / 下载 / 批量下载 / 缩略图
│   │   │   ├── settings.py                          # 设置模型与校验 + 敏感字段分离
│   │   │   ├── music.py                             # 音乐库上传 / 标签编辑 / 删除
│   │   │   ├── assets.py                            # 跨任务片段资产浏览与筛选
│   │   │   ├── commerce.py                          # AI 商品素材（识图 / 文案 / 生图 / 批量）
│   │   │   ├── system.py                            # 系统资源监控（cgroup + Redis ping）
│   │   │   ├── error_handler.py                     # 全局异常处理（ASR / 通用 HTTP 错误）
│   │   │   └── validation.py                        # UUID / 安全路径正则校验
│   │   ├── services/
│   │   │   ├── clothing_change_detector.py          # 换衣检测（五信号联合 + 多信号独立 EMA）
│   │   │   ├── clothing_segmenter.py                # MediaPipe 像素分割 + YOLO 品类检测
│   │   │   ├── frame_extractor.py                   # FFmpeg 抽帧（候选场景区域内）
│   │   │   ├── scene_detector.py                    # PySceneDetect 场景分割
│   │   │   ├── vlm_confirmor.py                     # VLM 二次确认（Qwen / GLM）
│   │   │   ├── vlm_client.py                        # Provider 感知的 VLM API 客户端
│   │   │   ├── vlm_parser.py                        # VLM 响应解析（多层 JSON 提取 + 容错）
│   │   │   ├── dashscope_asr_client.py              # DashScope paraformer-v2 ASR
│   │   │   ├── volcengine_asr_client.py             # 火山 BigModel ASR（标准版 + 极速版）
│   │   │   ├── volcengine_vc_client.py              # 火山 VC 字幕 ASR（剪映引擎分句）
│   │   │   ├── asr_errors.py                        # ASR 异常层级（Auth / Timeout / API / NoSpeech）
│   │   │   ├── transcript_merger.py                 # 分段 ASR 结果合并 + 偏移校正
│   │   │   ├── srt_generator.py                     # SRT / ASS 字幕生成（含 karaoke 逐字高亮）
│   │   │   ├── ffmpeg_builder.py                    # FFmpeg 命令构建（裁切 / 烧录 / 变速 / BGM）
│   │   │   ├── filler_filter.py                     # 语气词过滤（三级词表 + 视频裁剪）
│   │   │   ├── sensitive_filter.py                  # 敏感词过滤（用户自定义词库）
│   │   │   ├── subtitle_overrides.py                # 字幕覆盖校验（行数 / 长度 / ASS 注入过滤）
│   │   │   ├── cover_selector.py                    # 智能封面（双策略评分 + 遮挡检测）
│   │   │   ├── bgm_selector.py                      # BGM 自动选曲（双库 + 商品类型匹配）
│   │   │   ├── product_matcher.py                   # 商品名匹配（VLM > ASR > 描述 fallback）
│   │   │   ├── segment_validator.py                 # 分段合法性校验（时长 + 去重）
│   │   │   ├── text_segment_analyzer.py             # LLM 文本边界分析
│   │   │   ├── segment_fusion.py                    # 两层树信号融合（Outfit + Product）
│   │   │   ├── boundary_snapper.py                  # 句边界对齐（ASR 句子边界 snap）
│   │   │   ├── boundary_refiner.py                  # LLM 边界精修（开头完整性 + 结尾自然）
│   │   │   ├── resource_detector.py                 # cgroup v2 容器资源检测（CPU / 内存）
│   │   │   ├── gemini_vision_client.py              # Gemini 封面识图 + 平台文案生成
│   │   │   ├── openai_image_client.py               # OpenAI Image 模特图 / 详情图生成
│   │   │   ├── list_index.py                        # SQLite 列表索引缓存（WAL + 自动重建）
│   │   │   ├── memory_cache.py                      # API 进程内 mtime 指纹缓存
│   │   │   ├── state_machine.py                     # 任务状态机（状态转换规则）
│   │   │   ├── cleanup.py                           # 临时文件 / 抽帧目录清理
│   │   │   └── validator.py                         # 视频文件校验（ffprobe 格式/编码/音频流）
│   │   ├── utils/
│   │   │   └── json_io.py                           # 统一 JSON 读写（原子写入 + 临时文件）
│   │   └── tasks/
│   │       ├── pipeline.py                          # 薄编排器（~310 行）+ Celery task 定义
│   │       ├── shared.py                            # 跨 stage 共享工具（路径 / JSON / 日志）
│   │       └── stages/
│   │           ├── visual_prescreen.py              # Stage 1: 抽帧 + 换衣检测
│   │           ├── vlm_confirm.py                   # Stage 2: VLM 二次确认
│   │           ├── enrich_segments.py               # Stage 3: ASR + LLM + 融合 + 边界对齐
│   │           └── process_clips.py                 # Stage 4: 字幕 + FFmpeg + BGM + 封面
│   └── tests/                                       # 测试文件
└── frontend/
    ├── Dockerfile                                   # Node 20 构建 + Nginx 运行
    ├── nginx.conf                                   # Nginx（20G 上传 + WebSocket 代理）
    ├── package.json
    └── src/
        ├── main.tsx                                 # React 入口
        ├── App.tsx                                  # 根组件
        ├── router.tsx                               # react-router-dom 路由配置
        ├── components/
        │   ├── AdminDashboard.tsx                   # 主应用壳（左侧导航 + 右侧内容区）
        │   ├── UploadZone.tsx                       # 拖拽上传区域
        │   ├── ProgressBar.tsx                      # 管线进度条（8 阶段）
        │   ├── ResultGrid.tsx                       # 片段结果网格
        │   ├── VideoPreview.tsx                     # 视频预览弹窗
        │   ├── ErrorCard.tsx                        # 错误卡片
        │   ├── ConfirmDialog.tsx                    # 通用确认弹窗
        │   ├── ToastViewport.tsx                    # Toast 通知容器
        │   ├── ui/
        │   │   └── dialog.tsx                       # 自定义 Dialog 组件
        │   └── admin/
        │       ├── api.ts                           # API 调用封装（fetchJson / fetchText）
        │       ├── types.ts                         # 全局类型定义
        │       ├── context.ts                       # Admin 上下文（项目切换 / 共享状态）
        │       ├── format.ts                        # 格式化工具（状态分类 / 时长 / 日期）
        │       ├── constants.tsx                    # 常量（状态映射 / 图标 / 枚举中文标签）
        │       ├── shared.tsx                       # 共享 UI 组件（DrawerShell / FilterToolbar / Card）
        │       ├── settings/
        │       │   ├── labels.ts                       # 设置项中文标签映射
        │       │   ├── SettingsControls.tsx             # 通用表单控件（Select / Slider / Switch）
        │       │   ├── SettingsSections.tsx             # 设置分块渲染（AI / 转写 / 字幕 / 导出等）
        │       │   └── types.ts                         # 设置页内部类型定义
        │       └── pages/
        │           ├── ProjectManagementPage.tsx    # 项目总览（任务列表 + 右侧详情抽屉）
        │           ├── CreateProjectPage.tsx        # 新建项目 + 上传
        │           ├── QueuePage.tsx                # 任务队列（流式列表 + 进度 + 日志）
        │           ├── ReviewPage.tsx               # 剪辑复核（卡片 + 字幕编辑 + 重导出）
        │           ├── AssetsPage.tsx               # 片段资产（按项目分组 + AI 素材状态）
        │           ├── CommerceWorkbenchPage.tsx    # AI 商品素材工作台（识图 / 文案 / 生图）
        │           ├── MusicPage.tsx                # 音乐库管理（上传 / 播放 / 标签编辑）
        │           ├── DiagnosticsPage.tsx          # 任务诊断（指标卡 + 漏斗图 + 事件日志）
        │           └── SettingsPage.tsx             # 设置页容器（状态 / 保存 / 页签）
        ├── hooks/
        │   ├── useAdminQueries.ts                   # TanStack Query hooks（15+ 查询）
        │   ├── useWebSocket.ts                      # WebSocket 实时进度推送
        │   └── useDebouncedValue.ts                 # 搜索输入防抖 hook
        ├── stores/
        │   ├── settingsStore.ts                     # 设置状态（64+ 字段 + localStorage 持久化）
        │   ├── taskStore.ts                         # 任务列表状态
        │   ├── toastStore.ts                        # Toast 通知状态
        │   └── confirmStore.ts                      # 确认弹窗状态
        └── lib/
            └── utils.ts                             # cn() Tailwind 类名合并工具
```

</details>

## 系统架构

![技术架构图](docs/images/technical-architecture.png)

前端为 React Router 单页应用，`AdminDashboard.tsx` 是 layout shell，页面组件拆分到 `admin/pages/` 目录（共 9 个页面：项目管理、创建任务、任务队列、片段审核、素材资产、AI 商品素材工作台、音乐库、任务诊断、设置）。桌面端左侧固定导航栏，右侧内容区独立滚动。详情信息优先用右侧抽屉承载，AI 商品素材采用独立工作台页面。

后端采用 FastAPI + Celery + Redis 架构。API 层处理同步请求（上传、列表、审核、设置），Celery Worker 处理异步视频管线（四阶段串行，stage 间通过任务目录文件通信，不依赖 Celery chain 返回值）。任务数据以文件系统为主存储（`uploads/<task_id>/` 下多个 JSON），SQLite 只做列表索引缓存。

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | React 19 + TypeScript + Vite + Tailwind CSS + Zustand + TanStack Query |
| 后端 | FastAPI + Celery + Redis |
| 检测 | YOLOv8 (ONNX) + MediaPipe (TFLite) + HSV + ORB |
| VLM | Qwen / GLM (OpenAI 兼容 API) |
| ASR | 火山 VC / 火山大模型 / 阿里 DashScope |
| 视频处理 | FFmpeg |
| 部署 | Docker Compose (4 services) |

## 配置说明

编辑 `.env` 文件，关键配置：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `VLM_API_KEY` | VLM API Key（Qwen / GLM 通用） | 空 |
| `VOLCENGINE_ASR_API_KEY` | 火山引擎 ASR API Key（BigModel / VC 共用） | 空 |
| `TOS_AK` / `TOS_SK` | 火山 TOS 凭据（火山引擎 ASR 需要上传音频到 TOS） | 空 |
| `TOS_BUCKET` / `TOS_REGION` / `TOS_ENDPOINT` | 火山 TOS 存储桶配置 | 空 |
| `LLM_API_KEY` | LLM API Key（文本分析 / 边界精修） | 空 |
| `DOCKER_REGISTRY` | Docker 镜像加速（国内可选） | 空 |

ASR 的 Provider 选择和 API Key 在前端设置页面配置。VLM 和 LLM 的 API Base / Model 也可在前端设置页自定义，支持 OpenAI 兼容的第三方代理。完整配置参考 [.env.example](.env.example)。

## 服务说明

| 服务 | 端口 | 说明 | 内存 |
|------|------|------|------|
| frontend | 5537 | React SPA + Nginx | 默认 |
| api | 5538 | FastAPI + Uvicorn | 2G |
| worker | — | Celery 异步任务 | 4G |
| redis | 6379 | 消息队列 | 默认 |

Docker Volumes：

- `./uploads:/app/uploads` — 任务数据持久化（视频、字幕、封面、AI 商品素材）
- `redis_data` — Redis 持久化
- `model_cache` — ML 模型缓存

内置模型文件（Docker 构建时打包进镜像，无需运行时下载）：

- `selfie_multiclass_256x256.tflite` — MediaPipe 6类像素分割（16MB），用于换衣检测和封面选择
- `yolov8n-fashionpedia.onnx` — YOLO 46类服装检测（12MB），用于换衣检测和封面评分
- `yolov8n.onnx` — COCO YOLOv8n 80类（12MB），仅用于封面遮挡检测

BGM 自动选曲基于双库架构：内置曲库（`backend/assets/bgm/`）+ 用户上传曲库（`uploads/bgm_library/`）。选曲时从 segment 的商品类型推断 mood，在曲库中匹配，用户曲目优先选，跨 clip 去重避免重复。曲库为空时 fallback 到 `default_bgm.mp3`。前端 `/music` 页面支持拖拽上传 MP3、编辑标签（mood / categories / tempo / energy）、播放预览和删除。

Worker 启动参数（docker-compose.yml 已配置）：

- `--concurrency=1` — 单进程，为 FFmpeg 子进程留资源
- `--max-tasks-per-child=100` — 处理 100 个任务后回收进程，防止内存泄漏
- `--max-memory-per-child=3000000` — 3GB 内存上限后回收（4GB 容器的 75%）
- `--prefetch-multiplier=1` — 只拉取 1 个任务，避免长耗时任务堆积
- `-Ofair` — 公平调度

## API 接口一览

| 模块 | 方法 | 路径 | 说明 |
|------|------|------|------|
| **健康检查** | GET | `/health` | 服务健康状态 |
| **上传** | POST | `/api/upload` | 上传视频 + 设置 |
| **任务管理** | GET | `/api/tasks` | 分页任务列表 |
| | GET | `/api/tasks/{id}` | 任务状态 |
| | GET | `/api/tasks/{id}/summary` | 任务摘要 |
| | DELETE | `/api/tasks/{id}` | 删除任务 |
| | POST | `/api/tasks/{id}/retry` | 重试失败任务 |
| | WS | `/ws/tasks/{id}` | 实时进度推送 |
| **诊断** | GET | `/api/tasks/{id}/diagnostics` | 诊断数据 |
| | GET | `/api/tasks/{id}/events` | 事件日志 |
| | GET | `/api/tasks/{id}/diagnostics/export` | 导出诊断报告 |
| | GET | `/api/tasks/{id}/artifacts.zip` | 下载调试包 |
| **审核** | GET | `/api/tasks/{id}/review` | 复核状态 |
| | PATCH | `/api/tasks/{id}/review/segments/{sid}` | 保存审核结果 |
| | POST | `/api/tasks/{id}/clips/{sid}/reprocess` | 单片段重导出 |
| **片段** | GET | `/api/tasks/{id}/clips` | 片段列表 |
| | GET | `/api/clips/{id}/{name}/download` | 下载片段 |
| | GET | `/api/clips/{id}/{name}/preview` | 预览片段（inline） |
| | GET | `/api/clips/{id}/{name}/thumbnail` | 缩略图 |
| | GET | `/api/clips/batch` | 批量 ZIP 下载 |
| **资产** | GET | `/api/assets/clips` | 跨任务片段资产 |
| **音乐库** | GET | `/api/music/library` | 曲目列表 |
| | POST | `/api/music/upload` | 上传 MP3 |
| | PATCH | `/api/music/{id}` | 编辑标签 |
| | DELETE | `/api/music/{id}` | 删除曲目 |
| | GET | `/api/music/{id}/audio` | 音频文件 |
| **AI 商品素材** | GET | `/api/commerce/clips/{tid}/{sid}` | 工作台数据 |
| | POST | `/api/commerce/clips/{tid}/{sid}/analyze` | Gemini 商品识图 |
| | POST | `/api/commerce/clips/{tid}/{sid}/copywriting` | 文案生成 |
| | POST | `/api/commerce/clips/{tid}/{sid}/images` | OpenAI 生图 |
| | POST | `/api/commerce/clips/{tid}/{sid}/images/{key}` | 单张重试 |
| | POST | `/api/commerce/batch` | 批量提交 |
| **设置** | POST | `/api/settings/validate` | 校验设置 |
| **系统** | GET | `/api/system/resources` | CPU / 内存 / Redis 状态 |

## 性能基准

测试环境：MacBook Air M4 32GB，Docker Desktop 分配 8 核 CPU + 8GB 内存，测试视频 20 分钟 1080x1920 直播录像。

### 完整链路（推荐配置）

配置：smart 模式 + VLM (Qwen) + volcengine_vc ASR + karaoke 字幕 + LLM 文本分析 + BGM

| 阶段 | 耗时 | 说明 |
|------|------|------|
| Stage 1: 抽帧 | 46s | FFmpeg 0.5fps 抽帧 |
| Stage 1: 换衣检测 | 165s | 五信号联合检测，3 个并行 worker |
| Stage 2: VLM 确认 | 72s | Qwen 确认 15 个候选 |
| Stage 3: ASR 转写 | 23s | 火山 VC 字幕（剪映引擎） |
| Stage 3: LLM 分析 | 19s | 文本边界识别 + 信号融合 |
| Stage 4: 导出剪辑 | 285s | 17 个 clips，3 个并行 worker |
| **总计** | **~10 分钟** | 20 分钟视频 → 17 个短视频片段 |

Clip 导出明细（Stage 4 内部）：

| 指标 | 值 |
|------|-----|
| 片段数 | 17 |
| 封面选择均耗时 | 11.7s / clip |
| FFmpeg 导出均耗时 | 36.0s / clip |
| 单 clip 总均耗时 | 47.7s / clip |

即：**20 分钟直播视频，约 10 分钟处理完成，产出 17 个可独立传播的商品讲解短视频**。

### 资源自适应

Worker 并行数由 `resource_detector.py` 根据 cgroup v2 资源自适应计算，无需手动配置：

- 计算公式：`clip_workers = min(cpu_cores, (mem - 2.0GB) / 0.6GB, 4)`
- 4GB 容器 → 2-3 个 clip workers
- 8GB 容器 → 4 个 clip workers（上限）

并行使用 `ThreadPoolExecutor`（非 ProcessPoolExecutor），因为 Celery prefork worker 是 daemon 进程不允许再 fork。每个线程启动独立 FFmpeg 子进程，GIL 在 `subprocess.run()` 期间释放。

### FFmpeg 优化

单实例优化参数：

- `-x264opts rc-lookahead=5:bframes=1:ref=1` — 降低编码缓冲区，每实例省约 100MB
- `-threads 4 -filter_threads 2` — 限制线程数，避免内存膨胀
- `-movflags +faststart` — MP4 元数据前置，支持流式播放

### 封面选择

从 clip 中采样最多 30 帧评分，`content_first` 优先选突出商品/服装的帧，`person_first` 优先选突出主播人脸的帧。评分综合考虑清晰度（Laplacian variance）、对比度、亮度、语义得分和遮挡惩罚（COCO YOLOv8n 检测手机/笔记本遮挡时自动降权）。导出阶段优先复用 Stage 1 的预抽帧，不足时 FFmpeg 补采样。

## 用户文档

面向非技术用户的完整使用指南，按操作流程组织：

| 文档 | 说明 |
|------|------|
| [快速开始](docs/user-guide/getting-started.md) | 5 分钟上手：上传视频 → 选预设 → 拿到成品 |
| [上传视频](docs/user-guide/uploading-videos.md) | 格式要求、四种预设对比、上传流程 |
| [片段审核](docs/user-guide/reviewing-clips.md) | 审核/通过/跳过/重导出操作流程 |
| [字幕编辑](docs/user-guide/editing-subtitles.md) | 字幕草稿修改、时间调整、重导出 |
| [设置详解](docs/user-guide/settings-explained.md) | 8 个设置页签的白话版逐项说明 |
| [AI 商品素材](docs/user-guide/commerce-workbench.md) | Gemini 识图 + OpenAI 生图工作台 |
| [音乐库](docs/user-guide/music-library.md) | 上传曲库、标签编辑、BGM 自动选曲 |
| [任务诊断](docs/user-guide/diagnostics.md) | 诊断仪表盘各指标含义 |
| [常见问题](docs/faq.md) | 20 个高频问题速查 |
| [排障指南](docs/troubleshooting.md) | 按症状排查：上传失败/处理卡住/字幕异常 |
| [费用估算](docs/cost-estimation.md) | 不同配置下每条视频的成本 |
| [术语表](docs/glossary.md) | 技术名词的大白话解释 |

文档入口：[`docs/user-guide/index.md`](docs/user-guide/index.md)

## License

MIT
