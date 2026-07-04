from __future__ import annotations

import asyncio
import os
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

os.environ.setdefault("COGNEE_SKIP_CONNECTION_TEST", "true")
os.environ["LLM_PROVIDER"] = "openai"
os.environ["LLM_ENDPOINT"] = "https://openrouter.ai/api/v1"
openrouter_model = os.getenv("OPENROUTER_MODEL", "poolside/laguna-xs-2.1:free")
os.environ["LLM_MODEL"] = os.getenv("LLM_MODEL") or f"openai/{openrouter_model}"
if os.getenv("OPENROUTER_API_KEY"):
    os.environ["LLM_API_KEY"] = os.getenv("OPENROUTER_API_KEY", "")

import cognee  # noqa: E402

DATASET_NAME = os.getenv("COGNEE_DATASET_NAME", "devmate_memory")
SESSION_ID = os.getenv("COGNEE_SESSION_ID", "devmate-default-session")
DEFAULT_TOP_K = int(os.getenv("COGNEE_TOP_K", "8"))
PERMANENT_MEMORY = os.getenv("COGNEE_PERMANENT_MEMORY", "true").lower() == "true"


class MemoryError(RuntimeError):
    """Raised when Cognee memory operations fail."""


@dataclass
class MemoryResult:
    text: str
    source: str = "cognee"
    score: float | None = None


def cognee_is_configured() -> bool:
    return True


def _run_async(coro: Any) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    result: dict[str, Any] = {}

    def runner() -> None:
        try:
            result["value"] = asyncio.run(coro)
        except Exception as exc:
            result["error"] = exc

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    thread.join()

    if "error" in result:
        raise result["error"]
    return result.get("value")


def _stamp(text: str, category: str) -> str:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    clean_category = category.strip() or "general"
    return (
        f"DevMate memory\n"
        f"Category: {clean_category}\n"
        f"Saved at: {timestamp}\n"
        f"Content: {text.strip()}"
    )


def _extract_text(item: Any) -> str:
    for attr in ("answer", "text", "content", "context"):
        value = getattr(item, attr, None)
        if value:
            return str(value)

    if isinstance(item, dict):
        for key in ("answer", "text", "content", "context"):
            value = item.get(key)
            if value:
                return str(value)

    return str(item)


def _extract_score(item: Any) -> float | None:
    score = getattr(item, "score", None)
    if score is None and isinstance(item, dict):
        score = item.get("score")
    try:
        return float(score) if score is not None else None
    except (TypeError, ValueError):
        return None


async def _remember_async(text: str, category: str) -> Any:
    memory_text = _stamp(text, category)
    session_result = await cognee.remember(
        memory_text,
        dataset_name=DATASET_NAME,
        session_id=SESSION_ID,
        self_improvement=False,
    )

    if not PERMANENT_MEMORY:
        return session_result

    # Permanent graph memory needs Cognee's configured LLM key.
    # Session memory still works locally when the API key has not been added yet.
    if not os.getenv("LLM_API_KEY"):
        return session_result

    try:
        return await cognee.remember(
            memory_text,
            dataset_name=DATASET_NAME,
            self_improvement=False,
        )
    except Exception:
        return session_result


async def _recall_async(query: str, top_k: int) -> list[Any]:
    return await cognee.recall(
        query_text=query,
        datasets=[DATASET_NAME],
        session_id=SESSION_ID,
        only_context=True,
        top_k=top_k,
    )


def remember(text: str, category: str = "general") -> str:
    if not text or not text.strip():
        raise MemoryError("Memory text cannot be empty.")

    try:
        result = _run_async(_remember_async(text, category))
    except Exception as exc:
        raise MemoryError(f"Cognee could not save this memory: {exc}") from exc

    status = getattr(result, "status", "saved")
    return f"Memory saved to Cognee ({status})."


def recall(query: str, top_k: int = DEFAULT_TOP_K) -> list[MemoryResult]:
    if not query or not query.strip():
        raise MemoryError("Recall query cannot be empty.")

    try:
        raw_results = _run_async(_recall_async(query, top_k))
    except Exception as exc:
        if "DatasetNotFound" in str(exc) or "No datasets found" in str(exc):
            try:
                raw_results = _run_async(
                    cognee.recall(
                        query_text=query,
                        session_id=SESSION_ID,
                        only_context=True,
                        top_k=top_k,
                    )
                )
            except Exception:
                return []
        else:
            raise MemoryError(f"Cognee could not recall memory: {exc}") from exc

    results = []
    for item in raw_results or []:
        text = _extract_text(item).strip()
        if text:
            source = getattr(item, "source", "cognee")
            if isinstance(item, dict):
                source = item.get("source", source)
            results.append(MemoryResult(text=text, source=str(source), score=_extract_score(item)))
    return results


def get_memory(query: str, top_k: int = DEFAULT_TOP_K) -> str:
    try:
        results = recall(query, top_k=top_k)
    except MemoryError as exc:
        return f"Cognee memory unavailable: {exc}"

    if not results:
        return "No relevant Cognee memory found."

    lines = []
    for index, result in enumerate(results, start=1):
        lines.append(f"{index}. {result.text}")
    return "\n".join(lines)
