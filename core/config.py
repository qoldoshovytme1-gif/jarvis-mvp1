"""
Configuration System
======================
Single source of truth for all settings. Every module reads config
from here — nothing reads `os.environ` directly outside this file.
This means: adding a new setting, or changing where config comes from
(env vars -> a config.yaml -> a remote config service) later touches
ONLY this file.

Usage:
    from core.config import get_config
    config = get_config()
    config.llm_provider
"""

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class JarvisConfig:
    # --- LLM ---
    llm_provider: str = "claude"           # "claude" | "openai" | "gemini" | "openrouter" | "local" | "mock"
    llm_fallback_providers: str = ""       # comma-separated, e.g. "openai,mock"
    llm_timeout_seconds: float = 20.0
    llm_max_retries: int = 2               # retries PER provider before falling back
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    gemini_api_key: str = ""
    openrouter_api_key: str = ""
    openrouter_model: str = "openai/gpt-4o"

    # --- Internet ---
    serper_api_key: str = ""

    # --- Memory ---
    memory_db_path: str = "data/jarvis_memory.db"

    # --- Logging ---
    log_level: str = "INFO"
    log_file: str = "data/logs/jarvis.log"

    # --- Verifier ---
    max_retries: int = 1


@lru_cache()
def get_config() -> JarvisConfig:
    """Loads config once (cached) from environment variables, falling
    back to sane defaults. `lru_cache` makes this a cheap singleton —
    call `get_config()` anywhere, no need to pass config around
    manually except where Dependency Injection makes the dependency
    explicit (which we still prefer for the modules that use it).
    """
    return JarvisConfig(
        llm_provider=os.environ.get("JARVIS_LLM_PROVIDER", "claude"),
        llm_fallback_providers=os.environ.get("JARVIS_LLM_FALLBACK_PROVIDERS", ""),
        llm_timeout_seconds=float(os.environ.get("JARVIS_LLM_TIMEOUT_SECONDS", "20")),
        llm_max_retries=int(os.environ.get("JARVIS_LLM_MAX_RETRIES", "2")),
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        openai_api_key=os.environ.get("OPENAI_API_KEY", ""),
        gemini_api_key=os.environ.get("GEMINI_API_KEY", ""),
        openrouter_api_key=os.environ.get("OPENROUTER_API_KEY", ""),
        openrouter_model=os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o"),
        serper_api_key=os.environ.get("SERPER_API_KEY", ""),
        memory_db_path=os.environ.get("JARVIS_MEMORY_DB", "data/jarvis_memory.db"),
        log_level=os.environ.get("JARVIS_LOG_LEVEL", "INFO"),
        log_file=os.environ.get("JARVIS_LOG_FILE", "data/logs/jarvis.log"),
        max_retries=int(os.environ.get("JARVIS_MAX_RETRIES", "1")),
    )
