from openai import OpenAI
from pydantic_settings import BaseSettings
from .base import BaseLLMClient, LLMClientError


class OpenRouterConfig(BaseSettings):
    api_key: str
    base_url: str = "https://openrouter.ai/api/v1"
    model: str = "meta-llama/llama-3.3-70b-instruct"
    max_tokens: int = 4096

    model_config = {"env_file": ".env", "env_prefix": "OPENROUTER_", "extra": "ignore"}


class OpenRouterClient(BaseLLMClient):

    def __init__(self, config: OpenRouterConfig):
        self.config = config
        self._client = OpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
        )

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
            return (
                response.choices[0].message.content,
                response.usage.prompt_tokens,
                response.usage.completion_tokens,
            )
        except Exception as e:
            raise LLMClientError(f"OpenRouter API call failed: {e}")