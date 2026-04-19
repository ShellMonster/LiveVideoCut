"""
语气词过滤服务模块

提供字幕级别的语气词过滤和视频裁剪时间点计算。
纯函数设计，无第三方依赖，无副作用。
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# 语气词词表
# ---------------------------------------------------------------------------

# Level 1: 安全删除 — 纯语气词，100% 无语义损失
FILLER_SAFE: set[str] = {
    # 单字语气词
    "嗯", "啊", "呃", "哦", "呀", "嘛", "噢", "哎", "唉", "唔", "喔",
    "嗷", "诶", "哇", "嘿", "哟", "啧",
    # 叠字语气词
    "嗯嗯", "啊啊", "哦哦", "呃呃", "嗯哼",
    # 三叠字
    "对对对", "好好好", "来来来", "是是是",
    # 带波浪号
    "嗯~", "啊~", "呃~",
}

# Level 2: 句首/句尾删除 — 话语标记
FILLER_SENTENCE_EDGE: set[str] = {
    "就是说", "怎么说呢", "那个什么",
    "你知道吗", "你知道", "其实吧", "所以呢",
    "我跟你说", "我跟你讲",
}

# 合并词表
FILLER_ALL: set[str] = FILLER_SAFE | FILLER_SENTENCE_EDGE


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def is_filler(text: str, filler_set: set[str] | None = None) -> bool:
    """判断一个 word 是否是语气词。strip 后检查是否在 set 中。"""
    if filler_set is None:
        filler_set = FILLER_ALL
    return text.strip() in filler_set


# ---------------------------------------------------------------------------
# 核心函数 1: 字幕级过滤
# ---------------------------------------------------------------------------

def filter_subtitle_words(
    subtitle_segments: list[dict],
    filler_set: set[str] | None = None,
) -> list[dict]:
    """
    从字幕 segments 中移除语气词 word。

    - 遍历每个 segment 的 words[]，删掉 text 匹配 filler_set 的 word
    - 删完后重建 segment text（把剩余 word 拼接）
    - 如果 segment 的 words 全部被删，则整句删除
    - 不改变任何时间戳（remaining words 的时间不变）
    """
    if filler_set is None:
        filler_set = FILLER_ALL

    result: list[dict] = []

    for seg in subtitle_segments:
        words = seg.get("words")

        # 没有 word-level 数据，退回到整句文本匹配
        if not words:
            seg_text = seg.get("text", "").strip()
            # 如果整句文本本身就是语气词，跳过该 segment
            if seg_text in filler_set:
                continue
            result.append(seg)
            continue

        # 保留非语气词的 words
        kept_words = [w for w in words if not is_filler(w.get("text", ""), filler_set)]

        # 全部被删 → 整句删除
        if not kept_words:
            continue

        # 重建 segment
        new_seg = dict(seg)
        new_seg["words"] = kept_words
        # 用保留的 word 拼接重建 text
        new_seg["text"] = "".join(w.get("text", "") for w in kept_words)

        result.append(new_seg)

    return result


# ---------------------------------------------------------------------------
# 核心函数 2: 视频裁剪时间点计算
# ---------------------------------------------------------------------------

def compute_filler_cut_ranges(
    subtitle_segments: list[dict],
    filler_set: set[str] | None = None,
    min_cut_duration: float = 0.1,
    padding: float = 0.02,
    merge_gap: float = 0.2,
) -> list[dict]:
    """
    找出所有语气词对应的时间范围，用于后续视频裁剪。

    - 相邻 filler（间距 < merge_gap）合并为一段
    - 每段加 padding（前后各），但不超过相邻非 filler word 的时间边界
    - 过滤掉时长 < min_cut_duration 的段
    - 返回 [{start_time, end_time, text}]（要被删除的时间段）
    """
    if filler_set is None:
        filler_set = FILLER_ALL

    # 1. 收集所有 filler word 的时间片段
    raw_ranges: list[dict] = []

    for seg in subtitle_segments:
        words = seg.get("words")
        if not words:
            continue
        for w in words:
            if is_filler(w.get("text", ""), filler_set):
                raw_ranges.append({
                    "start_time": w.get("start_time", 0.0),
                    "end_time": w.get("end_time", 0.0),
                    "text": w.get("text", ""),
                })

    if not raw_ranges:
        return []

    # 按开始时间排序
    raw_ranges.sort(key=lambda r: r["start_time"])

    # 2. 合并相邻片段（间距 < merge_gap）
    merged: list[dict] = [raw_ranges[0]]
    for r in raw_ranges[1:]:
        last = merged[-1]
        if r["start_time"] - last["end_time"] < merge_gap:
            # 合并
            last["end_time"] = max(last["end_time"], r["end_time"])
            last["text"] = last["text"] + r["text"]
        else:
            merged.append(dict(r))  # 浅拷贝避免引用问题

    # 3. 收集所有非 filler word 的时间边界（用于限制 padding）
    all_non_filler_times: list[tuple[float, float]] = []
    for seg in subtitle_segments:
        for w in seg.get("words", []):
            if not is_filler(w.get("text", ""), filler_set):
                all_non_filler_times.append((
                    w.get("start_time", 0.0),
                    w.get("end_time", 0.0),
                ))

    # 4. 加 padding 并限制边界
    cut_ranges: list[dict] = []
    for m in merged:
        start = max(0.0, m["start_time"] - padding)
        end = m["end_time"] + padding

        # 不超过相邻非 filler word 的时间边界
        for nf_start, nf_end in all_non_filler_times:
            # 如果非 filler 紧接在 filler 之前，start 不能越过它
            if nf_end <= m["start_time"] and nf_end > start:
                start = nf_end
            # 如果非 filler 紧接在 filler 之后，end 不能越过它
            if nf_start >= m["end_time"] and nf_start < end:
                end = nf_start

        duration = end - start
        if duration >= min_cut_duration:
            cut_ranges.append({
                "start_time": round(start, 4),
                "end_time": round(end, 4),
                "text": m["text"],
            })

    return cut_ranges
