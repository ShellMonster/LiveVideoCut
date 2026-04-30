import pytest

from app.services import app_settings


def test_current_settings_prefers_sqlite_over_env_and_returns_plaintext(tmp_path, monkeypatch):
    monkeypatch.setenv("COMMERCE_GEMINI_API_BASE", "https://env-gemini.example.com")
    monkeypatch.setenv("COMMERCE_GEMINI_API_KEY", "env-gemini-key")
    monkeypatch.setenv("COMMERCE_IMAGE_API_BASE", "https://env-image.example.com/v1")
    monkeypatch.setenv("COMMERCE_IMAGE_API_KEY", "env-image-key")

    initial = app_settings.get_current_settings(tmp_path)
    assert initial["commerce_gemini_api_base"] == "https://env-gemini.example.com"
    assert initial["commerce_gemini_api_key"] == "env-gemini-key"
    assert initial["commerce_image_api_base"] == "https://env-image.example.com/v1"
    assert initial["commerce_image_api_key"] == "env-image-key"

    saved = app_settings.save_current_settings(
        {
            "commerce_gemini_api_base": "https://sqlite-gemini.example.com",
            "commerce_gemini_api_key": "sqlite-gemini-key",
            "commerce_image_api_base": "https://sqlite-image.example.com/v1",
            "commerce_image_api_key": "sqlite-image-key",
        },
        tmp_path,
    )

    assert saved["commerce_gemini_api_base"] == "https://sqlite-gemini.example.com"
    assert saved["commerce_gemini_api_key"] == "sqlite-gemini-key"
    assert saved["commerce_image_api_base"] == "https://sqlite-image.example.com/v1"
    assert saved["commerce_image_api_key"] == "sqlite-image-key"
    assert (tmp_path / "app_config.sqlite3").exists()


def test_env_fallback_is_not_persisted_until_user_overrides(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_API_BASE", "https://env-llm.example.com/v1")
    monkeypatch.setenv("LLM_MODEL", "env-model")

    current = app_settings.get_current_settings(tmp_path)

    assert current["llm_api_base"] == "https://env-llm.example.com/v1"
    assert current["llm_model"] == "env-model"
    assert app_settings.read_saved_settings(tmp_path) == {}

    saved = app_settings.save_current_settings({"llm_model": "sqlite-model"}, tmp_path)

    assert saved["llm_api_base"] == "https://env-llm.example.com/v1"
    assert saved["llm_model"] == "sqlite-model"
    assert app_settings.read_saved_settings(tmp_path) == {"llm_model": "sqlite-model"}


def test_empty_value_removes_override_and_returns_to_env(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_API_BASE", "https://env-llm.example.com/v1")

    app_settings.save_current_settings({"llm_api_base": "https://sqlite-llm.example.com/v1"}, tmp_path)
    assert app_settings.read_saved_settings(tmp_path)["llm_api_base"] == "https://sqlite-llm.example.com/v1"

    saved = app_settings.save_current_settings({"llm_api_base": ""}, tmp_path)

    assert saved["llm_api_base"] == "https://env-llm.example.com/v1"
    assert "llm_api_base" not in app_settings.read_saved_settings(tmp_path)


@pytest.mark.anyio
async def test_current_settings_api_persists_plaintext_values(client, tmp_path, monkeypatch):
    monkeypatch.setattr("app.api.settings.UPLOAD_DIR", tmp_path)
    monkeypatch.setattr("app.api.settings.app_settings.UPLOAD_DIR", tmp_path)
    monkeypatch.setenv("LLM_API_BASE", "https://env-llm.example.com/v1")

    response = await client.get("/api/settings/current")
    assert response.status_code == 200
    assert response.json()["llm_api_base"] == "https://env-llm.example.com/v1"

    save_response = await client.put(
        "/api/settings/current",
        json={
            "llm_api_key": "sqlite-llm-key",
            "llm_api_base": "https://sqlite-llm.example.com/v1",
            "llm_model": "sqlite-model",
            "commerce_gemini_api_base": "https://sqlite-gemini.example.com",
            "commerce_gemini_api_key": "sqlite-gemini-key",
        },
    )

    assert save_response.status_code == 200
    payload = save_response.json()
    assert payload["llm_api_key"] == "sqlite-llm-key"
    assert payload["llm_api_base"] == "https://sqlite-llm.example.com/v1"
    assert payload["llm_model"] == "sqlite-model"
    assert payload["commerce_gemini_api_base"] == "https://sqlite-gemini.example.com"
    assert payload["commerce_gemini_api_key"] == "sqlite-gemini-key"

    next_response = await client.get("/api/settings/current")
    assert next_response.status_code == 200
    assert next_response.json()["llm_api_key"] == "sqlite-llm-key"
