from enum import Enum

from .anthropic import AnthropicClient, AnthropicConfig
from .base import BaseLLMClient
from .fortiss_token_manager import FortissConfig, FortissTokenManager
from .ollama import OllamaClient, OllamaConfig
from .openai import OpenAIClient, OpenAIConfig
from .openrouter import OpenRouterClient, OpenRouterConfig


class LLMProvider(str, Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    OLLAMA = "ollama"
    FORTISS = "fortiss"
    OPENROUTER = "openrouter"


class LLMClientFactory:
    @staticmethod
    def create(provider: LLMProvider, model: str) -> BaseLLMClient:
        # Config values are loaded from the environment, so mute pyright complaints here is safe
        if provider == LLMProvider.ANTHROPIC:
            return AnthropicClient(AnthropicConfig(model=model))  # pyright: ignore[reportCallIssue]

        if provider == LLMProvider.OPENAI:
            return OpenAIClient(OpenAIConfig(model=model))  # pyright: ignore[reportCallIssue]

        if provider == LLMProvider.OLLAMA:
            return OllamaClient(OllamaConfig(model=model))  # pyright: ignore[reportCallIssue]

        if provider == LLMProvider.FORTISS:
            fortiss_config = FortissConfig()  # pyright: ignore[reportCallIssue]
            ollama_config = OllamaConfig(model=model, base_url=fortiss_config.base_url)
            return OllamaClient(ollama_config, FortissTokenManager(fortiss_config))

        if provider == LLMProvider.OPENROUTER:
            return OpenRouterClient(OpenRouterConfig(model=model))  # pyright: ignore[reportCallIssue]

        raise ValueError(f"Unknown provider: {provider}")
