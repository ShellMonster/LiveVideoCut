"""Shared configuration constants — safe to import from any layer (API, services, tasks)."""

from enum import Enum


class VLMProvider(str, Enum):
    qwen = "qwen"
    glm = "glm"


QWEN_API_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"
GLM_API_BASE = "https://open.bigmodel.cn/api/paas/v4"

DEFAULT_API_BASES = {
    "qwen": QWEN_API_BASE,
    "glm": GLM_API_BASE,
}

DEFAULT_MODELS = {
    "qwen": "qwen-vl-plus",
    "glm": "glm-5v-turbo",
}

PROVIDER_HOST_HINTS = {
    "qwen": ("dashscope.aliyuncs.com",),
    "glm": ("open.bigmodel.cn",),
}

PROVIDER_MODEL_PREFIXES = {
    "qwen": ("qwen-",),
    "glm": ("glm-",),
}
