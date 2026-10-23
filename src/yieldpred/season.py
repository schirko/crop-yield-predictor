"""This season so far, beside a normal season and the drought years (the web app's front page, v0.2.0).

Scott, 2026-10-22, chose A of notes/yp-front-A-desk-2026-10-22.png: a farmer's county first, then "This Season So Far":
rain since May 1, days over 90°F and July rain, each beside a normal season and 2012 and 2022 over the same days.

Every year is cut to the same days, so a half-finished season is compared fairly: on August 10, 2026 is May 1 to
August 10, and so is the normal and so is 2012. The normal is the average of 2000 to 2025 over those days (NASA POWER,
the same daily weather the model uses: data/raw/power/). The season so far comes from data/raw/power_season/, which
scripts/fetch_season.py downloads, and scripts/season_so_far.py turns both into data/processed/season_ne.parquet, the
one small file the web app reads.

Plain functions, no web code: tested in tests/test_season.py.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

SEASON_START = (5, 1)            # May 1: corn is in the ground across Nebraska by then (planting from late April)
SEASON_END = (9, 30)             # September 30: the end of the growing season the model uses for rain
HOT_F = 90.0                     # "days over 90°F": the high above 90°F (32.2°C)
MM_PER_INCH = 25.4
NORMAL_YEARS = (2000, 2025)      # the years the model was built on; the normal stays put until they're extended
COMPARE = (2012, 2022)           # Nebraska's two drought years in the record


def window(year: int, through: date) -> tuple[date, date]:
    """May 1 to the same month and day as `through` (never past Sep 30) in `year`."""
    end = min((through.month, through.day), SEASON_END)
    return date(year, *SEASON_START), date(year, *end)


def summarize(daily: pd.DataFrame, year: int, through: date) -> dict | None:
    """One county-year over the window: rain (in), days over 90°F, July rain so far (in), and the days counted.
    None when the weather doesn't cover the whole window (a gap would make the year look drier than it was)."""
    start, end = window(year, through)
    days = daily[(daily["date"] >= pd.Timestamp(start)) & (daily["date"] <= pd.Timestamp(end))]
    expected = (end - start).days + 1
    if len(days) < expected or days[["tmax_c", "precip_mm"]].isna().any().any():
        return None
    july = days[days["date"].dt.month == 7]
    return {"year": year, "rain_in": round(days["precip_mm"].sum() / MM_PER_INCH, 2),
            "hot_days": int((days["tmax_c"] * 9 / 5 + 32 > HOT_F).sum()),
            "jul_rain_in": round(july["precip_mm"].sum() / MM_PER_INCH, 2) if len(july) else None,
            "days": expected}


def county_table(history: pd.DataFrame, current: pd.DataFrame | None, fips: str, season: int,
                 through: date) -> pd.DataFrame:
    """Every year of one county over the same window: 2000-2025 from `history`, and `season` from `current`."""
    rows = []
    for year in sorted(history["date"].dt.year.unique()):
        if year >= season:
            continue
        found = summarize(history, int(year), through)
        if found:
            rows.append(found)
    if current is not None:
        found = summarize(current, season, through)
        if found:
            rows.append(found)
    out = pd.DataFrame(rows)
    if not out.empty:
        out.insert(0, "fips", fips)
        out["through"] = pd.Timestamp(window(season, through)[1])
    return out


def last_full_day(current: pd.DataFrame) -> date | None:
    """The last day this season's file covers with weather (POWER runs a few days behind)."""
    full = current.dropna(subset=["tmax_c", "precip_mm"])
    return full["date"].max().date() if len(full) else None


def compare(table: pd.DataFrame, fips: str, season: int) -> dict | None:
    """What the page shows for one county: this season, the normal, 2012 and 2022, all over the same days.
    None when this season isn't in the file (before May 1, or the county has no weather yet)."""
    county = table[table["fips"] == fips]
    now = county[county["year"] == season]
    if now.empty:
        return None
    normal = county[(county["year"] >= NORMAL_YEARS[0]) & (county["year"] <= NORMAL_YEARS[1])]
    through = pd.Timestamp(now["through"].iloc[0]).date()

    def row(frame: pd.DataFrame) -> dict | None:
        if frame.empty:
            return None
        jul = frame["jul_rain_in"].dropna()
        return {"rain_in": round(float(frame["rain_in"].mean()), 1), "hot_days": round(float(frame["hot_days"].mean()), 1),
                "jul_rain_in": round(float(jul.mean()), 1) if len(jul) else None}

    return {"season": season, "from": date(season, *SEASON_START).isoformat(), "through": through.isoformat(),
            "complete": (through.month, through.day) >= SEASON_END,
            "now": row(now), "normal": row(normal), "normal_years": [int(normal["year"].min()), int(normal["year"].max())]
            if len(normal) else None,
            "years": {str(y): row(county[county["year"] == y]) for y in COMPARE}}


def words(c: dict) -> str:
    """One plain sentence about the season, from the numbers only (no forecast)."""
    now, normal = c["now"], c["normal"]
    if not now or not normal:
        return ""
    ratio = now["rain_in"] / normal["rain_in"] if normal["rain_in"] else 1.0
    if ratio >= 1.10:
        rain = "Wetter than normal"
    elif ratio <= 0.75:
        rain = "Much drier than normal"
    elif ratio <= 0.90:
        rain = "Drier than normal"
    else:
        rain = "About normal rain"
    drought = [y for y, r in c["years"].items() if r and now["rain_in"] <= r["rain_in"] * 1.15]
    tail = f", close to {' and '.join(drought)}" if drought else ", nothing like 2012 or 2022"
    hot = now["hot_days"] - normal["hot_days"]
    heat = ("more hot days than usual" if hot >= 5 else "fewer hot days than usual" if hot <= -5
            else "about the usual number of hot days")
    return f"{rain}{tail}; {heat} ({now['hot_days']:.0f} against {normal['hot_days']:.0f})."
