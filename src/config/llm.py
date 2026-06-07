import os
from typing import Any

from langchain_ollama import ChatOllama

# Fetches the environment URL (Docker or Local). Defaults to standard localhost.
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_MODEL = "llama3.1"


def get_llm(temperature: float = 0.0, num_ctx: int = 2048, **kwargs: Any) -> ChatOllama:
    """
    Centralized factory to instantiate the local LLM.
    Ensures that all multi-agent components automatically share the same base URL and context window limits.
    """
    return ChatOllama(
        model=DEFAULT_MODEL,
        temperature=temperature,
        num_ctx=num_ctx,
        base_url=OLLAMA_BASE_URL,
        **kwargs
    )
