"""Download this season's daily weather for every Nebraska county (the web app's "This Season So Far").

One NASA POWER request per county (93 of them), January 1 to yesterday, saved as data/raw/power_season/<fips>_<year>.csv
(not in Git, like data/raw/power/). Then run scripts/season_so_far.py to rebuild the small file the web app reads.

    python scripts/fetch_season.py                  # this year
    python scripts/fetch_season.py --year 2026

POWER is free and needs no key; it asks for polite use, so there's a pause between requests. It usually runs a few days
behind today: the last day it filled in is what the page's "through" date shows.
"""

from __future__ import annotations

import argparse
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests

from yieldpred.weather import POWER_FILL, POWER_PARAMS, POWER_URL, county_points

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw" / "power_season"


def fetch(lat: float, lon: float, start: date, end: date, timeout: int = 120) -> pd.DataFrame:
    """Daily weather for one point, `start` to `end`: date, tmax_c, tmin_c, precip_mm. Days POWER hasn't filled in
    yet (its -999) are dropped from the end."""
    params = {"parameters": ",".join(POWER_PARAMS), "community": "AG", "latitude": round(lat, 4),
              "longitude": round(lon, 4), "start": start.strftime("%Y%m%d"), "end": end.strftime("%Y%m%d"),
              "format": "JSON"}
    resp = requests.get(POWER_URL, params=params, timeout=timeout)
    resp.raise_for_status()
    block = resp.json()["properties"]["parameter"]
    df = pd.DataFrame({"tmax_c": pd.Series(block["T2M_MAX"]), "tmin_c": pd.Series(block["T2M_MIN"]),
                       "precip_mm": pd.Series(block["PRECTOTCORR"])}).astype(float)
    df = df.mask(df <= POWER_FILL + 1)
    df.index = pd.to_datetime(df.index, format="%Y%m%d")
    df = df.rename_axis("date").reset_index()
    complete = df.dropna()
    return df[df["date"] <= complete["date"].max()].reset_index(drop=True) if len(complete) else complete


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--year", type=int, default=date.today().year)
    parser.add_argument("--pause", type=float, default=1.0, help="Seconds between requests (be polite to NASA)")
    args = parser.parse_args()

    end = min(date.today() - timedelta(days=1), date(args.year, 12, 31))
    OUT.mkdir(parents=True, exist_ok=True)
    points = county_points("31")
    failures = []
    for i, row in points.iterrows():
        try:
            daily = fetch(row.lat, row.lon, date(args.year, 1, 1), end)
        except (requests.RequestException, KeyError, ValueError) as exc:
            print(f"[{i + 1:>2}/{len(points)}] {row.county_name:<18} FAILED ({type(exc).__name__})")
            failures.append(row.fips)
            continue
        daily.to_csv(OUT / f"{row.fips}_{args.year}.csv", index=False)
        last = daily["date"].max().date() if len(daily) else "nothing yet"
        print(f"[{i + 1:>2}/{len(points)}] {row.county_name:<18} through {last}")
        time.sleep(args.pause)
    if failures:
        print(f"\n{len(failures)} counties failed; run it again to fetch them: {', '.join(failures)}")
    print("\nNext: python scripts/season_so_far.py")


if __name__ == "__main__":
    main()
