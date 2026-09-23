"""Optional LLM providers for generated hypothesis text.

Nothing in ``research`` or ``jev`` imports this package: a provider is constructed by the caller
(the CLI or a test) and injected into the hypothesis stage. GDC remains anonymously accessed.
"""

from cancerjev.llm.openrouter import (
    DEFAULT_MODEL,
    GENERATOR_NAME,
    LlmProviderError,
    OpenRouterGenerator,
)

__all__ = ["DEFAULT_MODEL", "GENERATOR_NAME", "LlmProviderError", "OpenRouterGenerator"]
