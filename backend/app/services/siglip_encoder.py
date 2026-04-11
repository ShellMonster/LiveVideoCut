"""FashionSigLIP image encoder using ONNX Runtime with mock fallback."""

import hashlib
from pathlib import Path

import numpy as np
from PIL import Image

try:
    import onnxruntime as ort
except ImportError:
    ort = None


class FashionSigLIPEncoder:
    """Encodes images using FashionSigLIP ONNX model → 768-dim vectors.

    Falls back to deterministic mock vectors when the ONNX model file is
    not available (dev/test mode).
    """

    EMBEDDING_DIM = 768
    INPUT_SIZE = (224, 224)
    IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)

    def __init__(self, model_dir: str = "models/fashion_siglip"):
        self._model_dir = Path(model_dir)
        self._session = None
        self._input_name = None
        self._mock_mode = True

        model_path = self._model_dir / "model.onnx"
        if model_path.exists() and ort is not None:
            try:
                self._session = ort.InferenceSession(
                    str(model_path), providers=["CPUExecutionProvider"]
                )
                self._input_name = self._session.get_inputs()[0].name
                self._mock_mode = False
            except Exception:
                self._mock_mode = True

    @property
    def mock_mode(self) -> bool:
        """True if real model not available, uses random vectors."""
        return self._mock_mode

    def encode_image(self, image_path: str) -> np.ndarray:
        """Encode a single image to a 768-dim vector. Returns shape (768,)."""
        if self._mock_mode:
            return self._mock_encode(image_path)

        img = self._load_and_preprocess(image_path)
        output = self._session.run(None, {self._input_name: img})
        return output[0].flatten()

    def encode_batch(self, image_paths: list[str], batch_size: int = 32) -> np.ndarray:
        """Encode multiple images. Returns shape (N, 768)."""
        if not image_paths:
            return np.empty((0, self.EMBEDDING_DIM), dtype=np.float32)

        if self._mock_mode:
            return np.stack([self._mock_encode(p) for p in image_paths])

        all_embeddings = []
        for i in range(0, len(image_paths), batch_size):
            batch_paths = image_paths[i : i + batch_size]
            batch_arrays = [self._load_and_preprocess(p) for p in batch_paths]
            batch_input = np.concatenate(batch_arrays, axis=0)
            output = self._session.run(None, {self._input_name: batch_input})
            all_embeddings.append(output[0].reshape(len(batch_paths), -1))

        return np.concatenate(all_embeddings, axis=0)

    def _load_and_preprocess(self, image_path: str) -> np.ndarray:
        """Load image, resize to 224x224, normalize with ImageNet stats."""
        img = Image.open(image_path).convert("RGB")
        img = img.resize(self.INPUT_SIZE, Image.BILINEAR)
        arr = np.array(img, dtype=np.float32) / 255.0
        arr = (arr - self.IMAGENET_MEAN) / self.IMAGENET_STD
        # HWC → CHW, add batch dim
        arr = arr.transpose(2, 0, 1)[np.newaxis, ...]
        return arr.astype(np.float32)

    def _mock_encode(self, image_path: str) -> np.ndarray:
        """Deterministic mock encoding seeded by image path hash."""
        seed = int(hashlib.md5(image_path.encode()).hexdigest(), 16) % (2**31)
        rng = np.random.RandomState(seed)
        vec = rng.randn(self.EMBEDDING_DIM).astype(np.float32)
        # Normalize to unit vector
        vec /= np.linalg.norm(vec)
        return vec
