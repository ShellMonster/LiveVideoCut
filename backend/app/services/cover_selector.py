"""Cover frame selector — scores video frames and picks the best thumbnail.

Strategies:
- content_first (default): prefers frames with clear clothing/product items
- person_first: prefers frames with visible, centered faces
"""

import logging
import os
import subprocess
import tempfile
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)

_segmenter_instance = None
_face_detection_instance = None


def _get_segmenter():
    global _segmenter_instance
    if _segmenter_instance is None:
        from app.services.clothing_segmenter import ClothingSegmenter
        _segmenter_instance = ClothingSegmenter()
    return _segmenter_instance


def _get_face_detection():
    global _face_detection_instance
    if _face_detection_instance is None:
        import mediapipe as mp
        _face_detection_instance = mp.solutions.face_detection.FaceDetection(
            model_selection=1,
        )
    return _face_detection_instance


def _sample_frames(
    video_path: str,
    clip_start: float,
    clip_end: float,
    max_frames: int = 30,
) -> list[tuple[float, np.ndarray]]:
    """Extract up to *max_frames* uniformly spaced frames from the clip.

    Returns list of (timestamp, bgr_array). Timestamps are relative to video start.
    """
    duration = clip_end - clip_start
    if duration <= 0:
        return []

    interval = max(1.0, duration / max_frames)
    timestamps: list[float] = []
    t = clip_start
    while t < clip_end and len(timestamps) < max_frames:
        timestamps.append(round(t, 3))
        t += interval

    if not timestamps:
        return []

    frames: list[tuple[float, np.ndarray]] = []
    tmpdir = tempfile.mkdtemp(prefix="cover_sel_")

    for ts in timestamps:
        out_path = os.path.join(tmpdir, f"f_{ts:.3f}.jpg")
        cmd = [
            "ffmpeg",
            "-ss", str(ts),
            "-i", video_path,
            "-vframes", "1",
            "-q:v", "2",
            "-y", out_path,
        ]
        try:
            subprocess.run(cmd, capture_output=True, timeout=15, check=True)
            img = cv2.imread(out_path)
            if img is not None:
                frames.append((ts, img))
        except Exception as exc:
            logger.debug("Failed to extract frame at %.3f: %s", ts, exc)

    for f in os.listdir(tmpdir):
        try:
            os.remove(os.path.join(tmpdir, f))
        except OSError:
            pass
    try:
        os.rmdir(tmpdir)
    except OSError:
        pass

    return frames


def _score_quality(frame_bgr: np.ndarray) -> float:
    """Compute a 0-1 quality score based on sharpness, contrast, brightness."""
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape

    # Sharpness — Laplacian variance, normalize to 0-1 (typical range 0-2000)
    lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    sharpness = min(lap_var / 1000.0, 1.0)

    # Contrast — std dev of gray, normalize (typical range 0-80)
    contrast = min(gray.std() / 80.0, 1.0)

    # Brightness — bell curve around ideal=130
    mean_brightness = gray.mean()
    brightness = float(np.exp(-0.5 * ((mean_brightness - 130) / 50) ** 2))

    return float(0.50 * sharpness + 0.30 * contrast + 0.20 * brightness)


def _score_person_first(frame_bgr: np.ndarray) -> float:
    """Score frame for person-first strategy using face detection."""
    face_det = _get_face_detection()
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    result = face_det.process(rgb)

    if not result.detections:
        return 0.0

    h, w = frame_bgr.shape[:2]
    diagonal = float(np.sqrt(h * h + w * w))
    center_x, center_y = w / 2.0, h / 2.0

    best_score = 0.0
    for det in result.detections:
        rb = det.location_data.relative_bounding_box
        face_w = rb.width * w
        face_h = rb.height * h
        face_area = face_w * face_h
        frame_area = float(h * w)
        area_ratio = face_area / frame_area if frame_area > 0 else 0.0

        # Face center distance from frame center, normalized by half-diagonal
        face_cx = (rb.xmin + rb.width / 2) * w
        face_cy = (rb.ymin + rb.height / 2) * h
        dist = float(np.sqrt((face_cx - center_x) ** 2 + (face_cy - center_y) ** 2))
        norm_dist = dist / (diagonal / 2) if diagonal > 0 else 1.0
        distance_score = max(0.0, 1.0 - norm_dist)

        confidence = float(det.score[0]) if det.score else 0.0

        score = 0.40 * min(area_ratio, 1.0) + 0.25 * distance_score + 0.20 * confidence
        # Add sharpness as a minor factor (reuse quality partially)
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        sharpness = min(lap_var / 1000.0, 1.0)
        score += 0.15 * sharpness

        best_score = max(best_score, score)

    return best_score


def _score_content_first(frame_bgr: np.ndarray) -> float:
    """Score frame for content-first strategy using YOLO clothing detection."""
    segmenter = _get_segmenter()
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    items = segmenter.detect_clothing_items(rgb)

    if not items:
        # Fallback: use center frame quality
        return 0.0

    h, w = frame_bgr.shape[:2]
    frame_area = float(h * w)
    diagonal = float(np.sqrt(h * h + w * w))

    # Rule-of-thirds reference points
    third_points = [(w / 3, h / 3), (2 * w / 3, 2 * h / 3)]

    best_score = 0.0
    for item in items:
        bbox = item["bbox"]
        x1, y1, x2, y2 = bbox
        bbox_area = max((x2 - x1), 0) * max((y2 - y1), 0)
        area_ratio = bbox_area / frame_area if frame_area > 0 else 0.0
        # Cap at 0.5 — items filling too much of the frame are too close
        capped_area = min(area_ratio, 0.5) / 0.5

        # Distance to nearest rule-of-thirds point
        item_cx = (x1 + x2) / 2.0
        item_cy = (y1 + y2) / 2.0
        min_dist = min(
            float(np.sqrt((item_cx - tx) ** 2 + (item_cy - ty) ** 2))
            for tx, ty in third_points
        )
        norm_dist = min_dist / (diagonal / 2) if diagonal > 0 else 1.0
        distance_score = max(0.0, 1.0 - norm_dist)

        confidence = float(item["confidence"])

        # Local sharpness in the bbox region
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        ix1 = max(0, int(x1))
        iy1 = max(0, int(y1))
        ix2 = min(w, int(x2))
        iy2 = min(h, int(y2))
        if ix2 > ix1 and iy2 > iy1:
            crop = gray[iy1:iy2, ix1:ix2]
            local_sharp = min(cv2.Laplacian(crop, cv2.CV_64F).var() / 1000.0, 1.0)
        else:
            local_sharp = 0.0

        score = (
            0.35 * capped_area
            + 0.25 * confidence
            + 0.20 * distance_score
            + 0.20 * local_sharp
        )
        best_score = max(best_score, score)

    return best_score


def select_cover_frame(
    video_path: str,
    clip_start: float,
    clip_end: float,
    strategy: str = "content_first",
    max_frames: int = 30,
) -> float:
    """Return the timestamp (relative to video start) of the best cover frame.

    Falls back to clip midpoint if scoring fails.
    """
    midpoint = clip_start + (clip_end - clip_start) / 2

    try:
        frames = _sample_frames(video_path, clip_start, clip_end, max_frames)
        if not frames:
            logger.debug("No frames sampled, falling back to midpoint")
            return midpoint

        best_ts = midpoint
        best_final_score = -1.0

        for ts, bgr in frames:
            quality = _score_quality(bgr)

            if strategy == "person_first":
                semantic = _score_person_first(bgr)
            else:
                semantic = _score_content_first(bgr)

            # If no semantic signal, give a neutral baseline so quality still matters
            if semantic <= 0.0:
                semantic = 0.3

            final_score = semantic * quality

            if final_score > best_final_score:
                best_final_score = final_score
                best_ts = ts

        logger.debug(
            "Cover selection: strategy=%s, best_ts=%.3f (score=%.4f)",
            strategy, best_ts, best_final_score,
        )
        return best_ts

    except Exception as exc:
        logger.warning("Cover selection failed, falling back to midpoint: %s", exc)
        return midpoint
