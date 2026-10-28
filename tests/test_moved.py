"""The Streamlit app once the Yield Predictor moved (v0.2.2). Scott, 2026-10-28: "I don't need anything on streamlit ...
"I'm fine with it being nothing more than a redirect to the live site on render." With YIELD_PREDICTOR_MOVED=1
(a secret on Streamlit Community Cloud) the app is one page with two buttons; without it, the research app as before."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

MAIN = Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py"


def test_on_streamlit_cloud_the_app_only_says_it_moved(monkeypatch):
    monkeypatch.setenv("YIELD_PREDICTOR_MOVED", "1")
    app = AppTest.from_file(str(MAIN), default_timeout=60).run()
    assert not app.exception
    assert [t.value for t in app.title] == ["The Yield Predictor Has Moved"]
    buttons = [(b.proto.label, b.proto.url) for b in app.get("link_button")]
    assert buttons == [("Open the Yield Predictor", "https://yield.cornerpostlogic.com/"),
                       ("Cornerpost Logic Home", "https://cornerpostlogic.com/")]
    assert not app.get("plotly_chart") and not app.get("metric")        # none of the research app ran


def test_every_research_page_says_where_farmers_go():
    """v0.2.3: without the secret, the Streamlit app is Scott's portfolio research app
    (cornerpostlogic-crop-yield-predictor.streamlit.app); every page opens with a line to the farmers' app."""
    source = (MAIN.parents[1] / "src" / "yieldpred" / "brand.py").read_text(encoding="utf-8")
    assert '"[yield.cornerpostlogic.com](https://yield.cornerpostlogic.com/).")' in source
    setup = source[source.index("def page_setup("):source.index("def page_heading(")]
    assert "st.info(RESEARCH_NOTE)" in setup
