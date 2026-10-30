"""The web app's pages and hosting files (v0.2.0): Help names only what exists, the suite files match the masters, the
page builds no markup from data, and the Render image needs only what it copies."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "src" / "yieldpred" / "web" / "static"


def text(name: str) -> str:
    return (WEB / name).read_text(encoding="utf-8")


def test_every_name_in_help_is_on_a_page():
    """Every name in italics in Help is a heading, tab, button or link the app shows (so a rename shows up here)."""
    help_ = text("help.html")
    body = help_[help_.index('<main'):help_.index('</main>')]
    names = set(re.findall(r"<i>([^<]+)</i>", body))
    assert len(names) >= 10      # v0.2.2: Maps, Research and How It Works left with the Streamlit links
    shown = text("index.html") + text("app.js") + help_[:help_.index('<main')]
    missing = [n for n in names if n not in shown]
    assert not missing, f"Help names things the app doesn't show: {missing}"


def test_help_has_the_suites_four_parts_and_is_in_learn():
    help_ = text("help.html")
    for part in ("Getting Started", "How Do I&hellip;", "What the Numbers Mean", "When Something Looks Wrong"):
        assert f"<h2>{part}</h2>" in help_
    learn = text("index.html")
    assert learn.index('href="help.html"') < learn.index("About This App")      # Help first in Learn


def test_the_ranges_are_described_as_they_were_built():
    """The ranges came from a model that never saw the county's crop district (yieldpred/ranges.py), not 'without that
    year' as the first mockup said."""
    for name in ("app.js", "help.html"):
        words = text(name)
        assert "never saw" in words and "without that year" not in words


def test_no_markup_is_built_from_data():
    for name in ("app.js", "header.js"):
        assert "innerHTML" not in text(name) and "insertAdjacentHTML" not in text(name)


def test_buttons_and_headings_are_title_case():
    page = text("index.html") + text("app.js")
    for words in ("This Season So Far", "Your County", "How often the range held", "A trend year for"):
        assert words in page
    assert ">Change County<" in page and ">Show This County<" in page and '"Show the Numbers"' in page


def test_suite_files_match_the_masters():
    master = ROOT.parent / "herd-planner" / "brand"
    if not master.exists():
        pytest.skip("Herd Planner isn't checked out next to this project")
    for name in ("suite.css", "suite.js", "suite-apps.json"):
        copy = (WEB / name).read_bytes().replace(b"\r\n", b"\n")
        assert copy == (master / name).read_bytes().replace(b"\r\n", b"\n"), f"{name} drifted: copy herd-planner/brand/{name} here again"


def test_suite_files_match_the_streamlit_apps_copies():
    for name in ("suite.css", "suite-apps.json"):
        assert (WEB / name).read_bytes() == (ROOT / "app" / "assets" / name).read_bytes()


def test_the_image_copies_every_file_the_app_reads():
    docker = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    copied = re.findall(r"data/processed/([\w*.]+)", docker)
    for name in copied:
        assert list((ROOT / "data" / "processed").glob(name)), f"the Dockerfile copies {name}, which isn't there"
    for state, crop in (("ne", "corn"), ("ne", "soybeans"), ("ia", "corn"), ("ia", "soybeans")):
        stem = {"ne": "ranges", "ia": "ranges_ia"}[state] + ("_soy" if crop == "soybeans" else "")
        assert f"{stem}.parquet" in docker
    assert "season_ne.parquet" in docker


def test_the_server_needs_no_data_science_libraries():
    """Online the app runs on requirements-web.txt only: importing it must not pull in Streamlit, scikit-learn or
    geopandas."""
    lock = [line.split("==")[0] for line in (ROOT / "requirements-web.txt").read_text(encoding="utf-8").lower().splitlines()
            if line.strip() and not line.startswith("#")]
    for heavy in ("streamlit", "scikit-learn", "geopandas", "matplotlib"):
        assert heavy not in lock
    code = ("import sys; import yieldpred.web.app; "
            "bad = [m for m in ('streamlit', 'sklearn', 'geopandas', 'matplotlib') if m in sys.modules]; "
            "print(','.join(bad))")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == ""


def test_the_blueprint_holds_no_secrets():
    blueprint = (ROOT / "render.yaml").read_text(encoding="utf-8")
    assert "YIELD_PREDICTOR_FARM_ACCOUNT_KEY" in blueprint and "sync: false" in blueprint
    assert not re.search(r"value:\s*\"?[A-Za-z0-9_\-]{24,}", blueprint)


def test_the_blueprint_names_both_addresses():
    """v0.2.1: the Yield Predictor moves to yield.cornerpostlogic.com (Scott, 2026-10-28: "Let's go with render").
    v0.2.2: it signs in at My Farm's own address, apps.cornerpostlogic.com (v0.2.1 wrongly sent it to the onrender one)."""
    blueprint = (ROOT / "render.yaml").read_text(encoding="utf-8")
    assert "key: YIELD_PREDICTOR_PUBLIC_URL\n        value: https://yield.cornerpostlogic.com" in blueprint
    assert "key: YIELD_PREDICTOR_FARM_ACCOUNT_URL\n        value: https://apps.cornerpostlogic.com" in blueprint
    assert 'farm_account_url: str = "https://apps.cornerpostlogic.com"' in (ROOT / "src" / "yieldpred" / "web" / "config.py").read_text(encoding="utf-8")


def test_learn_has_plans_after_about_this_app():
    """Plans in every app's Learn menu (Scott chose A of farm-account/notes/apps-plans-link-2026-10-22.png)."""
    plans = '<a href="https://cornerpostlogic.com/plans.html" data-note="Free and paid">Plans</a>'
    for name in ("index.html", "help.html"):
        page = text(name)
        assert page.index(">About This App</a>") < page.index(plans) < page.index(">How We Test</a>"), name


def test_nothing_sends_anyone_to_streamlit():
    """v0.2.2 (Scott chose B, 2026-10-28): the Streamlit app only says it moved, so Maps, Research and How It Works
    come off these pages until they're rebuilt here. How the model was built is under Learn, How We Test."""
    for name in ("index.html", "help.html"):
        page = text(name)
        assert "data-streamlit" not in page and ">Maps<" not in page and ">Research<" not in page, name
        assert ">How It Works</a>" not in page, name
    assert "is on Research" not in text("app.js")


def test_the_landing_page_is_there_for_people_signed_out():
    """v0.2.4 (Scott, 2026-10-30: "We need a splash page like the other apps have for when a person is not logged in";
    notes/yp-splash-*-2026-10-30.png): the landing page sits before the county page, app.js picks one, Help says so."""
    page, js = text("index.html"), text("app.js")
    assert page.index('id="landing"') < page.index('<main id="main">')
    for words in ("What You Get with the Yield Predictor", ">See Your County<", ">Sign In<", "With a Subscription",
                  "Your County stays free."):
        assert words in page
    assert 'dataset.view = "landing"' in js and 'dataset.view = "county"' in js and '"view") !== "county"' in js
    assert 'href="./?view=county" id="land-county"' in page and 'href="./?view=county" aria-current="page"' in page
    assert "<i>See Your County</i>" in text("help.html")
    for shot in ("yield-computer.jpg", "yield-phone.jpg"):
        assert (WEB / "shots" / shot).stat().st_size < 150_000 and f"shots/{shot}" in page


def test_paid_features_on_the_landing_page_are_marked_coming():
    """Nothing paid is built yet (claude/subscription-benefits.md), so the subscription column says Coming."""
    page = text("index.html")
    paid = page[page.index('class="land-col paid"'):page.index('class="land-foot"')]
    assert ">Coming<" in paid and "nothing is charged today" in page


def test_the_landing_page_numbers_match_their_sources():
    """Every number on the landing page names a source, and these checks recompute them from the same files."""
    import pandas as pd
    data = ROOT / "data" / "processed"
    page = text("index.html")
    cov = pd.read_parquet(data / "ranges_coverage.parquet")
    row = cov[(cov["ranges"] == "width scaled to irrigation") & (cov["group"] == "all")].iloc[0]
    assert f"<b>{round(row['held_pct'])}%</b>" in page and f"{int(row['rows']):,} county-years" in page
    counties, years = 0, set()
    for state in ("ne", "ia"):
        y = pd.read_parquet(data / f"{state}_corn_yield_county.parquet")
        y = y[y["practice"] == "all"]
        counties += y["fips"].nunique()
        years |= set(y["year"])
    assert f"<b>{counties}</b>" in page and f"<b>{len(years)}</b>" in page
    assert f"{min(years)} to {max(years)}" in page
