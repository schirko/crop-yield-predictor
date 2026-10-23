"""The Yield Predictor's web app (v0.2.0): FastAPI, like the suite's other apps, beside the Streamlit app.

Migration step 1 (Scott, 2026-10-22: "Let's go with step 1", then A of notes/yp-front-A-desk-2026-10-22.png): a
farmer's front page (your county, its yields with the model's 80% ranges, this season so far against 2012 and 2022),
the suite header with Learn and Help, and Sign In With My Farm. Maps and Research still open the Streamlit app until
step 2 moves them here.

Run it on your computer:   uvicorn yieldpred.web.app:app --reload --port 8030
Then open http://127.0.0.1:8030/

    GET  /                               the front page (web/index.html); /help.html the Help
    GET  /health                         {"ok": true, "version": ...} for Render
    GET  /api/counties?state=ne&crop=corn every county with yields
    GET  /api/county/31079?crop=corn     one county's page (yieldpred.web.county)
    GET  /auth/status                    signed in? and your county from My Farm
    GET  /auth/sign-in?county=31079      off to My Farm (it comes straight back when already signed in there)
    GET  /suite/sign-in/done             My Farm sends the browser back here with a one-time code
    POST /auth/sign-out                  ends the sign-in here and at My Farm

Nothing is downloaded or trained here: it reads data/processed/, as the Streamlit app does. Nothing about visitors is
kept on the server; a signed-in person's first name and county ride in a locked cookie (sso.py).
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlencode

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from yieldpred import __version__
from yieldpred.crops import CROPS
from yieldpred.web import county as county_data
from yieldpred.web import sso
from yieldpred.web.config import Settings, get_settings

WEB = Path(__file__).resolve().parent / "static"
MY_FARM = "https://apps.cornerpostlogic.com"


class SecurityHeaders(BaseHTTPMiddleware):
    """As in the suite's other apps: no sniffing, no framing, our page addresses stay ours, and pages may only load
    what comes from this server (Ask a Question also talks to My Farm)."""

    def __init__(self, app, hsts: bool, noindex: bool):
        super().__init__(app)
        self.hsts, self.noindex = hsts, noindex

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        h = response.headers
        h.setdefault("X-Content-Type-Options", "nosniff")
        h.setdefault("Referrer-Policy", "same-origin")
        h.setdefault("X-Frame-Options", "DENY")
        h.setdefault("Content-Security-Policy",
                     "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
                     f"connect-src 'self' {MY_FARM}; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
        if self.hsts:
            h.setdefault("Strict-Transport-Security", "max-age=31536000")
        if self.noindex:      # side by side with the Streamlit app until the links move (step 3): not in search yet
            h.setdefault("X-Robots-Tag", "noindex, nofollow")
        path = request.url.path
        if path.startswith(("/auth", "/suite/")):
            h["Cache-Control"] = "no-store"
        elif path == "/" or path.endswith((".html", ".js", ".css", ".json")):
            h["Cache-Control"] = "no-cache"        # checked with the server every time, so an update shows at once
        return response


_settings = get_settings()
if _settings.problems():
    raise SystemExit("The Yield Predictor can't start safely:\n- " + "\n- ".join(_settings.problems()))

app = FastAPI(title="Yield Predictor", version=__version__, docs_url=None, redoc_url=None)
app.add_middleware(SecurityHeaders, hsts=_settings.secure_cookies, noindex=_settings.hosted)


@app.get("/health")
def health() -> dict:
    return {"ok": True, "version": __version__}


# --- the numbers ----------------------------------------------------------------------------------------------------

def _crop(crop: str) -> str:
    if crop not in CROPS:
        raise HTTPException(422, "Crop must be corn or soybeans.")
    return crop


@app.get("/api/counties")
def counties(state: str = Query("ne", pattern="^(ne|ia)$"), crop: str = Query("corn", max_length=12)) -> dict:
    try:
        return {"state": state, "crop": _crop(crop), "counties": county_data.counties(state, crop)}
    except county_data.NotFound as exc:
        raise HTTPException(404, str(exc)) from None


@app.get("/api/county/{fips}")
def county(fips: str, crop: str = Query("corn", max_length=12)) -> dict:
    if not (fips.isdigit() and len(fips) == 5):
        raise HTTPException(404, "That isn't a county code.")
    try:
        return county_data.page(fips, _crop(crop))
    except county_data.NotFound as exc:
        raise HTTPException(404, str(exc)) from None


# --- Sign In With My Farm -------------------------------------------------------------------------------------------

def _cookie(response: Response, name: str, value: str, settings: Settings, max_age: int) -> None:
    response.set_cookie(name, value, max_age=max_age, httponly=True, samesite="lax", secure=settings.secure_cookies,
                        path="/")


def _off(settings: Settings) -> None:
    if not settings.my_farm_sign_in:
        raise HTTPException(404, "Signing in through My Farm isn't switched on here.")


@app.get("/auth/status")
def status(request: Request, response: Response, settings: Settings = Depends(get_settings)) -> dict:
    """Who's signed in (first name and county only), after asking My Farm again when it's due."""
    out = {"sign_in": settings.my_farm_sign_in, "user": None, "streamlit_url": settings.streamlit_url}
    if not settings.my_farm_sign_in:
        return out
    signed = sso.unseal(request.cookies.get(sso.SESSION_COOKIE), settings)
    if signed is None:
        return out
    fresh = sso.recheck(signed, settings)
    if fresh is None:
        response.delete_cookie(sso.SESSION_COOKIE, path="/")
        return out
    if fresh != signed:
        _cookie(response, sso.SESSION_COOKIE, sso.seal(fresh, settings), settings, sso.SESSION_DAYS * 86400)
    out["user"] = {"name": fresh.get("name"), "place": fresh.get("place")}
    return out


@app.get("/auth/sign-in", include_in_schema=False)
def sign_in(county: str | None = Query(None, max_length=5), settings: Settings = Depends(get_settings)):
    _off(settings)
    if not settings.farm_account_key_to_send:
        raise HTTPException(503, "Sign-in isn't set up on this server yet: YIELD_PREDICTOR_FARM_ACCOUNT_KEY is missing.")
    url, cookie = sso.start(settings, county)
    out = RedirectResponse(url, status_code=303)
    _cookie(out, sso.START_COOKIE, cookie, settings, sso.START_MINUTES * 60)
    return out


@app.get(sso.DONE_PATH, include_in_schema=False)
def done(request: Request, code: str = Query("", max_length=200), state: str = Query("", max_length=200),
         settings: Settings = Depends(get_settings)):
    _off(settings)
    try:
        if not code or not state:
            raise sso.SignInError("My Farm didn't send a sign-in code back. Press Sign In again.")
        answer, county = sso.finish(settings, request.cookies.get(sso.START_COOKIE), code, state)
    except sso.SignInError as exc:
        out = RedirectResponse(f"/?{urlencode({'why': str(exc)})}", status_code=303)
        out.delete_cookie(sso.START_COOKIE, path="/")
        return out
    signed = sso.session_from(answer)
    mine = (signed.get("place") or {}).get("fips")
    out = RedirectResponse(f"/?{urlencode({'county': county or mine})}" if (county or mine) else "/", status_code=303)
    out.delete_cookie(sso.START_COOKIE, path="/")
    _cookie(out, sso.SESSION_COOKIE, sso.seal(signed, settings), settings, sso.SESSION_DAYS * 86400)
    return out


@app.post("/auth/sign-out", status_code=204)
def sign_out(request: Request, settings: Settings = Depends(get_settings)) -> Response:
    signed = sso.unseal(request.cookies.get(sso.SESSION_COOKIE), settings)
    out = Response(status_code=204)
    out.delete_cookie(sso.SESSION_COOKIE, path="/")
    if signed:
        sso.sign_out_at_my_farm(settings, signed.get("sid"))
    return out


@app.exception_handler(HTTPException)
async def plain(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=getattr(exc, "headers", None))


app.mount("/", StaticFiles(directory=WEB, html=True), name="pages")
