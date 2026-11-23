"""M1.4: demo guardrails that don't need a browser (the banner markup and the site check)."""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
NFA = "Not financial advice. Paper trading only."


def _build(tmp_path):
    sys.path.insert(0, str(ROOT / "tools"))
    try:
        import build_demo
    finally:
        sys.path.pop(0)
    return build_demo.build(tmp_path / "site", day="2026-10-22")


def _check(site):
    return subprocess.run([sys.executable, str(ROOT / "tools" / "check_site.py"), str(site)], capture_output=True, text=True)


def test_demo_banner_back_link_and_reset_exist_for_static_mode_only():
    # CHL-DEMO-BAR: the old #demo-banner became the studio demo bar (pm-tools docs/DEMO-BANNER.md).
    html = (WEB / "index.html").read_text()
    m = re.search(r'<section\b[^>]*aria-label="Demo"[^>]*>.*?</section>', html, re.S)
    assert m, "the static demo needs its demo bar"
    banner = m.group(0)
    open_tag = re.match(r"<section\b[^>]*>", banner).group(0)
    assert "static-only" in open_tag and "hidden" in open_tag
    assert "Sample data" in banner and "changes stay in this browser" in banner
    assert "saved only in this browser" in banner
    assert banner.count('href="https://chaseholroyd.com/"') >= 2  # ← Portfolio and the drawer's full way back
    assert re.search(r"<button\b[^>]*>\s*Reset demo\s*</button>", banner)
    js = (WEB / "app.js").read_text()
    assert ".static-only" in js and "Sample data restored." in js


def test_chat_panel_shows_the_disclaimer_in_markup():
    # Re-pinned by qa-tdd, Nov 22, after Chase's NAV-13 call (decision card: drop Chat's page-level paragraph).
    # Old: NFA appears inside the #tab-chat section. New (at least as strict): the Chat view's rendered page shows the
    # exact disclaimer through #disclaimer-line, static markup outside every view (so present on Chat), AND the
    # rule-based reply, from both chat.py and the browser router, ends with it, once.
    from datetime import date

    from charlie import chat
    from charlie.data.market import MarketData
    from charlie.profile import build_profile
    from charlie.store import Store
    from tests.test_browser import FakeStorage
    from charlie.browser_store import BrowserStore
    from charlie.handlers import Api

    html = (WEB / "index.html").read_text()
    def block(start):
        tag = re.match(r"<(\w+)", html[start:]).group(1)
        depth = 0
        for t in re.finditer(rf"<(/?){tag}\b[^>]*>", html[start:]):
            depth += -1 if t.group(1) else 1
            if depth == 0:
                return start, start + t.end()

    m = re.search(r'<\w+[^>]*\bid="disclaimer-line"[^>]*>', html)
    assert m, "no #disclaimer-line in the page"
    for v in re.finditer(r'<section\b[^>]*\bid="tab-\w+"[^>]*>', html):
        a, b = block(v.start())
        assert not a < m.start() < b, f"#disclaimer-line sits inside {v.group(0)}; it must be outside every view"
    a, b = block(m.start())
    line = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html[a:b])).strip()
    assert re.sub(r"\s*Read more$", "", line) == NFA, f"#disclaimer-line reads {line!r}"

    md = MarketData(mode="mock", today=date(2026, 10, 22), cache_dir="/tmp/charlie-test-cache")
    msgs = [{"role": "user", "content": "Tell me about Visa"}]
    out = chat.chat(msgs, md, Store(":memory:"), build_profile(capital=30000))
    assert out["reply"].rstrip("_ \n").endswith(NFA) and out["reply"].count(NFA) == 1, out["reply"][-120:]
    status, out = Api(BrowserStore(FakeStorage()), md, static=True).route("POST", "/api/chat", body={"messages": msgs})
    assert status == 200 and out["reply"].rstrip("_ \n").endswith(NFA) and out["reply"].count(NFA) == 1, out["reply"][-120:]


def test_site_check_passes_on_the_real_build(tmp_path):
    r = _check(_build(tmp_path))
    assert r.returncode == 0, r.stdout + r.stderr


def test_site_check_fails_on_a_key_or_an_unknown_host(tmp_path):
    site = _build(tmp_path)
    js = site / "app.js"
    clean = js.read_text()
    js.write_text(clean + '\nfetch("https://tracker.example.net/collect");\n')
    r = _check(site)
    assert r.returncode == 1 and "tracker.example.net" in r.stdout
    js.write_text(clean + '\nconst k = "sk-ant-' + "a" * 24 + '";\n')
    r = _check(site)
    assert r.returncode == 1 and "key" in r.stdout.lower()


def test_CHL_DEMO_R4_site_check_allows_only_the_repo_link_on_github(tmp_path):
    # The drawer's "Code on GitHub" link is the one github.com URL the build may hold; nothing else there.
    site = _build(tmp_path)
    assert 'href="https://github.com/holroydchase-afk/charlie"' in (site / "index.html").read_text()
    r = _check(site)
    assert r.returncode == 0, r.stdout + r.stderr
    js = site / "app.js"
    clean = js.read_text()
    for bad in ("https://github.com/someone-else/x", "https://github.com/holroydchase-afk/charlie/raw/main/x.js",
                "https://github.com/holroydchase-afk/charlie-evil", "https://github.com/holroydchase-afk/charlie~x",
                "https://github.com/holroydchase-afk/charlie@evil", "https://github.com/holroydchase-afk/charlie:x"):
        js.write_text(clean + f'\nfetch("{bad}");\n')
        r = _check(site)
        assert r.returncode == 1 and "github.com" in r.stdout, bad


def test_site_check_reads_the_python_zip_too(tmp_path):
    import zipfile
    site = _build(tmp_path)
    with zipfile.ZipFile(site / "charlie.zip", "a") as z:
        z.writestr("charlie/leak.py", 'URL = "https://api.anthropic.com/v1/messages"\n')
    r = _check(site)
    assert r.returncode == 1 and "api.anthropic.com" in r.stdout


def test_demo_profile_form_reads_right_without_upload():
    html = (WEB / "index.html").read_text()
    form = html[html.index('id="profile-form"'):]
    form = form[:form.index("</form>")]
    assert re.search(r'class="server-only"[^>]*>…or paste it<', form)
    assert re.search(r'class="static-only hidden"[^>]*>Paste a resume<', form)
    assert re.search(r'<button[^>]*id="use-sample"[^>]*class="[^"]*static-only hidden', form)


def test_prebuilt_carries_the_fictional_sample_resume():
    from charlie import browser, demo
    assert browser.prebuild("2026-10-22")["sample_resume"] == demo.SAMPLE_RESUME


def test_sample_name_reads_naturally_in_the_circle_heading():
    js = (WEB / "app.js").read_text()
    assert "'s circle (sample)" in js
