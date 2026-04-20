"""Snap segment boundaries to transcript sentence edges.

Prevents truncated text at clip start/end by aligning segments
to full ASR sentence boundaries.
"""

import logging
from typing import Any, TypedDict

logger = logging.getLogger(__name__)


class _Sentence(TypedDict):
    start: float
    end: float
    text: str


def snap_to_sentence_boundaries(
    segments: list[dict[str, Any]],
    transcript: list[dict[str, Any]],
    min_duration: float = 10.0,
) -> list[dict[str, Any]]:
    """Snap segment start/end times to transcript sentence boundaries.

    Args:
        segments: List of segment dicts with start_time/end_time.
        transcript: List of ASR sentence dicts with start_time/end_time/text/words.
        min_duration: Minimum allowed duration after snapping (reverts if violated).

    Returns:
        Modified segments list (same objects, mutated in place).
    """
    if not transcript or not segments:
        return segments

    sentences: list[_Sentence] = [
        {
            "start": float(s.get("start_time", 0.0)),
            "end": float(s.get("end_time", 0.0)),
            "text": str(s.get("text", "")),
        }
        for s in transcript
    ]

    for i, seg in enumerate(segments):
        orig_start = float(seg.get("start_time", 0.0))
        orig_end = float(seg.get("end_time", 0.0))

        # Snap start: first sentence with start_time >= segment start
        new_start = orig_start
        for s in sentences:
            if s["start"] >= orig_start:
                new_start = s["start"]
                break

        # Snap end: last sentence with end_time <= segment end
        new_end = orig_end
        for s in reversed(sentences):
            if s["end"] <= orig_end:
                new_end = s["end"]
                break

        # Orphan trim: drop single-char sentences at edges
        if new_start < new_end:
            inner = [s for s in sentences if s["start"] >= new_start and s["end"] <= new_end]
            if inner:
                first = inner[0]
                if len(first["text"]) <= 1 and len(inner) > 1:
                    candidate_start = inner[1]["start"]
                    if candidate_start < new_end and (new_end - candidate_start) >= min_duration:
                        logger.info(
                            "Segment %d: trimmed leading orphan '%s' at start %.1f → %.1f",
                            i, first["text"], new_start, candidate_start,
                        )
                        new_start = candidate_start
                        inner = inner[1:]

                if inner:
                    last = inner[-1]
                    if len(last["text"]) <= 1 and len(inner) > 1:
                        candidate_end = inner[-2]["end"]
                        if candidate_end > new_start and (candidate_end - new_start) >= min_duration:
                            logger.info(
                                "Segment %d: trimmed trailing orphan '%s' at end %.1f → %.1f",
                                i, last["text"], new_end, candidate_end,
                            )
                            new_end = candidate_end

        # Safety: revert if duration too short
        if (new_end - new_start) < min_duration:
            logger.info(
                "Segment %d: snapped duration %.1fs < min %.1fs, reverting to original",
                i, new_end - new_start, min_duration,
            )
            new_start = orig_start
            new_end = orig_end

        if new_start != orig_start:
            logger.info(
                "Segment %d: snapped start %.1f → %.1f (sentence boundary)",
                i, orig_start, new_start,
            )
        if new_end != orig_end:
            logger.info(
                "Segment %d: snapped end %.1f → %.1f (sentence boundary)",
                i, orig_end, new_end,
            )

        seg["start_time"] = new_start
        seg["end_time"] = new_end

    logger.info(
        "Snapped %d segments to sentence boundaries (min_duration=%.1fs)",
        len(segments), min_duration,
    )
    return segments
