"""The web app (yieldpred.web.app): its answers, its pages and headers, and Sign In With My Farm against a pretend My Farm."""

from __future__ import annotations

import json
from datetime import timedelta
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi.testclient import TestClient

from yieldpred import __version__
from yieldpred.web import app as web
from yieldpred.web import sso
from yieldpred.web.config import Settings, get_settings

ON = Settings(my_farm_sign_in=True, farm_account_url="https://myfarm.test", public_url="https://yp.test")


@pytest.fixture
def client():
    web.app.dependency_overrides.clear()
    yield TestClient(web.app, base_url="https://yp.test")
    web.app.dependency_overrides.clear()


@pytest.fixture
def signing(client):
    web.app.dependency_overrides[get_settings] = lambda: ON
    return client


def test_health_and_pages(client):
    assert client.get("/health").json() == {"ok": True, "version": __version__}
    for path in ("/", "/help.html", "/app.js", "/header.js", "/style.css", "/suite.css", "/suite.js", "/suite-apps.json",
                 "/icons/logo.svg", "/suite-logos/corn-yield-predictor.svg"):
        assert client.get(path).status_code == 200, path
    page = client.get("/")
    assert "Content-Security-Policy" in page.headers and page.headers["X-Frame-Options"] == "DENY"
    assert page.headers["Cache-Control"] == "no-cache"


def test_county_answers(client):
    p = client.get("/api/county/31079").json()
    assert p["county"] == "Hall" and p["record"] == {"held": 23, "years": 25}
    assert p["season"] is None or p["season"]["normal_years"] == [2000, 2025]
    assert client.get("/api/county/19153?crop=soybeans").json()["state"] == "Iowa"
    assert client.get("/api/county/99999").status_code == 404
    assert client.get("/api/county/abc").status_code == 404
    assert client.get("/api/county/31079?crop=wheat").status_code == 422
    names = client.get("/api/counties?state=ne").json()["counties"]
    assert {"fips": "31079", "name": "Hall"} in names and len(names) >= 90
    assert client.get("/api/counties?state=co").status_code == 422


def test_sign_in_is_off_unless_switched_on(client):
    web.app.dependency_overrides[get_settings] = lambda: Settings()
    assert client.get("/auth/status").json()["sign_in"] is False
    assert client.get("/auth/sign-in", follow_redirects=False).status_code == 404


class FakeMyFarm:
    """What farm-account's /sso/token, /sso/check and /sso/sign-out answer."""

    def __init__(self):
        self.calls, self.active, self.up = [], True, True
        self.place = {"name": "Prairie Home", "calls_it": "farm", "state": "NE", "county_fips": "31079",
                      "county": "Hall County, Nebraska"}

    def post(self, url, headers=None, json=None, timeout=None):
        self.calls.append((url, headers, json))
        if not self.up:
            raise httpx.ConnectError("asleep")
        req = httpx.Request("POST", url)
        assert headers == {"Authorization": "Bearer local-dev-yield-predictor"}
        answer = {"user_id": "7f3c2a10-0000-4000-8000-000000000001", "email": "sam@example.com", "name": "Sam Rancher",
                  "role": "user", "place": self.place, "active": self.active, "sid": "5d1e0000-0000-4000-8000-000000000002"}
        if url.endswith("/sso/token"):
            return httpx.Response(200 if self.active else 403, json=answer, request=req)
        if url.endswith("/sso/check"):
            return httpx.Response(200, json=[answer], request=req)
        return httpx.Response(204, request=req)


@pytest.fixture
def my_farm(monkeypatch):
    fake = FakeMyFarm()
    monkeypatch.setattr(sso.httpx, "post", fake.post)
    return fake


def _sign_in(client):
    start = client.get("/auth/sign-in?county=19153", follow_redirects=False)
    assert start.status_code == 303 and start.headers["location"].startswith("https://myfarm.test/#continue/")
    q = parse_qs(start.headers["location"].split("#continue/", 1)[1])
    assert q["app"] == ["corn-yield-predictor"] and len(q["challenge"][0]) == 43
    return client.get(f"/suite/sign-in/done?code={'c' * 30}&state={q['state'][0]}", follow_redirects=False)


def test_sign_in_brings_the_county_and_keeps_no_email(signing, my_farm):
    done = _sign_in(signing)
    assert done.status_code == 303 and done.headers["location"] == "/?county=19153"     # where they started
    token_call = my_farm.calls[0]
    assert token_call[0] == "https://myfarm.test/sso/token"
    assert token_call[2]["return_to"] == "https://yp.test/suite/sign-in/done" and len(token_call[2]["verifier"]) >= 43
    cookie = signing.cookies.get(sso.SESSION_COOKIE)
    assert cookie and "Sam" not in cookie                                                # locked, not readable
    kept = sso.unseal(cookie.strip('"'), ON)
    assert kept["name"] == "Sam" and kept["place"]["fips"] == "31079" and "email" not in json.dumps(kept)
    me = signing.get("/auth/status").json()
    assert me["user"] == {"name": "Sam", "place": {"fips": "31079", "county": "Hall County, Nebraska", "state": "NE",
                                                   "name": "Prairie Home"}}


def test_a_sign_in_that_did_not_start_here_is_refused(signing, my_farm):
    out = signing.get(f"/suite/sign-in/done?code={'c' * 30}&state=made-up-state-123456", follow_redirects=False)
    assert out.status_code == 303 and out.headers["location"].startswith("/?why=")
    assert not my_farm.calls and signing.cookies.get(sso.SESSION_COOKIE) is None


def test_no_access_at_my_farm_says_so(signing, my_farm):
    my_farm.active = False
    out = _sign_in(signing)
    assert "can%27t+sign+in" in out.headers["location"] or "can't" in parse_qs(urlparse(out.headers["location"]).query)["why"][0]


def test_a_changed_cookie_is_ignored(signing, my_farm):
    _sign_in(signing)
    good = signing.cookies.get(sso.SESSION_COOKIE)
    signing.cookies.set(sso.SESSION_COOKIE, good[:-6] + "AAAAAA", domain="yp.test")
    assert signing.get("/auth/status").json()["user"] is None


def test_my_farm_is_asked_again_after_five_minutes(signing, my_farm, monkeypatch):
    _sign_in(signing)
    real_now = sso.now()
    monkeypatch.setattr(sso, "now", lambda: real_now + timedelta(minutes=6))
    my_farm.calls.clear()
    my_farm.place = {**my_farm.place, "county_fips": "31001", "county": "Adams County, Nebraska"}
    assert signing.get("/auth/status").json()["user"]["place"]["fips"] == "31001"          # moved the farm in My Farm
    assert my_farm.calls[0][0] == "https://myfarm.test/sso/check"
    # signed out at My Farm: signed out here at the next check
    monkeypatch.setattr(sso, "now", lambda: real_now + timedelta(minutes=13))
    my_farm.active = False
    assert signing.get("/auth/status").json()["user"] is None


def test_my_farm_asleep_keeps_the_sign_in_for_two_hours(signing, my_farm, monkeypatch):
    _sign_in(signing)
    real_now = sso.now()
    my_farm.up = False
    monkeypatch.setattr(sso, "now", lambda: real_now + timedelta(minutes=30))
    assert signing.get("/auth/status").json()["user"]["name"] == "Sam"
    monkeypatch.setattr(sso, "now", lambda: real_now + timedelta(hours=3))
    assert signing.get("/auth/status").json()["user"] is None


def test_sign_out_ends_it_here_and_at_my_farm(signing, my_farm):
    _sign_in(signing)
    my_farm.calls.clear()
    assert signing.post("/auth/sign-out").status_code == 204
    assert my_farm.calls[0][0] == "https://myfarm.test/sso/sign-out"
    assert my_farm.calls[0][2] == {"sid": "5d1e0000-0000-4000-8000-000000000002"}
    assert signing.get("/auth/status").json()["user"] is None


def test_a_server_refuses_to_start_without_its_key():
    hosted = Settings(hosted=True, my_farm_sign_in=True, public_url="https://yp.onrender.com")
    assert any("FARM_ACCOUNT_KEY" in p for p in hosted.problems())
    ok = Settings(hosted=True, my_farm_sign_in=True, public_url="https://yp.onrender.com", farm_account_key="k" * 40)
    assert ok.problems() == [] and ok.farm_account_key_to_send == "k" * 40
    assert Settings(hosted=True).farm_account_key_to_send is None      # never the development key online
