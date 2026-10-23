"""Build data/processed/season_ne.parquet: every Nebraska county, every year, over this season's days so far.

Reads data/raw/power/<fips>_2000_2025.csv (scripts/fetch_weather.py) and data/raw/power_season/<fips>_<year>.csv
(scripts/fetch_season.py). Every year is cut to the same days, May 1 to the last day this season's weather reaches
(yieldpred.season), so the web app compares like with like. The file is small (about 2,500 rows) and goes in Git:
the web app reads it, and never downloads anything itself.

    python scripts/season_so_far.py                 # this year
    python scripts/season_so_far.py --year 2026
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import pandas as pd

from yieldpred.season import last_full_day, county_table
from yieldpred.weather import county_points

ROOT = Path(__file__).resolve().parents[1]
HISTORY = ROOT / "data" / "raw" / "power"
SEASON = ROOT / "data" / "raw" / "power_season"
OUT = ROOT / "data" / "processed" / "season_ne.parquet"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--year", type=int, default=date.today().year)
    args = parser.parse_args()

    points = county_points("31")
    current = {}
    for fips in points["fips"]:
        path = SEASON / f"{fips}_{args.year}.csv"
        if path.exists():
            current[fips] = pd.read_csv(path, parse_dates=["date"])
    if not current:
        raise SystemExit(f"No {args.year} weather in {SEASON.relative_to(ROOT)}: run scripts/fetch_season.py first.")
    # One cut-off for the whole state (the earliest last day among the counties), so every county shows the same days.
    through = min(d for d in (last_full_day(f) for f in current.values()) if d is not None)

    frames, missing = [], []
    for fips in points["fips"]:
        hist = next(HISTORY.glob(f"{fips}_2000_*.csv"), None)
        if hist is None:
            missing.append(fips)
            continue
        table = county_table(pd.read_csv(hist, parse_dates=["date"]), current.get(fips), fips, args.year, through)
        if not table.empty:
            frames.append(table)
    out = pd.concat(frames, ignore_index=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(OUT, index=False)
    now = out[out["year"] == args.year]
    print(f"Saved {len(out):,} county-years to {OUT.relative_to(ROOT)}: {args.year} through {through:%B} {through.day}")
    print(f"{len(now)} counties have {args.year}; {len(missing)} have no 2000-2025 file")


if __name__ == "__main__":
    main()
