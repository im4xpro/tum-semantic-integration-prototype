# clients/factory.py
from enum import Enum

from .openrouter import OpenRouterClient, OpenRouterConfig
from .base import BaseLLMClient
from .anthropic import AnthropicClient, AnthropicConfig
from .openai import OpenAIClient, OpenAIConfig
from .ollama import OllamaClient, OllamaConfig
from .fortiss_token_manager import FortissTokenManager, FortissConfig


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
            config = AnthropicConfig.model_construct()
            config.model = model
            return AnthropicClient(config)

        if provider == LLMProvider.OPENAI:
            config = OpenAIConfig.model_construct()
            config.model = model
            return OpenAIClient(config)

        if provider == LLMProvider.OLLAMA:
            config = OllamaConfig.model_construct()
            config.model = model
            return OllamaClient(config)

        if provider == LLMProvider.FORTISS:
            ollama_config = OllamaConfig.model_construct()
            ollama_config.model = model
            fortiss_config = FortissConfig.model_construct()
            ollama_config.base_url = fortiss_config.base_url
            token_manager = FortissTokenManager(fortiss_config)
            return OllamaClient(ollama_config, token_manager)

        if provider == LLMProvider.OPENROUTER:
            config = OpenRouterConfig.model_construct()
            config.model = model
            return OpenRouterClient(config)

        raise ValueError(f"Unknown provider: {provider}")