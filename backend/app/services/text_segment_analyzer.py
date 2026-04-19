import json
import logging
import time
from typing import Any, cast
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from openai import OpenAI

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
TIMEOUT_SECONDS = 60
CHUNK_DURATION = 300  # 5 minutes
CHUNK_OVERLAP = 30  # 30 seconds overlap
MERGE_THRESHOLD = 10  # dedup boundaries within 10 seconds

SYSTEM_PROMPT = """你是一位直播视频内容分析专家。你的任务是分析直播转写文本，识别主播讲解的每一个商品/服装切换边界。

你需要输出严格的 JSON 格式（不要包含 markdown 代码块标记），结构如下：
{
  "segments": [
    {
      "start_time": 123.45,
      "end_time": 234.56,
      "product_description": "对当前讲解商品的简要描述（10字以内）",
      "product_type": "服装类别，如：连衣裙、外套、上衣、裤子、半裙、配饰、其他",
      "confidence": 0.85,
      "key_phrases": ["关键词1", "关键词2"],
      "boundary_reason": "判断边界的原因"
    }
  ]
}

判断规则：
1. 关注主播语言中的商品切换信号词，如"接下来"、"看这个"、"这款"、"另一件"、"下一个"等
2. 每个segment必须只对应一个商品。即使主播在讲搭配（如"这个毛衣配这条裙子"），每个单品也应该单独拆成一个segment
3. 当主播从讲解一个商品转向另一个商品时，必须标记为新边界，即使两个商品是搭配关系
4. product_description 尽量简短（10字以内），只写单品名称，不要写搭配组合描述
5. 宁可多切也不要漏切——把一个大段拆成多个小段比把多个商品合成一段更好
6. confidence 反映你对边界判断的把握程度
7. 如果无法确定商品切换，输出空 segments 数组
8. 只输出 JSON，不要有任何其他文字"""

SYSTEM_PROMPT_OUTFIT = """你是一位直播视频内容分析专家。你的任务是分析直播转写文本，识别主播讲解的商品/服装切换边界。

你需要输出严格的 JSON 格式（不要包含 markdown 代码块标记），结构如下：
{
  "segments": [
    {
      "start_time": 123.45,
      "end_time": 234.56,
      "product_description": "对当前讲解商品的简要描述",
      "product_type": "服装类别，如：连衣裙、外套、上衣、裤子、配饰、其他",
      "confidence": 0.85,
      "key_phrases": ["关键词1", "关键词2"],
      "boundary_reason": "判断边界的原因"
    }
  ]
}

判断规则：
1. 关注主播语言中的商品切换信号词，如"接下来"、"看这个"、"这款"、"另一件"等
2. 当主播从讲解一个商品转向另一个商品时，标记为边界
3. 同一套搭配（如毛衣+裙子+背心正在一起展示）应归为一段，只有明显切换到另一套搭配时才标记边界
4. product_description 可以包含搭配描述
5. confidence 反映你对边界判断的把握程度
6. 如果无法确定商品切换，输出空 segments 数组
7. 只输出 JSON，不要有任何其他文字"""


class TextSegmentAnalyzer:
    def __init__(self, api_key: str, api_base: str, model: str, llm_type: str = "openai"):
        self.api_key = api_key
        self.api_base = api_base
        self.model = model
        self.llm_type = llm_type
        self._granularity = "single_item"

        if llm_type == "gemini":
            self._caller = _GeminiCaller(api_key, api_base, model)
        else:
            self._caller = _OpenAICaller(api_key, api_base, model)

    def analyze(self, transcript: list[dict[str, Any]], segment_granularity: str = "single_item") -> list[dict[str, Any]]:
        if not transcript:
            logger.info("Empty transcript, returning no boundaries")
            return []

        self._granularity = segment_granularity
        total_duration = transcript[-1].get("end_time", 0)
        logger.info(
            "Analyzing transcript: %d segments, %.1fs, granularity=%s",
            len(transcript),
            total_duration,
            segment_granularity,
        )

        if total_duration <= CHUNK_DURATION + CHUNK_OVERLAP:
            return self._analyze_chunk(transcript)

        chunks = self._split_into_chunks(transcript)
        logger.info("Split transcript into %d chunks", len(chunks))

        all_boundaries: list[dict[str, Any]] = []
        for i, chunk in enumerate(chunks):
            logger.info("Processing chunk %d/%d (%d segments)", i + 1, len(chunks), len(chunk))
            boundaries = self._analyze_chunk(chunk)
            all_boundaries.extend(boundaries)

        merged = _merge_boundaries(all_boundaries)
        logger.info("Merged %d boundaries into %d", len(all_boundaries), len(merged))
        return merged

    def _split_into_chunks(self, transcript: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
        chunks: list[list[dict[str, Any]]] = []
        chunk_start = 0.0

        while chunk_start < transcript[-1]["end_time"]:
            chunk_end = chunk_start + CHUNK_DURATION
            overlap_start = max(0.0, chunk_start - CHUNK_OVERLAP) if chunks else chunk_start

            chunk = [
                seg
                for seg in transcript
                if seg["start_time"] >= overlap_start and seg["start_time"] < chunk_end + CHUNK_OVERLAP
            ]
            if chunk:
                chunks.append(chunk)

            chunk_start = chunk_end

        return chunks

    def _analyze_chunk(self, chunk: list[dict[str, Any]]) -> list[dict[str, Any]]:
        text_parts: list[str] = []
        for seg in chunk:
            start = seg.get("start_time", 0)
            end = seg.get("end_time", 0)
            text = seg.get("text", "").strip()
            if text:
                text_parts.append(f"[{start:.1f}s - {end:.1f}s] {text}")

        if not text_parts:
            return []

        user_content = "以下是直播转写文本（含时间戳），请分析商品/服装切换边界：\n\n" + "\n".join(text_parts)

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT_OUTFIT if getattr(self, "_granularity", "single_item") == "outfit" else SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

        response_text = self._call_api(messages)
        if not response_text:
            return []

        return _parse_response(response_text)

    def _call_api(self, messages: list[dict[str, Any]]) -> str:
        return self._caller.call(messages)


class _OpenAICaller:
    def __init__(self, api_key: str, api_base: str, model: str):
        self.model = model
        self.client = OpenAI(api_key=api_key, base_url=api_base)

    def call(self, messages: list[dict[str, Any]]) -> str:
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=cast(Any, messages),
                    timeout=TIMEOUT_SECONDS,
                )
                return response.choices[0].message.content or ""
            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    wait = 2**attempt
                    logger.warning(
                        "OpenAI API call failed (attempt %d/%d), retrying in %ds: %s",
                        attempt + 1, MAX_RETRIES, wait, str(e),
                    )
                    time.sleep(wait)
                else:
                    logger.error(
                        "OpenAI API call failed after %d attempts: %s",
                        MAX_RETRIES, str(e),
                    )
        raise RuntimeError(
            f"OpenAI API call failed after {MAX_RETRIES} attempts: {last_error}"
        )


class _GeminiCaller:
    GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(self, api_key: str, api_base: str, model: str):
        self.api_key = api_key
        self.base_url = api_base.rstrip("/") if api_base else self.GEMINI_BASE
        self.model = model

    def call(self, messages: list[dict[str, Any]]) -> str:
        url = f"{self.base_url}/{self.model}:generateContent"
        payload = self._build_payload(messages)
        body = json.dumps(payload).encode("utf-8")

        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                req = Request(url, data=body, method="POST")
                req.add_header("x-goog-api-key", self.api_key)
                req.add_header("Content-Type", "application/json")

                with urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
                    data = json.loads(resp.read())

                candidates = data.get("candidates", [])
                if not candidates:
                    block = data.get("promptFeedback", {}).get("blockReason", "unknown")
                    raise RuntimeError(f"Gemini returned no candidates, blockReason={block}")

                return candidates[0]["content"]["parts"][0]["text"]
            except Exception as e:
                last_error = e
                if isinstance(e, HTTPError):
                    error_body = ""
                    try:
                        error_body = e.read().decode("utf-8", errors="replace")
                    except Exception:
                        pass
                    logger.warning(
                        "Gemini API HTTP %d (attempt %d/%d): %s",
                        e.code, attempt + 1, MAX_RETRIES, error_body[:300],
                    )
                else:
                    logger.warning(
                        "Gemini API call failed (attempt %d/%d): %s",
                        attempt + 1, MAX_RETRIES, str(e),
                    )
                if attempt < MAX_RETRIES - 1:
                    time.sleep(2**attempt)
                else:
                    logger.error(
                        "Gemini API call failed after %d attempts: %s",
                        MAX_RETRIES, str(last_error),
                    )

        raise RuntimeError(
            f"Gemini API call failed after {MAX_RETRIES} attempts: {last_error}"
        )

    def _build_payload(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        system_text = ""
        user_parts: list[dict[str, str]] = []

        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "system":
                system_text = content if isinstance(content, str) else str(content)
            elif role == "user":
                if isinstance(content, str):
                    user_parts.append({"text": content})
                elif isinstance(content, list):
                    for part in content:
                        if isinstance(part, dict) and part.get("type") == "text":
                            user_parts.append({"text": part["text"]})

        payload: dict[str, Any] = {
            "contents": [{"role": "user", "parts": user_parts}],
        }
        if system_text:
            payload["systemInstruction"] = {"parts": [{"text": system_text}]}
        return payload


def _parse_response(text: str) -> list[dict[str, Any]]:
    text = text.strip()
    if text.startswith("```"):
        first_newline = text.index("\n") if "\n" in text else len(text)
        text = text[first_newline + 1 :]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Failed to parse LLM response as JSON: %.200s", text)
        return []

    segments = data.get("segments", [])
    if not isinstance(segments, list):
        logger.warning("LLM response 'segments' is not a list")
        return []

    valid: list[dict[str, Any]] = []
    for seg in segments:
        if not isinstance(seg, dict):
            continue
        if "start_time" not in seg or "end_time" not in seg:
            continue
        try:
            seg["start_time"] = float(seg["start_time"])
            seg["end_time"] = float(seg["end_time"])
            seg["confidence"] = float(seg.get("confidence", 0.5))
        except (ValueError, TypeError):
            continue
        seg.setdefault("product_description", "")
        seg.setdefault("product_type", "")
        seg.setdefault("key_phrases", [])
        seg.setdefault("boundary_reason", "")
        valid.append(seg)

    logger.info("Parsed %d valid segments from LLM response", len(valid))
    return valid


def _merge_boundaries(boundaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not boundaries:
        return []

    sorted_bounds = sorted(boundaries, key=lambda b: b["start_time"])
    merged: list[dict[str, Any]] = [sorted_bounds[0]]

    for boundary in sorted_bounds[1:]:
        last = merged[-1]
        gap = boundary["start_time"] - last["start_time"]

        if gap < MERGE_THRESHOLD:
            if boundary["confidence"] > last["confidence"]:
                merged[-1] = boundary
        else:
            merged.append(boundary)

    return merged
