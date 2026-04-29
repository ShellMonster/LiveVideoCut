import pytest

from app.utils import json_io


def test_read_json_silent_returns_fallback_for_invalid_json(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{broken")

    assert json_io.read_json_silent(path, {"ok": False}) == {"ok": False}


def test_write_json_writes_atomically_and_supports_json_default(tmp_path):
    path = tmp_path / "payload.json"

    json_io.write_json(path, {"value": tmp_path}, json_default=str)

    assert json_io.read_json(path, {}) == {"value": str(tmp_path)}


def test_write_json_keeps_existing_file_when_replace_fails(tmp_path, monkeypatch):
    path = tmp_path / "payload.json"
    path.write_text('{"old": true}')

    def fail_replace(src, dst):
        raise RuntimeError("replace failed")

    monkeypatch.setattr(json_io.os, "replace", fail_replace)

    with pytest.raises(RuntimeError, match="replace failed"):
        json_io.write_json(path, {"old": False})

    assert path.read_text() == '{"old": true}'
    assert list(tmp_path.glob(".payload.json.*.tmp")) == []
