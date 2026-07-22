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
        if provider == LLMProvider.ANTHROPIC:
            return AnthropicClient(AnthropicConfig(model=model))

        if provider == LLMProvider.OPENAI:
            return OpenAIClient(OpenAIConfig(model=model))

        if provider == LLMProvider.OLLAMA:
            return OllamaClient(OllamaConfig(model=model))

        if provider == LLMProvider.FORTISS:
            fortiss_config = FortissConfig()
            ollama_config = OllamaConfig(model=model, base_url=fortiss_config.base_url)
            return OllamaClient(ollama_config, FortissTokenManager(fortiss_config))

        if provider == LLMProvider.OPENROUTER:
            return OpenRouterClient(OpenRouterConfig(model=model))

        raise ValueError(f"Unknown provider: {provider}")
