"""Tests for FashionSigLIPEncoder — mock mode only (no ONNX model in dev)."""

import numpy as np
import pytest

from app.services.siglip_encoder import FashionSigLIPEncoder


@pytest.fixture
def encoder():
    return FashionSigLIPEncoder(model_dir="/nonexistent/model/path")


class TestMockMode:
    def test_mock_mode_is_true_when_model_not_found(self, encoder):
        assert encoder.mock_mode is True

    def test_encode_image_returns_correct_shape(self, encoder, tmp_path):
        from PIL import Image

        img = Image.new("RGB", (100, 100), color="red")
        img_path = tmp_path / "test.jpg"
        img.save(img_path)

        result = encoder.encode_image(str(img_path))
        assert result.shape == (768,)
        assert result.dtype == np.float32

    def test_encode_image_returns_unit_vector(self, encoder, tmp_path):
        from PIL import Image

        img = Image.new("RGB", (100, 100), color="blue")
        img_path = tmp_path / "test.jpg"
        img.save(img_path)

        result = encoder.encode_image(str(img_path))
        norm = np.linalg.norm(result)
        assert abs(norm - 1.0) < 1e-5

    def test_encode_batch_returns_correct_shape(self, encoder, tmp_path):
        from PIL import Image

        paths = []
        for i in range(5):
            img = Image.new("RGB", (50, 50), color=(i * 50, 0, 0))
            p = tmp_path / f"img_{i}.jpg"
            img.save(p)
            paths.append(str(p))

        result = encoder.encode_batch(paths)
        assert result.shape == (5, 768)

    def test_encode_batch_empty_returns_empty(self, encoder):
        result = encoder.encode_batch([])
        assert result.shape == (0, 768)

    def test_deterministic_encoding(self, encoder, tmp_path):
        from PIL import Image

        img = Image.new("RGB", (100, 100), color="green")
        img_path = tmp_path / "test.jpg"
        img.save(img_path)

        result1 = encoder.encode_image(str(img_path))
        result2 = encoder.encode_image(str(img_path))
        np.testing.assert_array_equal(result1, result2)

    def test_different_images_different_vectors(self, encoder, tmp_path):
        from PIL import Image

        img1 = Image.new("RGB", (100, 100), color="red")
        img2 = Image.new("RGB", (100, 100), color="blue")
        p1 = tmp_path / "red.jpg"
        p2 = tmp_path / "blue.jpg"
        img1.save(p1)
        img2.save(p2)

        v1 = encoder.encode_image(str(p1))
        v2 = encoder.encode_image(str(p2))
        # Different images should produce different vectors
        assert not np.allclose(v1, v2)
