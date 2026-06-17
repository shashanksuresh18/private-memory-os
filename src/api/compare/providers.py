"""Provider-agnostic cloud-model registry + transports for Compare / Council.

Compare is a NORMAL chat feature. It calls cloud models only -- no local Ollama
-- and is surfaced to the UI with every model labelled ``CLOUD``. Only providers
whose API key is present in the environment are exposed by ``available_models()``,
so the Anthropic / OpenAI seams stay inert until they are actually keyed. Out of
the box (Nebius key only) just DeepSeek-V3.2 is selectable.

The Nebius path reuses the already-tested cloud seam
``src.retrieval.answer._nebius_chat`` (the same function the S1/S2 answer tests
monkeypatch), so Compare adds no second Nebius transport. The Anthropic / OpenAI
transports here are thin, monkeypatchable functions; tests replace them and no
real network is touched.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass

import httpx
import requests

# Neutral chat system prompt. NOT the retrieval extraction SYSTEM_PROMPT (that
# one forces verbatim-citation output and would be wrong for free-form chat).
COMPARE_SYSTEM_PROMPT = (
    "You are a helpful, knowledgeable assistant. Answer the user's question "
    "directly, clearly, and concisely."
)

# Default per-model wall-clock budget for a single Compare call.
DEFAULT_TIMEOUT_S = float(os.environ.get("COMPARE_TIMEOUT_S", "60"))


@dataclass
class ModelResult:
    """One model's response to a Compare prompt.

    ``status`` is ``"ok" | "error" | "timeout"``. Token counts are best-effort
    estimates (tiktoken) when the transport does not return usage; the UI shows
    them as approximate.
    """

    status: str
    text: str = ""
    latency_ms: int = 0
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    provider: str = ""
    model: str = ""
    error: str | None = None


def _estimate_tokens(text: str) -> int:
    """Best-effort token count. tiktoken is already a project dependency; fall
    back to a coarse chars/4 heuristic if the encoding is unavailable."""
    if not text:
        return 0
    try:
        import tiktoken

        return len(tiktoken.get_encoding("cl100k_base").encode(text))
    except Exception:
        return max(1, len(text) // 4)


def _elapsed_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


class Provider:
    """Base cloud provider. Subclasses implement ``_call`` only; timing, token
    accounting, and timeout/error classification live here so every provider
    returns a uniform :class:`ModelResult`."""

    name = "base"
    env_key = ""

    def is_configured(self) -> bool:
        return bool(os.environ.get(self.env_key, "").strip())

    def _call(self, model: str, prompt: str, system: str, timeout_s: float) -> str:
        raise NotImplementedError

    def chat(
        self,
        model: str,
        prompt: str,
        system: str = COMPARE_SYSTEM_PROMPT,
        timeout_s: float = DEFAULT_TIMEOUT_S,
    ) -> ModelResult:
        start = time.perf_counter()
        try:
            text = self._call(model, prompt, system, timeout_s)
        except (requests.Timeout, httpx.TimeoutException) as exc:
            return ModelResult(
                status="timeout",
                latency_ms=_elapsed_ms(start),
                provider=self.name,
                model=model,
                error=str(exc) or "model timed out",
            )
        except Exception as exc:  # partial failure: this pane errors, others go on
            return ModelResult(
                status="error",
                latency_ms=_elapsed_ms(start),
                provider=self.name,
                model=model,
                error=str(exc) or exc.__class__.__name__,
            )
        return ModelResult(
            status="ok",
            text=text,
            latency_ms=_elapsed_ms(start),
            prompt_tokens=_estimate_tokens(prompt),
            completion_tokens=_estimate_tokens(text),
            provider=self.name,
            model=model,
        )


class NebiusProvider(Provider):
    name = "nebius"
    env_key = "NEBIUS_API_KEY"

    def _call(self, model: str, prompt: str, system: str, timeout_s: float) -> str:
        # Reuse the existing, already-tested Nebius/DeepSeek seam. Imported
        # lazily so this package stays decoupled from the retrieval engine and
        # so test monkeypatches on ``answer._nebius_chat`` are honoured.
        from src.retrieval import answer as answer_mod

        return answer_mod._nebius_chat(model, prompt, system)


# --- Anthropic seam (inert until ANTHROPIC_API_KEY is set) -------------------

ANTHROPIC_BASE_URL = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
ANTHROPIC_VERSION = os.environ.get("ANTHROPIC_VERSION", "2023-06-01")
ANTHROPIC_MAX_TOKENS = int(os.environ.get("COMPARE_MAX_TOKENS", "1024"))


def _anthropic_chat(model: str, prompt: str, system: str, timeout_s: float) -> str:
    """Anthropic Messages API (POST /v1/messages). Returns concatenated text
    blocks. Only called when ANTHROPIC_API_KEY is configured."""
    key = os.environ["ANTHROPIC_API_KEY"]
    r = httpx.post(
        f"{ANTHROPIC_BASE_URL.rstrip('/')}/v1/messages",
        headers={
            "x-api-key": key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        },
        json={
            "model": model,
            "max_tokens": ANTHROPIC_MAX_TOKENS,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=timeout_s,
    )
    r.raise_for_status()
    body = r.json()
    return "".join(
        block.get("text", "")
        for block in body.get("content", [])
        if block.get("type") == "text"
    )


class AnthropicProvider(Provider):
    name = "anthropic"
    env_key = "ANTHROPIC_API_KEY"

    def _call(self, model: str, prompt: str, system: str, timeout_s: float) -> str:
        return _anthropic_chat(model, prompt, system, timeout_s)


# --- OpenAI seam (inert until OPENAI_API_KEY is set) -------------------------

OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")


def _openai_chat(model: str, prompt: str, system: str, timeout_s: float) -> str:
    """OpenAI-compatible chat completions. Only called when OPENAI_API_KEY is
    configured."""
    key = os.environ["OPENAI_API_KEY"]
    r = httpx.post(
        f"{OPENAI_BASE_URL.rstrip('/')}/chat/completions",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        },
        timeout=timeout_s,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


class OpenAIProvider(Provider):
    name = "openai"
    env_key = "OPENAI_API_KEY"

    def _call(self, model: str, prompt: str, system: str, timeout_s: float) -> str:
        return _openai_chat(model, prompt, system, timeout_s)


# --- Registry ---------------------------------------------------------------

_PROVIDERS: dict[str, Provider] = {
    "nebius": NebiusProvider(),
    "anthropic": AnthropicProvider(),
    "openai": OpenAIProvider(),
}

# Static model catalogue. Kept in Python (not YAML) so it needs no extra runtime
# dependency and is trivially testable. Adding a model = one row here; it only
# becomes selectable once its provider's key is configured. The Nebius model id
# tracks NEBIUS_MODEL so a single env override moves both retrieval and Compare.
_NEBIUS_MODEL = os.environ.get("NEBIUS_MODEL", "deepseek-ai/DeepSeek-V3.2")

_MODEL_REGISTRY: list[dict] = [
    # All Nebius (one NEBIUS_API_KEY, OpenAI-compatible endpoint). Model slugs
    # verified live against the configured Nebius base. Cheap text-to-text models
    # are included so a multi-model comparison runs on a single key.
    {"id": "deepseek-v3.2", "provider": "nebius", "model": _NEBIUS_MODEL, "label": "DeepSeek V3.2"},
    {"id": "llama3.3-70b", "provider": "nebius", "model": "meta-llama/Llama-3.3-70B-Instruct", "label": "Llama 3.3 70B"},
    {"id": "gemma3-27b", "provider": "nebius", "model": "google/gemma-3-27b-it", "label": "Gemma 3 27B"},
    {"id": "gpt-oss-120b", "provider": "nebius", "model": "openai/gpt-oss-120b", "label": "GPT-OSS 120B"},
    {"id": "hermes4-70b", "provider": "nebius", "model": "NousResearch/Hermes-4-70B", "label": "Hermes 4 70B"},
    {"id": "nemotron-ultra", "provider": "nebius", "model": "nvidia/Llama-3_1-Nemotron-Ultra-253B-v1", "label": "Nemotron Ultra 253B"},
    # Inert seams — only surface if their own provider key is configured.
    {"id": "claude-opus-4-8", "provider": "anthropic", "model": "claude-opus-4-8", "label": "Claude Opus 4.8"},
    {"id": "gpt-4o", "provider": "openai", "model": "gpt-4o", "label": "GPT-4o"},
]


def get_provider(name: str) -> Provider | None:
    return _PROVIDERS.get(name)


def model_by_id(model_id: str) -> dict | None:
    for entry in _MODEL_REGISTRY:
        if entry["id"] == model_id:
            return entry
    return None


def is_model_available(model_id: str) -> bool:
    """True only if the model exists AND its provider is configured."""
    entry = model_by_id(model_id)
    if entry is None:
        return False
    provider = _PROVIDERS.get(entry["provider"])
    return bool(provider and provider.is_configured())


def available_models() -> list[dict]:
    """Catalogue rows whose provider is configured, each tagged ``kind:cloud``.
    This is what the model selector renders -- unconfigured providers never
    appear, so they cannot be selected."""
    out: list[dict] = []
    for entry in _MODEL_REGISTRY:
        provider = _PROVIDERS.get(entry["provider"])
        if provider and provider.is_configured():
            out.append({**entry, "kind": "cloud"})
    return out
