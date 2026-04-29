# 直播视频 AI 智能剪辑

一键将直播录像自动拆分为商品讲解短视频片段，支持烧录字幕、karaoke 逐字高亮、语气词过滤、智能封面选择、BGM 自动选曲和视频变速。上传 MP4，AI 自动识别换衣节点、转写语音、匹配商品名、导出短视频。

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
- **字幕烧录** — 四种模式：off / basic / styled / karaoke（逐字高亮 + 弹跳动画）
- **智能封面** — 商品优先 / 主播优先双策略，COCO YOLO 遮挡检测
- **BGM 自动选曲** — 双库架构（内置 + 用户上传），按商品类型自动匹配
- **语气词过滤** — 三级词表（38词），可仅过滤字幕或同时裁剪视频段
- **视频变速** — 0.5x ~ 3x，先烧字幕再变速
- **实时进度** — WebSocket 推送，前端实时展示处理阶段

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
