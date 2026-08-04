from openai import OpenAI
from pydantic_settings import BaseSettings

from .base import BaseLLMClient, LLMClientError


class OpenAIConfig(BaseSettings):
    api_key: str
    model: str = "gpt-4o"
    max_tokens: int = 32000

    model_config = {"env_file": ".env", "env_prefix": "OPENAI_", "extra": "ignore"}


class OpenAIClient(BaseLLMClient):
    def __init__(self, config: OpenAIConfig):
        self.config = config
        self._client = OpenAI(api_key=config.api_key)

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
    ) -> tuple[str, int, int]:
        try:
            response = self._client.chat.completions.create(
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            content = response.choices[0].message.content or ""
            return (
                content,
                response.usage.prompt_tokens if response.usage else 0,
                response.usage.completion_tokens if response.usage else 0,
            )
        except Exception as e:
            raise LLMClientError(f"OpenAI API call failed: {e}")
