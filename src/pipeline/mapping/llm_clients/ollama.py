import requests
from pydantic_settings import BaseSettings

from .base import BaseLLMClient, LLMClientError
from .fortiss_token_manager import FortissTokenManager


class OllamaConfig(BaseSettings):
    base_url: str
    model: str = "llama3.3:latest"
    max_tokens: int = 4096

    model_config = {"env_file": ".env", "env_prefix": "OLLAMA_", "extra": "ignore"}


class OllamaClient(BaseLLMClient):

    def __init__(self, config: OllamaConfig, token_manager: FortissTokenManager | None = None):
        self.config = config
        self._token_manager = token_manager

    def _get_headers(self) -> dict:
        if self._token_manager:
            return {"Authorization": f"Bearer {self._token_manager.get_token()}"}
        return {}

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
    ) -> tuple[str, int, int]:
        try:
            response = requests.post(
                f"{self.config.base_url}chat",
                headers=self._get_headers(),
                json={
                    "model": self.config.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "stream": False,
                    "options": {"temperature": temperature},
                },
                timeout=120
            )
            response.raise_for_status()
            data = response.json()

            text = data["message"]["content"]
            prompt_tokens = data.get("prompt_eval_count", 0)
            completion_tokens = data.get("eval_count", 0)

            return text, prompt_tokens, completion_tokens

        except Exception as e:
            raise LLMClientError(f"Ollama API call failed: {e}")