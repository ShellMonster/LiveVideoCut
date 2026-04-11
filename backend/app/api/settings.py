from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class SettingsRequest(BaseModel):
    api_key: str
    api_base: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    model: str = "qwen-vl-plus"


@router.post("/api/settings/validate")
async def validate_settings(settings: SettingsRequest):
    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.api_key, base_url=settings.api_base)
        client.chat.completions.create(
            model=settings.model,
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=1,
        )
        return {"valid": True}
    except Exception as e:
        return {"valid": False, "error": str(e)}
