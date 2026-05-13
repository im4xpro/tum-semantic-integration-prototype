# clients/base.py
from abc import ABC, abstractmethod


class LLMClientError(Exception):
    pass


class BaseLLMClient(ABC):

    @abstractmethod
    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
    ) -> tuple[str, int, int]:
        # returns (response_text, prompt_tokens, completion_tokens)
        pass