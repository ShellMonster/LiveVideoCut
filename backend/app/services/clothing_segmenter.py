"""Clothing segmenter — MediaPipe clothes mask + YOLO fashionpedia detection.

Combines two models for robust clothing analysis:
1. MediaPipe SelfieMulticlass — pixel-level "clothes" mask for HSV histogram
2. YOLO fashionpedia ONNX — 46-category clothing item detection

Both models run on CPU. Each is lazy-loaded on first use and has graceful
fallback if the model file is missing or fails to load.
"""

import logging
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Main garment classes — used for category-change detection
# Indices into FASHPEDIA_CLASSES that represent whole garments
MAIN_GARMENT_INDICES = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11}
UPPER_BODY_CLASSES = {0, 1, 2, 3, 4, 5, 9, 10, 11}
LOWER_BODY_CLASSES = {6, 7, 8}

FASHPEDIA_CLASSES = [
    "shirt, blouse",       # 0
    "top, t-shirt, sweatshirt",  # 1
    "sweater",             # 2
    "cardigan",            # 3
    "jacket",              # 4
    "vest",                # 5
    "pants",               # 6
    "shorts",              # 7
    "skirt",               # 8
    "coat",                # 9
    "dress",               # 10
    "jumpsuit",            # 11
    "cape",                # 12
    "glasses",             # 13
    "hat",                 # 14
    "headband, head covering, hair accessory",  # 15
    "tie",                 # 16
    "glove",               # 17
    "watch",               # 18
    "belt",                # 19
    "leg warmer",          # 20
    "tights, stockings",   # 21
    "sock",                # 22
    "shoe",                # 23
    "bag, wallet",         # 24
    "scarf",               # 25
    "umbrella",            # 26
    "hood",                # 27
    "collar",              # 28
    "lapel",               # 29
    "epaulette",           # 30
    "sleeve",              # 31
    "pocket",              # 32
    "neckline",            # 33
    "buckle",              # 34
    "zipper",              # 35
    "applique",            # 36
    "bead",                # 37
    "bow",                 # 38
    "flower",              # 39
    "fringe",              # 40
    "ribbon",              # 41
    "rivet",               # 42
    "ruffle",              # 43
    "sequin",              # 44
    "tassel",              # 45
]

# Default path for YOLO model inside Docker container
DEFAULT_YOLO_MODEL_PATH = "/app/assets/models/yolov8n-fashionpedia.onnx"


class ClothingSegmenter:
    """Combines MediaPipe clothes mask + YOLO fashionpedia detection."""

    def __init__(self, yolo_model_path: str | None = None) -> None:
        self._yolo_model_path = yolo_model_path or DEFAULT_YOLO_MODEL_PATH
        self._mp_segmenter = None
        self._yolo_session = None
        self._mp_available: bool | None = None
        self._yolo_available: bool | None = None
        self._orb = cv2.ORB_create(nfeatures=128)
        self._bf_matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)

    # ------------------------------------------------------------------
    # Lazy initialization
    # ------------------------------------------------------------------

    def _init_mediapipe(self) -> bool:
        """Initialize MediaPipe Image Segmenter. Returns True on success."""
        if self._mp_available is not None:
            return self._mp_available

        try:
            import mediapipe as mp
            from mediapipe.tasks import python
            from mediapipe.tasks.python import vision

            options = vision.ImageSegmenterOptions(
                base_options=python.BaseOptions(
                    model_asset_path="/app/assets/models/selfie_multiclass_256x256.tflite",
                ),
                output_category_mask=True,
            )
            self._mp_segmenter = vision.ImageSegmenter.create_from_options(options)
            self._mp_available = True
            logger.info("MediaPipe selfie_multiclass segmenter loaded successfully")
        except Exception as exc:
            logger.warning("MediaPipe segmenter unavailable, falling back to whole-frame HSV: %s", exc)
            self._mp_available = False
        return self._mp_available

    def _init_yolo(self) -> bool:
        """Initialize YOLO ONNX session. Returns True on success."""
        if self._yolo_available is not None:
            return self._yolo_available

        model_path = Path(self._yolo_model_path)
        if not model_path.exists():
            logger.warning(
                "YOLO model not found at %s, skipping category detection",
                self._yolo_model_path,
            )
            self._yolo_available = False
            return False

        try:
            import onnxruntime as ort

            self._yolo_session = ort.InferenceSession(
                str(model_path),
                providers=["CPUExecutionProvider"],
            )
            self._yolo_available = True
            logger.info("YOLO fashionpedia ONNX model loaded from %s", self._yolo_model_path)
        except Exception as exc:
            logger.warning("YOLO ONNX session failed to load: %s", exc)
            self._yolo_available = False
        return self._yolo_available

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def mediapipe_available(self) -> bool:
        """Whether MediaPipe segmenter loaded successfully."""
        if self._mp_available is None:
            self._init_mediapipe()
        return bool(self._mp_available)

    @property
    def yolo_available(self) -> bool:
        """Whether YOLO ONNX model loaded successfully."""
        if self._yolo_available is None:
            self._init_yolo()
        return bool(self._yolo_available)

    def extract_clothes_mask(self, image_rgb: np.ndarray) -> np.ndarray:
        """Extract binary mask where clothes pixels are True.

        Falls back to a full-frame mask (all True) if MediaPipe is unavailable.
        """
        if not self._init_mediapipe():
            # Fallback: treat entire frame as "clothes"
            return np.ones(image_rgb.shape[:2], dtype=bool)

        try:
            import mediapipe as mp

            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image_rgb)
            assert self._mp_segmenter is not None  # guaranteed by _init_mediapipe() check
            result = self._mp_segmenter.segment(mp_image)
            category_mask = result.category_mask.numpy()
            return category_mask == 4  # class 4 = clothes
        except Exception as exc:
            logger.debug("MediaPipe segmentation failed on frame: %s", exc)
            return np.ones(image_rgb.shape[:2], dtype=bool)

    def detect_clothing_items(self, image_rgb: np.ndarray) -> list[dict]:
        """Detect clothing items using YOLO fashionpedia.

        Returns:
            List of {class_id, class_name, confidence, bbox: [x1, y1, x2, y2]}
        """
        if not self._init_yolo():
            return []

        try:
            return self._run_yolo_inference(image_rgb)
        except Exception as exc:
            logger.debug("YOLO inference failed: %s", exc)
            return []

    def analyze_frame(self, image_path: str) -> dict:
        img_bgr = cv2.imread(image_path)
        if img_bgr is None:
            logger.warning("Failed to read image: %s", image_path)
            img_bgr = np.zeros((360, 640, 3), dtype=np.uint8)

        h, w = img_bgr.shape[:2]
        max_dim = 640
        if max(h, w) > max_dim:
            scale = max_dim / max(h, w)
            img_bgr = cv2.resize(img_bgr, (int(w * scale), int(h * scale)))

        image_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

        mask = self.extract_clothes_mask(image_rgb)
        items = self.detect_clothing_items(image_rgb)

        hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
        mask_uint8 = mask.astype(np.uint8) * 255

        # Global HSV (full MediaPipe clothes mask)
        hsv_hist = self._calc_hsv_hist(hsv, mask_uint8)

        # Per-region HSV (YOLO bbox ∩ MediaPipe mask)
        upper_mask = np.zeros(img_bgr.shape[:2], dtype=np.uint8)
        lower_mask = np.zeros(img_bgr.shape[:2], dtype=np.uint8)
        for item in items:
            if item["class_id"] not in UPPER_BODY_CLASSES | LOWER_BODY_CLASSES:
                continue
            x1, y1, x2, y2 = (int(v) for v in item["bbox"])
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)
            if x2 <= x1 or y2 <= y1:
                continue
            region_mask = mask[y1:y2, x1:x2].astype(np.uint8) * 255
            if item["class_id"] in UPPER_BODY_CLASSES:
                upper_mask[y1:y2, x1:x2] = np.maximum(upper_mask[y1:y2, x1:x2], region_mask)
            else:
                lower_mask[y1:y2, x1:x2] = np.maximum(lower_mask[y1:y2, x1:x2], region_mask)

        upper_hist = self._calc_hsv_hist(hsv, upper_mask) if np.any(upper_mask) else None
        lower_hist = self._calc_hsv_hist(hsv, lower_mask) if np.any(lower_mask) else None

        # ORB texture features on upper body crop
        orb_desc = self._extract_orb_features(img_bgr, items)

        return {
            "mask": mask,
            "items": items,
            "hsv_hist": hsv_hist,
            "upper_hsv_hist": upper_hist,
            "lower_hsv_hist": lower_hist,
            "orb_descriptors": orb_desc,
        }

    @staticmethod
    def _calc_hsv_hist(
        hsv: np.ndarray, mask_uint8: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        h_hist = cv2.calcHist([hsv], [0], mask_uint8, [180], [0, 180])
        s_hist = cv2.calcHist([hsv], [1], mask_uint8, [256], [0, 256])
        v_hist = cv2.calcHist([hsv], [2], mask_uint8, [256], [0, 256])
        cv2.normalize(h_hist, h_hist)
        cv2.normalize(s_hist, s_hist)
        cv2.normalize(v_hist, v_hist)
        return (
            h_hist.flatten().astype(np.float32),
            s_hist.flatten().astype(np.float32),
            v_hist.flatten().astype(np.float32),
        )

    def _extract_orb_features(
        self, img_bgr: np.ndarray, items: list[dict],
    ) -> np.ndarray | None:
        upper_item = None
        for item in items:
            if item["class_id"] in UPPER_BODY_CLASSES:
                if upper_item is None or item["confidence"] > upper_item["confidence"]:
                    upper_item = item
        if upper_item is None:
            return None

        x1, y1, x2, y2 = (int(v) for v in upper_item["bbox"])
        h, w = img_bgr.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        if x2 <= x1 or y2 <= y1:
            return None

        crop_gray = cv2.cvtColor(img_bgr[y1:y2, x1:x2], cv2.COLOR_BGR2GRAY)
        _, descriptors = self._orb.detectAndCompute(crop_gray, None)
        return descriptors

    # ------------------------------------------------------------------
    # YOLO inference internals
    # ------------------------------------------------------------------

    def _run_yolo_inference(self, image_rgb: np.ndarray) -> list[dict]:
        """Run YOLO ONNX inference and post-process results."""
        if self._yolo_session is None:
            return []

        orig_h, orig_w = image_rgb.shape[:2]

        img_resized = cv2.resize(image_rgb, (640, 640))
        img_input = img_resized.astype(np.float32) / 255.0
        img_input = img_input.transpose(2, 0, 1)[np.newaxis, ...]

        input_name = self._yolo_session.get_inputs()[0].name
        outputs = self._yolo_session.run(None, {input_name: img_input})

        predictions = np.array(outputs[0])[0].T

        boxes_cxcywh = predictions[:, :4]   # cx, cy, w, h format
        class_scores = predictions[:, 4:]    # 46 class scores

        # Per-detection: best class and confidence
        best_class_ids = class_scores.argmax(axis=1)
        confidences = class_scores.max(axis=1)

        # Filter by confidence threshold
        keep = confidences > 0.25
        boxes_filtered = boxes_cxcywh[keep]
        classes_filtered = best_class_ids[keep]
        confs_filtered = confidences[keep]

        if len(boxes_filtered) == 0:
            return []

        # Convert cx,cy,w,h → x1,y1,x2,y2 (in 640x640 space)
        boxes_xyxy = np.zeros_like(boxes_filtered)
        boxes_xyxy[:, 0] = boxes_filtered[:, 0] - boxes_filtered[:, 2] / 2  # x1
        boxes_xyxy[:, 1] = boxes_filtered[:, 1] - boxes_filtered[:, 3] / 2  # y1
        boxes_xyxy[:, 2] = boxes_filtered[:, 0] + boxes_filtered[:, 2] / 2  # x2
        boxes_xyxy[:, 3] = boxes_filtered[:, 1] + boxes_filtered[:, 3] / 2  # y2

        # Scale to original image size
        scale_x = orig_w / 640.0
        scale_y = orig_h / 640.0
        boxes_xyxy[:, 0] *= scale_x
        boxes_xyxy[:, 2] *= scale_x
        boxes_xyxy[:, 1] *= scale_y
        boxes_xyxy[:, 3] *= scale_y

        # NMS using cv2.dnn
        indices = cv2.dnn.NMSBoxes(
            boxes_xyxy.tolist(),
            confs_filtered.tolist(),
            score_threshold=0.25,
            nms_threshold=0.45,
        )
        if len(indices) == 0:
            return []

        indices = indices.flatten() if isinstance(indices, np.ndarray) else np.array(indices).flatten()

        results = []
        for idx in indices:
            cls_id = int(classes_filtered[idx])
            results.append({
                "class_id": cls_id,
                "class_name": FASHPEDIA_CLASSES[cls_id] if cls_id < len(FASHPEDIA_CLASSES) else f"unknown_{cls_id}",
                "confidence": float(confs_filtered[idx]),
                "bbox": boxes_xyxy[idx].tolist(),
            })

        return results

    @staticmethod
    def get_main_garment_set(items: list[dict]) -> set[int]:
        """Extract the set of main garment class IDs from detections."""
        return {
            item["class_id"]
            for item in items
            if item["class_id"] in MAIN_GARMENT_INDICES
        }
