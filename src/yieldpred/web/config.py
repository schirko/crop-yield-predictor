"""The web app's settings, from environment variables (Render's dashboard online; nothing to set on your computer).

    YIELD_PREDICTOR_HOSTED=1               on a server: secure cookies, and the checks in problems()
    YIELD_PREDICTOR_MY_FARM_SIGN_IN=1      show Sign In With My Farm (on by default online). The app is open to
                                           everyone either way; signing in only brings your county from My Farm.
    YIELD_PREDICTOR_FARM_ACCOUNT_URL=..    My Farm's address (default https://apps.cornerpostlogic.com)
    YIELD_PREDICTOR_FARM_ACCOUNT_KEY=..    this app's private key at My Farm: the same long random string as
                                           corn-yield-predictor:<key> in farm-account's FARM_ACCOUNT_APP_KEYS.
                                           It also locks this app's cookies, so it must be long and random.
    YIELD_PREDICTOR_PUBLIC_URL=..          this app's own address, as My Farm knows it (Render sets
                                           RENDER_EXTERNAL_URL, which is used when this isn't set)
    YIELD_PREDICTOR_STREAMLIT_URL=..       the Streamlit app, where Maps and Research still live
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

DEV_FARM_ACCOUNT_KEY = "local-dev-yield-predictor"     # farm-account knows it too, on your computer only
STREAMLIT_URL = "https://nebraska-yield-predictor-izzr8x4rxcppkcfjmqmiej.streamlit.app"


def _flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    hosted: bool = False
    my_farm_sign_in: bool = False
    farm_account_url: str = "https://apps.cornerpostlogic.com"
    farm_account_key: str | None = None
    public_url: str | None = None
    streamlit_url: str = STREAMLIT_URL

    @property
    def secure_cookies(self) -> bool:
        return self.hosted

    @property
    def own_url(self) -> str:
        return (self.public_url or "http://127.0.0.1:8030").rstrip("/")

    @property
    def farm_account_key_to_send(self) -> str | None:
        return self.farm_account_key or (None if self.hosted else DEV_FARM_ACCOUNT_KEY)

    def problems(self) -> list[str]:
        """Settings a server can't run safely without: the app refuses to start (the old version keeps running)."""
        if not self.hosted:
            return []
        found = []
        if self.my_farm_sign_in:
            if not self.farm_account_key or len(self.farm_account_key) < 32:
                found.append("YIELD_PREDICTOR_FARM_ACCOUNT_KEY must be set to a random string of at least 32 characters")
            if not self.farm_account_url.startswith("https://"):
                found.append("YIELD_PREDICTOR_FARM_ACCOUNT_URL must be an https:// address")
            if not self.own_url.startswith("https://"):
                found.append("YIELD_PREDICTOR_PUBLIC_URL must be this service's https:// address")
        return found

    @classmethod
    def from_env(cls) -> "Settings":
        hosted = _flag("YIELD_PREDICTOR_HOSTED", False)
        return cls(
            hosted=hosted,
            my_farm_sign_in=_flag("YIELD_PREDICTOR_MY_FARM_SIGN_IN", hosted),
            farm_account_url=(os.getenv("YIELD_PREDICTOR_FARM_ACCOUNT_URL") or "").strip().rstrip("/")
            or cls.farm_account_url,
            farm_account_key=(os.getenv("YIELD_PREDICTOR_FARM_ACCOUNT_KEY") or "").strip() or None,
            public_url=((os.getenv("YIELD_PREDICTOR_PUBLIC_URL") or os.getenv("RENDER_EXTERNAL_URL") or "").strip()
                        or None),
            streamlit_url=(os.getenv("YIELD_PREDICTOR_STREAMLIT_URL") or "").strip().rstrip("/") or STREAMLIT_URL,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings.from_env()
