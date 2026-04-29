# CLAUDE.md

## 项目定位

这是一个“直播视频 AI 智能剪辑”项目：

- 输入：一段直播录像 MP4
- 输出：一组可预览、可下载的短视频片段（clips）
- 目标：把直播里适合单独传播的商品讲解片段自动切出来，并带上烧录字幕
- README 顶部使用 `docs/images/product-flow.png` 作为产品流程图，系统架构章节使用 `docs/images/technical-architecture.png` 作为技术架构图；原 Mermaid 图已移除。


## 当前真实架构

不要只看 README，当前代码的真实运行架构如下：

- 前端：React 19 + TypeScript 6 + Vite 8 + Tailwind CSS 4 + Zustand 5 + react-router-dom + TanStack Query（AdminDashboard 作为 layout shell，页面拆分到 `admin/pages/`）
- 后端 API：FastAPI
- 异步任务：Celery
- 队列/状态：Redis
- 视频处理：FFmpeg
- 换衣检测：ClothingChangeDetector（五信号联合：YOLO 46类检测 + MediaPipe 像素分割 + 全帧 HSV + 分区域 HSV（上身/下身）+ ORB 纹理），默认多信号独立 EMA 任一信号触发 + 滞后阈值 + 连续帧确认，也支持设置页切换为加权投票融合
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

### 0. 前端架构

前端为 **React Router 单页应用**，`AdminDashboard.tsx` 是 layout shell，路由页面组件拆分到 `admin/pages/` 目录：

- **projects** — 项目管理（列表、搜索、筛选、右侧项目详情抽屉、诊断事件）
- **create** — 创建任务（上传 + 4 种预设：高质量字幕版/快速低成本版/全量候选调试版/只切不烧字幕版）
- **queue** — 任务队列（队列流、可关闭右侧详情抽屉、设计图式任务摘要/阶段 checklist/最近日志、窄屏任务卡片、Worker 资源 CPU/内存/Redis、中文阶段、固定图标操作）
- **review** — 片段审核（卡片队列、右侧复核抽屉、approve/skip/needs_adjustment/reprocess、字幕草稿文本与起止秒覆盖、单片段重导出）
- **assets** — 跨项目素材资产浏览器（项目分组卡片、右侧详情抽屉、多选、底部批量下载/批量 AI 素材生成条、批量队列抽屉、文件大小估算、AI 商品素材入口）
- **assets/:taskId/:segmentId/commerce** — 独立 AI 商品素材工作台，从片段资产页新标签打开；异步调用 Gemini 商品识别/平台文案生成，并异步调用 OpenAI Image/gpt-image-2 生成默认 2K 的模特图和淘宝详情页示例；片段视频用 `/preview` 内嵌播放，支持单张素材图独立重试
- **music** — 音乐库管理（指标卡、曲目表格、覆盖式右侧标签编辑抽屉、全宽底部播放器、上传、删除）
- **diagnostics** — 任务诊断（项目工具栏、指标卡、横向管线阶段、Recharts 漏斗图、异常建议、分页事件日志、右侧事件详情、导出报告/artifacts.zip）
- **settings** — 设置编辑器（侧栏+面板布局；顶层页签拆为处理预设、AI 服务、转写服务、字幕设置、敏感词过滤、切分策略、导出与音频、高级参数，避免不同性质的设置挤在一个大表单里；`SettingsPage.tsx` 只保留容器状态/保存/页签布局，分组和通用表单控件放在 `admin/settings/`；字幕位置编辑器使用左侧设置项 + 右侧 9:16 视频模拟预览的左右布局，顶部/中部/底部/自定义必须呈现为明确可点击的按钮组件；页面展示枚举值时必须转中文，不直接显示 `subtitle_position`、`middle`、`no_vlm` 等内部 key）

`admin/` 目录结构：`api.ts`（API 调用）、`types.ts`（类型定义）、`format.ts`（格式化工具）、`constants.tsx`（常量）、`shared.tsx`（共享组件）、`pages/`（9 个页面组件）。

布局约定：`AdminDashboard.tsx` 使用固定视口高度的后台壳，右侧内容区独立滚动；桌面端左侧导航栏保持整屏高度，Worker 资源/服务状态卡固定在侧栏底部。列表页不要做无限下滑。项目总览、任务队列、片段资产使用后端 `offset/limit` 分页；剪辑复核片段队列、音乐库、诊断事件日志使用 `Pagination` 组件做页面内分页。项目总览、任务队列、剪辑复核、片段资产、音乐库、诊断报告的详情信息优先用右侧抽屉承载，避免列表被详情面板挤压；AI 商品素材采用独立工作台页面，不放在片段资产抽屉里。

共享前端组件约定：`shared.tsx` 是后台 UI 组件的统一入口。新做或重构页面级右侧抽屉时优先使用 `DrawerShell`、`DrawerTabs`、`DrawerSection`；列表筛选栏优先使用 `FilterToolbar`、`SearchInput`、`ToolbarSelect`；普通按钮和白底边框卡片优先使用 `Button`、`Card`。不要在每个页面重复写同一套 `rounded-lg border border-slate-200 bg-white`、搜索框和 select class，除非该元素是媒体卡、表格行或有特殊布局。

前端性能约定：项目总览、任务队列、片段资产和音乐库搜索输入使用 `useDebouncedValue()` 做 300ms debounce，避免每个字符触发请求或大列表过滤；`useTaskList()` / `useTasks()` 的轮询根据任务活跃度动态切换，存在处理中/等待中任务时 5s，全部完成/失败时 30s；Review/Music/Assets/Diagnostics 页面的大列表派生数据优先用 `useMemo`，避免 render 时重复 filter/map/reduce。

后端列表性能约定：`uploads/index.sqlite3` 是 SQLite 读模型，只做 `/api/tasks` 和 `/api/assets/clips` 的列表索引缓存，不是主存储。真实数据仍以 `uploads/<task_id>/state.json`、`meta.json`、`settings.json`、`review.json`、`clips/*_meta.json`、`commerce/<segment_id>/*.json` 为准。SQLite 连接必须启用 `PRAGMA journal_mode=WAL;`、`PRAGMA synchronous=NORMAL;`、`PRAGMA busy_timeout=5000;`、`PRAGMA foreign_keys=ON;`；索引缺失或 schema 版本变化时可从 uploads 全量重建，查询异常必须回退文件扫描。列表查询的 SQL LIKE 关键字必须转义 `%` / `_` 并声明 `ESCAPE '\\'`；API 进程内缓存索引 ready 状态，避免每次查询都重复 schema 检查。上传、状态流转、复核保存、任务删除、单片段重导出、AI 商品素材 job 更新时刷新对应 task 的索引。

后端接口缓存约定：当前只使用 API 进程内缓存，不引入 Redis 缓存。`/api/system/resources` 使用 3 秒 TTL；`/api/tasks/{id}/summary`、`/diagnostics`、`/events`、`/review`、`/api/tasks/{id}/clips` 和 `/api/music/library` 使用文件 mtime/size 指纹缓存。缓存只保存接口组装结果，相关 JSON、clips、covers 或音乐库文件变化后必须自动失效；不要缓存写接口、ZIP 下载流或上传结果。

后端通用工具约定：任务目录、索引、音乐库和 AI 商品素材相关 JSON 文件读写统一使用 `app.utils.json_io.read_json()` / `read_json_silent()` / `write_json()`；新增 API 不要再裸写 `json.loads(path.read_text())` 或 `path.write_text(json.dumps(...))`。静默 fallback 读取用 `read_json_silent()`，不要在每个模块重复封装 `_read_json()`。`write_json()` 使用同目录临时文件 + `os.replace()` 原子写入；如需 `json.dumps(..., default=str)` 这类非原生 JSON 类型转换，使用 `write_json(..., json_default=str)`。任务 ID、片段 ID、图片文件名和安全任务目录名校验统一从 `app.api.validation` 导入，不要重复定义 `_TASK_ID_RE` / `_SEGMENT_ID_RE` / `_CLIP_NAME_RE`。上传根目录和用户 BGM 目录统一从 `app.config.UPLOAD_DIR` / `USER_BGM_DIR` 获取，不要硬编码 `/app/uploads`。任务 API 路由保持在 `app.api.tasks`，但任务摘要、诊断、事件和复核 payload 组装放在 `app.api.task_helpers`，不要再把这类纯组装逻辑堆回 `tasks.py`。

AI 商品素材设置位于设置页 **AI 服务** 页签内，但必须和剪辑 VLM 上下分成两个独立面板：上方为剪辑 VLM/导出模式，下方为 **AI 商品素材**。商品素材配置独立于剪辑流水线 VLM/LLM，并且在 AI 商品素材面板内继续分成 **Gemini 商品识图** 和 **OpenAI Image 生图** 两个子块：`commerce_gemini_api_base/model/api_key/timeout` 用于 Gemini 封面识图和抖音/淘宝文案生成，默认 `https://generativelanguage.googleapis.com` + `gemini-3-flash-preview`；`commerce_image_api_base/model/api_key/size/quality/timeout` 用于 OpenAI Image 生图，默认 `https://api.openai.com/v1` + `gpt-image-2` + `2K`。后端会把 `commerce_image_size=2K` 解析为 `2048x2048` 发送给 OpenAI Images；`commerce_gemini_api_key` 和 `commerce_image_api_key` 是敏感字段，上传时只写入 `secrets.json`。

AI 商品素材后端接口：`GET /api/commerce/clips/{task_id}/{segment_id}` 返回工作台数据和异步 job 状态；`POST /api/commerce/clips/{task_id}/{segment_id}/analyze` 提交 Gemini `generateContent` 封面识图任务并写 `product_analysis.json`；`POST /api/commerce/clips/{task_id}/{segment_id}/copywriting` 提交 Gemini 文案任务并写 `copywriting.json`；`POST /api/commerce/clips/{task_id}/{segment_id}/images` 提交 OpenAI Image `/images/edits` 任务，以片段封面作为参考图生成正面、侧面、背面/细节和淘宝详情页示例图，写入 `commerce/<segment_id>/images/` 与 `images.json`；`POST /api/commerce/clips/{task_id}/{segment_id}/images/{item_key}` 支持单张图独立重试，`item_key` 限 `model_front` / `model_side` / `model_back` / `detail_page`；`POST /api/commerce/batch` 支持片段资产页批量提交 `analyze` / `copywriting` / `images`，前端提交后用右侧队列抽屉展示 accepted/rejected。

片段视频有两个用途不同的接口：`/api/clips/{task_id}/{clip_name}/download` 保持下载语义；`/api/clips/{task_id}/{clip_name}/preview` 返回 inline MP4，前端工作台和预览型播放器应优先使用 `preview_url`，避免点击视频时下载到本地。

错误和成功提示约定：前端必须使用自定义 toast 或已有页面组件，不使用浏览器原生 alert/confirm。后端英文异常不能直接展示给用户，前端统一经过 `userFacingMessage()` 转成中文；商品素材工作台的异步 job 错误用 toast 提示，页面只保留中文状态说明。

字幕编辑采用覆盖草稿机制：前端复核抽屉的字幕草稿保存到 `review.json` 的 segment override（`subtitle_overrides`），不修改原始 `transcript.json`。字幕覆盖的 `start_time/end_time` 是源视频绝对秒，不是片段内相对秒；前端保存时保留 2 位小数并过滤空文本、结束时间不大于开始时间的行。后端会限制 `subtitle_overrides` 行数、单行长度、总文本量并拒绝 ASS 控制字符；`process_clips._collect_clip_subtitle_segments()` 对历史脏数据再做防御性清洗。`reprocess_clip` 会通过 `_load_review_segment()` 合并 override，优先使用 `subtitle_overrides` 生成字幕并单片段重导出。

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
  - `subtitle_position`: `top` / `middle` / `bottom` / `custom`
  - `custom_position_y`: 0-100 的纵向百分比，`custom` 时由设置页预览区拖拽写入；basic/styled 通过 FFmpeg `force_style` 生效，karaoke ASS 通过动态 `Alignment/MarginV` 生效
  - `subtitle_font_size`: 普通字幕字号，默认 `60`，basic/styled 通过 FFmpeg `force_style` 生效，karaoke 用作 Default 样式字号
  - `subtitle_highlight_font_size`: karaoke 逐字高亮层字号，默认 `72`
  - `subtitle_template`
- 语气词过滤：`filter_filler_mode`：`off` / `subtitle` / `video`
  - `off`：不过滤（默认）
  - `subtitle`：仅从字幕中删除语气词
  - `video`：从字幕删除语气词 + 裁剪掉语气词对应的短视频段
- 敏感词过滤：
  - `sensitive_filter_enabled`：是否开启（默认关闭）
  - `sensitive_words`：用户自定义词库，最多 200 个词，后端会去空、去重并跳过超长词
  - `sensitive_filter_mode`：`video_segment`（默认，裁掉命中字幕句对应视频段）/ `drop_clip`（命中即跳过整个 clip）
  - `sensitive_match_mode`：`contains`（默认，包含匹配）/ `exact`（整句精确匹配）
- 封面策略：`cover_strategy`：`content_first` / `person_first`
  - `content_first`（默认）：优先选择突出商品/服装的帧作为封面
  - `person_first`：优先选择突出主播人脸的帧作为封面
- 视频倍速：`video_speed`：0.5 / 0.75 / 1.25（默认）/ 1.5 / 1.75 / 2 / 3
  - FFmpeg 滤镜顺序：先烧录字幕再变速，字幕与语音时序保持一致
  - 视频：`setpts=PTS/{speed}`，音频：`atempo` 链（>2x 时链式拼接）
- 换衣检测融合：
  - `change_detection_fusion_mode`：`any_signal`（默认，保持旧逻辑）/ `weighted_vote`
  - `change_detection_sensitivity`：`conservative` / `balanced`（默认）/ `sensitive`，只影响 `weighted_vote`
  - `clothing_yolo_confidence`：服装 YOLO 检测阈值，默认 `0.25`
- FFmpeg 编码：
  - `ffmpeg_preset`：`veryfast` / `fast`（默认）/ `medium`
  - `ffmpeg_crf`：18-32，默认 `23`
  - 设置页新增项必须保留 hover tooltip，解释速度、画质、召回和误切 tradeoff；高级参数面板默认展开
- LLM 文本分析：`enable_llm_analysis`：是否开启（默认关闭）
  - `llm_type`：API 类型 `openai`（默认）/ `gemini`（预留）
  - `llm_api_key` / `llm_api_base` / `llm_model`：独立的 LLM 配置（不与 VLM 共用）
  - 在 ASR 转写完成后，用 LLM 分析 transcript 文本识别换品边界，与视觉检测信号融合
- 切分粒度：`segment_granularity`：`single_item`（默认）/ `outfit`
  - `single_item`：把搭配中的每件单品（毛衣、裙子、背心等）各切成一段
  - `outfit`：整套搭配合为一段
- 导出分辨率：`export_resolution`：`1080p`（默认）/ `4k` / `original`
- 句边界对齐：`boundary_snap`：`true`（默认）/ `false`
  - 将 clip 起止时间对齐到 ASR 句子边界，避免截断半句话
  - 对齐后自动裁剪首尾孤立单字（如"的"、"了"），确保片段时长 ≥ min_duration
- LLM 边界精修：`enable_boundary_refinement`：`false`（默认）/ `true`
  - 用 LLM 审查每个片段的起止边界，确保开头完整独立、结尾自然不截断
  - LLM 返回的调整建议自动 snap 到实际 ASR 句子边界（防时间戳幻觉）
  - 允许与相邻段重叠几秒（每段独立审查）
  - 需要开启 LLM 文本分析并配置 LLM API Key
  - 失败时静默跳过，不阻塞管线
- BGM 设置：
  - `bgm_enabled`：是否开启背景音乐（默认 `true`）
  - `bgm_volume`：BGM 音量（0-1，默认 0.25）
  - `original_volume`：原声音量（0-2，默认 1.0）
- ASR 设置：
  - `asr_provider`：`dashscope` / `volcengine` / `volcengine_vc`（默认 `volcengine_vc`）
  - `asr_api_key`：ASR API Key（火山引擎共用）
  - TOS 配置：`tos_ak` / `tos_sk` / `tos_bucket` / `tos_region` / `tos_endpoint`

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

Celery stage 重试中不要提前把 `state.json` 写成 `ERROR`；只有达到最终重试失败时才通过 `PipelineErrorHandler` 写失败状态，避免前端出现 `ERROR → PROCESSING` 闪烁。Stage 间通信以任务目录文件为准，Celery chain 返回值不作为下游输入。

### 4. 结果展示

任务完成后，前端请求 `/api/tasks/{task_id}/clips` 获取片段列表，展示：

- 视频片段
- 缩略图
- 时长
- 商品名
- 下载入口

### 5. 历史记录

用户可以点击导航栏的"项目总览"查看所有历史任务。

- 后端：`GET /api/tasks` 分页接口（offset/limit + q 搜索 + 状态过滤；`status=processing` 聚合处理中状态；返回 summary 状态计数和 clip 总数）
- 后端：`GET /api/assets/clips` 分页接口（offset/limit + q 搜索 + status 复核状态 + duration 时长过滤；返回筛选后 total 和 summary）
- 后端：`uploads/index.sqlite3` 是上述两个列表接口的 SQLite 索引缓存；不要把 transcript/review 全量内容迁入 SQLite，不要用 SQLite 替代任务目录 JSON 真源。
- 后端：`DELETE /api/tasks/{task_id}` 删除任务
- 前端：`ProjectManagementPage.tsx` 项目切换中心，支持分页、搜索、状态筛选、右侧详情抽屉、复核/资产/诊断快捷入口、删除
- 前端：`QueuePage.tsx` 采用队列流 + 可关闭右侧任务详情抽屉，窄屏切换为任务卡片 + 遮罩抽屉；抽屉概览按设计图组织为任务摘要、进度信息卡、阶段 checklist 和最近日志；当前阶段字段统一转中文展示，操作列使用固定图标按钮；详情内切换概览、日志、资源；删除必须使用自定义确认弹窗。
- 前端：`ReviewPage.tsx` 采用方案 C 卡片网格 + 右侧复核抽屉；字幕页签支持字幕文本和起止秒覆盖，保存后可触发单片段重导出。注意不要直接改 `transcript.json`，必须通过 `subtitle_overrides` 保持原始 ASR 可追溯。
- 前端：`AssetsPage.tsx` 采用项目分组卡片 + 右侧片段详情抽屉 + 底部批量选择条；“AI素材”入口必须新标签打开独立工作台；批量 AI 素材提交成功后打开右侧队列抽屉展示已排队和失败项；批量 ZIP 下载单次最多 20 个片段，超过时前端禁用下载并提示限制。
- 前端：`MusicPage.tsx` 采用设计图式指标卡 + 曲目表格 + 覆盖式右侧标签编辑抽屉 + 全宽底部播放器；抽屉不挤占列表宽度，列表拆分来源、时长、Mood、商品分类和居中操作列；Mood/商品分类前端中文展示但保存值保持英文；内置曲目只读，用户上传曲目可编辑和删除。
- 前端：`DiagnosticsPage.tsx` 采用设计图式诊断仪表盘：顶部项目工具栏、紧凑指标卡、横向流水线耗时、Recharts 漏斗图、右侧异常建议/事件详情和分页事件日志；窄屏下指标与流水线自动降密度展示，事件详情展示完整消息、阶段、级别、文件来源和处理建议。
- 上传时 `meta.json` 记录 `created_at`（ISO 时间戳）和 `original_filename`
- 老任务这两个字段为空，前端用"—"显示


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
- 写出 `frames/frames.json` 预抽帧索引（含 path/timestamp/scene_idx），供导出阶段封面选择复用
- 用 ClothingChangeDetector（五信号联合：YOLO 品类变化 + MediaPipe 像素分割 + 全帧 HSV + 分区域 HSV（上身/下身）+ ORB 纹理）检测换衣节点
- 默认五信号各自独立走 EMA 平滑，任何一个信号的 EMA 低于阈值即可触发换衣检测；如果 `change_detection_fusion_mode=weighted_vote`，则按品类、上身 HSV、下身 HSV、纹理、全局 HSV 加权投票，并根据 `change_detection_sensitivity` 决定进入阈值
- 帧分析可使用 `resource_detector.calculate_parallelism()["frame_workers"]` 并行，每个 worker 线程持有自己的 ClothingSegmenter，避免 MediaPipe/ONNX session 跨线程共享；分析失败帧标记为缺失信号，不再写均匀直方图
- 写出 `scenes/person_presence.json`（每帧人物出现标记，用于下游空镜过滤）
- 产出 `candidates.json` 和 `scenes.json`

### 2) vlm_confirm

根据导出模式决定是否走 VLM：

- `smart`：走 VLM 确认
- `no_vlm`：跳过 VLM
- `all_candidates`：导出所有候选
- `all_scenes`：导出所有场景

VLM API Key 不通过 Celery 消息参数传递；`vlm_confirm` worker 执行时必须从任务目录 `secrets.json`/`settings.json` 或环境变量读取。`all_candidates` / `all_scenes` / `no_vlm` 不需要实例化 VLM client。

### 3) enrich_segments

做这些事：

- 整体转写，写出 `transcript.json`
- 只有字幕开启、LLM 文本分析开启，或敏感词过滤开启且词库非空时才执行 ASR；`all_candidates` / `all_scenes` 也必须遵守 `_need_asr(settings)`，避免没有下游文本需求时浪费 ASR 费用
- LLM 文本分析（如果 `enable_llm_analysis` 开启）：用 LLM 分析 transcript 识别换品边界，产出 `text_boundaries.json`
- 信号融合（`segment_fusion.py`）：**两层树架构**
  - Level 0（Outfit Period）：视觉 candidates 定义换装区间，每个 visual candidate 是两个 outfit period 的边界
  - Level 1（Product Discussion）：LLM text boundaries 按最大重叠度嵌套进 Level 0 区间
  - 导出粒度由 `segment_granularity` 控制：
    - `single_item` → 展平到 Level 1（每个商品讨论段一个视频）
    - `outfit` → 展平到 Level 0（每套搭配一个视频，合并所有子商品）
  - 无视觉信号时退化为单层（整个视频是一个 outfit period）
  - 无 LLM 信号时退化为单层（每个 visual candidate 自成一个 segment）
- 融合后分段重建（如果融合成功）：`fused_to_segments()` 将融合结果转为 segments，替换 VLM segments
  - 融合 candidates 带 `region_start_time`（LLM 区间起点），避免片段起点被视觉候选点 timestamp 截短
  - 未开启 LLM 或融合失败时退回用原始 VLM segments（行为不变）
- 句边界对齐（`boundary_snapper.py`，默认开启）：将 segment 起止时间 snap 到 ASR 句子边界
  - 起点对齐到第一个 `start_time >= segment.start` 的句子
  - 终点对齐到最后一个 `end_time <= segment.end` 的句子
  - 自动裁剪首尾孤立单字（确保时长 ≥ min_duration）
  - snap 后时长不足时回退到原始边界
- LLM 边界精修（`boundary_refiner.py`，默认关闭，需开启 LLM 文本分析）：用 LLM 审查片段起止边界
  - 提取每个 segment 起止 ±15s 的 ASR 句子作为上下文
  - LLM 判断开头是否完整独立（避免语气词/残句）、结尾是否自然
  - 返回的 adjusted_start/end 自动 snap 到最近的真实 ASR 句子边界（10s 容差）
  - 调整后时长 < min_duration 则回退
  - 失败时静默跳过（retry 2 次），不阻塞管线
- 换衣检测增强：
  - 多信号独立 EMA：全局 HSV、上身 HSV、下身 HSV、ORB 纹理各自独立走 EMA 平滑，任何一个信号的 EMA 低于进入阈值即触发检测，所有信号恢复到退出阈值以上才结束
  - 纹理信号取反处理：`(1.0 - tex_sim)`，进入阈值 0.6，退出阈值 0.7
  - 品类变化（YOLO 46类）不再单独触发候选，必须同时有至少一个视觉佐证信号（HSV 下降 / 分区域 HSV 下降 / 纹理变化），过滤主播拿放物品误触
- 商品名匹配
- 分段合法性校验
- 产出 `enriched_segments.json`

### 4) process_clips

这是最终导出阶段，会：

- 为每个 clip 重新从 `transcript.json` 裁对应字幕
- 生成 `.srt` 或 `.ass`
- 调用 FFmpeg 烧录字幕并导出 mp4
- 敏感词过滤在导出阶段基于裁好的字幕句执行：`video_segment` 会把命中的整句字幕和对应视频段一起裁掉，`drop_clip` 会跳过该 clip
- BGM 自动选曲（`bgm_selector.py`）：双库架构（内置+用户上传），基于商品类型和 mood 匹配，用户曲目优先，跨 clip 去重避免重复
- 封面选择：根据 `cover_strategy` 最多评分 30 帧；优先复用 `visual_prescreen` 已抽帧，预抽帧不足时再用 FFmpeg 补足候选，评分选出最佳封面
- 生成缩略图（保存到 `covers/clip_xxx.jpg`）
- 空镜过滤：读取 `scenes/person_presence.json`，两层过滤：(1) 段内人物出现率 < 60% 丢弃；(2) 开头连续无人 ≥ 8 秒丢弃；缺文件时不过滤
- 写 `clip_xxx_meta.json`
- 导出完成后递归清理临时 `frames/` 目录（包含 `frames.json` 和 `scene000/frame_*.jpg`），避免抽帧文件长期占用磁盘

**并发处理**：使用 `ThreadPoolExecutor` 并行处理多个 clip，并发数由 `resource_detector.py` 根据容器 cgroup 资源动态计算（4GB 容器默认 2 workers）


## 并发处理与性能优化（resource_detector.py）

### 资源检测

`resource_detector.py` 在 Docker 容器内通过 cgroup v2 实时检测资源：
- CPU：读 `/sys/fs/cgroup/cpu.max`
- 内存：读 `/sys/fs/cgroup/memory.max`
- 计算公式：`clip_workers = min(cpu_cores, (mem - 2.0GB) / 0.6GB, 4)`，`frame_workers` 上限为 3；4GB 容器实测通常约 3 个 clip workers

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
- `--max-tasks-per-child=100` — 处理 100 个任务后回收进程（避免内存高水位泄漏）
- `--max-memory-per-child=3000000` — 3GB 内存上限后回收（4GB 容器的 75%）
- `--prefetch-multiplier=1` — 只拉取 1 个任务（长耗时任务必须设 1）
- `-Ofair` — 公平调度

### 实测数据（20 分钟直播视频，9 clips）

| 阶段 | 串行 | 并行 2w + FFmpeg 优化 | 改善 |
|------|------|---------------------|------|
| process_clips | 276s | **195s** | **-29%** |
| visual_prescreen | 336s | 269s | 不稳定（受系统负载影响） |

### 最新性能基准（2026-04-26）

同一条 20 分钟 1080x1920 直播视频：

| 场景 | 关键结果 |
|---|---|
| 本地隔离链路（VLM/ASR/LLM/BGM/字幕关闭） | 封面选择平均约 `20.16s → 15.87s/clip`，子阶段约 -21%；总耗时受 FFmpeg 负载波动影响，不能直接宣称端到端加速 |
| 完整链路（smart + VLM + volcengine_vc + karaoke + LLM + BGM） | 监控总耗时约 600s；主要瓶颈为 `process_clips=285.08s` 和视觉抽帧+检测约 211.74s |

基准报告：`.gstack/benchmark-reports/2026-04-26-pipeline-benchmark.md`


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
1. 将要删除的段反转为 `keep_ranges`（要保留的段）；语气词 `filler_cut_ranges` 会和敏感词 `sensitive_cut_ranges` 先合并、排序、去重叠
2. 对每个 keep range 用 FFmpeg `trim/atrim` 提取，`setpts=PTS-STARTPTS` 重置时间戳
3. `concat=n=N:v=1:a=1` 拼接所有保留段
4. 在拼接后的视频上烧字幕、变速、混 BGM
5. 整个过程单条 FFmpeg 命令，无中间临时文件


## 敏感词过滤（sensitive_filter.py）

敏感词用于规避违规口播内容，词库由用户在设置页维护，上传任务时写入 `settings.json`：

- `contains`：只要字幕句包含任一敏感词即命中，适合常规风控词库
- `exact`：字幕句文本完全等于敏感词才命中，适合精确屏蔽短词
- `video_segment`：计算命中字幕句的 `start_time/end_time`，导出时裁掉整句视频段，并从字幕文件中移除该句
- `drop_clip`：任一字幕句命中即跳过整个 clip，不生成该片段

敏感词过滤依赖 transcript，所以即使字幕关闭，只要敏感词过滤开启且词库非空，`enrich_segments` 仍会执行 ASR。后端当前按字幕句切除，不做单词级静音或只删局部词，避免音画和字幕时序错位。


## BGM 自动选曲（bgm_selector.py）

双库架构：内置曲库（开发者预置）+ 用户曲库（前端上传），用户曲目优先选曲。

### 音乐库结构

- **内置曲库**
  - 索引文件：`backend/assets/bgm/bgm_library.json`
  - 音频文件：`backend/assets/bgm/*.mp3`
- **用户曲库**（前端上传）
  - 索引文件：`uploads/bgm_library/library.json`（Docker volume）
  - 音频文件：`uploads/bgm_library/user_xxxxxxxx.mp3`
- 前端浏览/管理页：`/music` 路由 → `MusicPage.tsx`

### 选曲逻辑

1. `BGMSelector.with_user_library()` 加载内置库后再加载用户库，用户曲目 prepend 到列表（优先选）
2. 从 segment 的 `product_type` 或 `product_name` 推断商品类型
3. 从 `category_defaults` 映射获取首选 mood 列表
4. 在合并曲库中筛选 category 或 mood 匹配的曲目
5. 跨 clip 去重（`used_bgm_ids`），优先选未使用的
6. 无匹配时 fallback 到全曲库；曲库为空时 fallback 到 `default_bgm.mp3`
7. `_resolve_track_path()` 先查用户目录再查内置目录

### 音乐库 API

- `GET /api/music/library` — 返回合并曲目列表（含 `source: "user" | "built-in"` 标记）
- `POST /api/music/upload` — 上传 MP3（mutagen 校验 + 提取时长），返回曲目对象并自动弹出标签编辑
- `PATCH /api/music/{track_id}` — 编辑用户曲目标签（title/mood/categories/tempo/energy/genre）
- `DELETE /api/music/{track_id}` — 删除用户曲目（含 MP3 文件），仅限用户曲目
- `GET /api/music/{track_id}/audio` — 返回 MP3 音频文件（用户目录优先，fallback 到内置目录）

### 前端音乐库管理

- 拖拽上传（.mp3 only, 20MB limit, XHR progress）
- 上传后自动弹出标签编辑模态框（title, mood×12, categories×10, tempo, energy）
- 分段列表："我的音乐" + "内置曲目"
- 来源标记："我的"(蓝) vs "内置"(灰)
- 编辑/删除按钮（仅用户曲目可操作）

### 扩充内置音乐库

将 MP3 文件放入 `backend/assets/bgm/`，在 `bgm_library.json` 的 `tracks` 数组中追加条目，Docker 重建后生效。


## 封面选择策略（cover_selector.py）

从 clip 中采样最多 30 帧进行评分，选最佳帧作为缩略图。导出阶段会优先复用 `visual_prescreen` 的预抽帧；如果预抽帧数量不足，再用 FFmpeg 补足候选，避免因为 0.5fps 抽帧太稀导致封面质量下降。

### 评分算法

**质量分**（所有策略都会算，作为乘法基数）：
- 清晰度（Laplacian variance）50% + 对比度（std dev）30% + 亮度（钟形曲线 ideal=130）20%

**语义分**（按策略选择）：
- `content_first`（默认）：商品 bbox 面积比(cap 0.5) 35% + 置信度 25% + 三分法距离 20% + 局部清晰度 20%
- `person_first`：人脸面积比 40% + 中心距 25% + 人脸置信度 20% + 清晰度 15%

**最终得分** = 语义分 × 质量分 × 遮挡惩罚。无信号时 fallback 到 clip 中点。

### 遮挡检测

使用第二个 YOLO 模型（COCO YOLOv8n，80类）检测遮挡物：
- 检测类别：cell phone (67)、laptop (63)、remote (66)、book (73)、clock (74)、vase (75)
- 检测到遮挡物 bbox 与服装 bbox 重叠 >30% → 遮挡惩罚 = 0.1（大幅降权但不完全排除）
- 无服装 bbox 时（person_first 策略），只要画面中有遮挡物即触发惩罚
- 模型懒加载，缺失时自动跳过（不影响现有流程）

### 依赖模型

- `content_first` 复用已有 YOLO 46类 ONNX（通过 ClothingSegmenter.detect_clothing_items）
- `person_first` 用 MediaPipe FaceDetection（已有依赖 mediapipe>=0.10.14）
- **遮挡检测** 用 COCO YOLOv8n ONNX（`backend/assets/models/yolov8n.onnx`，12.3MB，80类）


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
- karaoke 的 ASS header 会根据 `subtitle_position/custom_position_y` 动态生成 `Alignment/MarginV`，和 basic/styled 的 FFmpeg `force_style` 位置逻辑保持一致
- 字幕字号由 `subtitle_font_size` / `subtitle_highlight_font_size` 控制；设置页右侧 9:16 直播演示图使用 `frontend/public/images/subtitle-preview-live-demo.png`

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
- `backend/app/api/tasks.py`           # 任务路由（CRUD + WebSocket + 诊断 + 审核 + 重试 + 重处理）
- `backend/app/api/task_helpers.py`    # 任务摘要 / 诊断 / 事件 / 复核 payload 组装
- `backend/app/api/clips.py`           # 片段列表 / 下载 / 批量下载 / 缩略图
- `backend/app/api/settings.py`
- `backend/app/api/music.py`
- `backend/app/api/commerce.py`
- `backend/app/api/assets.py`          # 跨任务素材资产浏览
- `backend/app/api/system.py`          # 系统资源监控
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
- `backend/app/services/text_segment_analyzer.py`
- `backend/app/services/segment_fusion.py`
- `backend/app/services/boundary_snapper.py`
- `backend/app/services/boundary_refiner.py`
- `backend/app/services/bgm_selector.py`

### 前端

- `frontend/src/App.tsx`               # 入口，渲染 AdminDashboard
- `frontend/src/components/AdminDashboard.tsx`  # 主应用壳（330 行，8 页状态机）
- `frontend/src/components/admin/`     # 拆分后的子模块
  - `api.ts`                           # API 调用封装
  - `types.ts`                         # 类型定义（PageKey 等）
  - `format.ts`                        # 格式化工具
  - `constants.tsx`                    # 常量
  - `shared.tsx`                       # 共享 UI 组件
  - `settings/`                        # 设置页分组组件、labels、通用表单控件
  - `pages/`                           # 9 个页面组件
    - `ProjectManagementPage.tsx`      # 项目管理
    - `CreateProjectPage.tsx`          # 创建任务
    - `QueuePage.tsx`                  # 任务队列
    - `ReviewPage.tsx`                 # 片段审核
    - `AssetsPage.tsx`                 # 素材资产
    - `CommerceWorkbenchPage.tsx`      # AI 商品素材工作台
    - `MusicPage.tsx`                  # 音乐库
    - `DiagnosticsPage.tsx`            # 诊断
    - `SettingsPage.tsx`               # 设置容器
- `frontend/src/components/UploadZone.tsx`
- `frontend/src/components/SettingsPage.tsx`   # 独立设置页（备选入口）
- `frontend/src/components/MusicPage.tsx`      # 独立音乐页（备选入口）
- `frontend/src/components/HistoryPage.tsx`    # 独立历史页（备选入口）
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
- `uploads/<task_id>/frames/frames.json`（临时预抽帧索引，process_clips 完成后清理）
- `uploads/<task_id>/frames/scene000/frame_*.jpg`（临时预抽帧，process_clips 完成后清理）
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
pytest tests/
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
  - `yolov8n.onnx`（COCO YOLOv8n，12MB，80类，仅封面遮挡检测用）
  - Docker 构建时通过 `COPY assets/` 打包进镜像
  - 模型来源：MediaPipe 从 Google GCS 下载，Fashionpedia YOLO 从 HuggingFace 下载（国内需代理），COCO YOLO 从 ultralytics 导出
- `frame_sample_fps` 默认值已改为 `0.5`（float 类型），原来 `2` 导致帧数过多、处理慢且容易 OOM
- `visual_prescreen` 的预抽帧会暂存到 `frames/frames.json` + `frames/scene000/`，`process_clips` 封面选择优先复用这些帧；候选不足时才额外 FFmpeg 补采样，导出结束后递归清理整个 `frames/` 目录
- `cover_selector.py` 的 ClothingSegmenter、MediaPipe FaceDetection、COCO YOLO ONNX session 是全局懒加载单例，初始化必须用线程锁保护；`process_clips` 会用 ThreadPoolExecutor 并行处理多个 clip
- 换衣检测的帧分析会在处理前 resize 到 640px 以降低内存占用
- 新增依赖 `mediapipe>=0.10.14`（在 requirements.txt 中）
- 换衣检测已从三信号升级到五信号：YOLO 品类变化 + MediaPipe 像素分割 + 全帧 HSV + 分区域 HSV（上身/下身，用 YOLO bbox 区分 UPPER_BODY_CLASSES / LOWER_BODY_CLASSES）+ ORB 纹理（上身 bbox 裁剪后提取描述子）
- 换衣检测 EMA 已升级为多信号独立触发：全局 HSV、上身 HSV、下身 HSV、纹理各自独立走 EMA 平滑，任何一个信号 EMA 低于阈值即可触发，所有信号恢复才结束。`hist_debug.json` 新增 `ema_global`、`ema_upper`、`ema_lower`、`ema_texture` 字段
- 空镜过滤：`person_presence.json` 由换衣检测写入 `scenes/` 目录，`process_clips` 从 `scenes/person_presence.json` 读取；两层过滤：(1) 整体出现率 < 60% 丢弃；(2) 开头连续无人 ≥ 8 秒丢弃
- `hist_debug.json` 新增 `upper_correlations`、`lower_correlations`、`texture_similarities` 字段
- `analyze_frame()` 返回值已扩展：`{mask, items, hsv_hist, upper_hsv_hist, lower_hsv_hist, orb_descriptors}`
- 融合修复：fused candidates 带 `region_start_time` 字段，`fused_to_segments()` 优先用 LLM 区间起点避免片段被截短
- 前端设置页面：ASR/LLM 关闭时折叠子配置，VLM 导出模式非 smart 时折叠 VLM 子配置
- BGM 自动选曲基于双库架构（内置 `backend/assets/bgm/` + 用户上传 `uploads/bgm_library/`），用户曲目优先选曲
- 音乐库管理：前端 `/music` 页面支持拖拽上传 MP3、编辑标签、删除用户曲目；后端 `music.py` 提供 upload/patch/delete/library/audio 五个 API
- 用户曲目存储：`uploads/bgm_library/user_{uuid}.mp3` + `library.json`（Docker volume 持久化）
- `BGMSelector.with_user_library()` 加载双库，`_resolve_track_path()` 先查用户目录再查内置目录
- FFmpeg `amix` 滤镜已加 `normalize=0:dropout_transition=0`，修复语音被自动降低音量的 bug
- `bgm_enabled=False` 时跳过 BGM 输入和 amix 混音，FFmpeg 命令不含 bgm 相关参数
- `process_clips` 新增单片段重处理支持：`POST /api/tasks/{id}/clips/{segment_id}/reprocess` 用于审核后重新导出单个片段
