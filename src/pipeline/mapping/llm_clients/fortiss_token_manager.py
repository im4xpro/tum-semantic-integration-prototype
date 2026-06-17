# clients/token_manager.py
import time
import requests
from pydantic_settings import BaseSettings


class FortissConfig(BaseSettings):
    api_key: str
    token_endpoint: str
    base_url: str

    model_config = {"env_file": ".env", "env_prefix": "FORTISS_", "extra": "ignore"}


class FortissTokenManagerError(Exception):
    pass


class FortissTokenManager:

    def __init__(self, config: FortissConfig):
        self.config = config
        self._token: str | None = None
        self._expires_at: float = 0

    def get_token(self) -> str:
        if self._token is None or time.time() >= self._expires_at - 60:
            self._refresh()
        return self._token

    def _refresh(self) -> None:
        try:
            response = requests.post(
                self.config.token_endpoint,
                headers={"api-key": self.config.api_key},
            )
            response.raise_for_status()
            self._token = response.json()["access_token"]
            self._expires_at = time.time() + 3600
        except Exception as e:
            raise FortissTokenManagerError(f"Failed to refresh token: {e}")
