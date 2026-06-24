from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

ProviderMode = Literal["deterministic", "ollama", "hosted", "hybrid"]


@dataclass
class ProviderSelection:
    name: str
    provider_type: ProviderMode
    fallback_chain: list[str]
    fallback_used: bool
    reason: str


def _has_hosted_credentials() -> bool:
    return bool(os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY"))


def _has_ollama_endpoint() -> bool:
    return bool(os.getenv("OLLAMA_BASE_URL") or os.getenv("OLLAMA_MODEL"))


def resolve_provider(mode: ProviderMode) -> ProviderSelection:
    if mode == "deterministic":
        return ProviderSelection(
            name="deterministic-engine",
            provider_type="deterministic",
            fallback_chain=["deterministic-engine"],
            fallback_used=False,
            reason="Deterministic mode requested explicitly",
        )

    if mode == "ollama":
        if _has_ollama_endpoint():
            return ProviderSelection(
                name="ollama-local",
                provider_type="ollama",
                fallback_chain=["ollama-local", "deterministic-engine"],
                fallback_used=False,
                reason="Ollama configuration detected",
            )
        return ProviderSelection(
            name="deterministic-engine",
            provider_type="deterministic",
            fallback_chain=["ollama-local", "deterministic-engine"],
            fallback_used=True,
            reason="Ollama configuration missing; fallback to deterministic",
        )

    if mode == "hosted":
        if _has_hosted_credentials():
            return ProviderSelection(
                name="hosted-llm",
                provider_type="hosted",
                fallback_chain=["hosted-llm", "deterministic-engine"],
                fallback_used=False,
                reason="Hosted credentials detected",
            )
        return ProviderSelection(
            name="deterministic-engine",
            provider_type="deterministic",
            fallback_chain=["hosted-llm", "deterministic-engine"],
            fallback_used=True,
            reason="Hosted credentials missing; fallback to deterministic",
        )

    # hybrid mode: prefer hosted, then ollama, then deterministic
    if _has_hosted_credentials():
        return ProviderSelection(
            name="hosted-llm",
            provider_type="hosted",
            fallback_chain=["hosted-llm", "ollama-local", "deterministic-engine"],
            fallback_used=False,
            reason="Hybrid mode selected with hosted credentials available",
        )

    if _has_ollama_endpoint():
        return ProviderSelection(
            name="ollama-local",
            provider_type="ollama",
            fallback_chain=["hosted-llm", "ollama-local", "deterministic-engine"],
            fallback_used=True,
            reason="Hosted credentials missing; using local Ollama",
        )

    return ProviderSelection(
        name="deterministic-engine",
        provider_type="deterministic",
        fallback_chain=["hosted-llm", "ollama-local", "deterministic-engine"],
        fallback_used=True,
        reason="No hosted or Ollama configuration available; using deterministic",
    )


def provider_status() -> dict[str, bool]:
    return {
        "hostedConfigured": _has_hosted_credentials(),
        "ollamaConfigured": _has_ollama_endpoint(),
    }
