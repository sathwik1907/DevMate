from __future__ import annotations

import json
import logging
import os
import time
from functools import lru_cache
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from dotenv import load_dotenv
from openai import APIConnectionError, APITimeoutError, BadRequestError, OpenAI, OpenAIError, RateLimitError

from prompts import (
    BUG_FIX_PROMPT,
    CODE_REVIEW_PROMPT,
    COMMIT_PROMPT,
    DEV_MATE_SYSTEM_PROMPT,
    README_PROMPT,
)

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

LOGGER = logging.getLogger(__name__)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_MODELS_URL = f"{OPENROUTER_BASE_URL}/models"
DEFAULT_MAX_TOKENS = 4096
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_FREE_MODEL_CANDIDATES = (
    "poolside/laguna-xs-2.1:free",
    "cohere/north-mini-code:free",
    "qwen/qwen3-next-80b-a3b-instruct:free",
    "openai/gpt-oss-120b:free",
)


class OpenRouterError(RuntimeError):
    """Raised for local OpenRouter configuration issues."""


def openrouter_is_configured() -> bool:
    return bool(os.getenv("OPENROUTER_API_KEY"))


def _normalise_memory(memory: str | None) -> str:
    return (memory or "").strip() or "No relevant Cognee memory found."


def _is_free_text_model(model: dict) -> bool:
    pricing = model.get("pricing") or {}
    architecture = model.get("architecture") or {}
    supported_parameters = set(model.get("supported_parameters") or [])

    return (
        str(model.get("id", "")).endswith(":free")
        and pricing.get("prompt") == "0"
        and pricing.get("completion") == "0"
        and architecture.get("input_modalities") == ["text"]
        and architecture.get("output_modalities") == ["text"]
        and "max_tokens" in supported_parameters
    )


@lru_cache(maxsize=1)
def _current_free_models() -> tuple[str, ...]:
    try:
        with urlopen(OPENROUTER_MODELS_URL, timeout=5) as response:
            payload = json.load(response)
    except (OSError, URLError, ValueError) as exc:
        LOGGER.warning("Could not refresh OpenRouter model list: %s", exc)
        return ()

    models = payload.get("data", [])
    return tuple(model["id"] for model in models if _is_free_text_model(model))


def _model_candidates() -> list[str]:
    configured = os.getenv("OPENROUTER_MODEL", "").strip()
    fallbacks = [
        model.strip()
        for model in os.getenv("OPENROUTER_FALLBACK_MODELS", "").split(",")
        if model.strip()
    ]
    current_free_models = _current_free_models()
    known_free_models = set(current_free_models or DEFAULT_FREE_MODEL_CANDIDATES)

    candidates: list[str] = []
    for model in [configured, *fallbacks, *current_free_models, *DEFAULT_FREE_MODEL_CANDIDATES]:
        if model and model.endswith(":free") and model in known_free_models and model not in candidates:
            candidates.append(model)
    return candidates


def get_openrouter_model() -> str:
    candidates = _model_candidates()
    return candidates[0] if candidates else DEFAULT_FREE_MODEL_CANDIDATES[0]


@lru_cache(maxsize=1)
def _build_client() -> OpenAI:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise OpenRouterError("OPENROUTER_API_KEY is missing. Add it to your .env file.")

    return OpenAI(
        api_key=api_key,
        base_url=OPENROUTER_BASE_URL,
        timeout=float(os.getenv("OPENROUTER_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS)),
        default_headers={
            "HTTP-Referer": os.getenv("OPENROUTER_SITE_URL", "http://localhost:8501"),
            "X-Title": os.getenv("OPENROUTER_APP_NAME", "DevMate"),
        },
    )


def _friendly_error(exc: Exception) -> str:
    if isinstance(exc, OpenRouterError):
        return str(exc)
    if isinstance(exc, (APITimeoutError, TimeoutError)):
        return "OpenRouter request timed out. Please try again."
    if isinstance(exc, APIConnectionError):
        return "Could not connect to OpenRouter. Check your internet connection."
    if isinstance(exc, RateLimitError):
        return "OpenRouter rate limit reached. Please wait and try again."
    if isinstance(exc, BadRequestError):
        return f"OpenRouter rejected the request: {exc}"
    if isinstance(exc, OpenAIError):
        return f"OpenRouter API error: {exc}"
    return str(exc)


def _call_openrouter(user_prompt: str, system_prompt: str = DEV_MATE_SYSTEM_PROMPT.strip()) -> str:
    if not user_prompt.strip():
        return "OpenRouter is temporarily unavailable: prompt is empty."

    errors: list[str] = []
    candidates = _model_candidates()
    if not candidates:
        return "OpenRouter is temporarily unavailable: no free chat models are available."

    for attempt, model in enumerate(candidates):
        try:
            response = _build_client().chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt.strip()},
                ],
                temperature=float(os.getenv("OPENROUTER_TEMPERATURE", "0.2")),
                top_p=float(os.getenv("OPENROUTER_TOP_P", "0.9")),
                max_tokens=int(os.getenv("OPENROUTER_MAX_TOKENS", DEFAULT_MAX_TOKENS)),
                stream=False,
            )
            content = (response.choices[0].message.content or "").strip()
            if content:
                return content
            errors.append(f"{model}: empty response")
        except RateLimitError as exc:
            errors.append(f"{model}: {_friendly_error(exc)}")
            time.sleep(min(2**attempt, 8))
        except Exception as exc:
            LOGGER.warning("OpenRouter model %s failed: %s", model, exc)
            errors.append(f"{model}: {_friendly_error(exc)}")

    return "OpenRouter is temporarily unavailable: " + " | ".join(errors)


def ask_llm(prompt: str, memory: str = "") -> str:
    combined_prompt = f"""Previous memory:
{_normalise_memory(memory)}

User:
{prompt.strip()}"""
    return _call_openrouter(combined_prompt)


def review_code(code: str, language: str, memory: str = "") -> str:
    prompt = CODE_REVIEW_PROMPT.format(
        system_prompt=DEV_MATE_SYSTEM_PROMPT.strip(),
        memory_context=_normalise_memory(memory),
        language=language or "text",
        code=code.strip(),
    )
    return _call_openrouter(prompt)


def explain_bug(traceback: str, memory: str = "") -> str:
    prompt = BUG_FIX_PROMPT.format(
        system_prompt=DEV_MATE_SYSTEM_PROMPT.strip(),
        memory_context=_normalise_memory(memory),
        traceback=traceback.strip(),
    )
    return _call_openrouter(prompt)


def generate_readme(description: str, memory: str = "") -> str:
    prompt = README_PROMPT.format(
        system_prompt=DEV_MATE_SYSTEM_PROMPT.strip(),
        memory_context=_normalise_memory(memory),
        description=description.strip(),
    )
    return _call_openrouter(prompt)


def generate_commit_message(changes: str) -> str:
    prompt = COMMIT_PROMPT.format(
        system_prompt=DEV_MATE_SYSTEM_PROMPT.strip(),
        changes=changes.strip(),
    )
    return _call_openrouter(prompt)
