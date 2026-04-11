import importlib
import sys


def _reload_pipeline_module():
    sys.modules.pop("app.tasks.pipeline", None)
    return importlib.import_module("app.tasks.pipeline")


def test_celery_uses_redis_url_from_environment(monkeypatch):
    redis_url = "redis://redis:6379/0"
    monkeypatch.setenv("REDIS_URL", redis_url)

    pipeline = _reload_pipeline_module()

    assert pipeline.celery_app.conf.broker_url == redis_url
    assert pipeline.celery_app.conf.result_backend == redis_url
