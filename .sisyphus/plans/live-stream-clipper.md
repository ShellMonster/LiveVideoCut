# 直播视频AI切片工具 (Live Stream Clipper) — 三级混合管线

## TL;DR

> **Quick Summary**: 构建面向服装电商直播的AI自动切片工具。采用**视觉驱动+文字补充**的三级混合管线：PySceneDetect场景筛选→FashionSigLIP服装视觉预筛→Qwen-VL-Plus多模态确认商品切换→FunASR语音转文字补充商品名，按商品切割并自动加字幕+BGM+水印。
> 
> **Deliverables**:
> - React单页Web应用（上传→AI分析→预览→下载）
> - Python FastAPI后端（三级混合Pipeline + 异步任务队列 + WebSocket实时进度）
> - PySceneDetect + FashionSigLIP（ONNX Runtime）本地视觉分析 + Qwen-VL-Plus多模态API + FunASR语音转写
> - Docker Compose一键部署（ONNX镜像~500MB）
> 
> **Estimated Effort**: Large
> **Parallel Execution**: YES - 4 waves
> **Critical Path**: T1 → T2 → T5 → T6 → T7 → T8 → T9 → T10 → T11

---

## Context

### Original Request
开发一个直播视频剪辑工具，主要用于公司服装电商直播后，AI自动按商品SKU剪成单品讲解片段，全自动加字幕+BGM+水印，输出可直接发布的短视频文件。

### Interview Summary
**Key Discussions**:
- 品类定位：服装/服饰（需识别换装、上身效果、搭配展示）
- 直播规模：3-6小时，20-50个SKU
- 产品形态：Web单页应用，首期不做登录注册/历史记录/推送
- 用户否决了纯文字方案，要求加入视觉识别能力
- 用户确认三级混合管线：PySceneDetect→FashionSigLIP预筛→VLM确认→ASR补充
- 普通CLIP ViT-B/32对服装变化检测Top-1仅41%，改用Marqo-FashionSigLIP（+57%准确率）

**Research Findings**:
- 行业头部工具（极睿iCut）使用"视觉-语义双模态AI"，纯文字方案不够
- 普通CLIP ViT-B/32对服装检测能力差（Top-1 41%），Marqo-FashionSigLIP专为时尚领域优化
- PySceneDetect ContentDetector先快速筛选场景变化，候选区域再1fps精抽帧
- FashionSigLIP滑动窗口5帧 + 自适应阈值0.78-0.82，比固定0.85更适合服装场景
- 60秒冷却期防止换装过渡期误报
- Qwen-VL-Plus实际定价¥0.8/百万token（非¥0.16），200对图片约¥3仍便宜
- Qwen-VL-Plus不支持原生JSON mode，需Prompt工程+解析容错
- FunASR处理>30分钟音频会OOM+内存泄漏，需独立进程分片（30分钟+3-5秒重叠）
- FFmpeg `-c copy` 精度不够（±2-5秒），必须重编码
- MoviePy比FFmpeg慢6-22倍，所有视频处理用FFmpeg单命令
- ONNX Runtime替代PyTorch，Docker镜像从8GB→500MB

### Metis Review
**Identified Gaps** (addressed):
- `-c copy` 精度问题：改用 `libx264 -preset fast -crf 23` 重编码
- MoviePy性能问题：完全去除，用FFmpeg `filter_complex` 单命令处理
- FunASR内存泄漏：音频按30分钟分片+3-5秒重叠+独立进程处理每个chunk+偏移量合并
- 硬件需求：默认16GB RAM + 8核CPU + 无GPU（ONNX Runtime CPU模式）
- 上传大小限制：配置Nginx `client_max_body_size 20G`
- Qwen-VL-Plus无原生JSON mode：Prompt工程输出JSON + 正则提取 + 解析容错
- 边界条件：最短60秒、最长600秒、同名5分钟去重
- CLIP服装检测差：换用Marqo-FashionSigLIP（ONNX Runtime，Top-1提升57%）
- 固定阈值不适用：自适应阈值0.78-0.82 + 滑动窗口5帧
- 直接每5秒抽帧漏检：PySceneDetect先筛选→候选区域1fps精抽帧
- 无冷却期误报：60秒冷却期防止过渡期频繁触发
- 冲突解决规则：视觉为准（VLM>FashionSigLIP>ASR）

---

## Work Objectives

### Core Objective
构建一个可Docker一键部署的Web应用，实现**视觉驱动**的直播录像AI自动切片，通过PySceneDetect→FashionSigLIP→VLM→ASR三级管线准确识别每个商品SKU的讲解段落。

### Pipeline Architecture (三级混合管线)

```
┌──────────────────────────────────────────────────────────┐
│  第一级：PySceneDetect场景筛选 + FashionSigLIP视觉预筛      │
│  （本地，免费，ONNX Runtime）                               │
│                                                          │
│  直播MP4                                                  │
│  → PySceneDetect ContentDetector(threshold=27.0)         │
│    快速检测场景变化（本地，秒级）                              │
│  → 候选场景区域内 1fps 抽帧（非全局每5秒）                    │
│  → FashionSigLIP编码每帧 → 768维向量                       │
│  → 滑动窗口5帧 → 自适应阈值0.78-0.82                       │
│  → 候选切换点 + 60秒冷却期（防过渡期误报）                    │
│  → 约50-100个候选切换段                                    │
│  耗时：~3-5分钟    成本：¥0（本地CPU）                      │
└────────────────────┬─────────────────────────────────────┘
                     ↓ 候选切换点
┌──────────────────────────────────────────────────────────┐
│  第二级：VLM多模态确认（API，极便宜）                       │
│                                                          │
│  每个候选段首尾关键帧 → Qwen-VL-Plus API                    │
│  Prompt: 5维度结构化对比                                    │
│    1. 服装类型（上衣/裙子/裤子/外套...）                     │
│    2. 主色调（红色/黑色/白色...）                            │
│    3. 图案/纹理（纯色/条纹/碎花...）                        │
│    4. 版型/剪裁（修身/宽松/A字...）                         │
│    5. 穿着方式（单穿/叠搭/配饰变化...）                      │
│  → Prompt工程输出JSON + 正则提取 + 解析容错                 │
│  → 只保留is_different=true的段 → 约20-50个确认切换点        │
│  耗时：~2分钟    成本：~¥3（200对图片）                     │
└────────────────────┬─────────────────────────────────────┘
                     ↓ 确认的商品切换点
┌──────────────────────────────────────────────────────────┐
│  第三级：ASR文字补充 + 内容丰富                            │
│                                                          │
│  ① FunASR语音转文字                                       │
│     分片30分钟 + 3-5秒重叠 + 独立进程处理每chunk             │
│     + 偏移量合并（防内存泄漏）                               │
│  → 每个片段匹配主播说的商品名/价格/卖点                     │
│  ② 商品名优先级（冲突解决）：                               │
│     VLM识别 > ASR提取 > VLM描述兜底                        │
│  ③ Qwen-VL-Plus为每个片段生成：                            │
│     商品标题、卖点摘要、推荐封面帧                           │
│  耗时：~10分钟    成本：~¥0.5-1                             │
└────────────────────┬─────────────────────────────────────┘
                     ↓
┌──────────────────────────────────────────────────────────┐
│  后期处理：FFmpeg单命令输出                                │
│                                                          │
│  每个确认段 → FFmpeg filter_complex 单命令：               │
│  精确切割 + 字幕烧录 + BGM混合 + 水印叠加                  │
│  → 输出可直接发布的MP4短视频                               │
│  耗时：~5分钟    成本：¥0（本地）                          │
└──────────────────────────────────────────────────────────┘

总耗时：~20-30分钟/3小时直播    总成本：¥3-5/场
```

### Concrete Deliverables
- `frontend/` — React + shadcn/ui + Tailwind CSS + Zustand + Vite 单页应用
- `backend/` — Python FastAPI + Celery + Redis 三级混合Pipeline
- `docker-compose.yml` — 一键启动（api, worker, redis, funasr容器）
- PySceneDetect + FashionSigLIP模型集成（ONNX Runtime本地运行，镜像~500MB）
- 默认BGM音频文件 + 水印PNG图片
- 完整单元测试 + 集成测试 + E2E测试

### Definition of Done
- [ ] `docker compose up` 启动所有服务，`curl localhost:8000/health` 返回 `{"status":"ok"}`
- [ ] 上传测试MP4 → PySceneDetect筛选→FashionSigLIP预筛→VLM确认→ASR补充→生成带字幕/BGM/水印的切片视频
- [ ] 前端显示结果卡片 → 可预览 → 可下载
- [ ] 所有单元测试通过：`cd backend && pytest`
- [ ] E2E测试通过：Playwright完整流程测试

### Must Have
- MP4/H.264文件上传验证（格式+编码+音频+大小≤20GB）
- **PySceneDetect场景筛选**：ContentDetector快速检测场景变化→候选区域
- **FashionSigLIP本地视觉预筛**：ONNX Runtime编码→滑动窗口5帧→自适应阈值0.78-0.82→60秒冷却期
- **Qwen-VL-Plus多模态确认**：5维度结构化对比→商品切换确认+商品描述
- FunASR语音转文字（30分钟分片+3-5秒重叠+独立进程）→ 商品名匹配补充
- 冲突解决规则：VLM识别>FashionSigLIP>ASR
- FFmpeg单命令处理：切割+字幕+BGM+水印
- WebSocket实时进度推送（7种状态）
- 设置弹窗（VLM API Key / Base URL / Model / FunASR配置）
- 结果卡片展示 + 视频预览弹窗 + 单个/批量下载
- Celery异步任务队列 + 错误重试
- 临时文件清理
- Docker Compose一键部署（ONNX Runtime，镜像~500MB）

### Must NOT Have (Guardrails)
- ❌ 不用MoviePy（比FFmpeg慢6-22倍）
- ❌ 不用 `ffmpeg -c copy` 切割（精度±2-5秒不可接受）
- ❌ 不用PyTorch（用ONNX Runtime替代，镜像8GB→500MB）
- ❌ 不用普通CLIP ViT-B/32（服装检测Top-1仅41%，用FashionSigLIP）
- ❌ 不用固定阈值0.85（服装场景不适用，用自适应0.78-0.82）
- ❌ 不做视频编辑UI（时间轴、拖拽裁剪等）
- ❌ 不做用户认证/登录/注册
- ❌ 不用数据库（仅文件系统+JSON元数据）
- ❌ 不做非MP4/H.264格式支持
- ❌ 不做云存储（S3/OSS等）
- ❌ 不做视频转码（输出与源格式一致）
- ❌ 不做字幕编辑器（自动生成，直接烧录）
- ❌ 不做BGM库管理（单一默认BGM）
- ❌ 不做段落边界编辑UI（AI输出即最终结果）
- ❌ 不做多用户并发（单用户单任务）
- ❌ 不做国际化（仅中文UI）
- ❌ 不做历史记录功能
- ❌ 不做第三方推送（钉钉/飞书/企微）
- ❌ 不做分析/遥测
- ❌ 不做AI精确度调优循环（基线prompt先上线）
- ❌ 不做服装像素级分割（后续迭代，FASHN Human Parser）

---

## Verification Strategy

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: NO (new project)
- **Automated tests**: TDD (Red-Green-Refactor)
- **Framework**: Python pytest (backend) + Playwright (E2E)
- **If TDD**: Each task follows RED (failing test) → GREEN (minimal impl) → REFACTOR

### QA Policy
Every task MUST include agent-executed QA scenarios.
Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`.

- **Frontend/UI**: Use Playwright — Navigate, interact, assert DOM, screenshot
- **API/Backend**: Use Bash (curl) — Send requests, assert status + response fields
- **Pipeline**: Use Bash (pytest) — Run unit/integration tests, verify outputs
- **Video Output**: Use Bash (ffprobe) — Verify codec, duration, streams
- **Visual Pipeline**: Use Bash (pytest) — Verify嵌入向量维度（768维）、自适应阈值计算、冷却期逻辑
- **PySceneDetect**: Use Bash (pytest) — Verify场景检测输出格式和内容

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately - foundation):
├── Task 1: Project scaffold (monorepo + Docker Compose + ONNX + PySceneDetect) [deep]

Wave 2 (After Wave 1 - core infrastructure, PARALLEL):
├── Task 2: Upload API + UI (depends: 1) [deep]
├── Task 3: WebSocket progress system (depends: 1) [deep]
├── Task 4: Settings UI (depends: 1) [quick]

Wave 3 (After Wave 2 - AI pipeline, SEQUENTIAL):
├── Task 5: Scene detect + FashionSigLIP visual pre-screening (depends: 2) [deep]
├── Task 6: VLM confirmation — Qwen-VL-Plus integration (depends: 4, 5) [deep]
├── Task 7: ASR transcription + segment enrichment (depends: 5, 6) [deep]
├── Task 8: Video processing — FFmpeg single-pass (depends: 7) [deep]

Wave 4 (After Wave 3 - integration + polish):
├── Task 9: Result display + preview + download UI (depends: 3, 8) [visual-engineering]
├── Task 10: Error handling + validation + cleanup (depends: 8) [deep]
├── Task 11: Docker Compose finalization + README (depends: 10) [deep]

Wave FINAL (After ALL tasks — 4 parallel reviews):
├── F1: Plan compliance audit (oracle)
├── F2: Code quality review (unspecified-high)
├── F3: Real manual QA (unspecified-high)
└── F4: Scope fidelity check (deep)
-> Present results -> Get explicit user okay

Critical Path: T1 → T2 → T5 → T6 → T7 → T8 → T9 → T10 → T11 → F1-F4
Parallel Speedup: T3 || T2, T4 || T2
Max Concurrent: 3 (Wave 2)
```

### Dependency Matrix

| Task | Depends On | Blocks | Wave |
|------|-----------|--------|------|
| 1    | -         | 2,3,4  | 1    |
| 2    | 1         | 5      | 2    |
| 3    | 1         | 9      | 2    |
| 4    | 1         | 6      | 2    |
| 5    | 2         | 6, 7   | 3    |
| 6    | 4, 5      | 7      | 3    |
| 7    | 5, 6      | 8      | 3    |
| 8    | 7         | 9, 10  | 3/4  |
| 9    | 3, 8      | F1-F4  | 4    |
| 10   | 8         | 11     | 4    |
| 11   | 10        | F1-F4  | 4    |
| F1-F4| ALL       | -      | FINAL|

### Agent Dispatch Summary

- **Wave 1**: 1 task — T1 → `deep`
- **Wave 2**: 3 tasks — T2 → `deep`, T3 → `deep`, T4 → `quick`
- **Wave 3**: 4 tasks — T5 → `deep`, T6 → `deep`, T7 → `deep`, T8 → `deep`
- **Wave 4**: 3 tasks — T9 → `visual-engineering`, T10 → `deep`, T11 → `deep`
- **FINAL**: 4 tasks — F1 → `oracle`, F2 → `unspecified-high`, F3 → `unspecified-high`, F4 → `deep`

---

## TODOs

- [x] 1. **Project Scaffold — Monorepo + ONNX + PySceneDetect + Docker Compose**

  **What to do**:
  - 创建monorepo结构：`frontend/`（Vite+React+shadcn/ui+Tailwind+Zustand）+ `backend/`（FastAPI+Celery）
  - `frontend/`: `npm create vite@latest` → React+TypeScript → 安装 shadcn/ui + Tailwind CSS + Zustand
  - `backend/`: Python虚拟环境 → `pip install fastapi uvicorn celery redis python-multipart websockets onnxruntime scenedetect[opencv] Pillow openai numpy`（ONNX Runtime替代PyTorch；PySceneDetect含OpenCV；VLM调用：openai SDK兼容Qwen API）
  - `backend/` 目录结构：`app/api/`, `app/services/`, `app/tasks/`, `app/models/`
  - 下载FashionSigLIP ONNX模型权重到 `backend/models/fashion_siglip/`（或首次运行时自动下载）
  - 验证FashionSigLIP ONNX模型可加载：`python -c "import onnxruntime as ort; print('ONNX OK')"`
  - 验证PySceneDetect可运行：`python -c "from scenedetect import ContentDetector; print('PySceneDetect OK')"`
  - `docker-compose.yml`: 4个服务 — `api`（FastAPI）, `worker`（Celery+ONNX Runtime）, `redis`, `funasr`
  - `backend/Dockerfile`: Python 3.11-slim + FFmpeg系统依赖 + ONNX Runtime（CPU版，镜像~500MB vs PyTorch 8GB）
  - `frontend/Dockerfile`: Node 20 build + nginx serve
  - 创建测试MP4样本文件（FFmpeg生成30秒测试视频 `test_30s.mp4`）
  - **TDD**: 先写空测试骨架文件确认pytest配置正确

  **Must NOT do**:
  - 不安装MoviePy
  - 不安装PyTorch（用ONNX Runtime替代）
  - 不创建数据库相关文件
  - 不配置用户认证
  - 不提交大型模型文件到git（`.gitignore`添加`*.onnx`, `*.bin`, `*.safetensors`）

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: [`fullstack-dev`]

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 1 (solo)
  - **Blocks**: Tasks 2, 3, 4
  - **Blocked By**: None

  **References**:
  - FashionSigLIP ONNX: `marqo-ai/marqo-FashionSigLIP` → 导出为ONNX格式使用onnxruntime加载
  - PySceneDetect: `pip install scenedetect[opencv]` → `ContentDetector(threshold=27.0)`
  - ONNX Runtime CPU: `pip install onnxruntime`（无GPU依赖，镜像极小）
  - FunASR Docker镜像: `registry.cn-hangzhou.aliyuncs.com/funasr_repo/funasr:funasr-runtime-sdk-online-cpu-0.1.12`
  - `.gitignore`: 添加 `*.onnx`, `*.bin`, `*.safetensors`, `*.pt`, `uploads/`, `__pycache__/`

  **QA Scenarios:**

  ```
  Scenario: Docker Compose启动所有服务
    Tool: Bash
    Steps:
      1. `docker compose up -d --build`
      2. 等待60秒让服务启动（ONNX镜像~500MB）
      3. `curl -s http://localhost:8000/health`
      4. `curl -s -o /dev/null -w "%{http_code}" http://localhost:5173`
    Expected Result: health返回 `{"status":"ok"}`，前端返回HTTP 200
    Evidence: .sisyphus/evidence/task-1-docker-up.txt

  Scenario: FashionSigLIP ONNX模型加载成功
    Tool: Bash (pytest)
    Steps:
      1. `cd backend && python -m pytest tests/test_visual_load.py -v`
      2. 验证ONNX模型加载不报错
      3. 验证输出向量维度=768
    Expected Result: 模型加载成功，encode_image返回768维向量
    Evidence: .sisyphus/evidence/task-1-siglip-load.txt

  Scenario: PySceneDetect可正常运行
    Tool: Bash (pytest)
    Steps:
      1. `cd backend && python -m pytest tests/test_scenedetect.py -v`
      2. 对test_30s.mp4运行场景检测
      3. 验证输出场景列表
    Expected Result: ContentDetector运行无报错，输出场景列表
    Evidence: .sisyphus/evidence/task-1-scenedetect.txt

  Scenario: 测试视频生成成功
    Tool: Bash
    Steps:
      1. `ffmpeg -f lavfi -i color=c=blue:s=1920x1080:d=30 -f lavfi -i sine=frequency=440:duration=30 -c:v libx264 -c:a aac -y tests/fixtures/test_30s.mp4`
      2. `ffprobe -v error -show_entries format=duration -of csv=p=0 tests/fixtures/test_30s.mp4`
    Expected Result: 30秒测试视频，duration≈30.0
    Evidence: .sisyphus/evidence/task-1-test-video.txt
  ```

  **Commit**: YES
  - Message: `feat(scaffold): init monorepo with frontend + backend + ONNX + PySceneDetect + docker-compose`
  - Pre-commit: `cd backend && python -c "import onnxruntime; from scenedetect import ContentDetector; print('OK')"`

---

- [x] 2. **Upload API + UI — 文件上传与验证**

  **What to do**:
  - 后端: `POST /api/upload` multipart端点
    - 验证：MP4格式→ H.264编码（ffprobe）→ 有音频轨（ffprobe）→ 大小≤20GB
    - 生成UUID task_id，创建 `uploads/{task_id}/` 目录
    - 保存文件为 `uploads/{task_id}/original.mp4`
    - 获取视频元数据存入 `uploads/{task_id}/meta.json`
    - 创建Celery任务入队，返回task_id
  - 前端: 上传组件（拖拽区域+文件选择按钮+进度条）
  - **TDD**: 先写上传验证单元测试

  **Must NOT do**: 不做断点续传、不多文件并发、不做非MP4支持

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: [`fullstack-dev`]

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 3, 4)
  - **Blocks**: Task 5
  - **Blocked By**: Task 1

  **QA Scenarios:**

  ```
  Scenario: 上传有效MP4成功
    Tool: Bash (curl)
    Steps:
      1. `curl -s -F "file=@tests/fixtures/test_30s.mp4" http://localhost:8000/api/upload`
      2. 验证返回JSON含task_id
      3. `ls uploads/{task_id}/original.mp4`
    Expected Result: HTTP 200, task_id非空, 文件存在
    Evidence: .sisyphus/evidence/task-2-upload-success.txt

  Scenario: 上传无效文件被拒绝
    Tool: Bash (curl)
    Steps:
      1. `echo "not a video" > /tmp/test.txt`
      2. `curl -s -w "\n%{http_code}" -F "file=@/tmp/test.txt" http://localhost:8000/api/upload`
    Expected Result: HTTP 400, "Only MP4 files are supported"
    Evidence: .sisyphus/evidence/task-2-upload-reject.txt

  Scenario: 上传无音频视频被拒绝
    Tool: Bash (curl)
    Steps:
      1. `ffmpeg -f lavfi -i color=c=red:s=1920x1080:d=10 -c:v libx264 -an -y /tmp/no_audio.mp4`
      2. `curl -s -w "\n%{http_code}" -F "file=@/tmp/no_audio.mp4" http://localhost:8000/api/upload`
    Expected Result: HTTP 400, "no audio track"
    Evidence: .sisyphus/evidence/task-2-no-audio.txt

  Scenario: 前端拖拽上传
    Tool: Playwright
    Steps:
      1. 导航到 `http://localhost:5173`
      2. 确认 `.upload-zone` 可见
      3. `page.setInputFiles('input[type="file"]', 'tests/fixtures/test_30s.mp4')`
      4. 等待 `.upload-progress` 可见
    Expected Result: 上传区域可见，上传后显示进度条
    Evidence: .sisyphus/evidence/task-2-ui-upload.png
  ```

  **Commit**: YES
  - Message: `feat(upload): add file upload API with validation and frontend component`
  - Pre-commit: `cd backend && python -m pytest tests/test_validator.py -v`

---

- [x] 3. **WebSocket Progress System — 实时进度推送**

  **What to do**:
  - 后端: `WS /ws/tasks/{task_id}` + `GET /api/tasks/{task_id}`
  - 任务状态机：UPLOADED → EXTRACTING_FRAMES → SCENE_DETECTING → VISUAL_SCREENING → VLM_CONFIRMING → TRANSCRIBING → PROCESSING → COMPLETED (+ ERROR)
  - 前端: `useWebSocket` Hook + 进度组件（步骤指示器+中文步骤名+loading动画）
  - **TDD**: 先写状态机单元测试

  **Must NOT do**: 不做精确百分比、不做历史回放

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: [`fullstack-dev`]

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 2, 4)
  - **Blocks**: Task 9
  - **Blocked By**: Task 1

  **QA Scenarios:**

  ```
  Scenario: 状态机转换合法性
    Tool: Bash (pytest)
    Steps:
      1. `cd backend && python -m pytest tests/test_state_machine.py -v`
    Expected Result: 合法转换通过，非法转换（如COMPLETED→SCENE_DETECTING）被拒绝
    Evidence: .sisyphus/evidence/task-3-state-machine.txt

  Scenario: WebSocket连接并接收状态
    Tool: Bash (python websocket client)
    Steps:
      1. 连接 `ws://localhost:8000/ws/tasks/{task_id}`
      2. 触发pipeline处理
      3. 验证收到状态消息序列含state/step/message字段
    Expected Result: 收到完整状态序列
    Evidence: .sisyphus/evidence/task-3-ws-messages.txt

  Scenario: 前端进度组件渲染
    Tool: Playwright
    Steps:
      1. 上传文件触发处理
      2. 等待 `.progress-bar` 可见
      3. 检查 `.step-indicator` 文本
    Expected Result: 进度条和步骤指示器正确显示
    Evidence: .sisyphus/evidence/task-3-progress-ui.png
  ```

  **Commit**: YES
  - Message: `feat(ws): add WebSocket progress endpoint and frontend real-time display`
  - Pre-commit: `cd backend && python -m pytest tests/test_state_machine.py -v`

---

- [x] 4. **Settings UI — VLM/FunASR配置弹窗**

  **What to do**:
  - 前端: 齿轮图标 → 设置弹窗（shadcn/ui Dialog）
    - VLM API Key（Qwen-VL-Plus / GLM-4V-Plus）
    - API Base URL（默认 `https://dashscope.aliyuncs.com/compatible-mode/v1`）
    - Model 名称（默认 `qwen-vl-plus`）
    - FunASR模式选择（local Docker / remote API）
    - 保存/取消按钮
  - Zustand settings store + localStorage持久化
  - 后端: `POST /api/settings/validate` 端点（验证API Key有效性）
  - **TDD**: settings store单元测试

  **Must NOT do**: 不做服务端存储、不做配置导入导出

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: [`frontend-dev`]

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 2, 3)
  - **Blocks**: Task 6
  - **Blocked By**: Task 1

  **QA Scenarios:**

  ```
  Scenario: 设置保存和持久化
    Tool: Playwright
    Steps:
      1. 点击 `.settings-btn`
      2. 在 `#api-key` 输入 `test-key-123`
      3. 在 `#api-base` 输入 `https://test.api.com/v1`
      4. 点击 `.save-btn`
      5. 刷新页面 → 再次打开设置
    Expected Result: 刷新后字段值保留
    Evidence: .sisyphus/evidence/task-4-settings-persist.png

  Scenario: 默认值正确
    Tool: Playwright
    Steps:
      1. 清除localStorage → 刷新 → 打开设置
    Expected Result: api-base默认阿里DashScope地址, model默认qwen-vl-plus
    Evidence: .sisyphus/evidence/task-4-settings-defaults.png

  Scenario: 空API Key阻止保存
    Tool: Playwright
    Steps:
      1. 清空API Key → 点击保存
    Expected Result: 验证错误提示
    Evidence: .sisyphus/evidence/task-4-settings-validation.png
  ```

  **Commit**: YES
  - Message: `feat(settings): add settings modal for VLM/FunASR configuration`
  - Pre-commit: `cd frontend && npm run build`

---

- [x] 5. **第一级Pipeline：PySceneDetect场景筛选 + FashionSigLIP视觉预筛**

  **What to do**:
  - PySceneDetect场景筛选: `SceneDetector` 类
    - 使用 `ContentDetector(threshold=27.0)` 快速检测场景变化
    - 输入：原始MP4文件
    - 输出：候选场景列表 `[{start_time, end_time}]`
    - 3小时直播 → 约100-300个场景片段（粗筛）
    - 保存到 `uploads/{task_id}/scene/scenes.json`
  - 候选区域精抽帧: `FrameExtractor` 类
    - **只在候选场景区域内**以1fps抽帧（非全局每5秒）
    - `ffmpeg -ss {start} -to {end} -i original.mp4 -vf fps=1 -q:v 2 uploads/{task_id}/frames/frame_%05d.jpg`
    - 3小时直播 → 约200-800帧（比全局2160帧少得多）
    - 输出帧列表到 `uploads/{task_id}/frames/frames.json`
  - FashionSigLIP编码器: `FashionSigLIPEncoder` 类
    - 加载 `marqo-FashionSigLIP` ONNX模型（首次自动下载）
    - 逐帧编码 → 768维向量（比CLIP 512维更丰富）
    - 存储嵌入到 `uploads/{task_id}/visual/embeddings.npy`（numpy格式）
    - 批量处理（batch_size=32）提高效率
  - 自适应相似度分析器: `AdaptiveSimilarityAnalyzer` 类
    - **滑动窗口5帧**：对连续5帧计算平均相似度，平滑噪声
    - **自适应阈值0.78-0.82**：基于视频整体相似度分布动态调整
      - 计算90th百分位作为基线 → 基线×0.9作为阈值 → clamp到[0.78, 0.82]
    - 窗口平均相似度<阈值的区域标记为候选切换点
    - **60秒冷却期**：确认一个切换点后，60秒内不再检测新切换点（防止换装过渡期误报）
    - 输出候选段到 `uploads/{task_id}/visual/candidates.json`
    - 格式：`[{start_frame, end_frame, start_time, end_time, similarity_drop, cooldown_applied}]`
  - Celery task: `visual_prescreen(task_id)`
    - 状态：UPLOADED → SCENE_DETECTING → VISUAL_SCREENING
    - 完成后触发VLM确认任务
  - **TDD**: 先写AdaptiveSimilarityAnalyzer单元测试（自适应阈值计算、滑动窗口、冷却期逻辑）

  **Must NOT do**:
  - 不做GPU必须要求（ONNX Runtime CPU也能跑）
  - 不做实时处理（仅批量）
  - 不提交模型文件到git
  - 不使用固定阈值0.85（服装场景不适用）
  - 不使用全局每5秒抽帧（用PySceneDetect先筛再精抽）

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: [`fullstack-dev`]

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 3
  - **Blocks**: Tasks 6, 7
  - **Blocked By**: Task 2

  **References**:
  - PySceneDetect: `from scenedetect import SceneManager, ContentDetector; sm = SceneManager(); sm.add_detector(ContentDetector(threshold=27.0))`
  - FashionSigLIP ONNX: `marqo-ai/marqo-FashionSigLIP` → 导出ONNX → `onnxruntime.InferenceSession`
  - 编码: ONNX session → preprocess image (resize+normalize) → run → 768维向量
  - 滑动窗口: `numpy.convolve(similarities, np.ones(5)/5, mode='valid')`
  - 自适应阈值: `np.percentile(similarities, 90) * 0.9 → clamp(0.78, 0.82)`
  - 冷却期: 记录最后一个切换点时间戳 → 下一个候选必须>60秒

  **QA Scenarios:**

  ```
  Scenario: PySceneDetect场景检测正确
    Tool: Bash (pytest)
    Steps:
      1. `cd backend && python -m pytest tests/test_scene_detector.py -v`
      2. 用test_30s.mp4测试
      3. 验证输出scenes.json格式正确
    Expected Result: 场景列表非空，格式正确
    Evidence: .sisyphus/evidence/task-5-scene-detect.txt

  Scenario: 候选区域精抽帧数量合理
    Tool: Bash (pytest)
    Steps:
      1. 30秒视频 + 2个候选场景 → 每场景1fps → 约30帧
      2. 90秒视频 + 3个候选场景 → 约90帧
    Expected Result: 帧数量在预期范围内（远少于全局2160帧）
    Evidence: .sisyphus/evidence/task-5-frame-extraction.txt

  Scenario: FashionSigLIP编码维度正确
    Tool: Bash (pytest)
    Steps:
      1. 加载FashionSigLIP ONNX模型
      2. 对单张图片编码
      3. 验证输出shape=(1, 768)
    Expected Result: 768维向量，值在合理范围
    Evidence: .sisyphus/evidence/task-5-siglip-encoding.txt

  Scenario: 自适应阈值计算正确
    Tool: Bash (pytest)
    Steps:
      1. 构造相似度序列（均值0.9，标准差0.05）
      2. 计算90th百分位×0.9 → clamp(0.78, 0.82)
      3. 验证阈值在[0.78, 0.82]范围内
    Expected Result: 自适应阈值合理
    Evidence: .sisyphus/evidence/task-5-adaptive-threshold.txt

  Scenario: 滑动窗口平滑噪声
    Tool: Bash (pytest)
    Steps:
      1. 构造有噪声的相似度序列（10帧，第5帧骤降但第4/6帧正常）
      2. 无窗口：检测到3个切换点（噪声）
      3. 窗口5帧：检测到1个切换点（平滑后）
    Expected Result: 窗口平滑减少噪声误检
    Evidence: .sisyphus/evidence/task-5-sliding-window.txt

  Scenario: 60秒冷却期防止连续触发
    Tool: Bash (pytest)
    Steps:
      1. 构造3个候选切换点（间隔20秒、30秒、90秒）
      2. 应用60秒冷却期
      3. 第1个保留，第2个被冷却过滤（<60s），第3个保留（>60s）
    Expected Result: 保留2个切换点，过滤1个
    Evidence: .sisyphus/evidence/task-5-cooldown.txt

  Scenario: 端到端视觉预筛
    Tool: Bash
    Steps:
      1. 用test_30s.mp4触发pipeline
      2. 等待VISUAL_SCREENING完成
      3. 验证scenes/frames/visual/目录文件存在
    Expected Result: 所有中间文件存在，candidates含候选段
    Evidence: .sisyphus/evidence/task-5-e2e.txt
  ```

  **Commit**: YES
  - Message: `feat(visual): add PySceneDetect + FashionSigLIP adaptive visual pre-screening`
  - Pre-commit: `cd backend && python -m pytest tests/test_scene_detector.py tests/test_siglip_encoder.py tests/test_adaptive_similarity.py -v`

---

- [x] 6. **第二级Pipeline：VLM多模态确认 — Qwen-VL-Plus商品识别（5维度结构化对比）**

  **What to do**:
  - VLM API客户端: `VLMClient` 类
    - 使用OpenAI SDK兼容接口（Qwen API兼容OpenAI格式）
    - 从settings获取API Key / Base URL / Model
    - 支持多图输入（候选段首尾2张关键帧，base64编码）
    - 超时120秒，重试3次指数退避
  - Prompt模板: **5维度结构化商品对比**（Qwen-VL-Plus不支持原生JSON mode，需Prompt工程）
    ```
    你是一位专业的服装商品分析师。请仔细对比这两张直播截图，从以下5个维度判断是否展示了不同的服装商品：
    
    1. 服装类型：上衣/裙子/裤子/外套/配饰/无服装展示
    2. 主色调：主要颜色（红/黑/白/蓝/绿/粉/黄/灰/棕/多色）
    3. 图案纹理：纯色/条纹/碎花/格子/印花/刺绣/无
    4. 版型剪裁：修身/宽松/A字/直筒/oversize/无
    5. 穿着方式：单穿/叠搭/配饰变化/模特展示/无
    
    请严格按以下JSON格式回复（不要添加任何其他文字）：
    {
      "is_different": true或false,
      "confidence": 0.0到1.0的置信度,
      "dimensions": {
        "type": {"same": true/false, "value_1": "...", "value_2": "..."},
        "color": {"same": true/false, "value_1": "...", "value_2": "..."},
        "pattern": {"same": true/false, "value_1": "...", "value_2": "..."},
        "cut": {"same": true/false, "value_1": "...", "value_2": "..."},
        "wear": {"same": true/false, "value_1": "...", "value_2": "..."}
      },
      "product_1": {"type": "服装类型", "color": "颜色", "style": "款式描述"},
      "product_2": {"type": "服装类型", "color": "颜色", "style": "款式描述"}
    }
    
    判断规则：
    - 如果两张图中是同一件衣服（仅角度/姿态不同），is_different=false
    - 如果图中没有服装展示（只有人脸/空镜头），is_different=false
    - 只有确实换了不同商品时才设为true
    ```
  - JSON解析容错: `VLMResponseParser` 类
    - 正则提取JSON：`re.search(r'\{[\s\S]*\}', response_text)`
    - 多层解析尝试：完整JSON→截取首个JSON对象→字段默认值
    - `confidence<0.6` 时标记为低置信度，可考虑后续人工确认
  - 确认器: `VLMConfirmor` 类
    - 遍历所有候选切换段
    - 每段取首尾关键帧发给VLM
    - 只保留 `is_different=true` 的段
    - 为每个确认段生成商品描述
    - 输出到 `uploads/{task_id}/vlm/confirmed_segments.json`
    - 格式：`[{start_time, end_time, confidence, product_info: {type, color, style, description}}]`
  - Celery task: `vlm_confirm(task_id)`
    - 状态：VISUAL_SCREENING → VLM_CONFIRMING
  - **TDD**: 先写VLM响应解析单元测试（JSON解析容错、字段验证、异常处理）

  **Must NOT do**:
  - 不做视觉像素级分割
  - 不做服装属性识别（颜色/面料等精细属性留给VLM自然描述）
  - 不做视频直传（只传截图，节省成本）
  - 不依赖原生JSON mode（Qwen-VL-Plus不支持）

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: [`fullstack-dev`]

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 3
  - **Blocks**: Task 7
  - **Blocked By**: Tasks 4, 5

  **References**:
  - Qwen-VL-Plus API: `POST https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions`
  - 多图输入: `content: [{"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}}, ...]`
  - OpenAI SDK兼容: `from openai import OpenAI; client = OpenAI(api_key=..., base_url=...)`
  - JSON解析容错: 正则提取 `r'\{[\s\S]*\}'` → json.loads → 异常时尝试修复（补括号等）

  **QA Scenarios:**

  ```
  Scenario: VLM标准JSON响应解析正确
    Tool: Bash (pytest)
    Steps:
      1. 输入标准VLM JSON响应
      2. 解析为ConfirmedSegment对象
      3. 验证字段映射：is_different, confidence, dimensions, product_info
    Expected Result: 正确解析所有字段
    Evidence: .sisyphus/evidence/task-6-vlm-parse.txt

  Scenario: 非JSON响应容错解析
    Tool: Bash (pytest)
    Steps:
      1. 输入包含文字+JSON的混合响应："好的，我来分析：{\"is_different\": true...}"
      2. 正则提取JSON部分
      3. 成功解析
    Expected Result: 正则提取成功，字段解析正确
    Evidence: .sisyphus/evidence/task-6-vlm-regex.txt

  Scenario: Malformed JSON重试
    Tool: Bash (pytest)
    Steps:
      1. Mock第1次返回纯文字无JSON
      2. Mock第2次返回合法JSON
      3. 验证重试成功
    Expected Result: 重试后成功
    Evidence: .sisyphus/evidence/task-6-vlm-retry.txt

  Scenario: is_different=false过滤
    Tool: Bash (pytest)
    Steps:
      1. 输入5个候选段，其中2个VLM返回is_different=false
      2. 验证最终只保留3个确认段
    Expected Result: 无效候选段被过滤
    Evidence: .sisyphus/evidence/task-6-vlm-filter.txt

  Scenario: 低置信度标记
    Tool: Bash (pytest)
    Steps:
      1. VLM返回confidence=0.5
      2. 标记为低置信度
    Expected Result: 段被标记low_confidence=true
    Evidence: .sisyphus/evidence/task-6-vlm-confidence.txt

  Scenario: 端到端VLM确认（mock模式）
    Tool: Bash
    Steps:
      1. 准备candidates.json（3个候选段）
      2. Mock VLM API返回
      3. 运行确认任务
      4. 验证confirmed_segments.json存在且内容合理
    Expected Result: 确认段生成正确
    Evidence: .sisyphus/evidence/task-6-vlm-e2e.txt
  ```

  **Commit**: YES
  - Message: `feat(vlm): add Qwen-VL-Plus 5-dimension multimodal confirmation with JSON parsing`
  - Pre-commit: `cd backend && python -m pytest tests/test_vlm_client.py tests/test_vlm_parser.py tests/test_vlm_confirmor.py -v`

---

- [x] 7. **第三级Pipeline：ASR转录 + 商品名匹配 + 内容丰富（含冲突解决）**

  **What to do**:
  - FunASR客户端: `FunASRClient` 类
    - 连接FunASR Docker容器
    - 逐个发送音频分片（≤30分钟 + **3-5秒重叠**，防内存泄漏）
    - **每个chunk使用独立进程处理**（subprocess隔离，处理完即释放内存）
    - 重试3次
  - 转录合并器: `TranscriptMerger` 类
    - 偏移量校正 + **3-5秒重叠区域去重**（取后一个分片的结果）
    - 输出 `transcript.json`: `[{text, start_time, end_time}]`
  - 商品名匹配器: `ProductNameMatcher` 类
    - **冲突解决优先级：VLM识别 > ASR提取 > VLM描述兜底**
    - Step 1: 使用VLM的5维度商品描述（type+color+style）作为首选名称
    - Step 2: 在对应时间段的ASR文本中搜索商品关键词，如果找到更具体的名称则覆盖
    - Step 3: 如果ASR没有匹配到，使用VLM描述拼接作为名称（如"黑色Oversize T恤"）
  - 段落验证器: `SegmentValidator` 类
    - 最短60秒、最长600秒
    - 同名商品5分钟窗口去重
    - 时间范围在视频时长内
  - Celery task: `enrich_segments(task_id)`
    - 状态：VLM_CONFIRMING → TRANSCRIBING
  - **TDD**: TranscriptMerger + ProductNameMatcher + SegmentValidator单元测试

  **Must NOT do**:
  - 不做说话人分离
  - 不做实时流式转写
  - 不做Whisper切换
  - 不在主进程中加载FunASR（内存泄漏风险）

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: [`fullstack-dev`]

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 3
  - **Blocks**: Task 8
  - **Blocked By**: Tasks 5, 6

  **QA Scenarios:**

  ```
  Scenario: 转录合并偏移量正确（3-5秒重叠去重）
    Tool: Bash (pytest)
    Steps:
      1. 3个分片offset=[0, 1800, 3600]，重叠3秒
      2. 合并验证时间戳偏移正确
      3. 重叠区域（如1797-1800秒）取后一个分片结果
    Expected Result: chunk_1+1800, chunk_2+3600, 重叠区域去重
    Evidence: .sisyphus/evidence/task-7-transcript-merge.txt

  Scenario: 商品名冲突解决 — VLM优先
    Tool: Bash (pytest)
    Steps:
      1. VLM描述：{type: "连衣裙", color: "白色", style: "A字裙"}
      2. ASR文本："这条裙子只要199"
      3. VLM名称="白色A字连衣裙" vs ASR="裙子" → VLM优先
    Expected Result: 商品名="白色A字连衣裙"
    Evidence: .sisyphus/evidence/task-7-conflict-vlm.txt

  Scenario: 商品名冲突解决 — ASR更具体时覆盖
    Tool: Bash (pytest)
    Steps:
      1. VLM描述：{type: "T恤", color: "黑色"}
      2. ASR文本："这款黑色冰丝透气圆领T恤"
      3. ASR更具体 → 覆盖VLM名称
    Expected Result: 商品名="黑色冰丝透气圆领T恤"
    Evidence: .sisyphus/evidence/task-7-conflict-asr.txt

  Scenario: 商品名 — ASR无匹配时VLM描述兜底
    Tool: Bash (pytest)
    Steps:
      1. ASR文本："看这一件"（无具体商品名）
      2. VLM描述：{type: "T恤", color: "黑色", style: "oversize"}
      3. 生成商品名："黑色Oversize T恤"
    Expected Result: VLM兜底生成商品名
    Evidence: .sisyphus/evidence/task-7-vlm-fallback.txt

  Scenario: 段落验证过滤
    Tool: Bash (pytest)
    Steps:
      1. 有效段120秒、太短30秒、太长700秒、同名5分钟内
    Expected Result: 有效保留、短段过滤、长段截断、同名去重
    Evidence: .sisyphus/evidence/task-7-segment-validate.txt

  Scenario: FunASR容器健康
    Tool: Bash
    Steps:
      1. `docker compose ps funasr`
    Expected Result: running/healthy
    Evidence: .sisyphus/evidence/task-7-funasr-health.txt
  ```

  **Commit**: YES
  - Message: `feat(asr): add FunASR transcription with 3-5s overlap and conflict resolution`
  - Pre-commit: `cd backend && python -m pytest tests/test_transcript_merger.py tests/test_product_matcher.py tests/test_segment_validator.py -v`

---

- [x] 8. **视频处理：FFmpeg单命令输出**

  **What to do**:
  - SRT生成器: `SRTGenerator`（同原方案）
  - FFmpeg命令构建器: `FFmpegBuilder`（同原方案，cut+subtitles+overlay+amix单命令）
  - 编码：`libx264 -preset fast -crf 23`（不用`-c copy`）
  - 缩略图：每个段50%时间点截图
  - 默认资源：`assets/default_bgm.mp3` + `assets/watermark.png`
  - Celery task: `process_clips(task_id)` 状态：TRANSCRIBING → PROCESSING
  - **TDD**: SRT生成器 + FFmpeg命令构建器单元测试

  **Must NOT do**:
  - 不用MoviePy、不用`-c copy`、不做分辨率转换

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: [`fullstack-dev`]

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 3
  - **Blocks**: Tasks 9, 10
  - **Blocked By**: Task 7

  **References**:
  - FFmpeg filter_complex命令:
    ```bash
    ffmpeg -ss {start} -i input.mp4 -i bgm.mp3 -i watermark.png \
      -filter_complex "[0:v]subtitles=srt.srt:force_style='...'[v_sub]; \
        [v_sub][2:v]overlay=W-w-15:15[v_out]; \
        [0:a]volume=1.0[orig]; [1:a]volume=0.25,aloop=loop=-1:size=2e+09[bgm]; \
        [orig][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]" \
      -map "[v_out]" -map "[aout]" -t {duration} \
      -c:v libx264 -preset fast -crf 23 -c:a aac -b:a 128k -y output.mp4
    ```

  **QA Scenarios:**

  ```
  Scenario: SRT生成正确
    Tool: Bash (pytest)
    Steps:
      1. 输入transcript段落
      2. 验证SRT格式：序号+时间轴+文本+空行
    Expected Result: 有效SRT格式
    Evidence: .sisyphus/evidence/task-8-srt.txt

  Scenario: FFmpeg命令包含所有必需参数
    Tool: Bash (pytest)
    Steps:
      1. 构建FFmpeg命令
      2. 验证包含: `-ss`, `-t`, `subtitles=`, `overlay=`, `amix=`, `libx264`, `-preset fast`
      3. 验证不包含: `-c copy`, `moviepy`
    Expected Result: 命令正确
    Evidence: .sisyphus/evidence/task-8-ffmpeg-cmd.txt

  Scenario: 端到端视频处理
    Tool: Bash
    Steps:
      1. test_30s.mp4 + 模拟segments触发处理
      2. 验证输出MP4: h264+aac, 缩略图存在
    Expected Result: clip.mp4有效，缩略图存在
    Evidence: .sisyphus/evidence/task-8-clip-output.txt
  ```

  **Commit**: YES
  - Message: `feat(video): add FFmpeg single-pass clip processing`
  - Pre-commit: `cd backend && python -m pytest tests/test_srt_generator.py tests/test_ffmpeg_builder.py -v`

---

- [x] 9. **Result Display + Preview + Download — 结果展示与下载**

  **What to do**:
  - 后端API: `GET /api/tasks/{task_id}/clips`, `GET /api/clips/{id}/download`, `GET /api/clips/batch?ids=...`（ZIP）, `GET /api/clips/{id}/thumbnail`
  - 前端: 结果卡片网格（CSS Grid: `repeat(auto-fill, minmax(280px, 1fr))`）
    - 每张卡片：缩略图 + 商品名 + 时长 + 播放按钮
    - 商品信息来自VLM描述（类型+颜色+款式）
  - 前端: 视频预览弹窗（shadcn/ui Dialog + HTML5 video）
  - 前端: 批量下载（全选/下载所选→ZIP）
  - WebSocket COMPLETED → 自动刷新结果
  - **TDD**: 下载API单元测试

  **Must NOT do**: 不做视频编辑、不做社交分享、不做字幕编辑

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
  - **Skills**: [`frontend-dev`]

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Task 10)
  - **Parallel Group**: Wave 4
  - **Blocks**: F1-F4
  - **Blocked By**: Tasks 3, 8

  **QA Scenarios:**

  ```
  Scenario: 完整E2E — 上传到下载
    Tool: Playwright
    Steps:
      1. 上传test_30s.mp4 → 等待COMPLETED（timeout: 600s）
      2. 验证 `.clip-card` 数量 > 0
      3. 点击卡片 → `.preview-modal` 可见 → video可播放
      4. 下载 → 验证.mp4文件
    Expected Result: 全流程无报错
    Evidence: .sisyphus/evidence/task-9-e2e-flow.png

  Scenario: 批量下载ZIP
    Tool: Bash (curl)
    Steps:
      1. `curl -s -o /tmp/clips.zip "http://localhost:8000/api/clips/batch?ids=clip_001,clip_002"`
      2. `file /tmp/clips.zip` → ZIP
    Expected Result: ZIP包含多个MP4
    Evidence: .sisyphus/evidence/task-9-batch-download.txt

  Scenario: 商品信息来自VLM描述
    Tool: Playwright
    Steps:
      1. 查看结果卡片
      2. 验证 `.clip-name` 包含具体商品描述（非空、非"未命名"）
    Expected Result: 卡片展示VLM生成的商品描述
    Evidence: .sisyphus/evidence/task-9-product-info.png
  ```

  **Commit**: YES
  - Message: `feat(ui): add result cards, preview modal, and download`
  - Pre-commit: `cd frontend && npm run build`

---

- [x] 10. **Error Handling + Validation + Cleanup**

  **What to do**:
  - 5种错误类型: UPLOAD_FAILED, VISUAL_FAILED, VLM_FAILED, ASR_FAILED, EXPORT_FAILED
  - Celery重试: max_retries=3, 指数退避
  - 前端: 错误卡片（红色）+ 重试按钮
  - 上传验证增强（ffprobe检查codec+audio+duration）
  - 临时文件清理（分片→处理后清理、SRT→输出后清理）
  - 磁盘空间检查（上传前 ≥ 文件大小×3）
  - **TDD**: 错误处理和重试逻辑单元测试

  **Must NOT do**: 不做日志持久化、不做统计分析、不做自动恢复

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: [`fullstack-dev`]

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Task 9)
  - **Parallel Group**: Wave 4
  - **Blocks**: Task 11
  - **Blocked By**: Task 8

  **QA Scenarios:**

  ```
  Scenario: 无效文件被拒绝
    Tool: Bash (curl)
    Steps: 上传.txt文件
    Expected Result: HTTP 400
    Evidence: .sisyphus/evidence/task-10-invalid.txt

  Scenario: 无音频视频被拒绝
    Tool: Bash (curl)
    Steps: 上传-an MP4
    Expected Result: HTTP 400, "no audio track"
    Evidence: .sisyphus/evidence/task-10-no-audio.txt

  Scenario: FashionSigLIP处理失败重试
    Tool: Bash (pytest)
    Steps: Mock前2次ONNX推理失败→第3次成功
    Expected Result: 最终COMPLETED
    Evidence: .sisyphus/evidence/task-10-retry.txt

  Scenario: VLM API失败→ERROR状态
    Tool: Bash (pytest)
    Steps: Mock VLM持续失败3次
    Expected Result: ERROR状态+错误消息
    Evidence: .sisyphus/evidence/task-10-vlm-error.txt

  Scenario: 临时文件清理
    Tool: Bash
    Steps: 任务完成后检查chunks/目录
    Expected Result: 中间文件已清理，最终切片保留
    Evidence: .sisyphus/evidence/task-10-cleanup.txt

  Scenario: 前端错误展示+重试
    Tool: Playwright
    Steps: ERROR任务→`.error-card`可见→重试按钮
    Expected Result: 错误卡片+可重试
    Evidence: .sisyphus/evidence/task-10-error-ui.png
  ```

  **Commit**: YES
  - Message: `feat(error): add error handling, retry, and cleanup`
  - Pre-commit: `cd backend && python -m pytest tests/test_error_handler.py -v`

---

- [x] 11. **Docker Compose Finalization + README**

  **What to do**:
  - 优化Dockerfile（多阶段构建，含ONNX Runtime + FashionSigLIP模型，镜像~500MB）
  - docker-compose.yml完善（healthcheck, volumes, depends_on, 资源限制）
  - `.env.example` 模板（含Qwen-VL-Plus API Key配置）
  - `nginx.conf`（SPA路由+API代理+upload 20G限制）
  - README.md（中文：一键启动+硬件要求+配置说明+常见问题）
  - **TDD**: Clean build → full E2E

  **Must NOT do**: 不做K8s、不做CI/CD、不做监控

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: [`fullstack-dev`]

  **Parallelization**:
  - **Can Run In Parallel**: YES (after T10)
  - **Parallel Group**: Wave 4
  - **Blocks**: F1-F4
  - **Blocked By**: Task 10

  **QA Scenarios:**

  ```
  Scenario: Clean build启动
    Tool: Bash
    Steps:
      1. `docker compose down -v && docker compose up --build -d`
      2. 等待所有服务healthy
    Expected Result: 所有服务healthy
    Evidence: .sisyphus/evidence/task-11-clean-build.txt

  Scenario: 完整E2E在Docker环境
    Tool: Bash + Playwright
    Steps: Upload → Wait → Download → Verify
    Expected Result: 全流程通过
    Evidence: .sisyphus/evidence/task-11-e2e-docker.txt

  Scenario: 数据持久化
    Tool: Bash
    Steps: docker compose down → up → 数据保留
    Expected Result: 重启后数据在
    Evidence: .sisyphus/evidence/task-11-persistence.txt
  ```

  **Commit**: YES
  - Message: `feat(deploy): finalize Docker Compose and README`
  - Pre-commit: `docker compose config --quiet`

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.

- [x] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists (read file, curl endpoint, run command). For each "Must NOT Have": search codebase for forbidden patterns (`import moviepy`, `ffmpeg -c copy`, auth module, database imports, `import torch`). Check evidence files exist in .sisyphus/evidence/. Compare deliverables against plan. Verify FashionSigLIP ONNX model loads and produces correct embedding dimensions (768). Verify PySceneDetect runs correctly. Verify Qwen-VL-Plus API calls work with test images.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [x] F2. **Code Quality Review** — `unspecified-high`
  Run `pytest` + linter. Review all changed files for: `as any`/type ignores, empty excepts, print in prod, commented-out code, unused imports. Check AI slop: excessive comments, over-abstraction, generic names. Verify no MoviePy imports anywhere (`grep -r "moviepy" backend/`). Verify no PyTorch imports (`grep -r "import torch" backend/` — should use ONNX Runtime instead). Verify all FFmpeg commands use re-encoding (not `-c copy` for cutting). Verify FashionSigLIP ONNX model size reasonable and not committed to git.
  Output: `Tests [N pass/N fail] | Lint [PASS/FAIL] | Files [N clean/N issues] | VERDICT`

- [x] F3. **Real Manual QA** — `unspecified-high` (+ `playwright` skill)
  Start from clean state (`docker compose down -v && docker compose up --build -d`). Execute EVERY QA scenario from EVERY task — follow exact steps, capture evidence. Test cross-task integration. Test edge cases: invalid file, no-audio video, large upload, CLIP model loading failure. Save to `.sisyphus/evidence/final-qa/`.
  Output: `Scenarios [N/N pass] | Integration [N/N] | Edge Cases [N tested] | VERDICT`

- [x] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", read actual diff. Verify 1:1 — everything in spec was built, nothing beyond spec was built. Check "Must NOT Have" compliance. Detect cross-task contamination. Flag unaccounted changes. Verify three-level pipeline architecture matches plan.
  Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

- **T1**: `feat(scaffold): init monorepo with frontend + backend + ONNX + PySceneDetect + docker-compose` — scaffold files, health check
- **T2**: `feat(upload): add file upload API with validation and frontend component` — backend upload + frontend upload zone
- **T3**: `feat(ws): add WebSocket progress endpoint and frontend real-time display` — ws endpoint + progress component
- **T4**: `feat(settings): add settings modal for VLM/FunASR configuration` — settings UI + localStorage
- **T5**: `feat(visual): add PySceneDetect + FashionSigLIP adaptive visual pre-screening` — 场景检测+视觉编码+自适应阈值+冷却期
- **T6**: `feat(vlm): add Qwen-VL-Plus 5-dimension multimodal confirmation with JSON parsing` — 5维度VLM + JSON解析容错
- **T7**: `feat(asr): add FunASR transcription with 3-5s overlap and conflict resolution` — ASR分片+重叠+冲突解决+商品名
- **T8**: `feat(video): add FFmpeg single-pass clip processing` — SRT gen + FFmpeg command builder
- **T9**: `feat(ui): add result cards, preview modal, and download` — result UI + download API
- **T10**: `feat(error): add error handling, retry, and cleanup` — error states + retry + temp cleanup
- **T11**: `feat(deploy): finalize Docker Compose and README` — multi-stage builds + docs

---

## Success Criteria

### Verification Commands
```bash
# 1. 服务启动
docker compose up -d
curl http://localhost:8000/health  # Expected: {"status":"ok"}

# 2. 前端可访问
curl http://localhost:5173  # Expected: HTML page

# 3. 单元测试
cd backend && pytest  # Expected: all pass

# 4. FashionSigLIP模型加载验证
cd backend && python -c "from app.services.visual_screener import FashionSigLIPEncoder; e=FlashSigLIPEncoder(); print(e.model_name)"  # Expected: marqo-FashionSigLIP

# 5. PySceneDetect验证
cd backend && python -c "from scenedetect import ContentDetector; d=ContentDetector(threshold=27.0); print('OK')"  # Expected: OK

# 6. 完整Pipeline
curl -F "file=@test_30s.mp4" http://localhost:8000/api/upload  # Expected: task_id
# Wait for WebSocket COMPLETED event
curl http://localhost:8000/api/tasks/{task_id}  # Expected: status=COMPLETED, clips > 0

# 7. 视频输出验证
ffprobe uploads/{task_id}/clips/clip_001.mp4  # Expected: h264+aac, duration matches segment

# 8. E2E测试
npx playwright test  # Expected: all pass
```

### Final Checklist
- [ ] All "Must Have" present
- [ ] All "Must NOT Have" absent (no MoviePy, no `-c copy`, no auth, no DB, no PyTorch)
- [ ] All tests pass (`pytest` + Playwright)
- [ ] Docker Compose一键启动成功（ONNX镜像~500MB）
- [ ] 三级Pipeline运行：PySceneDetect→FashionSigLIP预筛→VLM确认→ASR补充→视频输出
