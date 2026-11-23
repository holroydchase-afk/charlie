"""CHL-DARK-1 to DARK-9: dark-mode layering (intake #55, docs/product/SPEC-DARK-LAYERS.md, planning CHL-M1.16).

Written first, red, by qa-tdd on Nov 23 2026, before any change in web/. These checks need no browser; what a
visitor sees (computed backgrounds, control edges, axe) is in tests/e2e/test_dark_layers_e2e.py.
CHL-DARK-10 is manual (screenshots and ux-reviewer); CHL-DARK-11 to 13 wait on Chase's D5 call and are not here.

The rule (spec "Approach"): two Charlie-local tokens in web/themes.css, defined in every state.
- --raised: standard dark = the first mix of --surface toward --ink, in 1% steps, with contrast >= 1.15 against
  --bg. Light, HC light and HC dark = --surface (spec Triage QA-R2: in HC the --line border is the layer cue).
- No var(--tab-line) is left in styles.css; every use moves to --control-edge (Triage QA-R3, CHL-DARK-6b).
- --control-edge: the first mix of --tab-line toward --ink, in 1% steps, with contrast >= 3 against --raised,
  --surface and --bg (HC starts from the HC --tab-line).
The 16 studio tokens keep their tokens.json values. CSS is read with test_design_system.py's parser.
"""
from __future__ import annotations

import re

import pytest

from tests import test_design_system as ds

RAISED, EDGE = "--raised", "--control-edge"
MODES = [("light", False), ("dark", False), ("light", True), ("dark", True)]
MODE_IDS = ["light", "dark", "hc-light", "hc-dark"]
STATE_ID = lambda s: f"os-{s['scheme']}-theme-{s['theme']}-{'hc' if s['more'] else 'std'}"  # noqa: E731


def _studio(mode: str, more: bool) -> dict:
    """The 16 studio tokens as tokens.json (and Hearth's HC algorithm) give them."""
    c = dict(ds.PAPER[mode])
    if more:
        c.update(ds.HC_EXPECTED[mode])
    return c


def want_raised(c: dict, mode: str, more: bool = False) -> str:
    if mode == "light" or more:  # Triage QA-R2: --raised steps up only in standard dark
        return c["surface"]
    for i in range(101):
        m = ds.mix(c["surface"], c["ink"], i / 100)
        if ds.contrast(m, c["bg"]) >= 1.15:
            return m
    return c["ink"]


def want_edge(c: dict, raised: str) -> str:
    for i in range(101):
        m = ds.mix(c["tabLine"], c["ink"], i / 100)
        if all(ds.contrast(m, x) >= 3 for x in (raised, c["surface"], c["bg"])):
            return m
    return c["ink"]


def _vars(state) -> dict:
    return ds.resolve_root_vars(ds._themes_rules(), state)


def _local(state) -> dict:
    got = _vars(state)
    return {"raised": got.get(RAISED), "controlEdge": got.get(EDGE)}


def _styles():
    return ds.parse_css(ds.STYLES.read_text())


def _decl(rules, selector: str, prop: str):
    """The last value of prop on exactly this selector (outside @media), or None."""
    val = None
    for r in rules:
        if r["at"] or r["sel"].startswith("@"):
            continue
        if selector in [s.strip() for s in r["sel"].split(",")]:
            for p, v in r["decls"]:
                if p == prop:
                    val = v
    return val


def _bg_of(rules, selector):
    return _decl(rules, selector, "background") or _decl(rules, selector, "background-color")


def test_CHL_DARK_0_the_port_of_the_rule_gives_the_specs_numbers():
    # Guards the expected values themselves (spec: about #22201C, 1.15:1; edge at 3:1 on the raised card).
    c = _studio("dark", False)
    r = want_raised(c, "dark")
    assert ds.contrast(r, c["bg"]) >= 1.15 and ds.contrast(ds.mix(c["surface"], c["ink"], 0.0), c["bg"]) < 1.15
    assert ds._within1(r, "#22201C") or ds._within1(r, "#22201D"), r
    assert ds.contrast(c["tabLine"], r) < 3, "the spec's premise: --tab-line drops under 3:1 on a raised card"
    assert ds.contrast(want_edge(c, r), r) >= 3
    hc = _studio("dark", True)
    assert want_raised(hc, "dark", True) == hc["surface"], "Triage QA-R2: HC dark --raised = --surface"
    light = _studio("light", False)
    assert want_raised(light, "light") == light["surface"]
    assert want_edge(light, light["surface"]) == light["tabLine"], "light needs no edge change"


# ============================================================ CHL-DARK-1 the two local tokens, derived by rule
@pytest.mark.parametrize("state", ds.STATES, ids=STATE_ID)
def test_CHL_DARK_1_raised_and_control_edge_are_defined_and_follow_the_rule(state):
    got = _local(state)
    missing = [k for k, v in got.items() if not v]
    assert missing == [], f"themes.css does not define {missing} in this state (CHL-DARK-1)"
    mode = ds._mode(state)
    c = _studio(mode, state["more"])
    want = {"raised": want_raised(c, mode, state["more"])}
    want["controlEdge"] = want_edge(c, want["raised"])
    off = {k: (got[k], v) for k, v in want.items() if not ds._within1(got[k], v)}
    assert off == {}, f"{mode}{' HC' if state['more'] else ''}: local tokens vs the spec's rule (±1 per channel): {off}"
    raised = ds._hex(got["raised"])
    if mode == "dark" and not state["more"]:  # the 1.15:1 step is standard dark only (Triage QA-R2)
        assert ds.contrast(raised, c["bg"]) >= 1.15, f"--raised {raised} on --bg {c['bg']}"


# ============================================================ CHL-DARK-2 light and the studio tokens stay put
@pytest.mark.parametrize("state", ds.STATES, ids=STATE_ID)
def test_CHL_DARK_2_studio_tokens_byte_for_byte_and_light_raised_is_surface(state):
    got = ds._theme_values(state)
    mode = ds._mode(state)
    want = _studio(mode, state["more"])
    keys = [k for k in ds.TOKENS if not (state["more"] and k in ds.HC_KEYS)]
    wrong = {k: (got[k], want[k]) for k in keys if (got[k] or "").strip() != want[k]}
    assert wrong == {}, f"a studio token changed value in {mode} (spec: Not doing): {wrong}"
    if mode == "light":
        raised = _local(state)["raised"]
        assert raised and ds._hex(raised) == ds._hex(got["surface"]), \
            f"light --raised must equal --surface (light look unchanged), got {raised}"


def test_CHL_DARK_2_ds1_allowlists_exactly_the_two_local_tokens():
    assert ds.LOCAL_TOKENS == (RAISED, EDGE)
    rules = ds._themes_rules()
    defined = {p for r in rules for p, _ in r["decls"] if p.startswith("--")}
    assert defined == set(ds.TOKENS.values()) | {RAISED, EDGE}, \
        f"themes.css should define the 16 studio tokens plus exactly {RAISED} and {EDGE}: " \
        f"missing {sorted((set(ds.TOKENS.values()) | {RAISED, EDGE}) - defined)}"


# ============================================================ CHL-DARK-3/4/5 the layered surfaces use --raised
@pytest.mark.parametrize("selector", [".card", ".panel", ".modal-inner", ".drawer-inner", ".drawer-head"])
def test_CHL_DARK_3_4_5_layered_surfaces_paint_raised(selector):
    bg = _bg_of(_styles(), selector)
    assert bg and re.search(r"var\(--raised\)", bg), f"{selector} background is {bg!r}, want var(--raised)"


def test_CHL_DARK_4_5_modal_and_drawer_keep_the_scrim_and_trades_sit_on_the_drawer():
    rules = _styles()
    for sel in (".modal", ".drawer"):
        assert re.fullmatch(r"var\(--scrim\)", (_bg_of(rules, sel) or "").strip()), f"{sel} must paint --scrim"
    # UX11: trades in the drawer stay on the drawer surface, not in cards of their own.
    assert (_bg_of(rules, "#drawer-body .card") or "").strip() == "transparent"


# ============================================================ CHL-DARK-6 control edges use --control-edge
CONTROL_SELECTORS = ["input:not([type=checkbox]):not([type=radio]):not([type=range])", "select", "textarea", ".choice"]


@pytest.mark.parametrize("selector", CONTROL_SELECTORS)
def test_CHL_DARK_6_control_borders_use_control_edge(selector):
    border = _decl(_styles(), selector, "border")
    assert border and re.search(r"\b1px\b", border) and "var(--control-edge)" in border, \
        f"{selector} border is {border!r}, want 1px solid var(--control-edge)"


def test_CHL_DARK_6b_styles_css_has_no_tab_line_left():
    # Triage QA-R3: every var(--tab-line) moves to --control-edge (.row-card, .chip-check, .callout, .badge.mock,
    # .payoff .zero, and the controls above), so no edge is left at under 3:1 on a raised layer.
    left = [f"{r['sel'][:40]} {{ {p}: {v} }}" for r in _styles() for p, v in r["decls"] if re.search(r"var\(--tab-line\b", v)]
    assert left == [], f"styles.css still uses var(--tab-line), want var(--control-edge): {left}"


# ============================================================ CHL-DARK-7 the risk slider
def test_CHL_DARK_7_risk_slider_keeps_the_accent_and_its_outline_uses_control_edge():
    rules = _styles()
    assert (_decl(rules, ".risk-control input", "accent-color") or "").strip() == "var(--accent)"
    border = _decl(rules, ".risk-control", "border") or ""
    assert "var(--control-edge)" in border, f".risk-control border is {border!r}, want var(--control-edge)"


@pytest.mark.parametrize("mode,more", MODES, ids=MODE_IDS)
def test_CHL_DARK_7_accent_is_3_to_1_on_raised_and_surface(mode, more):
    v = _vars({"scheme": mode, "more": more, "theme": None})
    assert v.get(RAISED), f"--raised not defined in {mode}{' HC' if more else ''}"
    accent, raised, surface = (ds._hex(v[k]) for k in ("--accent", RAISED, "--surface"))
    assert ds.contrast(accent, raised) >= 3 and ds.contrast(accent, surface) >= 3


# ============================================================ CHL-DARK-8 DS-3 pairs with --raised for --surface
@pytest.mark.parametrize("mode,more", MODES, ids=MODE_IDS)
def test_CHL_DARK_8_ds3_contrast_pairs_still_pass_on_raised(mode, more):
    state = {"scheme": mode, "more": more, "theme": None}
    c = {k: (ds._hex(v) or v) for k, v in ds._theme_values(state).items()}
    loc = _local(state)
    assert all(loc.values()), f"local tokens missing in {mode}{' HC' if more else ''}: {loc}"
    # On a raised layer the surface is --raised and a control's edge is --control-edge (spec: Approach).
    c["surface"] = ds._hex(loc["raised"])
    c["tabLine"] = ds._hex(loc["controlEdge"])
    need = list(ds.PAIRS) + [("ink", "surface", 7), ("muted", "surface", 4.5)]
    if mode == "dark":
        need.append(("dangerText", "bg", 4.5))
    if more:
        need += [("muted", "bg", 7), ("accentInk", "accent", 7), ("line", "surface", 4.5)]
    fails = [f"{fg} {c[fg]} on {on} {c[on]}: {ds.contrast(c[fg], c[on]):.2f} < {r}" for fg, on, r in need
             if not ds.contrast(c[fg], c[on]) >= r]
    assert fails == []


# ============================================================ CHL-DARK-8b HC dark layers keep a 3:1 --line border
@pytest.mark.parametrize("selector", [".card", ".panel", ".modal-inner"])
def test_CHL_DARK_8b_hc_dark_layers_have_a_line_border_3_to_1_on_bg(selector):
    # Triage QA-R2: in HC dark --raised = --surface, so the layer cue is the --line border; it must be there.
    border = _decl(_styles(), selector, "border") or ""
    m = re.search(r"([\d.]+)px", border)
    assert m and float(m.group(1)) >= 1 and "solid" in border and re.search(r"var\(--line\)", border), \
        f"{selector} border is {border!r}, want a 1px or wider solid var(--line)"
    v = _vars({"scheme": "dark", "more": True, "theme": None})
    line, bg = ds._hex(v["--line"]), ds._hex(v["--bg"])
    assert ds.contrast(line, bg) >= 3, f"HC dark --line {line} on --bg {bg}: {ds.contrast(line, bg):.2f}:1"


# ============================================================ CHL-DARK-9 no new color literals; local tokens are colors
def test_CHL_DARK_9_no_color_literal_in_styles_or_scripts():
    ds.test_CHL_DS_4_styles_css_has_no_color_literals()
    ds.test_CHL_DS_4_app_js_and_static_js_draw_no_color_literals()


def test_CHL_DARK_9_styles_css_uses_the_local_tokens_only_where_the_spec_says():
    # The two local tokens are for layers and control edges; they must not leak in as text colors.
    rules = _styles()
    bad = [f"{r['sel'][:40]} {{ {p}: {v} }}" for r in rules for p, v in r["decls"]
           if p == "color" and re.search(r"var\(--(raised|control-edge)\)", v)]
    assert bad == []
    used = {n for r in rules for _, v in r["decls"] for n in re.findall(r"var\((--raised|--control-edge)\)", v)}
    assert used == {RAISED, EDGE}, f"styles.css should use both local tokens, uses {sorted(used)}"


# ============================================================ CHL-DS-4 allows exactly the two local tokens (Triage QA-R1)
def _ds4_with(tmp_path, monkeypatch, extra: str):
    f = tmp_path / "styles.css"
    f.write_text(ds.STYLES.read_text() + "\n" + extra + "\n")
    monkeypatch.setattr(ds, "STYLES", f)
    ds.test_CHL_DS_4_every_color_var_in_styles_css_comes_from_themes_css()


def test_CHL_DS_4_still_fails_a_made_up_var(tmp_path, monkeypatch):
    with pytest.raises(AssertionError, match=r"--foo"):
        _ds4_with(tmp_path, monkeypatch, ".qa-probe { color: var(--foo); }")


@pytest.mark.parametrize("name", [RAISED, EDGE])
def test_CHL_DS_4_accepts_the_two_local_tokens(tmp_path, monkeypatch, name):
    _ds4_with(tmp_path, monkeypatch, f".qa-probe {{ background: var({name}); border-color: var({name}); }}")


def test_CHL_DS_4_does_not_accept_a_third_local_looking_token(tmp_path, monkeypatch):
    with pytest.raises(AssertionError, match=r"--raised-2"):
        _ds4_with(tmp_path, monkeypatch, ".qa-probe { background: var(--raised-2); }")
