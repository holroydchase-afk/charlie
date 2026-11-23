"""CHL-DS-1 to DS-23: Charlie on the studio design core (hearth main 711fdb8, Paper theme).

Spec: the CHL-DS acceptance criteria (one PR, branch claude/project-thread-i8m939). Written first, red,
by qa-tdd on Nov 21 2026, before any screen change. These checks need no browser; what a visitor sees
(sizes, targets, focus, the Appearance control) is in tests/e2e/test_design_system_e2e.py.

Source of truth: STUDIO-CORE.md and tokens.json (Paper). The values below are copied from tokens.json
`themes.paper` so this file doesn't depend on the scratchpad copy; the high-contrast (HC) set is
recomputed here with a Python port of Hearth's app/src/ui/theme.ts (mix, nudge, edge, highContrast).
"""
from __future__ import annotations

import ast
import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

import pytest

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
THEMES = WEB / "themes.css"
STYLES = WEB / "styles.css"
FONT_FAMILY = '"Atkinson Hyperlegible Next", system-ui, sans-serif'
WEIGHTS = (400, 500, 600)
FONT_FILE = "atkinson-hyperlegible-next-latin-{w}-normal.woff2"

# tokens.json themes.paper, hearth main 711fdb8 (copied verbatim).
PAPER = {
    "light": {
        "safe": "#1C6E31", "danger": "#B3261E", "dangerText": "#B3261E", "onDanger": "#FFFFFF",
        "scrim": "rgba(0,0,0,0.4)", "bg": "#F7F7F4", "surface": "#FFFFFF", "ink": "#1E1B17", "muted": "#5C564E",
        "line": "#E3DED4", "fill": "#EFECE5", "accent": "#AD371D", "safeSoft": "#E8EDE6", "accentInk": "#FFFFFF",
        "accentSoft": "#F2EAE5", "tabLine": "#928E87",
    },
    "dark": {
        "safe": "#7DD394", "danger": "#F2B8B5", "dangerText": "#FF453A", "onDanger": "#601410",
        "scrim": "rgba(0,0,0,0.6)", "bg": "#131210", "surface": "#1C1A17", "ink": "#F1EEE8", "muted": "#B2ACA2",
        "line": "#2E2B27", "fill": "#24221E", "accent": "#FF8A65", "safeSoft": "#263528", "accentInk": "#000000",
        "accentSoft": "#3D281F", "tabLine": "#696661",
    },
}
# DS-2: what Hearth's algorithm gives for Paper under "increase contrast" (the spec's expected values).
HC_EXPECTED = {
    "light": {"muted": "#59534B", "line": "#77736C", "tabLine": "#77736C", "accent": "#822F1B", "accentSoft": "#EFE9E5"},
    "dark": {"muted": "#B2ACA2", "line": "#86837E", "tabLine": "#86837E", "accent": "#FBA88C", "accentSoft": "#3D2D26"},
}
TOKENS = {  # studio token -> CSS custom property (kebab-case)
    "bg": "--bg", "surface": "--surface", "ink": "--ink", "muted": "--muted", "line": "--line", "fill": "--fill",
    "accent": "--accent", "accentInk": "--accent-ink", "accentSoft": "--accent-soft", "safe": "--safe",
    "safeSoft": "--safe-soft", "danger": "--danger", "dangerText": "--danger-text", "onDanger": "--on-danger",
    "tabLine": "--tab-line", "scrim": "--scrim",
}
BASE_AND_FIXED = ("bg", "surface", "ink", "muted", "line", "fill", "accent",
                  "accentInk", "safe", "danger", "dangerText", "onDanger", "scrim")
DERIVED = ("accentSoft", "safeSoft", "tabLine")
HC_KEYS = ("muted", "line", "tabLine", "accent", "accentSoft")
FORBIDDEN_VARS = re.compile(r"--(?:warn|shadow)[\w-]*|--sunken\b|--line-strong\b|--good\b|--bad\b")


# ============================================================ a small CSS reader (no dependency)
def _strip_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def parse_css(css: str):
    """Flat list of rules: {"at": [conditions of enclosing @media/@supports], "sel": selector or "@font-face",
    "decls": [(prop, value)], "order": n}. @keyframes bodies are skipped."""
    css = _strip_comments(css)
    rules, i, n = [], 0, len(css)

    def block(i, at):
        while i < n:
            while i < n and css[i] in " \t\r\n;":
                i += 1
            if i >= n:
                return i
            if css[i] == "}":
                return i + 1
            j = css.find("{", i)
            k = css.find("}", i)
            if j == -1 or (k != -1 and k < j):  # stray declarations without a selector
                return k + 1 if k != -1 else n
            head = css[i:j].strip()
            if head.startswith("@media") or head.startswith("@supports"):
                i = block(j + 1, at + [head])
                continue
            # find the matching close brace (a rule body or a nested at-rule we skip)
            depth, m = 1, j + 1
            while m < n and depth:
                depth += {"{": 1, "}": -1}.get(css[m], 0)
                m += 1
            body = css[j + 1:m - 1]
            if not head.startswith("@keyframes"):
                decls = []
                for part in _split_decls(body):
                    if ":" in part:
                        p, v = part.split(":", 1)
                        decls.append((p.strip().lower(), v.strip()))
                rules.append({"at": at, "sel": head, "decls": decls, "order": len(rules)})
            i = m
        return i

    block(0, [])
    return rules


def _split_decls(body: str):
    out, cur, depth, quote = [], "", 0, None
    for ch in body:
        if quote:
            cur += ch
            if ch == quote:
                quote = None
            continue
        if ch in "\"'":
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == ";" and depth == 0:
            out.append(cur.strip())
            cur = ""
            continue
        cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


def _media_matches(cond: str, state: dict) -> bool:
    """Evaluate the @media conditions themes.css may use: prefers-color-scheme and prefers-contrast."""
    cond = re.sub(r"^@media\s+", "", cond).strip()
    for alt in cond.split(","):
        ok = True
        for part in re.split(r"\s+and\s+", alt.strip()):
            part = part.strip()
            if part in ("screen", "all", "only screen"):
                continue
            neg = part.startswith("not ")
            m = re.fullmatch(r"(?:not\s+)?\(\s*(prefers-color-scheme|prefers-contrast)\s*:\s*([\w-]+)\s*\)", part)
            if not m:
                raise AssertionError(f"themes.css uses a media condition this test can't read: {part!r}")
            feat, val = m.groups()
            if feat == "prefers-color-scheme":
                hit = state["scheme"] == val
            else:
                hit = state["more"] if val == "more" else (not state["more"]) if val == "no-preference" else False
            ok = ok and (hit != neg)
        if ok:
            return True
    return False


_SIMPLE = re.compile(r':root|html|:not\(([^()]*)\)|\[data-theme(?:=["\']?([\w-]+)["\']?)?\]')


def _root_selector(sel: str):
    """(specificity, predicate on the data-theme attribute) for a selector that targets <html>, else None."""
    sel = sel.strip()
    pos, spec, preds = 0, [0, 0, 0], []
    while pos < len(sel):
        m = _SIMPLE.match(sel, pos)
        if not m:
            return None
        tok = m.group(0)
        if tok == ":root":
            spec[1] += 1
        elif tok == "html":
            spec[2] += 1
        elif tok.startswith(":not("):
            im = re.fullmatch(r'\[data-theme(?:=["\']?([\w-]+)["\']?)?\]', m.group(1).strip())
            if not im:
                return None
            want = im.group(1)
            spec[1] += 1
            preds.append(lambda t, w=want: not (t is not None and (w is None or t == w)))
        else:
            want = m.group(2)
            spec[1] += 1
            preds.append(lambda t, w=want: t is not None and (w is None or t == w))
        pos = m.end()
    return tuple(spec), (lambda t: all(p(t) for p in preds))


def resolve_root_vars(rules, state: dict) -> dict:
    """Custom properties on <html> in a given state: {"scheme": light|dark, "more": bool, "theme": None|light|dark}."""
    won: dict[str, tuple] = {}
    for r in rules:
        if r["sel"].startswith("@"):
            continue
        if not all(_media_matches(c, state) for c in r["at"] if c.startswith("@media")):
            continue
        best = None
        for s in r["sel"].split(","):
            got = _root_selector(s)
            if got and got[1](state["theme"]):
                best = got[0] if best is None or got[0] > best else best
        if best is None:
            continue
        for p, v in r["decls"]:
            if p.startswith("--"):
                key = (best, r["order"])
                if p not in won or key >= won[p][0]:
                    won[p] = (key, v)
    out = {p: v for p, (_, v) in won.items()}
    for _ in range(5):  # resolve var() chains inside the theme
        out = {p: re.sub(r"var\((--[\w-]+)\)", lambda m: out.get(m.group(1), m.group(0)), v) for p, v in out.items()}
    return out


STATES = [{"scheme": s, "more": more, "theme": t} for s in ("light", "dark") for t in (None, "light", "dark")
          for more in (False, True)]


def _mode(state):
    return state["theme"] or state["scheme"]


def _themes_rules():
    assert THEMES.exists(), "web/themes.css is missing: Charlie's Paper theme (CHL-DS-1)"
    return parse_css(THEMES.read_text())


# ============================================================ Hearth's theme.ts, ported (DS-2, DS-3)
def mix(a: str, b: str, t: float) -> str:
    """theme.ts mix(); Math.round rounds halves up (Python's round() would round them to even)."""
    ch = lambda h, i: int(h[i:i + 2], 16)  # noqa: E731
    return "#" + "".join(format(math.floor(ch(a, i) + (ch(b, i) - ch(a, i)) * t + 0.5), "02x")
                         for i in (1, 3, 5)).upper()


def _lum(h: str) -> float:
    v = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    v = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in v]
    return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]


def contrast(a: str, b: str) -> float:
    hi, lo = sorted([_lum(a), _lum(b)], reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def nudge(frm: str, to: str, against: str, ratio: float, mn: float = 0.0) -> str:
    t = mn
    while t < 1:
        c = mix(frm, to, t)
        if contrast(c, against) >= ratio:
            return c
        t += 0.05
    return to


def edge(line: str, ink: str, surface: str, page: str) -> str:
    for i in range(101):
        m = mix(line, ink, i / 100)
        if contrast(m, surface) >= 3 and contrast(m, page) >= 3:
            return m
    return ink


SOFT = {"light": 0.93, "dark": 0.82}


def derive(base: dict, mode: str) -> dict:
    return {"accentSoft": mix(base["accent"], base["bg"], SOFT[mode]),
            "safeSoft": mix(base["safe"], base["bg"], SOFT[mode]),
            "tabLine": edge(base["line"], base["ink"], base["surface"], base["bg"]),
            "accentInk": "#000000" if mode == "dark" else "#FFFFFF"}


def high_contrast(c: dict, mode: str) -> dict:
    accent = nudge(c["accent"], c["ink"], c["bg"], 0, 0.3)
    t = 0.3
    while contrast(c["accentInk"], accent) < 7 and t < 1:
        accent = mix(c["accent"], c["ink"], t)
        t += 0.05
    line = nudge(c["line"], c["ink"], c["surface"], 4.5)
    return {"muted": nudge(c["muted"], c["ink"], c["bg"], 7), "line": line,
            "tabLine": edge(line, c["ink"], c["surface"], c["bg"]), "accent": accent,
            "accentSoft": mix(accent, c["bg"], SOFT[mode])}


def _hex(v: str) -> str | None:
    v = v.strip()
    m = re.fullmatch(r"#([0-9a-fA-F]{6})", v)
    if m:
        return "#" + m.group(1).upper()
    m = re.fullmatch(r"#([0-9a-fA-F]{3})", v)
    if m:
        return "#" + "".join(c * 2 for c in m.group(1)).upper()
    m = re.fullmatch(r"rgb\(\s*(\d+)[,\s]+(\d+)[,\s]+(\d+)\s*\)", v)
    if m:
        return "#" + "".join(format(int(x), "02X") for x in m.groups())
    return None


def _within1(a: str, b: str) -> bool:
    ha, hb = _hex(a), _hex(b)
    return bool(ha and hb) and all(abs(int(ha[i:i + 2], 16) - int(hb[i:i + 2], 16)) <= 1 for i in (1, 3, 5))


def _theme_values(state) -> dict:
    """Studio token name -> value in that state, from themes.css."""
    got = resolve_root_vars(_themes_rules(), state)
    return {k: got.get(v) for k, v in TOKENS.items()}


# ============================================================ CHL-DS-1 themes.css defines the studio tokens
def test_CHL_DS_1_themes_css_defines_exactly_the_studio_tokens():
    rules = _themes_rules()
    defined = {p for r in rules for p, _ in r["decls"] if p.startswith("--")}
    assert defined == set(TOKENS.values()), (
        f"themes.css custom properties: missing {sorted(set(TOKENS.values()) - defined)}, "
        f"extra {sorted(defined - set(TOKENS.values()))}")
    text = _strip_comments(THEMES.read_text())
    assert re.search(r"@media[^{]*prefers-color-scheme:\s*dark", text), "a prefers-color-scheme: dark block"
    assert re.search(r':root:not\(\[data-theme=["\']?light["\']?\]\)', text), \
        "the OS dark block skips a page set to Light: :root:not([data-theme=light])"
    assert re.search(r'\[data-theme=["\']?dark["\']?\]', text), "a [data-theme=dark] block for the in-app Dark choice"
    assert re.search(r"@media[^{]*prefers-contrast:\s*more", text), "a prefers-contrast: more block (HC)"


@pytest.mark.parametrize("state", STATES, ids=lambda s: f"os-{s['scheme']}-theme-{s['theme']}-{'hc' if s['more'] else 'std'}")
def test_CHL_DS_1_every_state_resolves_all_tokens_and_base_colors_equal_tokens_json(state):
    got = _theme_values(state)
    missing = [k for k, v in got.items() if not v]
    assert missing == [], f"tokens not defined in this state: {missing}"
    mode = _mode(state)
    keys = [k for k in BASE_AND_FIXED if not (state["more"] and k in HC_KEYS)]
    wrong = {k: (got[k], PAPER[mode][k]) for k in keys if got[k].strip() != PAPER[mode][k]}
    assert wrong == {}, f"{mode} values differ from tokens.json themes.paper (byte for byte): {wrong}"


def test_CHL_DS_1_no_old_tokens_anywhere_in_web():
    hits = []
    for f in sorted(WEB.rglob("*")):
        if f.is_file() and f.suffix in (".css", ".js", ".html"):
            for n, line in enumerate(f.read_text().splitlines(), 1):
                for m in FORBIDDEN_VARS.findall(line):
                    hits.append(f"{f.relative_to(ROOT)}:{n} {m}")
    assert hits == [], f"old tokens still used (no studio equivalent): {hits[:20]}"


# ============================================================ CHL-DS-2 derived and HC tokens follow Hearth's algorithm
def test_CHL_DS_2_the_port_reproduces_tokens_json_and_the_specs_hc_values():
    # Guards the port itself: it must give tokens.json's derived values and the spec's HC set exactly.
    for mode in ("light", "dark"):
        base = PAPER[mode]
        d = derive(base, mode)
        assert {k: d[k] for k in DERIVED} == {k: base[k] for k in DERIVED}, mode
        assert high_contrast(base, mode) == HC_EXPECTED[mode], mode


@pytest.mark.parametrize("state", STATES, ids=lambda s: f"os-{s['scheme']}-theme-{s['theme']}-{'hc' if s['more'] else 'std'}")
def test_CHL_DS_2_derived_and_hc_values_in_themes_css_match_the_algorithm(state):
    got = _theme_values(state)
    mode = _mode(state)
    want = {**{k: PAPER[mode][k] for k in DERIVED}, "accentInk": PAPER[mode]["accentInk"]}
    if state["more"]:
        want.update(high_contrast(PAPER[mode], mode))
    off = {k: (got[k], v) for k, v in want.items() if not (got[k] and _within1(got[k], v))}
    assert off == {}, f"{mode}{' HC' if state['more'] else ''}: themes.css vs Hearth's algorithm (±1 per channel): {off}"


# ============================================================ CHL-DS-3 contrast, 4 modes (Hearth's themes.test.ts pairs)
PAIRS = [("ink", "bg", 7), ("muted", "bg", 4.5), ("muted", "fill", 4.5),
         ("accent", "bg", 4.5), ("accent", "fill", 4.5), ("accent", "accentSoft", 4.5), ("accent", "surface", 4.5),
         ("accentInk", "accent", 4.5), ("safe", "bg", 4.5), ("danger", "bg", 4.5),
         ("tabLine", "bg", 3), ("tabLine", "surface", 3)]


@pytest.mark.parametrize("mode,more", [("light", False), ("dark", False), ("light", True), ("dark", True)],
                         ids=["light", "dark", "hc-light", "hc-dark"])
def test_CHL_DS_3_contrast_pairs_pass_in_every_mode(mode, more):
    c = _theme_values({"scheme": mode, "more": more, "theme": None})
    assert all(c.values()), f"tokens missing: {[k for k, v in c.items() if not v]}"
    c = {k: (_hex(v) or v) for k, v in c.items()}
    need = list(PAIRS)
    if mode == "dark":
        need.append(("dangerText", "bg", 4.5))
    if more:
        need += [("muted", "bg", 7), ("accentInk", "accent", 7), ("line", "surface", 4.5)]
    fails = [f"{fg} {c[fg]} on {on} {c[on]}: {contrast(c[fg], c[on]):.2f} < {r}" for fg, on, r in need
             if not contrast(c[fg], c[on]) >= r]
    assert fails == []
    assert c["accentInk"] == ("#000000" if mode == "dark" else "#FFFFFF")


# ============================================================ CHL-DS-4 no color literals in styles.css
NAMED = set("""aliceblue antiquewhite aqua aquamarine azure beige bisque black blanchedalmond blue blueviolet brown
burlywood cadetblue chartreuse chocolate coral cornflowerblue cornsilk crimson cyan darkblue darkcyan darkgoldenrod
darkgray darkgreen darkgrey darkkhaki darkmagenta darkolivegreen darkorange darkorchid darkred darksalmon darkseagreen
darkslateblue darkslategray darkslategrey darkturquoise darkviolet deeppink deepskyblue dimgray dimgrey dodgerblue
firebrick floralwhite forestgreen fuchsia gainsboro ghostwhite gold goldenrod gray green greenyellow grey honeydew
hotpink indianred indigo ivory khaki lavender lavenderblush lawngreen lemonchiffon lightblue lightcoral lightcyan
lightgoldenrodyellow lightgray lightgreen lightgrey lightpink lightsalmon lightseagreen lightskyblue lightslategray
lightslategrey lightsteelblue lightyellow lime limegreen linen magenta maroon mediumaquamarine mediumblue mediumorchid
mediumpurple mediumseagreen mediumslateblue mediumspringgreen mediumturquoise mediumvioletred midnightblue mintcream
mistyrose moccasin navajowhite navy oldlace olive olivedrab orange orangered orchid palegoldenrod palegreen
paleturquoise palevioletred papayawhip peachpuff peru pink plum powderblue purple rebeccapurple red rosybrown
royalblue saddlebrown salmon sandybrown seagreen seashell sienna silver skyblue slateblue slategray slategrey snow
springgreen steelblue tan teal thistle tomato turquoise violet wheat white whitesmoke yellow yellowgreen
canvas canvastext buttonface buttontext field fieldtext highlight highlighttext graytext linktext""".split())
COLOR_PROPS = re.compile(r"^(color|background(-color|-image)?|border(-(top|right|bottom|left))?(-color)?|outline(-color)?|"
                         r"fill|stroke|accent-color|caret-color|text-decoration(-color)?|column-rule(-color)?|"
                         r"box-shadow|text-shadow|--[\w-]+)$")


def _values_without_strings(v: str) -> str:
    v = re.sub(r'"[^"]*"|\'[^\']*\'', "", v)
    return re.sub(r"url\([^)]*\)", "", v)


def _css_custom_props(rules):
    props: dict[str, list[str]] = {}
    for r in rules:
        for p, v in r["decls"]:
            if p.startswith("--"):
                props.setdefault(p, []).append(v)
    return props


def test_CHL_DS_4_styles_css_has_no_color_literals():
    rules = parse_css(STYLES.read_text())
    hits = []
    for r in rules:
        for p, v in r["decls"]:
            if r["sel"].startswith("@font-face"):
                continue
            val = _values_without_strings(v)
            if re.search(r"#[0-9a-fA-F]{3,8}\b", val) or re.search(r"\b(rgba?|hsla?|hwb|lab|lch|oklab|oklch|color)\(", val):
                hits.append(f"{r['sel'][:40]} {{ {p}: {v} }}")
                continue
            if COLOR_PROPS.match(p):
                words = re.findall(r"(?<![\w-])([a-zA-Z]+)(?![\w-])", re.sub(r"var\([^)]*\)", "", val))
                bad = [w for w in words if w.lower() in NAMED]
                if bad:
                    hits.append(f"{r['sel'][:40]} {{ {p}: {v} }} names {bad}")
    assert hits == [], f"color literals in styles.css (every color must be a themes.css var): {hits[:20]}"


def test_CHL_DS_4_every_color_var_in_styles_css_comes_from_themes_css():
    theme_tokens = set(TOKENS.values())
    rules = parse_css(STYLES.read_text())
    local = _css_custom_props(rules)
    fallback_hooks = set(re.findall(r"var\((--[\w-]+)\s*,", _strip_comments(STYLES.read_text())))

    def ok(name, seen=()):
        if name in theme_tokens:
            return True
        if name in seen:
            return False
        if name in local:
            return all(all(ok(n, seen + (name,)) for n in re.findall(r"var\((--[\w-]+)", v)) and
                       re.findall(r"var\((--[\w-]+)", v) for v in local[name])
        return name in fallback_hooks  # an outside hook (var(--demo-bg, var(--surface))): its fallback is checked too

    bad = []
    for r in rules:
        for p, v in r["decls"]:
            if COLOR_PROPS.match(p) and not p.startswith("--") and p not in ("box-shadow", "text-shadow"):
                for name in re.findall(r"var\((--[\w-]+)", v):
                    if not ok(name):
                        bad.append(f"{r['sel'][:40]} {{ {p}: {v} }} uses {name}")
    assert bad == [], f"colors that don't come from themes.css tokens: {bad[:20]}"


def test_CHL_DS_4_favicon_is_paper_ink_not_the_old_green():
    html = (WEB / "index.html").read_text()
    m = re.search(r'<link[^>]*rel="icon"[^>]*href="([^"]+)"', html)
    assert m, "index.html keeps a favicon"
    svg = unquote(m.group(1))
    assert "1f5f4a" not in svg.lower(), "favicon still uses the old green #1f5f4a"
    fills = [f.upper() for f in re.findall(r'<rect[^>]*fill="(#[0-9a-fA-F]{6})"', svg)]
    assert fills == ["#1E1B17"], f"favicon tile fill should be Paper ink #1E1B17, got {fills}"


def test_CHL_DS_4_app_js_and_static_js_draw_no_color_literals():
    hits = []
    for name in ("app.js", "static.js", "theme-init.js"):
        f = WEB / name
        if not f.exists():
            continue
        for n, line in enumerate(f.read_text().splitlines(), 1):
            if re.search(r"""(?<![\w#$])#[0-9a-fA-F]{6}\b|\brgba?\(\s*\d|\bhsla?\(\s*\d""", line):
                hits.append(f"{name}:{n}: {line.strip()[:80]}")
    assert hits == [], hits


# ============================================================ CHL-DS-5 the font, self-hosted
def _all_rules():
    rules = parse_css(STYLES.read_text())
    if THEMES.exists():
        rules += parse_css(THEMES.read_text())
    return rules


def test_CHL_DS_5_one_font_face_per_weight_self_hosted_with_swap():
    faces = [dict(r["decls"]) for r in _all_rules() if r["sel"] == "@font-face"]
    by_weight = {}
    for f in faces:
        assert f.get("font-family", "").strip("\"' ") == "Atkinson Hyperlegible Next", f
        by_weight.setdefault(f.get("font-weight", "").strip(), []).append(f)
    assert sorted(by_weight) == ["400", "500", "600"], f"@font-face weights: {sorted(by_weight)} (want 400, 500, 600)"
    for w, fs in by_weight.items():
        assert len(fs) == 1, f"{len(fs)} @font-face rules for weight {w}"
        f = fs[0]
        src = f.get("src", "")
        url = re.fullmatch(r"""url\(\s*["']?([^"')]+)["']?\s*\)\s+format\(\s*["']woff2["']\s*\)""", src.strip())
        assert url, f"weight {w}: src must be one url(fonts/....woff2) format(\"woff2\"), got {src!r}"
        assert url.group(1) == "fonts/" + FONT_FILE.format(w=w), f"weight {w}: relative url, got {url.group(1)!r}"
        assert f.get("font-display") == "swap", f"weight {w}: font-display: swap"
        assert f.get("font-style", "normal") == "normal"


def test_CHL_DS_5_font_files_and_licence_ship_in_web_fonts():
    for w in WEIGHTS:
        p = WEB / "fonts" / FONT_FILE.format(w=w)
        assert p.is_file(), f"missing {p.relative_to(ROOT)}"
        assert p.read_bytes()[:4] == b"wOF2", f"{p.name} is not a woff2 file"
    lic = WEB / "fonts" / "OFL-LICENSE"
    assert lic.is_file(), "web/fonts/OFL-LICENSE (no suffix, so check_site doesn't scan its URL)"
    assert "SIL OPEN FONT LICENSE" in lic.read_text().upper()
    assert sorted(p.name for p in (WEB / "fonts").iterdir()) == sorted(
        [FONT_FILE.format(w=w) for w in WEIGHTS] + ["OFL-LICENSE"]), "web/fonts holds only the 3 weights and the licence"


def _body_family():
    for r in parse_css(STYLES.read_text()):
        if r["at"] or r["sel"].strip() != "body":
            continue
        d = dict(r["decls"])
        if "font-family" in d:
            return d["font-family"]
        if "font" in d:
            m = re.match(r"^.*?\S+(?:/\S+)?\s+((?:\"[^\"]+\"|[\w-]+)(?:\s*,\s*(?:\"[^\"]+\"|[\w-]+))*)$", d["font"])
            return m.group(1) if m else d["font"]
    return None


def test_CHL_DS_5_body_font_family_is_atkinson_with_the_studio_fallbacks():
    fam = _body_family()
    assert fam is not None, "styles.css sets the body font"
    assert re.sub(r"\s*,\s*", ", ", fam.strip()) == FONT_FAMILY, f"body font-family {fam!r}, want {FONT_FAMILY!r}"
    other = [f"{r['sel'][:30]}: {v}" for r in parse_css(STYLES.read_text()) for p, v in r["decls"]
             if p == "font-family" and v.strip() not in ("inherit", FONT_FAMILY) and r["sel"] != "@font-face"]
    assert other == [], f"other font families in styles.css (one family, no monospace): {other}"


# ============================================================ CHL-DS-7/8/9 type, statically (the e2e measures it)
TYPE_REM = {"1.0625rem": 17, "1.375rem": 22, "1.75rem": 28, "2.125rem": 34}


def _resolve(value: str, props: dict[str, list[str]], depth=0) -> list[str]:
    """Every value a var() chain can take (styles.css may redefine a var in media queries)."""
    m = re.fullmatch(r"\s*var\((--[\w-]+)(?:\s*,\s*(.*))?\)\s*", value)
    if not m or depth > 6:
        return [value.strip()]
    vals = props.get(m.group(1)) or ([m.group(2)] if m.group(2) else [])
    if not vals:
        return [f"undefined {m.group(1)}"]
    return [x for v in vals for x in _resolve(v, props, depth + 1)]


def _font_sizes(rules):
    for r in rules:
        for p, v in r["decls"]:
            if p == "font-size":
                yield r, v
            elif p == "font" and v.strip() not in ("inherit", "unset", "initial"):
                m = re.match(r"^(?:(?:normal|italic|oblique|small-caps|bold|bolder|lighter|\d{3})\s+)*"
                             r"(var\([^)]*\)|[\d.]+[a-z%]*)(?:\s*/\s*\S+)?\s+", v.strip())
                yield r, (m.group(1) if m else v)


def test_CHL_DS_7_DS_9_every_font_size_is_a_studio_size_in_rem():
    rules = parse_css(STYLES.read_text())
    props = _css_custom_props(rules)
    bad = []
    for r, v in _font_sizes(rules):
        if r["sel"] == "@font-face":
            continue
        for x in _resolve(v, props):
            if x not in TYPE_REM and x not in ("inherit", "1em", "100%"):
                bad.append(f"{r['sel'][:40]} font-size {v} -> {x}")
    assert bad == [], ("font sizes must be 17/22/28/34 in rem (1.0625rem, 1.375rem, 1.75rem, 2.125rem), "
                       f"so they grow with the browser's text size: {bad[:20]}")


def test_CHL_DS_9_no_line_height_in_px():
    rules = parse_css(STYLES.read_text())
    props = _css_custom_props(rules)
    bad = [f"{r['sel'][:40]} line-height {v}" for r in rules for p, v in r["decls"] if p == "line-height"
           for x in _resolve(v, props) if re.search(r"\d(px)\b", x)]
    assert bad == [], f"px line-heights don't grow with the text size: {bad}"


def test_CHL_DS_8_weights_styles_case_and_spacing_in_css():
    bad = []
    for r in parse_css(STYLES.read_text()):
        for p, v in r["decls"]:
            v = v.strip()
            if p == "font-weight" and v not in ("400", "500", "600", "normal", "inherit"):
                bad.append(f"{r['sel'][:40]} font-weight: {v}")
            if p == "font-style" and v not in ("normal", "inherit"):
                bad.append(f"{r['sel'][:40]} font-style: {v}")
            if p == "text-transform" and v not in ("none", "inherit"):
                bad.append(f"{r['sel'][:40]} text-transform: {v}")
            if p == "letter-spacing" and v not in ("normal", "0", "inherit"):
                bad.append(f"{r['sel'][:40]} letter-spacing: {v}")
            if p == "font" and re.search(r"\b(bold|bolder|700|800|900|italic|oblique)\b", v):
                bad.append(f"{r['sel'][:40]} font: {v}")
    assert bad == [], f"weights 400/500/600 only, no italics, caps or letter-spacing: {bad}"


# ============================================================ CHL-DS-10 space and corners
SPACE_PX = {0, 4, 8, 12, 16, 24, 32}
SPACE_REM = {0.25: 4, 0.5: 8, 0.75: 12, 1.0: 16, 1.5: 24, 2.0: 32}
SPACE_PROPS = re.compile(r"^(padding|margin)(-(top|right|bottom|left|inline|block)(-(start|end))?)?$|"
                         r"^(gap|row-gap|column-gap|inset|top|bottom)$")
RADIUS_PROPS = re.compile(r"^border(-(top|bottom|start|end)-(left|right|start|end))?-radius$")
SR_ONLY = (".sr-only",)  # the standard visually-hidden pattern (1px box, -1px margin) is not layout spacing


def _lengths_ok(value: str, props, allowed_px, allow_zero=True):
    """Problems in one spacing or radius value; vars are resolved, calc() only checks its own literals."""
    problems = []
    val = re.sub(r"env\([^)]*\)", "", value)
    calcs = re.findall(r"calc\(([^()]*(?:\([^()]*\)[^()]*)*)\)", val)
    val = re.sub(r"calc\(([^()]*(?:\([^()]*\)[^()]*)*)\)", " ", val)
    for c in calcs:
        for num, unit in re.findall(r"(-?[\d.]+)(px|rem)\b", c):
            px = float(num) * (16 if unit == "rem" else 1)
            if abs(px) not in allowed_px:
                problems.append(f"{num}{unit} in calc()")
    val = re.sub(r"\b(max|min|clamp)\(", " ", val).replace(")", " ").replace(",", " ")
    for tok in val.split():
        if tok.startswith("var("):
            tok = tok + ")"
            for x in _resolve(tok, props):
                problems += [f"{tok} -> {p}" for p in _lengths_ok(x, props, allowed_px, allow_zero)]
            continue
        if tok.startswith("var(") or tok in ("auto", "inherit", "initial", "unset", "!important"):
            continue
        m = re.fullmatch(r"(-?[\d.]+)(px|rem|em|%|vh|vw|dvh|svh|ch)?", tok)
        if not m:
            continue
        num, unit = float(m.group(1)), m.group(2)
        if num == 0:
            if not allow_zero:
                problems.append(tok)
            continue
        if unit in ("%", "vh", "vw", "dvh", "svh"):
            continue
        if unit == "px" and num in allowed_px:
            continue
        if unit == "rem" and num * 16 in allowed_px:
            continue
        problems.append(tok)
    return problems


def test_CHL_DS_10_spacing_is_on_the_studio_scale():
    rules = parse_css(STYLES.read_text())
    props = _css_custom_props(rules)
    # var(--x) tokens inside a value need their closing paren back after the split; handle "var(--s4)" directly
    bad = []
    for r in rules:
        if r["sel"].strip() in SR_ONLY or r["sel"] == "@font-face":
            continue
        for p, v in r["decls"]:
            if SPACE_PROPS.match(p):
                vv = re.sub(r"var\((--[\w-]+)\)", r"var(\1", v)
                probs = _lengths_ok(vv, props, SPACE_PX)
                if probs:
                    bad.append(f"{r['sel'][:40]} {{ {p}: {v} }} -> {probs}")
    assert bad == [], f"spacing off the 4/8/12/16/24/32 scale: {bad[:25]}"


def test_CHL_DS_10_corners_are_small_medium_or_pill():
    rules = parse_css(STYLES.read_text())
    props = _css_custom_props(rules)
    bad = []
    for r in rules:
        for p, v in r["decls"]:
            if RADIUS_PROPS.match(p):
                vv = re.sub(r"var\((--[\w-]+)\)", r"var(\1", v).replace("/", " ")
                if "%" in vv:
                    bad.append(f"{r['sel'][:40]} {{ {p}: {v} }}")
                    continue
                probs = _lengths_ok(vv, props, {4, 12, 999})
                if probs:
                    bad.append(f"{r['sel'][:40]} {{ {p}: {v} }} -> {probs}")
    assert bad == [], f"corners must be 4px, 12px or 999px: {bad[:25]}"


def test_CHL_DS_11_no_shadows_in_css():
    bad = [f"{r['sel'][:40]} {{ {p}: {v} }}" for r in _all_rules() for p, v in r["decls"]
           if p in ("box-shadow", "text-shadow", "filter") and v.strip() not in ("none", "inherit")
           and (p != "filter" or "drop-shadow" in v)]
    assert bad == [], f"no shadows (Charlie isn't image-led): {bad}"


# ============================================================ CHL-DS-15 button kinds, in the markup
KINDS = {"btn-primary", "btn-tinted", "btn-secondary", "btn-quiet", "btn-danger"}
NOT_BUTTON_KINDS = ("role=\"tab\"", "row-card", "demo-bar__toggle")  # tabs and whole-row targets (section 6 rows)


def _button_tags():
    html = (WEB / "index.html").read_text()
    js = (WEB / "app.js").read_text()
    for src, name in ((html, "index.html"), (js, "app.js")):
        for m in re.finditer(r"<button\b[^>]*>", src):
            yield name, m.group(0)


def test_CHL_DS_15_every_button_in_the_markup_has_exactly_one_kind():
    bad = []
    for name, tag in _button_tags():
        if any(x in tag for x in NOT_BUTTON_KINDS):
            continue
        cls = re.search(r'class="([^"]*)"', tag)
        if cls and "${" in cls.group(1) and not KINDS & set(cls.group(1).split()):
            bad.append(f"{name}: {tag[:90]} (dynamic class without a fixed kind)")
            continue
        kinds = KINDS & set(cls.group(1).split()) if cls else set()
        if len(kinds) != 1:
            bad.append(f"{name}: {tag[:90]} has kinds {sorted(kinds)}")
    assert bad == [], f"every <button> needs exactly one of {sorted(KINDS)}: {bad[:25]}"


def test_CHL_DS_15_deliberate_moments_use_primary_and_cannot_undo_uses_danger():
    html = (WEB / "index.html").read_text()

    def cls(sel_re):
        m = re.search(sel_re, html)
        assert m, sel_re
        return set(re.search(r'class="([^"]*)"', m.group(0)).group(1).split())
    assert "btn-primary" in cls(r'<button\b[^>]*id="ack-btn"[^>]*>'), "ack 'Got it' is the primary button"
    assert "btn-danger" in cls(r'<button\b[^>]*class="[^"]*demo-bar__yes[^"]*"[^>]*>'), "demo reset confirm is danger"
    # Fix round 1 (CHL-DS-R2, section 6: danger is for cannot-undo): the trigger is quiet in --danger-text and
    # opens an inline confirm; the confirm's "Delete my data" is the danger button.
    assert cls(r'<button\b[^>]*id="delete-profile"[^>]*>') == {"btn-quiet", "danger-text"}, "the delete trigger is quiet, danger-text"
    yes = re.search(r'<button\b[^>]*id="delete-yes"[^>]*>([^<]*)</button>', html)
    assert yes and yes.group(1).strip() == "Delete my data", "the inline confirm has a 'Delete my data' button"
    assert "btn-danger" in cls(r'<button\b[^>]*id="delete-yes"[^>]*>'), "the confirm's Delete my data is danger"
    stray = [f"{n}: {t[:90]}" for n, t in _button_tags() if "danger-text" in t and 'id="delete-profile"' not in t]
    assert stray == [], f"only the delete trigger may be a danger-text quiet button: {stray}"
    assert any(r["sel"].strip() == ".btn-quiet.danger-text" and ("color", "var(--danger-text)") in r["decls"] for r in _all_rules()), \
        ".btn-quiet.danger-text uses var(--danger-text)"


# ============================================================ CHL-DS-16/18 theme-init.js, index.html wiring
def test_CHL_DS_16_focus_ring_is_2px_solid_accent_and_never_box_shadow():
    rules = _all_rules()
    focus = [r for r in rules if ":focus-visible" in r["sel"]]
    assert focus, "a :focus-visible rule"
    for r in focus:
        d = dict(r["decls"])
        if "outline" in d:
            assert re.fullmatch(r"2px solid var\(--accent\)", d["outline"].strip()), f"{r['sel']}: outline {d['outline']}"
        assert "box-shadow" not in d, f"{r['sel']}: the ring is an outline that follows the corner, not a shadow"
        for p in ("border", "border-width", "padding", "margin", "width", "height"):
            assert p not in d, f"{r['sel']}: focusing must not change {p} (layout shift)"


def test_CHL_DS_18_index_html_loads_themes_and_theme_init_in_head_before_styles():
    html = (WEB / "index.html").read_text()
    head = html.split("</head>")[0]
    assert '<link rel="stylesheet" href="/static/themes.css">' in head, "themes.css linked in <head>"
    assert head.index("/static/themes.css") < head.index("/static/styles.css"), "themes.css before styles.css"
    tag = re.search(r'<script\b[^>]*src="/static/theme-init\.js"[^>]*></script>', head)
    assert tag, "theme-init.js loads from <head> (data-theme is set before first paint)"
    assert not re.search(r"\b(defer|async|type=\"module\")", tag.group(0)), "theme-init.js must run before first paint"
    assert not re.search(r"<script(?![^>]*\bsrc=)[^>]*>", html), "no inline script (CSP script-src 'self')"


THEME_INIT_HARNESS = r"""
const fs = require('fs'), vm = require('vm');
const src = fs.readFileSync(process.argv[2], 'utf8');
const cases = JSON.parse(process.argv[3]);
const out = [];
for (const c of cases) {
  const attrs = {};
  const el = {
    setAttribute: (k, v) => { attrs[k] = String(v); }, removeAttribute: (k) => { delete attrs[k]; },
    getAttribute: (k) => (k in attrs ? attrs[k] : null), hasAttribute: (k) => k in attrs,
  };
  el.dataset = new Proxy({}, {
    set: (_, k, v) => { attrs['data-' + k] = String(v); return true; },
    get: (_, k) => attrs['data-' + k], deleteProperty: (_, k) => { delete attrs['data-' + k]; return true; },
  });
  const store = c.throws ? null : { getItem: (k) => (k in c.ls ? c.ls[k] : null), setItem() {}, removeItem() {} };
  const sandbox = { document: { documentElement: el }, matchMedia: () => ({ matches: false }) };
  Object.defineProperty(sandbox, 'localStorage', { get() { if (!store) throw new Error('SecurityError'); return store; } });
  sandbox.window = sandbox; sandbox.self = sandbox; sandbox.globalThis = sandbox;
  let error = null;
  try { vm.runInNewContext(src, sandbox); } catch (e) { error = String(e); }
  out.push({ theme: attrs['data-theme'] ?? null, error });
}
console.log(JSON.stringify(out));
"""


@pytest.mark.skipif(not shutil.which("node"), reason="needs node to run web/theme-init.js")
def test_CHL_DS_18_theme_init_sets_data_theme_only_for_light_or_dark(tmp_path):
    f = WEB / "theme-init.js"
    assert f.is_file(), "web/theme-init.js sets data-theme before first paint (CSP forbids inline script)"
    key = "charlie-appearance"
    cases = [{"ls": {key: "light"}}, {"ls": {key: "dark"}}, {"ls": {key: "auto"}}, {"ls": {}},
             {"ls": {key: "purple"}}, {"ls": {key: ""}}, {"ls": {"charlie:appearance": "dark"}}, {"ls": {}, "throws": True}]
    harness = tmp_path / "harness.js"
    harness.write_text(THEME_INIT_HARNESS)
    r = subprocess.run(["node", str(harness), str(f), json.dumps(cases)], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    got = json.loads(r.stdout)
    assert [g["theme"] for g in got] == ["light", "dark", None, None, None, None, None, None], got
    assert [g["error"] for g in got] == [None] * len(cases), "theme-init.js must never throw (blocked storage too)"


def test_CHL_DS_18_appearance_is_stored_outside_the_reset_prefix():
    js = (WEB / "app.js").read_text()
    assert '"charlie-appearance"' in js or "'charlie-appearance'" in js, "app.js stores the choice in charlie-appearance"
    assert "charlie:appearance" not in js, "not under the charlie: prefix (Reset demo would wipe it)"


# ============================================================ CHL-DS-20/21 the demo build
def _build_demo():
    sys.path.insert(0, str(ROOT / "tools"))
    try:
        import build_demo
    finally:
        sys.path.pop(0)
    return build_demo


@pytest.fixture
def fake_pyodide(tmp_path):
    d = tmp_path / "pyodide-pkg"
    d.mkdir()
    for name in _build_demo().PYODIDE_FILES:
        (d / name).write_text(f"// {name}\n")
    return d


def _check(site, *flags):
    return subprocess.run([sys.executable, str(ROOT / "tools" / "check_site.py"), str(site), *flags],
                          capture_output=True, text=True)


def test_CHL_DS_20_demo_build_ships_themes_theme_init_and_fonts(tmp_path, fake_pyodide):
    out = _build_demo().build(tmp_path / "site", day="2026-10-22", pyodide_dir=fake_pyodide)
    for name in ("themes.css", "theme-init.js"):
        assert (out / name).is_file(), f"site/{name} missing"
        assert (out / name).read_bytes() == (WEB / name).read_bytes()
    fonts = sorted(p.name for p in (out / "fonts").iterdir()) if (out / "fonts").is_dir() else []
    assert fonts == sorted([FONT_FILE.format(w=w) for w in WEIGHTS] + ["OFL-LICENSE"]), fonts
    html = (out / "index.html").read_text()
    assert '<link rel="stylesheet" href="themes.css">' in html and 'src="theme-init.js"' in html, "linked relative"
    assert "/static/" not in html
    r = _check(out, "--no-cdn")
    assert r.returncode == 0, r.stdout


def test_CHL_DS_20_cdn_build_passes_check_site(tmp_path):
    out = _build_demo().build(tmp_path / "site", day="2026-10-22")
    assert (out / "themes.css").is_file() and (out / "fonts").is_dir()
    r = _check(out)
    assert r.returncode == 0, r.stdout


CSP_SELF = ("default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; connect-src 'self'; img-src 'self' data:; "
            "style-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'")
CSP_CDN = ("default-src 'self'; script-src 'self' 'wasm-unsafe-eval' https://cdn.jsdelivr.net; "
           "connect-src 'self' https://cdn.jsdelivr.net; img-src 'self' data:; style-src 'self'; object-src 'none'; "
           "base-uri 'none'; form-action 'self'")
PAGE_CSP = ("default-src 'self'; script-src 'self'; connect-src 'self'; img-src 'self' data:; style-src 'self'; "
            "object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")


def test_CHL_DS_21_csp_strings_are_unchanged():
    bd = _build_demo()
    assert bd.csp(cdn=False) == CSP_SELF
    assert bd.csp(cdn=True) == CSP_CDN
    from charlie import server
    assert server.PAGE_CSP == PAGE_CSP


def test_CHL_DS_21_no_new_host_anywhere():
    sys.path.insert(0, str(ROOT / "tools"))
    try:
        import check_site
    finally:
        sys.path.pop(0)
    assert check_site.ALLOWED == {"cdn.jsdelivr.net", "chaseholroyd.com", "www.w3.org"}
    hosts = set()
    for f in sorted(WEB.rglob("*")):
        if f.is_file() and f.suffix in (".css", ".js", ".html"):
            hosts |= {h.lower() for h in re.findall(r"https?://([A-Za-z0-9.-]+)", f.read_text())}
    assert hosts <= {"cdn.jsdelivr.net", "chaseholroyd.com", "www.w3.org", "github.com"}, hosts
    css = THEMES.read_text() if THEMES.exists() else ""
    assert not re.search(r"@import|fonts\.googleapis|fonts\.gstatic", css + STYLES.read_text())


# ============================================================ CHL-DS-22 the local server serves the new files
@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from charlie import server
    return TestClient(server.app, base_url="http://127.0.0.1:8000")


def test_CHL_DS_22_local_server_serves_themes_theme_init_and_fonts(client):
    for path in ("/static/themes.css", "/static/theme-init.js"):
        r = client.get(path)
        assert r.status_code == 200, f"{path}: {r.status_code}"
    for w in WEIGHTS:
        path = "/static/fonts/" + FONT_FILE.format(w=w)
        r = client.get(path)
        assert r.status_code == 200, f"{path}: {r.status_code}"
        assert r.headers["content-type"].split(";")[0] == "font/woff2", r.headers["content-type"]
    page = client.get("/").text
    assert "/static/themes.css" in page and "/static/theme-init.js" in page


# ============================================================ CHL-DS-23 the disclaimer tests are untouched
# Each test that checks "Not financial advice. Paper trading only." and a hash of its disclaimer lines, taken
# Nov 21 before the restyle. A failure here means a disclaimer test was deleted, skipped or its check changed.
NFA_TESTS = {
    "tests/e2e/test_demo_e2e.py::test_every_idea_card_shows_the_disclaimer": "77ea45acaa49b983",
    # Re-pinned Nov 22 after Chase's NAV-13 call (drop Chat's page paragraph), at least as strict: was 5348b9ab6291120b.
    "tests/e2e/test_demo_e2e.py::test_chat_panel_and_reply_show_the_disclaimer": "1f2e43a299ebe602",
    "tests/e2e/test_demo_e2e.py::test_first_screen_and_chat_starters_work_before_the_engine_loads": "ea2a504a83794e16",
    "tests/e2e/test_demo_verified_e2e.py::test_DEMO_SUBPATH_demo_works_when_served_under_charlie": "8ebfac2f671d5122",
    "tests/e2e/test_demo_verified_e2e.py::test_CHL_R9_screener_results_and_paper_positions_show_the_disclaimer": "e5fa3cdafbd4b583",
    "tests/e2e/test_enhancements_e2e.py::test_TR_UI_track_record_shows_below_the_ideas_with_labels": "8077612d47547afd",
    "tests/e2e/test_ui_polish_e2e.py::test_UX3_UX4_idea_cards_are_short_with_three_hero_metrics": "5c6f5dddc635e5b9",
    "tests/e2e/test_ui_polish_e2e.py::test_UX4_card_details_still_hold_the_plan_and_ticket": "c00632b943c69940",
    "tests/e2e/test_ui_polish_e2e.py::test_UX7_footer_fits_without_a_clipped_line": "c329cac7df4916cb",
    "tests/e2e/test_ui_polish_e2e.py::test_UX11_drawer_is_a_modal_dialog_that_moves_and_returns_focus": "bb984cc3bddb4383",
    "tests/e2e/test_ui_polish_e2e.py::test_UX14_ideas_error_offers_try_again_that_reloads": "0e06b3fc10cfd200",
    "tests/test_browser.py::test_router_ideas_trade_and_paper": "a38774dbdc7ee8b5",
    "tests/test_browser.py::test_static_mode_status_and_rule_based_chat": "b38a6d4669c8352c",
    "tests/test_demo.py::test_summary_carries_disclaimer_and_mock_label": "f792b9abfc18259f",
    "tests/test_enhancements.py::test_TR8_prebuilt_has_the_track_record_for_every_level": "adc7024f60eb0661",
    "tests/test_enhancements.py::test_ALERT7_shares_get_a_breakeven_alert_but_never_a_time_alert": "2e3b381c4dc282be",
    "tests/test_first_screen.py::test_prebuilt_shape": "7112acbfbd312448",
    "tests/test_first_screen.py::test_prebuilt_chat_answers_match_the_engine": "1fa5551803ac913c",
    # Re-pinned Nov 22 after Chase's NAV-13 call (the line on Chat + replies end with it): was 43a2b9ed3f24320b.
    "tests/test_guardrails.py::test_chat_panel_shows_the_disclaimer_in_markup": "3f9c9aff677a71f1",
    "tests/test_harden.py::test_CORE_chat_happy_and_bad": "7fabbd32b6714042",
    "tests/test_privacy.py::test_disclaimer_text": "f242a760404ffca4",
    "tests/test_privacy.py::test_every_rule_based_reply_ends_with_disclaimer": "7c6e46064b00528c",
    "tests/test_privacy.py::test_claude_reply_refusal_and_fallback_end_with_disclaimer": "984f56f1d616a8b5",
    "tests/test_privacy.py::test_every_trade_carries_disclaimer": "248f88af4cb80a6b",
    "tests/test_privacy.py::test_ui_renders_disclaimer_on_every_trade_surface": "101c0a27e7df09ab",
    "tests/test_ux.py::test_CHL_UX45_drawer_sticky_header_carries_the_disclaimer_and_demo_sample_label": "c1b7864d4d5ec9a4",
    "tests/test_ux.py::test_CHL_UX46_static_build_footer_links_back_to_chaseholroyd_com": "ab2e70325c2279ed",
}


def test_CHL_DS_23_disclaimer_tests_are_all_still_there_unskipped_and_unchanged():
    problems = []
    for node, want in NFA_TESTS.items():
        path, name = node.split("::")
        src = (ROOT / path).read_text()
        fn = next((n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == name), None)
        if fn is None:
            problems.append(f"{node}: gone")
            continue
        for d in fn.decorator_list:
            if re.search(r"skip|xfail", ast.unparse(d)):
                problems.append(f"{node}: marked {ast.unparse(d)}")
        body = ast.get_source_segment(src, fn)
        if re.search(r"pytest\.(skip|xfail)\(", body):
            problems.append(f"{node}: skips itself")
        lines = [ln.strip() for ln in body.splitlines() if re.search(r"NFA|nfa|Not financial advice", ln)]
        if hashlib.sha256("\n".join(lines).encode()).hexdigest()[:16] != want:
            problems.append(f"{node}: its disclaimer check changed")
    assert problems == []
    # Chase's call, Nov 22 (decision card, NAV-13 yes): Chat's page-level paragraph goes. Old pin:
    # html.count(NFA) >= 3 ("footer, drawer and chat"). New pin counts each required static copy by location:
    # exactly one in #disclaimer-line (outside every view, with the exact text), exactly one in the drawer, none
    # page-level in Chat, and no copy anywhere else unaccounted for. Replies and chat trade cards add theirs in code
    # (tests/test_privacy.py, test_guardrails::test_chat_panel_shows_the_disclaimer_in_markup).
    nfa = "Not financial advice. Paper trading only."
    html = (WEB / "index.html").read_text()

    def block(open_re):
        m = re.search(open_re, html)
        assert m, open_re
        tag = re.match(r"<(\w+)", m.group(0)).group(1)
        depth = 0
        for t in re.finditer(rf"<(/?){tag}\b[^>]*>", html[m.start():]):
            depth += -1 if t.group(1) else 1
            if depth == 0:
                return html[m.start(): m.start() + t.end()]
        raise AssertionError(f"unclosed {open_re}")

    line = block(r'<\w+[^>]*\bid="disclaimer-line"[^>]*>')
    drawer = block(r'<\w+[^>]*\bid="drawer"[^>]*>')
    chat = block(r'<section id="tab-chat"[^>]*>')
    chat_page = chat.replace(block(r'<div[^>]*id="chat-log"[^>]*>'), "")
    where = {"#disclaimer-line": line.count(nfa), "#drawer": drawer.count(nfa), "Chat page-level": chat_page.count(nfa)}
    assert where == {"#disclaimer-line": 1, "#drawer": 1, "Chat page-level": 0}, where
    line_text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", line)).strip()
    assert re.sub(r"\s*Read more$", "", line_text) == nfa, f"the line reads {line_text!r}"
    assert html.count(nfa) == sum(where.values()), f"{html.count(nfa)} copies in index.html, {sum(where.values())} accounted for"
