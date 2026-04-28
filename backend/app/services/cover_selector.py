"""Cover frame selector — scores video frames and picks the best thumbnail.

Strategies:
- content_first (default): prefers frames with clear clothing/product items
- person_first: prefers frames with visible, centered faces

Both strategies penalize frames with occluders (cell phone, laptop, etc.)
detected by a COCO YOLOv8n model.
"""

import logging
import importlib
import os
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)

_segmenter_instance = None
_face_detection_instance = None
_coco_yolo_session = None
_coco_yolo_available: bool | None = None
_segmenter_lock = threading.Lock()
_face_detection_lock = threading.Lock()
_coco_yolo_lock = threading.Lock()

# COCO 80-class IDs for objects that commonly occlude the presenter
OCCLUDER_CLASS_IDS = {
    67,  # cell phone
    63,  # laptop
    66,  # remote
    73,  # book
    74,  # clock
    75,  # vase
}

COCO_YOLO_MODEL_PATH = "/app/assets/models/yolov8n.onnx"


def _get_segmenter():
    global _segmenter_instance
    if _segmenter_instance is None:
        with _segmenter_lock:
            if _segmenter_instance is None:
                ClothingSegmenter = importlib.import_module(
                    "app.services.clothing_segmenter"
                ).ClothingSegmenter
                _segmenter_instance = ClothingSegmenter()
    return _segmenter_instance


def _get_face_detection():
    global _face_detection_instance
    if _face_detection_instance is None:
        with _face_detection_lock:
            if _face_detection_instance is None:
                mp = importlib.import_module("mediapipe")
                _face_detection_instance = mp.solutions.face_detection.FaceDetection(
                    model_selection=1,
                )
    return _face_detection_instance


def _record_timestamp(record: dict[str, object], default: float = -1.0) -> float:
    raw_timestamp = record.get("timestamp", default)
    if isinstance(raw_timestamp, (int, float, str)):
        try:
            return float(raw_timestamp)
        except ValueError:
            return default
    return default


def _get_coco_yolo():
    """Lazy-load COCO YOLOv8n ONNX session for occlusion detection."""
    global _coco_yolo_session, _coco_yolo_available
    if _coco_yolo_available is not None:
        return _coco_yolo_session if _coco_yolo_available else None

    with _coco_yolo_lock:
        if _coco_yolo_available is not None:
            return _coco_yolo_session if _coco_yolo_available else None

        model_path = Path(COCO_YOLO_MODEL_PATH)
        if not model_path.exists():
            logger.debug("COCO YOLO model not found at %s, skipping occlusion detection", COCO_YOLO_MODEL_PATH)
            _coco_yolo_available = False
            return None

        try:
            import onnxruntime as ort
            _coco_yolo_session = ort.InferenceSession(
                str(model_path),
                providers=["CPUExecutionProvider"],
            )
            _coco_yolo_available = True
            logger.info("COCO YOLOv8n occlusion model loaded from %s", COCO_YOLO_MODEL_PATH)
        except Exception as exc:
            logger.warning("COCO YOLO ONNX session failed to load: %s", exc)
            _coco_yolo_available = False
    return _coco_yolo_session if _coco_yolo_available else None


def _sample_frames(
    video_path: str,
    clip_start: float,
    clip_end: float,
    max_frames: int = 30,
) -> list[tuple[float, np.ndarray]]:
    candidates = _sample_frame_candidates(video_path, clip_start, clip_end, max_frames)
    try:
        return [(ts, frame) for ts, frame, _path in candidates]
    finally:
        _cleanup_candidate_files(candidates)


def _sample_frame_candidates(
    video_path: str,
    clip_start: float,
    clip_end: float,
    max_frames: int = 30,
) -> list[tuple[float, np.ndarray, str]]:
    """Extract up to *max_frames* uniformly spaced frames from the clip.

    Returns list of (timestamp, bgr_array, jpg_path). Timestamps are relative to video start.
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

    frames: list[tuple[float, np.ndarray, str]] = []
    tmpdir = tempfile.mkdtemp(prefix="cover_sel_")

    try:
        # Extract the uniformly spaced candidates in one FFmpeg process instead
        # of spawning one FFmpeg process per candidate frame.
        output_pattern = os.path.join(tmpdir, "frame_%05d.jpg")
        cmd = [
            "ffmpeg",
            "-y",
            "-ss", str(clip_start),
            "-t", str(duration),
            "-i", video_path,
            "-vf", f"fps=1/{interval:.6f}",
            "-frames:v", str(len(timestamps)),
            "-q:v", "2",
            "-an",
            output_pattern,
        ]
        _ = subprocess.run(cmd, capture_output=True, timeout=60, check=True)

        for idx, ts in enumerate(timestamps, start=1):
            out_path = os.path.join(tmpdir, f"frame_{idx:05d}.jpg")
            img = cv2.imread(out_path)
            if img is not None:
                frames.append((ts, img, out_path))
        if len(frames) < len(timestamps):
            logger.debug(
                "Batch cover frame extraction returned %d/%d frames, falling back to per-frame extraction",
                len(frames), len(timestamps),
            )
            frames = _sample_frames_individually(video_path, timestamps, tmpdir)
    except Exception as exc:
        logger.debug("Batch cover frame extraction failed: %s", exc)
        frames = _sample_frames_individually(video_path, timestamps, tmpdir)
    finally:
        # Keep the temp directory alive until select_cover_frame has a chance to
        # copy the chosen JPEG. The caller removes it via _cleanup_candidate_files.
        pass

    return frames


def _sample_pre_sampled_frame_candidates(
    frame_records: list[dict[str, object]],
    clip_start: float,
    clip_end: float,
    max_frames: int,
) -> list[tuple[float, np.ndarray, str]]:
    in_range = [
        record for record in frame_records
        if clip_start <= _record_timestamp(record) <= clip_end
        and Path(str(record.get("path", ""))).exists()
    ]
    if not in_range:
        return []

    if len(in_range) <= max_frames:
        selected = in_range
    else:
        selected = []
        last_index = len(in_range) - 1
        for idx in range(max_frames):
            source_index = round(idx * last_index / max(max_frames - 1, 1))
            selected.append(in_range[source_index])

    candidates: list[tuple[float, np.ndarray, str]] = []
    for record in selected:
        source_path = str(record.get("path", ""))
        img = cv2.imread(source_path)
        if img is not None:
            candidates.append((_record_timestamp(record, 0.0), img, source_path))
    return candidates


def _sample_frames_individually(
    video_path: str,
    timestamps: list[float],
    tmpdir: str,
) -> list[tuple[float, np.ndarray, str]]:
    frames: list[tuple[float, np.ndarray, str]] = []
    for ts in timestamps:
        out_path = os.path.join(tmpdir, f"fallback_{ts:.3f}.jpg")
        cmd = [
            "ffmpeg",
            "-ss", str(ts),
            "-i", video_path,
            "-vframes", "1",
            "-q:v", "2",
            "-an",
            "-y", out_path,
        ]
        try:
            _ = subprocess.run(cmd, capture_output=True, timeout=15, check=True)
            img = cv2.imread(out_path)
            if img is not None:
                frames.append((ts, img, out_path))
        except Exception as exc:
            logger.debug("Failed to extract frame at %.3f: %s", ts, exc)
    return frames


def _cleanup_candidate_files(candidates: list[tuple[float, np.ndarray, str]]) -> None:
    seen_dirs: set[str] = set()
    for _ts, _frame, path in candidates:
        frame_path = Path(path)
        try:
            frame_path.unlink()
        except OSError:
            pass
        seen_dirs.add(str(frame_path.parent))
    for directory in seen_dirs:
        directory_path = Path(directory)
        try:
            for leftover in directory_path.iterdir():
                try:
                    leftover.unlink()
                except OSError:
                    pass
        except OSError:
            pass
        try:
            directory_path.rmdir()
        except OSError:
            pass


def _detect_occluders(
    frame_bgr: np.ndarray,
    clothing_bboxes: list[list[float]] | None = None,
) -> bool:
    """Return True if an occluder overlaps with clothing regions."""
    session = _get_coco_yolo()
    if session is None:
        return False

    orig_h, orig_w = frame_bgr.shape[:2]
    img_resized = cv2.resize(frame_bgr, (640, 640))
    img_rgb = cv2.cvtColor(img_resized, cv2.COLOR_BGR2RGB)
    img_input = img_rgb.astype(np.float32) / 255.0
    img_input = img_input.transpose(2, 0, 1)[np.newaxis, ...]

    input_name = session.get_inputs()[0].name
    outputs = session.run(None, {input_name: img_input})

    # COCO YOLO output: [1, 84, 8400] → transpose to [8400, 84]
    predictions = np.array(outputs[0])[0].T
    boxes_cxcywh = predictions[:, :4]
    class_scores = predictions[:, 4:]  # 80 class scores

    best_class_ids = class_scores.argmax(axis=1)
    confidences = class_scores.max(axis=1)

    keep = confidences > 0.3
    if not np.any(keep):
        return False

    boxes_filtered = boxes_cxcywh[keep]
    classes_filtered = best_class_ids[keep]
    confs_filtered = confidences[keep]

    # Convert cx,cy,w,h → x1,y1,x2,y2 in 640x640 space, then scale
    boxes_xyxy = np.zeros_like(boxes_filtered)
    boxes_xyxy[:, 0] = boxes_filtered[:, 0] - boxes_filtered[:, 2] / 2
    boxes_xyxy[:, 1] = boxes_filtered[:, 1] - boxes_filtered[:, 3] / 2
    boxes_xyxy[:, 2] = boxes_filtered[:, 0] + boxes_filtered[:, 2] / 2
    boxes_xyxy[:, 3] = boxes_filtered[:, 1] + boxes_filtered[:, 3] / 2

    scale_x = orig_w / 640.0
    scale_y = orig_h / 640.0
    boxes_xyxy[:, 0] *= scale_x
    boxes_xyxy[:, 2] *= scale_x
    boxes_xyxy[:, 1] *= scale_y
    boxes_xyxy[:, 3] *= scale_y

    # NMS
    indices = cv2.dnn.NMSBoxes(
        boxes_xyxy.tolist(),
        confs_filtered.tolist(),
        score_threshold=0.3,
        nms_threshold=0.45,
    )
    if len(indices) == 0:
        return False
    indices = indices.flatten() if isinstance(indices, np.ndarray) else np.array(indices).flatten()

    occluder_boxes = []
    for idx in indices:
        cls_id = int(classes_filtered[idx])
        if cls_id in OCCLUDER_CLASS_IDS:
            occluder_boxes.append(boxes_xyxy[idx])

    if not occluder_boxes:
        return False

    # No clothing bboxes → occluder in frame is enough to penalize
    if not clothing_bboxes:
        return True

    # Check overlap: occluder bbox vs any clothing bbox
    def _iou(box_a, box_b):
        x1 = max(box_a[0], box_b[0])
        y1 = max(box_a[1], box_b[1])
        x2 = min(box_a[2], box_b[2])
        y2 = min(box_a[3], box_b[3])
        inter = max(0, x2 - x1) * max(0, y2 - y1)
        area_a = max(0, box_a[2] - box_a[0]) * max(0, box_a[3] - box_a[1])
        if area_a <= 0:
            return 0.0
        return inter / area_a

    for occ in occluder_boxes:
        for cloth in clothing_bboxes:
            if _iou(occ.tolist(), cloth) > 0.3:
                return True

    return False


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


def _score_content_first(
    frame_bgr: np.ndarray,
) -> tuple[float, list[list[float]]]:
    """Score frame for content-first strategy using YOLO clothing detection.

    Returns (score, clothing_bboxes) so callers can reuse the bboxes
    for occlusion checking without re-running YOLO.
    """
    segmenter = _get_segmenter()
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    items = segmenter.detect_clothing_items(rgb)

    if not items:
        return 0.0, []

    h, w = frame_bgr.shape[:2]
    frame_area = float(h * w)
    diagonal = float(np.sqrt(h * h + w * w))

    third_points = [(w / 3, h / 3), (2 * w / 3, 2 * h / 3)]

    best_score = 0.0
    clothing_bboxes: list[list[float]] = []
    for item in items:
        bbox = item["bbox"]
        clothing_bboxes.append(bbox)
        x1, y1, x2, y2 = bbox
        bbox_area = max((x2 - x1), 0) * max((y2 - y1), 0)
        area_ratio = bbox_area / frame_area if frame_area > 0 else 0.0
        capped_area = min(area_ratio, 0.5) / 0.5

        item_cx = (x1 + x2) / 2.0
        item_cy = (y1 + y2) / 2.0
        min_dist = min(
            float(np.sqrt((item_cx - tx) ** 2 + (item_cy - ty) ** 2))
            for tx, ty in third_points
        )
        norm_dist = min_dist / (diagonal / 2) if diagonal > 0 else 1.0
        distance_score = max(0.0, 1.0 - norm_dist)

        confidence = float(item["confidence"])

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

    return best_score, clothing_bboxes


def select_cover_frame(
    video_path: str,
    clip_start: float,
    clip_end: float,
    strategy: str = "content_first",
    max_frames: int = 30,
    output_path: str | None = None,
    pre_sampled_frames: list[dict[str, object]] | None = None,
) -> float:
    """Return the timestamp (relative to video start) of the best cover frame.

    Falls back to clip midpoint if scoring fails.
    """
    midpoint = clip_start + (clip_end - clip_start) / 2
    candidates: list[tuple[float, np.ndarray, str]] = []
    top_up_candidates: list[tuple[float, np.ndarray, str]] = []
    uses_pre_sampled_frames = False

    try:
        started_at = time.perf_counter()
        uses_pre_sampled_frames = bool(pre_sampled_frames)
        candidates = (
            _sample_pre_sampled_frame_candidates(pre_sampled_frames or [], clip_start, clip_end, max_frames)
            if uses_pre_sampled_frames
            else []
        )
        if uses_pre_sampled_frames and 0 < len(candidates) < max_frames:
            top_up_candidates = _sample_frame_candidates(
                video_path,
                clip_start,
                clip_end,
                max_frames - len(candidates),
            )
            candidates.extend(top_up_candidates)
        if not candidates:
            uses_pre_sampled_frames = False
            candidates = _sample_frame_candidates(video_path, clip_start, clip_end, max_frames)
        if not candidates:
            logger.debug("No frames sampled, falling back to midpoint")
            return midpoint

        best_ts = midpoint
        best_final_score = -1.0
        best_source_path: str | None = None

        for ts, bgr, source_path in candidates:
            quality = _score_quality(bgr)

            if strategy == "person_first":
                semantic = _score_person_first(bgr)
                clothing_bboxes: list[list[float]] = []
            else:
                semantic, clothing_bboxes = _score_content_first(bgr)

            if semantic <= 0.0:
                semantic = 0.3

            occlusion_penalty = 1.0
            if _detect_occluders(bgr, clothing_bboxes):
                occlusion_penalty = 0.1

            final_score = semantic * quality * occlusion_penalty

            if final_score > best_final_score:
                best_final_score = final_score
                best_ts = ts
                best_source_path = source_path

        if output_path and best_source_path is not None:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            # Reuse the already-encoded candidate JPEG instead of decoding and
            # re-encoding through OpenCV, preserving the same JPEG quality as extraction.
            shutil.copyfile(best_source_path, output_path)

        logger.info(
            "Cover selection: strategy=%s, frames=%d, source=%s, best_ts=%.3f, score=%.4f, elapsed=%.2fs",
            strategy, len(candidates), "pre_sampled" if uses_pre_sampled_frames else "ffmpeg", best_ts, best_final_score,
            time.perf_counter() - started_at,
        )
        return best_ts

    except Exception as exc:
        logger.warning("Cover selection failed, falling back to midpoint: %s", exc)
        return midpoint
    finally:
        if top_up_candidates:
            _cleanup_candidate_files(top_up_candidates)
        elif candidates and not uses_pre_sampled_frames:
            _cleanup_candidate_files(candidates)
