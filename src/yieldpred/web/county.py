"""What the web app's front page shows for one county (v0.2.0; Scott chose A of notes/yp-front-A-desk-2026-10-22.png).

Built only from the same files and functions the Streamlit app uses (yieldpred.appdata), so the two can't disagree:
tests/test_web_numbers.py checks every county against the Streamlit County Explorer's own functions.

- history: every year USDA published the county's yield, with the model's 80% range for that year and whether the
  yield landed inside it (data/processed/ranges*.parquet, from scripts/honest_ranges.py: each prediction came from a
  model that never saw the county's crop district, and its range from the misses in the other folds).
- record: how many of those years landed inside (appdata.range_record, the County Explorer's "Range held N of M").
- trend: a straight line through the county's own yields, carried one year on. Labeled on the page as a trend year,
  not a forecast: the model has no forecast for a season still in the field.
- dryland: non-irrigated yields, until USDA stopped publishing them by county (after 2018).
- season: this season so far against normal and the drought years (yieldpred.season; Nebraska only for now).
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd

from yieldpred import appdata, season as season_mod
from yieldpred.crops import CROPS, get_crop

STATES = {"ne": "Nebraska", "ia": "Iowa"}
STATE_FIPS = {"31": "ne", "19": "ia"}
SEASON_FILE = {"ne": "season_ne.parquet"}       # Iowa's season so far comes later


class NotFound(LookupError):
    """No such county (or no yields for it), in plain words."""


@lru_cache(maxsize=8)
def _yields(state: str, crop: str) -> pd.DataFrame:
    found = appdata.load_yields(state, crop)
    if found is None:
        raise NotFound(f"No {get_crop(crop).word} yields for {STATES[state]} yet.")
    return found


@lru_cache(maxsize=8)
def _ranges(state: str, crop: str) -> pd.DataFrame | None:
    return appdata.load_ranges(state, crop)


@lru_cache(maxsize=2)
def _season(state: str) -> pd.DataFrame | None:
    name = SEASON_FILE.get(state)
    path = appdata.PROCESSED / name if name else None
    return pd.read_parquet(path) if path is not None and path.exists() else None


def clear() -> None:
    """Forget the files read (tests that swap the data folder)."""
    for f in (_yields, _ranges, _season):
        f.cache_clear()


def state_of(fips: str) -> str:
    state = STATE_FIPS.get(str(fips)[:2])
    if state is None or not str(fips).isdigit() or len(str(fips)) != 5:
        raise NotFound("That isn't a Nebraska or Iowa county.")
    return state


def counties(state: str, crop: str = "corn") -> list[dict]:
    """Every county with yields, by name: [{fips, name}]. Name is "Hall" (the page adds "County")."""
    y = _yields(state, crop)
    names = y[y["practice"] == "all"][["fips", "county_name"]].drop_duplicates("fips")
    names = names.assign(name=names["county_name"].str.title()).sort_values("name")
    return [{"fips": f, "name": n} for f, n in zip(names["fips"], names["name"])]


def trend(years: pd.Series, values: pd.Series, ahead: int) -> dict | None:
    """A straight line (least squares) through the county's yields, and its value in `ahead`."""
    if len(years) < 10:
        return None
    slope, intercept = np.polyfit(years.astype(float), values.astype(float), 1)
    return {"year": int(ahead), "value": round(float(slope * ahead + intercept), 1),
            "slope": round(float(slope), 2), "from": int(years.min()), "to": int(years.max()), "years": int(len(years))}


def page(fips: str, crop: str = "corn", season_year: int | None = None) -> dict:
    """Everything the front page draws for one county and crop."""
    crop = get_crop(crop).key
    state = state_of(fips)
    y = _yields(state, crop)
    mine = y[y["fips"] == fips]
    if mine.empty:
        raise NotFound(f"USDA hasn't published {get_crop(crop).word} yields for that county.")
    name = str(mine["county_name"].iloc[0]).title()
    all_ = mine[mine["practice"] == "all"].sort_values("year")

    ranges = _ranges(state, crop)
    county_ranges = ranges[ranges["fips"] == fips].sort_values("year") if ranges is not None else pd.DataFrame()
    by_year = {int(r.year): r for r in county_ranges.itertuples()}
    history = []
    for r in all_.itertuples():
        row = {"year": int(r.year), "yield": round(float(r.yield_bu_acre), 1)}
        rr = by_year.get(int(r.year))
        if rr is not None:
            row.update(predicted=round(float(rr.predicted), 1), low=round(float(rr.low), 1),
                       high=round(float(rr.high), 1), inside=bool(rr.inside))
        history.append(row)
    record = appdata.range_record(ranges, fips) if not county_ranges.empty else None

    dry = mine[mine["practice"] == "non_irrigated"].sort_values("year")
    first, last = (int(all_["year"].min()), int(all_["year"].max())) if len(all_) else (None, None)
    latest = int(y[y["practice"] == "all"]["year"].max())     # the newest year USDA published for any county here
    missing = [yr for yr in range(first, last + 1) if yr not in set(all_["year"])] if first else []

    out = {"fips": fips, "county": name, "state": STATES[state], "state_code": state, "crop": crop,
           "crop_name": CROPS[crop].name, "unit": CROPS[crop].unit, "history": history,
           "record": record, "modeled": record is not None, "missing_years": missing, "latest_year": latest,
           "last": history[-1] if history else None,
           "trend": trend(all_["year"], all_["yield_bu_acre"], latest + 1) if last else None,
           "dryland": [{"year": int(r.year), "yield": round(float(r.yield_bu_acre), 1)} for r in dry.itertuples()],
           "season": None, "season_words": ""}
    table = _season(state)
    if table is not None:
        year = season_year or int(table["year"].max())
        found = season_mod.compare(table, fips, year)
        if found:
            out["season"], out["season_words"] = found, season_mod.words(found)
    return out
