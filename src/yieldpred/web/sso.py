"""Sign In With My Farm (v0.2.0), the suite's one sign-in, as in the Grazing Planner (its sso.py) but with no database.

The Yield Predictor is open to everyone: nothing here needs an account. Signing in only brings your farm's county from
My Farm, so the page opens on it. So this app keeps no accounts and no passwords; who you are rides in one cookie,
locked (encrypted and signed with Fernet, under a key made from this app's My Farm key, which lives in Render's
settings). A copy of the cookie can't be read or changed without that key.

1. start(): two random secrets. `state` goes through the browser and comes back; `verifier` never leaves this server
   (only its SHA-256, the challenge, goes to My Farm). Both ride in a short-lived locked cookie. The browser goes to
   My Farm's /#continue/... page, which signs the person in (or sees they already are).
2. My Farm sends the browser to /suite/sign-in/done with a one-time code (60 seconds) and the state.
3. finish(): check the state, then trade code + verifier, with this app's key, for who the person is and their place.
4. The session cookie: their My Farm id and sign-in (sid), first name and county. No email is kept.
5. recheck(): every 5 minutes of use, My Farm is asked again. A sign-out at My Farm (or in another app), a closed
   account or no access ends the sign-in here. If My Farm doesn't answer (asleep on Render's free plan), the last answer
   stands for up to 2 hours, so a slow wake-up never signs anyone out.
6. Sign Out: drops the cookie and ends the My Farm sign-in too, so every app tied to it ends.

farm-account's side is its routers/sso.py; this app's id there is "corn-yield-predictor" (the suite's id for it).
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from cryptography.fernet import Fernet, InvalidToken

from yieldpred.web.config import Settings

APP_ID = "corn-yield-predictor"
DONE_PATH = "/suite/sign-in/done"
START_COOKIE = "yp_sign_in"
SESSION_COOKIE = "yp_session"
START_MINUTES = 10
SESSION_DAYS = 30                     # the cookie's own limit; My Farm's answer ends it sooner
RECHECK = timedelta(minutes=5)
GRACE = timedelta(hours=2)
TIMEOUT = 20.0                        # My Farm may be waking up for the sign-in itself
CHECK_TIMEOUT = 4.0                   # but a recheck never holds a page up for long
LOCAL_SECRET = "local development only: not a secret"
PREFIX = "v1:"


class SignInError(Exception):
    """Something to tell the person, in plain words."""


def now() -> datetime:
    return datetime.now(timezone.utc)


def _fernet(settings: Settings) -> Fernet:
    secret = settings.farm_account_key_to_send or LOCAL_SECRET
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(b"yield-predictor cookie|" + secret.encode()).digest()))


def seal(value: dict, settings: Settings) -> str:
    return PREFIX + _fernet(settings).encrypt(json.dumps(value).encode()).decode()


def unseal(stored: str | None, settings: Settings) -> dict | None:
    if not stored or not stored.startswith(PREFIX):
        return None
    try:
        found = json.loads(_fernet(settings).decrypt(stored[len(PREFIX):].encode()).decode())
    except (InvalidToken, ValueError):
        return None
    return found if isinstance(found, dict) else None


def return_to(settings: Settings) -> str:
    return settings.own_url + DONE_PATH


def safe_next(county: str | None) -> str:
    """Only this app's own front page, optionally on a county: never an address from outside."""
    return county if county and county.isdigit() and len(county) == 5 else ""


def _key(settings: Settings) -> dict:
    return {"Authorization": f"Bearer {settings.farm_account_key_to_send or ''}"}


def start(settings: Settings, county: str | None = None) -> tuple[str, str]:
    """(where to send the browser, the locked cookie to set)."""
    state, verifier = secrets.token_urlsafe(24), secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    cookie = seal({"state": state, "verifier": verifier, "county": safe_next(county), "at": now().isoformat()}, settings)
    url = f"{settings.farm_account_url}/#continue/{urlencode({'app': APP_ID, 'state': state, 'challenge': challenge})}"
    return url, cookie


def finish(settings: Settings, cookie: str | None, code: str, state: str) -> tuple[dict, str]:
    """(My Farm's answer about the person, the county to open). Raises SignInError."""
    started = unseal(cookie, settings)
    try:
        at = datetime.fromisoformat(started["at"]) if started else None
    except (KeyError, ValueError, TypeError):
        at = None
    if (started is None or not secrets.compare_digest(str(started.get("state", "")), state or "")
            or at is None or at + timedelta(minutes=START_MINUTES) < now()):
        raise SignInError("That sign-in didn't start here, or took too long. Press Sign In again.")
    try:
        r = httpx.post(f"{settings.farm_account_url}/sso/token", headers=_key(settings), timeout=TIMEOUT,
                       json={"code": code, "verifier": started["verifier"], "return_to": return_to(settings)})
    except httpx.HTTPError as exc:
        raise SignInError("My Farm didn't answer. It may be waking up: press Sign In again in a minute.") from exc
    try:
        answer = r.json()
    except ValueError:
        answer = {}
    if r.status_code == 403:
        raise SignInError("Your My Farm account can't sign in to the Yield Predictor right now.")
    if r.status_code != 200 or not isinstance(answer, dict) or not answer.get("active") or not answer.get("user_id"):
        raise SignInError("My Farm didn't accept that sign-in. Press Sign In again.")
    return answer, safe_next(started.get("county"))


def first_name(name: str | None) -> str:
    return (str(name or "").strip().split() or ["Farmer"])[0][:40]


def place_of(answer: dict) -> dict | None:
    """The farm's county from My Farm's answer: {"fips", "county", "state", "name"}, or None when not set there."""
    place = answer.get("place")
    if not isinstance(place, dict) or not str(place.get("county_fips") or "").isdigit():
        return None
    return {"fips": str(place["county_fips"])[:5], "county": str(place.get("county") or "")[:80],
            "state": str(place.get("state") or "")[:2], "name": str(place.get("name") or "")[:80]}


def session_from(answer: dict) -> dict:
    t = now().isoformat()
    return {"uid": str(answer["user_id"]), "sid": str(answer["sid"]), "name": first_name(answer.get("name")),
            "place": place_of(answer), "checked": t, "good": t}


def recheck(signed: dict, settings: Settings) -> dict | None:
    """The session after asking My Farm again when it's due: None ends the sign-in. Not due, or My Farm asleep within
    the grace time: the same session (with the time it was last tried)."""
    t = now()
    try:
        checked = datetime.fromisoformat(signed["checked"])
        good = datetime.fromisoformat(signed["good"])
    except (KeyError, ValueError, TypeError):
        return None
    if checked + RECHECK > t:
        return signed
    try:
        r = httpx.post(f"{settings.farm_account_url}/sso/check", headers=_key(settings), timeout=CHECK_TIMEOUT,
                       json={"people": [{"user_id": signed["uid"], "sid": signed["sid"]}]})
        answer = r.json()[0] if r.status_code == 200 else None
    except (httpx.HTTPError, ValueError, IndexError, KeyError, TypeError):
        answer = None
    if not isinstance(answer, dict):
        return {**signed, "checked": t.isoformat()} if good + GRACE > t else None
    if not answer.get("active"):
        return None
    return {**signed, "name": first_name(answer.get("name")) if answer.get("name") else signed.get("name"),
            "place": place_of(answer), "checked": t.isoformat(), "good": t.isoformat()}


def sign_out_at_my_farm(settings: Settings, sid: str | None) -> None:
    """This app's Sign Out ends the My Farm sign-in too. Best effort."""
    if not sid:
        return
    try:
        httpx.post(f"{settings.farm_account_url}/sso/sign-out", headers=_key(settings), timeout=TIMEOUT,
                   json={"sid": sid})
    except httpx.HTTPError:
        pass
