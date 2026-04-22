"""LLM-based boundary refinement for video clip segments.

Reviews segment boundaries using LLM to ensure narrative completeness —
avoids truncated openings, filler-word starts, and cut-off endings.
Snaps LLM suggestions to actual ASR sentence boundaries to prevent
hallucinated timestamps.
"""

import json
import logging
import time
from typing import Any, cast

from openai import OpenAI

logger = logging.getLogger(__name__)

MAX_RETRIES = 2
TIMEOUT_SECONDS = 30

PROMPT_TEMPLATE = """你是一位直播视频剪辑专家。请审查以下商品讲解片段的起止边界是否合理。

【片段信息】商品：{product_name}，当前边界：{start:.1f}s - {end:.1f}s

【开头附近的句子】（带序号和时间戳，供你选择最佳起始句）
{sentences_around_start}

【结尾附近的句子】
{sentences_around_end}

请判断：
1. 开头是否完整独立？避免语气词（嗯、对、然后）、回指代词（这个也是、那件）开头的残句
2. 结尾是否自然？是否截断了完整的讲解思路

规则：
- 只能在上方列出的句子中选择，不要编造时间戳
- adjusted_start/adjusted_end 填写建议的时间戳（秒），不需要调整则填 null
- 宁可不调整也不要错误调整

输出严格 JSON（不要 markdown 代码块）：
{{"adjusted_start": null, "adjusted_end": null, "confidence": 0.0, "reason": "..."}}"""


def _extract_sentences_around(
    transcript: list[dict[str, Any]],
    anchor: float,
    window: float,
) -> list[dict[str, Any]]:
    """Return transcript sentences within `window` seconds of `anchor`."""
    return [
        s for s in transcript
        if abs(s.get("start_time", 0.0) - anchor) <= window
        or abs(s.get("end_time", 0.0) - anchor) <= window
    ]


def _format_numbered_sentences(sentences: list[dict[str, Any]]) -> str:
    """Format sentences as numbered list with timestamps."""
    if not sentences:
        return "（无可用句子）"
    lines = []
    for i, s in enumerate(sentences, 1):
        start = s.get("start_time", 0.0)
        end = s.get("end_time", 0.0)
        text = s.get("text", "").strip()
        if text:
            lines.append(f"{i}. [{start:.1f}s - {end:.1f}s] {text}")
    return "\n".join(lines) if lines else "（无可用句子）"


def _snap_to_sentence(
    suggested_time: float,
    sentences: list[dict[str, Any]],
    prefer: str = "start",
) -> float | None:
    """Snap a suggested timestamp to the nearest actual ASR sentence boundary.

    Args:
        suggested_time: LLM-suggested timestamp.
        sentences: Candidate sentences to snap to.
        prefer: "start" snaps to sentence start_time, "end" snaps to sentence end_time.

    Returns:
        Snapped timestamp, or None if no candidate within 10s.
    """
    if not sentences:
        return None

    best_delta = 10.0  # max 10s tolerance
    best_time = None

    for s in sentences:
        anchor = s.get("start_time", 0.0) if prefer == "start" else s.get("end_time", 0.0)
        delta = abs(anchor - suggested_time)
        if delta < best_delta:
            best_delta = delta
            best_time = anchor

    return best_time


def _parse_llm_response(text: str) -> dict[str, Any] | None:
    """Parse LLM response JSON, stripping markdown fences."""
    text = text.strip()
    if text.startswith("```"):
        first_nl = text.index("\n") if "\n" in text else len(text)
        text = text[first_nl + 1:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Failed to parse LLM boundary response as JSON: %.200s", text)
        return None

    if not isinstance(data, dict):
        logger.warning("LLM boundary response is not a dict")
        return None

    # Validate required fields
    for key in ("adjusted_start", "adjusted_end", "confidence", "reason"):
        if key not in data:
            logger.warning("LLM boundary response missing key '%s'", key)
            return None

    return data


def refine_boundaries(
    segments: list[dict[str, Any]],
    transcript: list[dict[str, Any]],
    llm_key: str,
    llm_base: str,
    llm_model: str,
    llm_type: str = "openai",
    context_window: float = 15.0,
    min_duration: float = 10.0,
) -> list[dict[str, Any]]:
    """Use LLM to review and adjust segment boundaries for narrative quality.

    For each segment, the LLM evaluates whether the start/end boundaries
    create clean narrative cuts. Suggestions are snapped to actual ASR
    sentence boundaries to prevent hallucinated timestamps.

    Args:
        segments: List of segment dicts with start_time/end_time.
        transcript: List of ASR sentence dicts.
        llm_key: LLM API key.
        llm_base: LLM API base URL.
        llm_model: LLM model name.
        llm_type: "openai" or "gemini".
        context_window: Seconds around each boundary to include as context.
        min_duration: Minimum duration after adjustment.

    Returns:
        Same segments list (mutated in place), unchanged on failure.
    """
    if not segments or not transcript:
        return segments

    client = OpenAI(api_key=llm_key, base_url=llm_base)
    logger.info(
        "Refining boundaries for %d segments (model=%s, window=%.1fs)",
        len(segments), llm_model, context_window,
    )

    for i, seg in enumerate(segments):
        orig_start = float(seg.get("start_time", 0.0))
        orig_end = float(seg.get("end_time", 0.0))
        product_name = seg.get("product_name", "未命名商品") or "未命名商品"

        # Collect context sentences around start and end boundaries
        start_sentences = _extract_sentences_around(transcript, orig_start, context_window)
        end_sentences = _extract_sentences_around(transcript, orig_end, context_window)

        prompt = PROMPT_TEMPLATE.format(
            product_name=product_name,
            start=orig_start,
            end=orig_end,
            sentences_around_start=_format_numbered_sentences(start_sentences),
            sentences_around_end=_format_numbered_sentences(end_sentences),
        )

        # Call LLM with retry
        response_text = None
        for attempt in range(MAX_RETRIES):
            try:
                response = client.chat.completions.create(
                    model=llm_model,
                    messages=[{"role": "user", "content": prompt}],
                    timeout=TIMEOUT_SECONDS,
                )
                response_text = response.choices[0].message.content or ""
                break
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    wait = 2 ** attempt
                    logger.warning(
                        "Boundary refine segment %d attempt %d/%d failed, retry in %ds: %s",
                        i, attempt + 1, MAX_RETRIES, wait, str(e),
                    )
                    time.sleep(wait)
                else:
                    logger.warning(
                        "Boundary refine segment %d failed after %d attempts: %s",
                        i, MAX_RETRIES, str(e),
                    )

        if not response_text:
            continue

        parsed = _parse_llm_response(response_text)
        if not parsed:
            continue

        adjusted_start = parsed.get("adjusted_start")
        adjusted_end = parsed.get("adjusted_end")
        reason = parsed.get("reason", "")
        confidence = parsed.get("confidence", 0.0)

        new_start = orig_start
        new_end = orig_end

        # Snap LLM suggestions to actual sentence boundaries
        if adjusted_start is not None:
            snapped = _snap_to_sentence(adjusted_start, start_sentences, prefer="start")
            if snapped is not None:
                new_start = snapped
            else:
                logger.warning(
                    "Segment %d: LLM suggested start %.1f but no matching sentence found, keeping original",
                    i, adjusted_start,
                )

        if adjusted_end is not None:
            snapped = _snap_to_sentence(adjusted_end, end_sentences, prefer="end")
            if snapped is not None:
                new_end = snapped
            else:
                logger.warning(
                    "Segment %d: LLM suggested end %.1f but no matching sentence found, keeping original",
                    i, adjusted_end,
                )

        # Validate duration
        if new_end - new_start < min_duration:
            logger.info(
                "Segment %d: refined duration %.1fs < min %.1fs, reverting",
                i, new_end - new_start, min_duration,
            )
            continue

        # Apply changes
        if new_start != orig_start:
            logger.info(
                "Segment %d: start %.1f → %.1f (%s)",
                i, orig_start, new_start, reason,
            )
            seg["start_time"] = new_start

        if new_end != orig_end:
            logger.info(
                "Segment %d: end %.1f → %.1f (%s)",
                i, orig_end, new_end, reason,
            )
            seg["end_time"] = new_end

    logger.info("Boundary refinement complete for %d segments", len(segments))
    return segments
