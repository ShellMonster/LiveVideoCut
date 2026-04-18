# 阿里云服饰分割 API 调研备忘

> **本文档为调研备忘，非当前实施计划。当前采用本地 MediaPipe + YOLO 方案。**

---

## 概述

阿里云视觉智能开放平台提供 **SegmentCloth（服饰分割）** API，能对图片中的人物服饰进行像素级分割。如果未来需要比本地 HSV 直方图检测更精确的换衣判断能力，可以考虑接入。

核心价值：像素级分割比直方图相关性判断更准确，能区分"换了上衣但外套没换"这类细节场景。代价是引入云端依赖和按量计费。

---

## API 详情

| 项目 | 内容 |
|------|------|
| API 名称 | SegmentCloth（服饰分割） |
| 所属平台 | 阿里云视觉智能开放平台 |
| 核心能力 | 像素级服饰分割，返回每个类别的 mask |
| 支持类别 | 7 类：上衣(tops)、外套(coat)、裙装(skirt)、裤装(pants)、包类(bag)、鞋子(shoes)、帽子(hat) |
| 图片限制 | ≤ 3MB，分辨率 50×50 ~ 3000×3000，格式 PNG/JPG/JPEG/BMP |
| QPS 限制 | 5（免费额度内可能更低） |

---

## 定价

阶梯计费，按月累计调用次数：

| 月调用量 | 单价 |
|----------|------|
| 0 ~ 10,000 次 | ¥0.002 / 次 |
| 10,001 ~ 5,000,000 次 | ¥0.0018 / 次 |
| > 5,000,000 次 | ¥0.0016 / 次 |

### 成本估算

以典型直播视频为例：

- 20 分钟视频，2fps 采样 = 2400 帧
- 每帧调用一次：2400 × ¥0.002 = **¥4.8 / 视频**
- 如果做优化（先用本地 HSV 预筛，只对疑似换衣帧调用云 API），实际成本可降到 **¥1~2 / 视频**

---

## 与当前方案的关系

### 当前方案

项目现有的换衣检测使用 `ClothingChangeDetector`（位于 `backend/app/services/clothing_change_detector.py`），基于 HSV 直方图相关性判断，完全本地运行，零成本。

### 云 API 适合的场景

- 不想安装和部署本地模型（YOLO、MediaPipe）
- 需要像素级精度，区分具体换了哪件衣服
- 批量处理大量视频，对单视频成本不敏感
- 本地方案检测效果不理想时的补充验证

### 不适合的场景

- 已有可用的本地方案，且效果尚可
- 需要完全离线处理
- 对成本敏感（每月处理几百个长视频，费用上百元）
- 对延迟敏感（每帧需要网络往返）

---

## 集成方案（如未来要接入）

以下为技术方案备忘，供实施时参考。

### 1. 安装 SDK

```bash
pip install alibabacloud_viapi20230117
```

### 2. 新增检测器类

在 `backend/app/services/clothing_change_detector.py` 中新增 `AlibabaCloudClothingDetector` 类，实现与现有 `ClothingChangeDetector` 相同的接口（`detect_change` 方法），内部调用阿里云 API。

核心逻辑：
- 对相邻帧分别调用 SegmentCloth，获取各类别 mask
- 比较同一类别的 mask 变化（IoU 或像素差异率）
- 超过阈值则判定为换衣

### 3. 设置开关

在 `backend/app/api/settings.py` 和前端 `SettingsModal.tsx` 中增加：

- `use_cloud_segmentation: bool`（是否使用云端分割）
- `aliyun_access_key_id: str`
- `aliyun_access_key_secret: str`

### 4. 流水线切换

在 `pipeline.py` 的 `visual_prescreen` 阶段，根据 `use_cloud_segmentation` 决定使用本地检测器还是云端检测器。

### 5. 注意事项

- AccessKey 不要硬编码，走环境变量或 settings.json
- API 有 QPS 限制（5），高频抽帧需要做节流或批量排队
- 网络异常要有 fallback 到本地方案的处理

---

## 其他云 API 备选参考

| 服务 | 能力 | 单价 | 备注 |
|------|------|------|------|
| 百度人体属性识别 | 检测衣着类别、颜色 | ¥0.002/次 | 属性级别，非像素分割 |
| 腾讯云 DetectProduct | 商品分类检测 | 按量计费 | 偏电商场景 |
| 火山引擎 | 服饰分割 | 未公开 | 需联系商务 |
| Google Cloud Vision | 通用图像标注 | ¥1.5/次 | 太贵，不推荐 |
| Azure Computer Vision | 图像分析 | ¥0.8~1.5/次 | 成本高，不推荐 |

综合来看，阿里云 SegmentCloth 在性价比和功能匹配度上最优。

---

## 相关链接

- [阿里云服饰分割 API 文档](https://help.aliyun.com/zh/viapi/developer-reference/api-clothing-segmentation)
- [分割抠图计费说明](https://help.aliyun.com/zh/viapi/developer-reference/billing-is-introduced-1)
