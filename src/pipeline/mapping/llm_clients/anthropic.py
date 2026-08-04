from anthropic import Anthropic
from anthropic.types import TextBlock
from pydantic_settings import BaseSettings

from .base import BaseLLMClient, LLMClientError


class AnthropicConfig(BaseSettings):
    api_key: str
    model: str = "claude-sonnet-4-6"
    max_tokens: int = 32000

    model_config = {"env_file": ".env", "env_prefix": "ANTHROPIC_", "extra": "ignore"}


class AnthropicClient(BaseLLMClient):
    def __init__(self, config: AnthropicConfig):
        self.config = config
        self._client = Anthropic(api_key=config.api_key)

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
    ) -> tuple[str, int, int]:
        try:
            response = self._client.messages.create(
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            text = "".join(
                block.text for block in response.content if isinstance(block, TextBlock)
            )
            return (
                text,
                response.usage.input_tokens,
                response.usage.output_tokens,
            )
        except Exception as e:
            raise LLMClientError(f"Anthropic API call failed: {e}")
