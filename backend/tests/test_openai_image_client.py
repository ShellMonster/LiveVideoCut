from app.services.openai_image_client import _resolve_image_size


def test_resolve_image_size_accepts_2k_alias():
    assert _resolve_image_size("2K") == "2048x2048"
    assert _resolve_image_size("") == "2048x2048"


def test_resolve_image_size_preserves_explicit_size():
    assert _resolve_image_size("1024x1536") == "1024x1536"
