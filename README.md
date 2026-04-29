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
- **敏感词过滤** — 用户自定义词库，命中字幕句可裁掉视频段或跳过整个 clip
- **视频变速** — 0.5x ~ 3x，先烧字幕再变速
- **实时进度** — WebSocket 推送，前端实时展示处理阶段

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
├── docker-compose.yml
├── .env.example
├── CLAUDE.md
├── AGENTS.md
├── docs/
│   └── images/
│       ├── product-flow.png
│       └── technical-architecture.png
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── assets/
│   │   ├── fonts/
│   │   ├── models/
│   │   │   ├── selfie_multiclass_256x256.tflite   # MediaPipe 6类像素分割
│   │   │   ├── yolov8n-fashionpedia.onnx           # YOLO 46类服装检测
│   │   │   └── yolov8n.onnx                        # COCO YOLO 80类（封面遮挡检测）
│   │   ├── bgm/
│   │   │   ├── bgm_library.json                    # 音乐库索引
│   │   │   └── *.mp3
│   │   ├── default_bgm.mp3
│   │   └── watermark.png
│   ├── app/
│   │   ├── main.py                                 # FastAPI 入口
│   │   ├── config.py                               # 共享配置常量
│   │   ├── api/
│   │   │   ├── health.py
│   │   │   ├── upload.py
│   │   │   ├── tasks.py
│   │   │   ├── clips.py
│   │   │   ├── settings.py
│   │   │   ├── music.py
│   │   │   ├── assets.py
│   │   │   ├── commerce.py
│   │   │   └── system.py
│   │   ├── services/
│   │   │   ├── clothing_change_detector.py          # 换衣检测（五信号联合）
│   │   │   ├── clothing_segmenter.py                # 服装分段
│   │   │   ├── frame_extractor.py                   # FFmpeg 抽帧
│   │   │   ├── vlm_confirmor.py                     # VLM 二次确认
│   │   │   ├── vlm_client.py                        # VLM API 客户端
│   │   │   ├── dashscope_asr_client.py              # DashScope ASR
│   │   │   ├── volcengine_asr_client.py             # 火山 BigModel ASR
│   │   │   ├── volcengine_vc_client.py              # 火山 VC 字幕 ASR
│   │   │   ├── srt_generator.py                     # SRT/ASS 字幕生成
│   │   │   ├── ffmpeg_builder.py                    # FFmpeg 命令构建
│   │   │   ├── filler_filter.py                     # 语气词过滤
│   │   │   ├── cover_selector.py                    # 智能封面选择
│   │   │   ├── bgm_selector.py                      # BGM 自动选曲
│   │   │   ├── resource_detector.py                 # 容器资源检测
│   │   │   ├── text_segment_analyzer.py             # LLM 文本边界分析
│   │   │   ├── segment_fusion.py                    # 两层树信号融合
│   │   │   ├── boundary_snapper.py                  # 句边界对齐
│   │   │   └── boundary_refiner.py                  # LLM 边界精修
│   │   ├── utils/
│   │   │   └── json_io.py                           # 统一 JSON 读写工具
│   │   └── tasks/
│   │       ├── pipeline.py                          # 薄编排器（~310 行）
│   │       ├── shared.py                            # 跨 stage 共享工具
│   │       └── stages/
│   │           ├── visual_prescreen.py
│   │           ├── vlm_confirm.py
│   │           ├── enrich_segments.py
│   │           └── process_clips.py
│   └── tests/
└── frontend/
    ├── Dockerfile
    ├── nginx.conf
    ├── package.json
    └── src/
        ├── App.tsx
        ├── router.tsx
        ├── components/
        │   ├── AdminDashboard.tsx
        │   ├── admin/
        │   │   ├── api.ts
        │   │   ├── types.ts
        │   │   ├── shared.tsx
        │   │   └── pages/
        │   │       ├── ProjectManagementPage.tsx
        │   │       ├── CreateProjectPage.tsx
        │   │       ├── QueuePage.tsx
        │   │       ├── ReviewPage.tsx
        │   │       ├── AssetsPage.tsx
        │   │       ├── CommerceWorkbenchPage.tsx
        │   │       ├── MusicPage.tsx
        │   │       ├── DiagnosticsPage.tsx
        │   │       └── SettingsPage.tsx
        │   ├── UploadZone.tsx
        │   ├── ProgressBar.tsx
        │   └── VideoPreview.tsx
        ├── hooks/
        │   ├── useAdminQueries.ts
        │   └── useWebSocket.ts
        ├── stores/
        │   ├── settingsStore.ts
        │   ├── taskStore.ts
        │   └── toastStore.ts
        └── lib/
            └── utils.ts
```

</details>

## 系统架构

![技术架构图](docs/images/technical-architecture.png)

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
| `VLM_API_KEY` | VLM API Key | 空 |
| `VOLCENGINE_ASR_API_KEY` | 火山引擎 ASR API Key | 空 |
| `TOS_AK` / `TOS_SK` | 火山 TOS 凭据 | 空 |
| `LLM_API_KEY` | LLM API Key | 空 |
| `DOCKER_REGISTRY` | Docker 镜像加速（国内可选） | 空 |

ASR 的 Provider 选择和 API Key 在前端设置页面配置。完整配置参考 [.env.example](.env.example)。

## 服务说明

| 服务 | 端口 | 说明 | 内存 |
|------|------|------|------|
| frontend | 5537 | React SPA + Nginx | 默认 |
| api | 5538 | FastAPI + Uvicorn | 2G |
| worker | — | Celery 异步任务 | 4G |
| redis | 6379 | 消息队列 | 默认 |

## 常见问题

**ASR 怎么选？** karaoke 字幕必须选 `volcengine_vc`；basic 字幕 `dashscope` 最便宜。

**上传大文件失败？** nginx 已默认配置 `client_max_body_size 20G`，如用反向代理需同步调整。

**查看日志：**

```bash
docker compose logs -f worker   # 任务处理日志
docker compose logs -f api      # API 日志
```

## License

MIT
