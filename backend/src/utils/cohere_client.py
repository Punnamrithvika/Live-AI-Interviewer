import os
from typing import Optional, Any, Dict
import concurrent.futures
import time as _time
from pathlib import Path

from dotenv import load_dotenv

# Cohere SDK imports can vary; prefer ClientV2 when available
try:
    import cohere  # type: ignore
except Exception:  # pragma: no cover - import fallback
    cohere = None  # type: ignore


_load_once = False
_client = None


def get_client():
    global _load_once, _client
    if not _load_once:
        # Load backend/.env explicitly so running from repo root works
        base_dir = Path(__file__).resolve().parents[2]
        env_path = base_dir / ".env"
        load_dotenv(dotenv_path=env_path if env_path.exists() else None)
        _load_once = True
    if _client is None:
        api_key = os.getenv("COHERE_API_KEY")
        if not api_key:
            raise RuntimeError("COHERE_API_KEY is missing in environment variables (.env)")
        if cohere is None:
            raise RuntimeError("cohere package not installed. Please add it to requirements and install.")
        # Prefer the newer ClientV2 if available
        client_ctor = getattr(cohere, "ClientV2", None)
        if client_ctor is None:
            # Fallback to legacy client
            _client = cohere.Client(api_key)
        else:
            _client = client_ctor(api_key=api_key)
    return _client


def generate_text(prompt: str, system: Optional[str] = None, json_mode: bool = False) -> str:
    """
    Generate text using Cohere Chat API. Prefer ClientV2 with messages=[...] and lowercase roles.
    If json_mode=True, add a system hint to return strict JSON only.
    """
    client = get_client()

    model = os.getenv("LLM_MODEL") or os.getenv("COHERE_MODEL") or "command-r-plus"
    sys_msg = system or ""
    if json_mode:
        sys_msg = (sys_msg + "\n" if sys_msg else "") + "Return only valid JSON with no extra commentary."

    # Build messages in lowercase role schema as used by ClientV2
    messages: list[dict[str, str]] = []
    if sys_msg:
        messages.append({"role": "system", "content": sys_msg})
    messages.append({"role": "user", "content": prompt})

    # Add a timeout wrapper so we can fall back quickly when LLM is slow
    timeout_s = float(os.getenv("COHERE_TIMEOUT_SECONDS", "6"))
    def _call_messages():
        return client.chat(
            model=model,
            messages=messages,
            temperature=float(os.getenv("COHERE_TEMPERATURE", "0.3")),
        )
    def _call_legacy():
        combined = (sys_msg + "\n" if sys_msg else "") + prompt
        return client.chat(
            model=model,
            message=combined,
            temperature=float(os.getenv("COHERE_TEMPERATURE", "0.3")),
        )
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(_call_messages)
            try:
                res = fut.result(timeout=timeout_s)
            except TypeError:
                # Fallback to legacy param signature
                fut2 = ex.submit(_call_legacy)
                res = fut2.result(timeout=timeout_s)
            except concurrent.futures.TimeoutError:
                raise RuntimeError(f"Cohere chat timeout after {timeout_s}s")
    except Exception as e:
        raise RuntimeError(f"Cohere chat failed (model={model}): {e}")

    # Extract text from response (v2: message.content is a list of parts)
    text = getattr(res, "text", None)
    if not text and hasattr(res, "message"):
        parts = getattr(res.message, "content", []) or []
        texts: list[str] = []
        for p in parts:
            t = getattr(p, "text", None)
            if t is None and isinstance(p, dict):
                t = p.get("text")
            if t:
                texts.append(t)
        text = " ".join(texts)
    return (text or "").strip()
