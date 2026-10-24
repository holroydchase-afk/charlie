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
    html = (WEB / "index.html").read_text()
    banner = re.search(r'<div id="demo-banner"[^>]*>.*?</div>', html, re.S).group(0)
    assert "static-only" in banner and "hidden" in banner
    assert "sample" in banner.lower() and "stays in this browser" in banner
    assert 'href="https://chaseholroyd.com/"' in banner and 'id="reset-demo"' in banner
    js = (WEB / "app.js").read_text()
    assert ".static-only" in js and "reset-demo" in js


def test_chat_panel_shows_the_disclaimer_in_markup():
    html = (WEB / "index.html").read_text()
    chat = html[html.index('id="tab-chat"'):]
    chat = chat[:chat.index("</section>")]
    assert NFA in chat


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
