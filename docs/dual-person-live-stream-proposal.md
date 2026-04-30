# 双人直播场景支持方案

> **状态**：调研完成，待实现
> **最后更新**：2026-04-30
> **关联文件**：`clothing_change_detector.py`、`clothing_segmenter.py`、`vlm_confirmor.py`、`visual_prescreen.py`

---

## 背景

当前换衣检测管线完全基于**单人直播**设计。五信号（YOLO 品类、MediaPipe 像素分割、全帧 HSV、分区域 HSV、ORB 纹理）全部在帧级别聚合，不区分画面中有几个人。当画面中出现双人（讲解+模特、双人试穿、双模特各自展示）时，信号会混杂，检测质量严重下降。

---

## 现状分析：双人场景下各信号表现

### ❌ 严重出错（High Impact）

| 信号 | 问题 | 根因 |
|------|------|------|
| MediaPipe 像素分割 | 只能分割一个人 | `selfie_multiclass_256x256.tflite` 是 "Selfie" 单人模型，双人画面产生不可靠混合 mask |
| 分区域 HSV（上身/下身） | 两个人的上衣混在一起 | `upper_mask` 把画面中**所有人**的上身区域 OR 到一起，颜色直方图混合 |
| ORB 纹理 | 只追踪一个人 | 代码取 confidence 最高的那件上衣提取纹理，可能帧间切换追踪对象 |

### ⚠️ 降质但不会崩溃（Medium Impact）

| 信号/模块 | 问题 | 影响 |
|-----------|------|------|
| YOLO 46 类检测 | 检测两人所有衣物，NMS 全局去重可能误删 | 品类变化混在一起，无法归人 |
| 全帧 HSV | 两人颜色混合成一个直方图 | 信号被稀释，灵敏度下降 |
| VLM 确认 | Prompt 说"主播"（单数），问"同一件衣服？" | 换衣检测准确但商品归属可能错 |
| LLM 文本分析 | ASR 单声道，两人语音混在一起；Prompt 假设单主播 | 双人同时说话时文本边界分析混乱 |

### ✅ 不受影响（Low Impact）

| 模块 | 原因 |
|------|------|
| 人物出现检测 (`person_present`) | 只判断 `len(items) > 0`，有人即可 |
| 信号融合 (`segment_fusion.py`) | 纯时间戳操作，不涉及人 ID |
| 封面选择 | 本身取最佳分数，天然支持多人 |
| 空镜过滤 | 二元判断"有没有人" |

---

## 三种典型双人场景

### 场景 A：一个讲解 + 一个模特

**描述**：主播讲解商品，模特穿衣服展示。

| 维度 | 当前表现 | 目标 |
|------|----------|------|
| 换衣信号 | 检测到"有人换了"但不知道是模特 | 只看模特的视觉变化 |
| 语音信号 | 两人声音混合 | 只关注讲解者的语音做文本边界 |
| 切分依据 | 混杂 | 模特换衣 OR 主播说到新商品 |

**关键缺失**：无法区分"谁在换衣"。

### 场景 B：双人穿同款不同色

**描述**：两人各穿一套搭配的不同颜色版本。

| 维度 | 当前表现 | 目标 |
|------|----------|------|
| 品类检测 | 两人品类相同，变化检测可能失效 | 分人品类追踪 |
| 颜色信号 | HSV 混合，颜色变化被稀释 | 分人 HSV 直方图 |
| 纹理信号 | 可能随机切换追踪对象 | 分人纹理追踪 |

**关键缺失**：品类相同但颜色不同时，需要分人追踪颜色变化。

### 场景 C：双人各自展示不同商品

**描述**：两个模特同时展示完全不同的商品，独立换衣。

| 维度 | 当前表现 | 目标 |
|------|----------|------|
| 换衣事件 | 两人候选点混杂 | 分人独立的换衣时间线 |
| clip 切分 | 混乱，可能一个 clip 混两件商品 | 每人独立产生候选，union 合并 |

**关键缺失**：分人独立的换衣时间线。

---

## 业界调研

### 平台现有做法

| 平台 | 做法 | 局限 |
|------|------|------|
| 抖音/TikTok Shop | ASR 语音内容驱动切分（识别关键词） | 双人同时说话无法区分 |
| 淘宝直播"智慧剪" | CLIP 多模态对齐（语音+文字+画面） | 公开信息未提分人处理 |
| 天池淘宝直播商品识别赛 | EfficientNet + ArcFace 商品实例检索 | 关注"商品匹配"而非"分人追踪" |

**结论**：目前没有公开的"直播电商双人换衣检测"完整方案。各平台主要靠语音驱动，视觉分人做得很少。

### 技术路线调研

#### 多人追踪（MOT）

| 方案 | 特点 | 推荐度 |
|------|------|--------|
| **YOLO + ByteTrack**（via `supervision` 库） | 轻量，`pip install supervision` 即可，CPU 可跑 | ⭐⭐⭐⭐⭐ 首选 |
| **YOLO + BoT-SORT** | 多了 ReID 外观特征 + 摄像头运动补偿，抗遮挡更好 | ⭐⭐⭐⭐ 可选 |
| `roboflow/supervision` | Roboflow 出品，封装 ByteTrack，API 简洁 | ⭐⭐⭐⭐⭐ 推荐 |

#### 人员 ReID（跨帧身份保持）

| 模型 | 参数量 | 说明 |
|------|--------|------|
| **OSNet x0.25** | **0.197M（约 2MB ONNX）** | 超轻量，可部署到单片机，Phase 3 可选 |
| OSNet x0.5 | ~0.5M | 速度/精度平衡 |
| OSNet x1.0 | ~2.2M | 最高精度 |

**关键洞察**：用**人脸 + 身材**做人 ID（不依赖衣服），衣服特征单独做换衣检测。我们已有 MediaPipe FaceDetection（封面选择在用），可以复用。

#### 换衣 ReID（Cloth-Changing ReID，学术界前沿）

| 论文 | 方法 | 关键思路 |
|------|------|----------|
| FIRe-CCReID (TIFS 2024) | 身体部位 DBSCAN 聚类 | 用身材特征而非衣服特征识人 |
| Simple-CCReID (CVPR 2022) | 仅 RGB 模态 | 不需要额外传感器 |
| MSP-ReID (2026) | 发型鲁棒 | 用脸+身材，忽略头发/衣服 |

---

## 推荐技术方案

### 架构变化

```
当前管线:
  抽帧 → 全帧换衣检测(5信号) → VLM确认 → ASR+融合 → 导出
                        ↑ 单人假设：所有信号在帧级别聚合

改后管线:
  抽帧 → 人检测+追踪(ByteTrack) → 分人换衣检测(5信号×N人) → VLM确认 → ASR+融合 → 导出
               ↑ 新增：每人独立 bbox + track_id          ↑ 每人独立 EMA
```

**核心思路**：底层换衣检测逻辑（YOLO + HSV + ORB）本身是信号级的，不依赖单人假设——只要把输入从"全帧"变成"按人裁剪"，大部分代码可以原封不动复用。

### 实施路径

#### Phase 1：加人追踪层（1-2 天）

**改动范围**：`visual_prescreen.py`、`clothing_change_detector.py`

- 新增依赖：`pip install supervision`（~1MB）
- 抽帧后，先用 YOLO COCO person class（`yolov8n.onnx` 已有）检测人物 bbox
- `sv.ByteTrack` 分配每帧的持久化 track ID
- 每个 tracked person 的 bbox 裁剪后，独立送入 `ClothingSegmenter.analyze_frame()`
- 每人维护独立的 EMA 状态

```python
# 核心伪代码
import supervision as sv
tracker = sv.ByteTrack(track_activation_threshold=0.3, frame_rate=30)

for frame in frames:
    # 1. 检测人物
    person_dets = yolo_detect(frame, classes=[0])  # person class
    tracked = tracker.update_with_detections(person_dets)

    # 2. 分人分析
    for person_id, bbox in zip(tracked.tracker_id, tracked.xyxy):
        person_crop = frame[bbox[1]:bbox[3], bbox[0]:bbox[2]]
        analysis = clothing_segmenter.analyze_frame(person_crop)
        # 每人独立 EMA → 独立换衣检测
```

#### Phase 2：分人信号聚合（1 天）

**改动范围**：`clothing_change_detector.py`、`vlm_confirmor.py`

- 换衣候选点标记 `person_id`
- VLM 确认时，裁剪到对应 person 的 bbox 区域，避免另一人干扰
- 候选点来源可以是任意 person 的变化

#### Phase 3（可选）：人脸锚定 ID（0.5 天）

**改动范围**：新增 `person_tracker.py` 或在 `visual_prescreen.py` 内

- 复用已有的 MediaPipe FaceDetection
- 用人脸位置辅助 ByteTrack 保持 ID 一致性
- 解决换衣后 ID 跳变问题

#### Phase 4（可选）：说话人分离（2-3 天）

**改动范围**：ASR 客户端、`text_segment_analyzer.py`

- 火山引擎 ASR 支持 speaker diarization
- LLM 文本分析可区分"谁在说什么"
- 主讲解+模特场景下，只关注讲解者的语音做文本边界

### 依赖变化

| 新增 | 大小 | 必要性 | 说明 |
|------|------|--------|------|
| `supervision`（ByteTrack） | ~1MB | Phase 1 必须 | `pip install supervision` |
| OSNet ONNX（ReID） | ~2MB | Phase 3 可选 | 人脸不够时的后备 |
| 无需 GPU | — | — | ByteTrack + OSNet 都能在 CPU 跑 |

### 已有可复用资产

| 资产 | 复用方式 |
|------|----------|
| `yolov8n.onnx`（COCO 80类） | person class 检测，已有 |
| `yolov8n-fashionpedia.onnx`（46类） | 分人裁剪后做品类检测，已有 |
| `selfie_multiclass_256x256.tflite`（MediaPipe） | 分人裁剪后做像素分割，已有 |
| MediaPipe FaceDetection | 人脸锚定 ID，已有（封面选择在用） |
| HSV/ORB/EMA 全套逻辑 | 分人独立运行，代码不变 |

---

## 三种场景的推荐策略

| 场景 | 追踪策略 | 换衣检测策略 | 切分策略 |
|------|----------|-------------|----------|
| A：讲解+模特 | 追踪两人，人脸锚定 | 只看模特的视觉变化信号 | 模特换衣 OR 主播说到新商品 |
| B：同款不同色 | 追踪两人，分人 HSV | 分人颜色变化检测（品类相同但颜色不同） | 任一人颜色变化触发切分 |
| C：各自展示 | 追踪两人，独立时间线 | 分人完全独立的 5 信号检测 | 每人独立产生候选点，union 合并 |

---

## 风险与注意事项

1. **性能影响**：分人分析意味着每人独立跑一次 `analyze_frame()`，双人场景计算量约 2x。当前 0.5fps 抽帧频率下应该可接受。
2. **ByteTrack ID 跳变**：两人近距离互动（如并排展示）可能导致 ID 交换，Phase 3 的人脸锚定可缓解。
3. **裁剪质量**：bbox 裁剪可能不够精确，导致部分衣物在裁剪边界外。可适当扩大 bbox padding（如 10-15%）。
4. **单人场景兼容**：改动后必须保持单人场景行为不变。当画面中只有 1 个人时，退化为当前的帧级分析。
5. **VLM Prompt 更新**：Phase 2 需要调整 VLM prompt 以支持多人场景，但单人场景 prompt 也应保持工作。

---

## 参考资料

- [ByteTrack](https://github.com/ifzhang/ByteTrack) — 字节跳动，Tacked by byte-level association
- [BoT-SORT](https://github.com/NirAharon/BoT-SORT) — BoT-SORT: Multi-Object Tracking with ReID
- [roboflow/supervision](https://github.com/roboflow/supervision) — ByteTrack 封装库
- [OSNet](https://github.com/KaiyangZhou/deep-person-reid) — 轻量 ReID，0.197M 参数
- [FIRe-CCReID](https://github.com/QizaoWang/FIRe-CCReID) — 换衣场景 ReID (TIFS 2024)
- [FashionFormer](https://github.com/xushilin1/FashionFormer) — 时尚品类实例分割 (ECCV 2022)
