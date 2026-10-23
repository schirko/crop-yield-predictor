"""This season so far (yieldpred.season): made-up weather with known answers, then the real file for Hall County."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from yieldpred import season
from yieldpred.appdata import PROCESSED


def days(year: int, rain_mm: float = 2.54, tmax_c: float = 30.0, end: str = "12-31") -> pd.DataFrame:
    d = pd.date_range(f"{year}-01-01", f"{year}-{end}")
    return pd.DataFrame({"date": d, "tmax_c": tmax_c, "tmin_c": 10.0, "precip_mm": rain_mm})


def test_the_window_is_may_1_to_the_same_day_and_never_past_september():
    assert season.window(2012, date(2026, 8, 10)) == (date(2012, 5, 1), date(2012, 8, 10))
    assert season.window(2026, date(2026, 10, 20)) == (date(2026, 5, 1), date(2026, 9, 30))


def test_a_season_is_summed_over_the_window_only():
    s = season.summarize(days(2020), 2020, date(2026, 7, 31))       # May 1 to Jul 31: 92 days of 0.1 in
    assert s["days"] == 92 and s["rain_in"] == pytest.approx(9.2) and s["jul_rain_in"] == pytest.approx(3.1)
    assert s["hot_days"] == 0                                         # 30°C is 86°F
    hot = season.summarize(days(2020, tmax_c=32.3), 2020, date(2026, 6, 30))
    assert hot["hot_days"] == 61                                      # 32.3°C is 90.1°F: every day counts
    assert season.summarize(days(2020, tmax_c=32.2), 2020, date(2026, 6, 30))["hot_days"] == 0   # 89.96°F
    assert season.summarize(days(2020), 2020, date(2026, 6, 30))["jul_rain_in"] is None


def test_a_gap_in_the_weather_drops_the_year():
    d = days(2020)
    d.loc[d["date"] == "2020-06-15", "precip_mm"] = None
    assert season.summarize(d, 2020, date(2026, 7, 1)) is None
    assert season.summarize(days(2020, end="06-30"), 2020, date(2026, 7, 1)) is None


def test_every_year_is_cut_to_this_seasons_days():
    history = pd.concat([days(y, rain_mm=2.54 * (2 if y == 2012 else 1)) for y in range(2000, 2026)])
    now = days(2026, rain_mm=5.08, end="08-10")
    t = season.county_table(history, now, "31001", 2026, season.last_full_day(now))
    assert t["year"].tolist() == list(range(2000, 2027))
    assert (t["days"] == 102).all() and (t["through"] == pd.Timestamp("2026-08-10")).all()
    c = season.compare(t, "31001", 2026)
    assert c["now"]["rain_in"] == pytest.approx(20.4) and c["through"] == "2026-08-10" and not c["complete"]
    assert c["normal"]["rain_in"] == pytest.approx(round((25 * 10.2 + 20.4) / 26, 1))
    assert c["years"]["2012"]["rain_in"] == pytest.approx(20.4)
    assert c["normal_years"] == [2000, 2025]
    assert season.compare(t, "31001", 2027) is None


def test_the_sentence_says_what_the_numbers_say():
    c = {"now": {"rain_in": 21.4, "hot_days": 47}, "normal": {"rain_in": 17.1, "hot_days": 36.6},
         "years": {"2012": {"rain_in": 7.7}, "2022": {"rain_in": 11.7}}}
    assert season.words(c) == "Wetter than normal, nothing like 2012 or 2022; more hot days than usual (47 against 37)."
    dry = {**c, "now": {"rain_in": 8.5, "hot_days": 38}}
    assert season.words(dry) == "Much drier than normal, close to 2012 and 2022; about the usual number of hot days (38 against 37)."


def test_the_real_file_for_hall_county():
    path = PROCESSED / "season_ne.parquet"
    if not path.exists():
        pytest.skip("run scripts/season_so_far.py first")
    t = pd.read_parquet(path)
    assert t["fips"].nunique() == 93                                # every Nebraska county
    year = int(t["year"].max())
    c = season.compare(t, "31079", year)
    assert c["normal_years"] == [2000, 2025]
    assert c["years"]["2012"]["rain_in"] < c["normal"]["rain_in"] / 2   # 2012: about a third of normal rain
    assert c["years"]["2012"]["hot_days"] > c["normal"]["hot_days"]
