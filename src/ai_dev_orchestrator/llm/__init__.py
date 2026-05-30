"""Internal LLM package.

Phase 3B added typed models + an env-driven config loader. Phase 3C adds the
mockable OpenAI-compatible chat client (:class:`LLMClient`) and its typed
errors. No model is called and no network request is made at import time.
"""

from ai_dev_orchestrator.llm.client import (
    LLMAuthError,
    LLMClient,
    LLMClientError,
    LLMResponseError,
    LLMTimeoutError,
    LLMTransportError,
)
from ai_dev_orchestrator.llm.config import (
    LLMConfigError,
    load_llm_client_config_from_env,
)
from ai_dev_orchestrator.llm.models import (
    LLMClientConfig,
    LLMMessage,
    LLMRequest,
    LLMResponse,
    LLMUsage,
)

__all__ = [
    "LLMAuthError",
    "LLMClient",
    "LLMClientConfig",
    "LLMClientError",
    "LLMConfigError",
    "LLMMessage",
    "LLMRequest",
    "LLMResponse",
    "LLMResponseError",
    "LLMTimeoutError",
    "LLMTransportError",
    "LLMUsage",
    "load_llm_client_config_from_env",
]
