# 直播视频 AI 智能剪辑

一键将直播录像自动拆分为商品讲解短视频片段。上传 MP4 → AI 自动分析 → 预览下载。

## 架构

```
上传视频 → [视觉预筛] → [VLM 确认] → [语音转写+商品匹配] → [FFmpeg 剪辑输出]
  │           │              │                │                      │
  │      FashionSigLIP   Qwen-VL-Plus     FunASR               FFmpeg
  │      ONNX Runtime    阿里云 API       Docker 容器           硬编码
  │           │              │                │                      │
  └───────────┴──────────────┴────────────────┴──────────────────────┘
                              三级管线架构
```

## 功能特性

- **上传** — 支持 20GB 以内 MP4 文件上传，自动校验编码格式
- **视觉预筛** — FashionSigLIP (ONNX) 提取帧特征，自适应相似度分析筛选候选片段
- **VLM 确认** — Qwen-VL-Plus 多模态大模型二次确认商品讲解场景
- **语音转写** — FunASR 中文语音识别，30 分钟分块处理避免内存溢出
- **商品匹配** — 自动关联商品名称与讲解片段
- **视频输出** — FFmpeg 硬编码剪辑，自动添加字幕、水印、背景音乐
- **实时进度** — WebSocket 推送处理进度，前端实时展示

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | React + TypeScript + Vite + Tailwind CSS |
| 后端 | FastAPI + Celery + Redis |
| 视觉模型 | FashionSigLIP (ONNX Runtime CPU) |
| 场景检测 | PySceneDetect + OpenCV |
| 多模态 VLM | Qwen-VL-Plus (阿里云 DashScope API) |
| 语音识别 | FunASR (Docker 容器部署) |
| 视频处理 | FFmpeg (系统级安装) |

## 快速开始

### 前置条件

- Docker + Docker Compose
- 16GB 内存 + 8 核 CPU
- 无需 GPU（ONNX Runtime CPU 模式）

### 部署步骤

```bash
# 1. 克隆项目
git clone <repo-url>
cd 直播视频剪辑_GLM

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，填入你的 VLM API Key
# VLM_API_KEY=sk-xxxxxxxxxxxxxxxx

# 3. 一键启动
docker compose up -d

# 4. 访问应用
# 前端：http://localhost
# 后端 API：http://localhost:8000/docs
```

### 获取 VLM API Key

1. 访问 [阿里云 DashScope 控制台](https://dashscope.console.aliyun.com/)
2. 开通「通义千问 VL」服务
3. 创建 API Key 并填入 `.env` 文件

## 配置说明

编辑 `.env` 文件进行配置：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `VLM_API_KEY` | Qwen-VL-Plus API Key（必填） | — |
| `VLM_BASE_URL` | VLM API 地址 | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `VLM_MODEL` | VLM 模型名称 | `qwen-vl-plus` |
| `FUNASR_URL` | FunASR 服务地址 | `http://funasr:10095` |
| `REDIS_URL` | Redis 连接地址 | `redis://redis:6379/0` |
| `MAX_UPLOAD_SIZE_GB` | 最大上传文件大小 (GB) | `20` |

## 常见问题

### Q: 启动后 FunASR 服务报错？

FunASR 容器首次启动需要加载模型，大约需要 1-2 分钟。等待容器健康检查通过后即可正常使用。

### Q: 上传大文件失败？

确保 nginx 配置了 `client_max_body_size 20G`（已默认配置）。如果使用反向代理，也需要调整代理层的上传限制。

### Q: Worker 内存不足？

Worker 默认内存限制 4GB。处理超长视频时可在 `docker-compose.yml` 中调大 `deploy.resources.limits.memory`。

### Q: 如何查看处理日志？

```bash
# 查看所有服务日志
docker compose logs -f

# 只看 worker 日志
docker compose logs -f worker
```

### Q: 支持哪些视频格式？

目前仅支持 MP4 (H.264 编码)，文件需包含音频流。

## 项目结构

```
直播视频剪辑_GLM/
├── docker-compose.yml          # Docker 编排（5 个服务）
├── .env.example                # 环境变量模板
├── backend/
│   ├── Dockerfile              # Python 3.11 + FFmpeg + ONNX Runtime
│   ├── requirements.txt        # Python 依赖
│   ├── assets/                 # 静态资源（背景音乐、水印）
│   ├── app/
│   │   ├── main.py             # FastAPI 入口
│   │   ├── api/                # API 路由
│   │   │   ├── health.py       # 健康检查
│   │   │   ├── upload.py       # 视频上传
│   │   │   ├── tasks.py        # 任务状态 + WebSocket
│   │   │   ├── clips.py        # 片段列表/下载
│   │   │   └── settings.py     # API Key 验证
│   │   ├── services/           # 业务逻辑
│   │   │   ├── scene_detector.py       # 场景检测
│   │   │   ├── frame_extractor.py      # 帧提取
│   │   │   ├── siglip_encoder.py       # FashionSigLIP 编码
│   │   │   ├── adaptive_similarity.py  # 自适应相似度
│   │   │   ├── vlm_client.py           # VLM API 客户端
│   │   │   ├── vlm_confirmor.py        # VLM 二次确认
│   │   │   ├── funasr_client.py        # FunASR 语音转写
│   │   │   ├── product_matcher.py      # 商品名称匹配
│   │   │   ├── ffmpeg_builder.py       # FFmpeg 剪辑
│   │   │   ├── srt_generator.py        # 字幕生成
│   │   │   └── ...
│   │   └── tasks/
│   │       └── pipeline.py     # Celery 三级管线任务
│   └── tests/                  # 测试
└── frontend/
    ├── Dockerfile              # Node 20 构建 + Nginx
    ├── nginx.conf              # Nginx 配置（20G 上传 + WebSocket）
    ├── src/
    │   ├── App.tsx
    │   ├── components/         # UI 组件
    │   ├── hooks/              # 自定义 Hooks
    │   ├── stores/             # 状态管理
    │   └── lib/                # 工具函数
    └── package.json
```

## 服务说明

| 服务 | 端口 | 说明 |
|------|------|------|
| frontend | 80 | Nginx 静态文件 + 反向代理 |
| api | 8000 | FastAPI 后端 API |
| worker | — | Celery 异步任务处理 |
| redis | 6379 | 消息队列 + 任务结果存储 |
| funasr | 10095 | FunASR 语音识别服务 |

## License

MIT
