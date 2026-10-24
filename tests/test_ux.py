"""Copy the user reads: no stray markdown in plain-text fields."""
from charlie.profile import build_profile


def test_profile_text_has_no_raw_markdown():
    p = build_profile("Nurse at HCA Healthcare", capital=20000)
    for text in (p.summary, p.caution):
        assert "*" not in text and "_" not in text
