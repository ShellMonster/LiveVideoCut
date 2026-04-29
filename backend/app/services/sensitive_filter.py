"""Sensitive word filtering for subtitles and exported clips."""

from __future__ import annotations

from typing import Any


def normalize_sensitive_words(words: list[str] | tuple[str, ...] | None) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for word in words or []:
        value = str(word).strip()
        if not value or value in seen:
            continue
        normalized.append(value)
        seen.add(value)
    return normalized


def _matches(text: str, sensitive_words: list[str], match_mode: str) -> list[str]:
    normalized_text = text.strip()
    if not normalized_text:
        return []
    if match_mode == "exact":
        return [word for word in sensitive_words if normalized_text == word]
    return [word for word in sensitive_words if word in normalized_text]


def find_sensitive_hits(
    subtitle_segments: list[dict[str, Any]],
    sensitive_words: list[str],
    match_mode: str = "contains",
) -> list[dict[str, Any]]:
    words = normalize_sensitive_words(sensitive_words)
    if not words:
        return []

    hits: list[dict[str, Any]] = []
    for seg in subtitle_segments:
        text = str(seg.get("text", "")).strip()
        matched = _matches(text, words, match_mode)
        if not matched:
            continue
        start = float(seg.get("start_time", 0.0))
        end = float(seg.get("end_time", 0.0))
        if end <= start:
            continue
        hits.append({
            "start_time": start,
            "end_time": end,
            "text": text,
            "matched_words": matched,
        })
    return hits


def compute_sensitive_cut_ranges(
    subtitle_segments: list[dict[str, Any]],
    sensitive_words: list[str],
    match_mode: str = "contains",
    padding: float = 0.08,
    merge_gap: float = 0.15,
) -> list[dict[str, Any]]:
    hits = find_sensitive_hits(subtitle_segments, sensitive_words, match_mode)
    if not hits:
        return []

    ranges = sorted(
        (
            {
                "start_time": max(0.0, hit["start_time"] - padding),
                "end_time": hit["end_time"] + padding,
                "text": "、".join(hit["matched_words"]),
            }
            for hit in hits
        ),
        key=lambda item: item["start_time"],
    )

    merged: list[dict[str, Any]] = []
    for item in ranges:
        if not merged or item["start_time"] - merged[-1]["end_time"] > merge_gap:
            merged.append(dict(item))
            continue
        merged[-1]["end_time"] = max(merged[-1]["end_time"], item["end_time"])
        if item["text"] not in merged[-1]["text"]:
            merged[-1]["text"] = f"{merged[-1]['text']}、{item['text']}"

    return [
        {
            "start_time": round(float(item["start_time"]), 4),
            "end_time": round(float(item["end_time"]), 4),
            "text": str(item["text"]),
        }
        for item in merged
        if float(item["end_time"]) > float(item["start_time"])
    ]


def remove_sensitive_subtitle_segments(
    subtitle_segments: list[dict[str, Any]],
    sensitive_words: list[str],
    match_mode: str = "contains",
) -> list[dict[str, Any]]:
    words = normalize_sensitive_words(sensitive_words)
    if not words:
        return subtitle_segments
    return [
        seg
        for seg in subtitle_segments
        if not _matches(str(seg.get("text", "")), words, match_mode)
    ]


def merge_cut_ranges(*range_groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranges = sorted(
        [
            {
                "start_time": float(item.get("start_time", 0.0)),
                "end_time": float(item.get("end_time", 0.0)),
                "text": str(item.get("text", "")),
            }
            for group in range_groups
            for item in group
            if float(item.get("end_time", 0.0)) > float(item.get("start_time", 0.0))
        ],
        key=lambda item: item["start_time"],
    )
    if not ranges:
        return []

    merged: list[dict[str, Any]] = [ranges[0]]
    for item in ranges[1:]:
        last = merged[-1]
        if item["start_time"] <= last["end_time"] + 0.05:
            last["end_time"] = max(last["end_time"], item["end_time"])
            if item["text"] and item["text"] not in last["text"]:
                last["text"] = f"{last['text']}、{item['text']}" if last["text"] else item["text"]
        else:
            merged.append(item)
    return [
        {
            "start_time": round(item["start_time"], 4),
            "end_time": round(item["end_time"], 4),
            "text": item["text"],
        }
        for item in merged
    ]
