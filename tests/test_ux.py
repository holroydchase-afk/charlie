"""Copy the user reads: no stray markdown in plain-text fields."""
from charlie.profile import build_profile


def test_profile_text_has_no_raw_markdown():
    p = build_profile("Nurse at HCA Healthcare", capital=20000)
    for text in (p.summary, p.caution):
        assert "*" not in text and "_" not in text


# ---------------------------------------------------------------- CHL-UX27 explainer headings
def test_UX27_every_strategy_has_a_grammatical_explainer_title():
    import re
    from charlie.strategies import STRATEGIES
    problems = []
    for key, s in STRATEGIES.items():
        title = s.get("explainer_title")
        if not title:
            problems.append(f"{key}: no explainer_title")
            continue
        if re.search(r"What is a buy", title, re.I) or "leaps" in title:
            problems.append(f"{key}: {title!r}")
        if not title[0].isupper():
            problems.append(f"{key}: should start with a capital: {title!r}")
        m = re.match(r"What is (an?) (\w)", title)
        if m and (m.group(1) == "an") != (m.group(2).lower() in "aeiou"):
            problems.append(f"{key}: wrong article: {title!r}")
    assert problems == []
    assert "shares" in STRATEGIES["shares"]["explainer_title"].lower()
    assert "LEAPS" in STRATEGIES["leaps_call"]["explainer_title"]


def test_UX27_trades_and_meta_carry_the_explainer_title():
    from datetime import date
    from charlie.browser_store import BrowserStore
    from charlie.data.market import MarketData
    from charlie.handlers import Api
    from charlie.strategies import STRATEGIES, build
    md = MarketData(mode="mock", today=date(2026, 10, 22), cache_dir="/tmp/charlie-test-cache")
    t = build("shares", "KO", md.quote("KO")["price"], md.chain("KO"), 25000, 1)
    assert t.get("explainer_title") == STRATEGIES["shares"]["explainer_title"]

    class Mem(dict):  # the browser's localStorage, in memory
        def getItem(self, k): return self.get(k)
        def setItem(self, k, v): self[k] = v
        def removeItem(self, k): self.pop(k, None)
    meta = Api(BrowserStore(Mem()), md, static=True).meta()
    missing = [k for k, v in meta["strategies"].items() if v.get("explainer_title") != STRATEGIES[k]["explainer_title"]]
    assert missing == [], f"/api/meta strategies without explainer_title: {missing}"


def test_UX27_app_js_never_builds_a_heading_from_the_lower_cased_label():
    from pathlib import Path
    js = (Path(__file__).resolve().parents[1] / "web" / "app.js").read_text()
    assert "What is a ${" not in js, "app.js builds 'What is a <label>?' from the label; use trade.explainer_title"
    assert "explainer_title" in js
