"""The web app's numbers match the Streamlit app's (migration step 1, Scott 2026-10-22: "a test that the numbers match
the Streamlit app"). Both read the same files; these tests make sure the web app shapes them the same way.

1. Every county, both states, both crops: the web page's yields, ranges and "held N of M" equal what the Streamlit
   County Explorer builds from (appdata.load_ranges, appdata.load_yields, appdata.range_record).
2. The Streamlit County Explorer itself, run with AppTest for a few counties: the sentence it prints, "Range held N of M
   years", carries the web page's numbers.
"""

from __future__ import annotations

import re

import pandas as pd
import pytest

from yieldpred import appdata
from yieldpred.web import county

CASES = [("ne", "corn"), ("ne", "soybeans"), ("ia", "corn"), ("ia", "soybeans")]


@pytest.mark.parametrize("state,crop", CASES)
def test_every_county_matches_the_streamlit_files(state, crop):
    yields = appdata.load_yields(state, crop)
    ranges = appdata.load_ranges(state, crop)
    listed = county.counties(state, crop)
    assert len(listed) == yields[yields["practice"] == "all"]["fips"].nunique()
    checked = 0
    for c in listed:
        page = county.page(c["fips"], crop)
        mine = yields[(yields["fips"] == c["fips"]) & (yields["practice"] == "all")].sort_values("year")
        assert [h["year"] for h in page["history"]] == mine["year"].tolist()
        assert [h["yield"] for h in page["history"]] == pytest.approx(mine["yield_bu_acre"].round(1).tolist())
        rr = ranges[ranges["fips"] == c["fips"]].set_index("year")
        for h in page["history"]:
            if h["year"] in rr.index:
                row = rr.loc[h["year"]]
                assert (h["low"], h["high"], h["predicted"]) == pytest.approx(
                    (round(row["low"], 1), round(row["high"], 1), round(row["predicted"], 1)))
                assert h["inside"] == bool(row["inside"])
            else:
                assert "low" not in h
        if len(rr):
            assert page["record"] == appdata.range_record(ranges, c["fips"])
            checked += 1
        else:
            assert page["record"] is None and not page["modeled"]
    assert checked >= 0.8 * len(listed)


def test_hall_county_corn_is_what_the_mockup_showed():
    """The numbers on notes/yp-front-A-desk-2026-10-22.png, which Scott chose."""
    p = county.page("31079", "corn")
    assert (p["county"], p["state"]) == ("Hall", "Nebraska")
    assert p["last"]["year"] == 2025 and p["last"]["yield"] == 210.4 and p["last"]["inside"]
    assert (round(p["last"]["low"]), round(p["last"]["high"])) == (193, 230)
    assert p["record"] == {"held": 23, "years": 25}
    assert p["trend"]["year"] == 2026 and round(p["trend"]["value"]) == 213 and p["trend"]["slope"] == pytest.approx(1.68)
    assert p["missing_years"] == [2021]
    assert p["dryland"][-1]["year"] == 2018 and p["dryland"][[d["year"] for d in p["dryland"]].index(2012)]["yield"] < 30


def test_the_trend_is_a_least_squares_line():
    years = pd.Series(range(2000, 2020))
    t = county.trend(years, 100 + 2 * (years - 2000), 2020)
    assert t["value"] == pytest.approx(140.0) and t["slope"] == pytest.approx(2.0) and t["years"] == 20
    assert county.trend(years[:5], years[:5], 2020) is None          # too few years for a trend


def test_unknown_counties_are_refused():
    for bad in ("99999", "31", "abcde", "08005"):
        with pytest.raises(county.NotFound):
            county.page(bad, "corn")


# --- the Streamlit County Explorer itself ---------------------------------------------------------------------------

st_testing = pytest.importorskip("streamlit.testing.v1")
EXPLORER = appdata.ROOT / "app" / "pages" / "2_County_Explorer.py"


@pytest.mark.parametrize("fips,state,crop", [("31079", "ne", "corn"), ("31055", "ne", "soybeans"),
                                             ("19153", "ia", "corn")])
def test_the_streamlit_county_explorer_says_the_same(fips, state, crop):
    page = county.page(fips, crop)
    app = st_testing.AppTest.from_file(str(EXPLORER), default_timeout=120)
    app.query_params["state"] = state
    app.query_params["crop"] = crop
    app.run()
    box = app.selectbox[0]
    name = next(o for o in box.options if o.lower() == page["county"].lower())
    box.set_value(name).run()
    assert not app.exception
    said = " ".join(m.value for m in app.markdown)
    found = re.search(r"Range held (\d+) of (\d+) years", said)
    assert found, "the County Explorer no longer prints 'Range held N of M years'"
    assert {"held": int(found.group(1)), "years": int(found.group(2))} == page["record"]


def test_the_trend_year_is_the_season_after_usdas_newest_even_where_a_year_is_missing():
    """Adams County, Nebraska has no 2025 corn yield from USDA: its trend year is still 2026, not 2025."""
    p = county.page("31001", "corn")
    assert p["last"]["year"] == 2024 and p["latest_year"] == 2025 and p["trend"]["year"] == 2026
