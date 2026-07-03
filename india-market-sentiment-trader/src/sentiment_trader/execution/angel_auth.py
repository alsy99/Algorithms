from __future__ import annotations

import pyotp
import structlog

from sentiment_trader.config import EnvSettings

logger = structlog.get_logger(__name__)


class AngelAuthSession:
    """Manages Angel One SmartAPI session tokens (jwt + feed)."""

    def __init__(self, env: EnvSettings) -> None:
        self._env = env
        self.jwt_token: str | None = None
        self.feed_token: str | None = None
        self.refresh_token: str | None = None
        self._smart_api = None

    def _get_smart_api(self):
        if self._smart_api is None:
            try:
                from SmartApi import SmartConnect
            except ImportError as exc:
                raise ImportError(
                    "Install angel extras: pip install '.[angel]'"
                ) from exc
            self._smart_api = SmartConnect(api_key=self._env.angel_api_key)
        return self._smart_api

    def login(self) -> tuple[str, str]:
        if not all(
            [
                self._env.angel_api_key,
                self._env.angel_client_code,
                self._env.angel_pin,
                self._env.angel_totp_secret,
            ]
        ):
            raise ValueError("Angel One credentials are incomplete in environment")

        totp = pyotp.TOTP(self._env.angel_totp_secret).now()
        api = self._get_smart_api()
        data = api.generateSession(self._env.angel_client_code, self._env.angel_pin, totp)

        if not data.get("status"):
            raise RuntimeError(f"Angel One login failed: {data}")

        self.jwt_token = data["data"]["jwtToken"]
        self.feed_token = data["data"]["feedToken"]
        self.refresh_token = data["data"].get("refreshToken")
        logger.info("angel_one.session_created", client=self._env.angel_client_code)
        return self.jwt_token, self.feed_token

    @property
    def smart_api(self):
        if self.jwt_token is None:
            self.login()
        return self._get_smart_api()
