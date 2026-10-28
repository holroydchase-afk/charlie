import os

import pytest

os.environ["CHARLIE_DATA"] = "mock"
os.environ["CHARLIE_LLM"] = "off"
os.environ["CHARLIE_TODAY"] = "2026-10-22"


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    os.environ["CHARLIE_DB"] = str(tmp_path_factory.mktemp("db") / "t.db")
    os.environ["CHARLIE_CACHE"] = str(tmp_path_factory.mktemp("cache"))
    from fastapi.testclient import TestClient

    import charlie.data.market as market
    market._market = None
    from charlie import server
    from charlie.store import Store
    server.store = Store(os.environ["CHARLIE_DB"])
    return TestClient(server.app, base_url="http://127.0.0.1:8000")


def test_status_and_meta(client):
    s = client.get("/api/status").json()
    assert s["data"]["mode"] == "mock" and s["llm"] is False and "not" in s["disclaimer"]
    m = client.get("/api/meta").json()
    assert set(m["risk_levels"]) == {"1", "2", "3", "4", "5"}


def test_profile_upload_and_ideas(client):
    files = {"resume": ("r.txt", b"Software engineer at Microsoft, Azure, Kubernetes, Python. 2016 - present", "text/plain")}
    r = client.post("/api/profile", files=files, data={"interests": "AI chips, NVDA", "brands": "Costco",
                                                       "holdings": "MSFT 100", "capital": "30000", "risk_level": "2"})
    assert r.status_code == 200, r.text
    p = r.json()["profile"]
    assert p["domains"][0]["key"] == "software_cloud" and p["holdings"] == {"MSFT": 100}
    ideas = client.get("/api/ideas?count=2").json()
    assert 1 <= len(ideas["ideas"]) <= 2 and ideas["risk_level"] == 2


def test_risk_slider_and_paper_gate(client):
    assert client.post("/api/profile/risk", json={"risk_level": 3}).json()["risk_level"] == 3
    t = client.get("/api/ticker/KO?risk=3").json()["trades"]
    spread = next(x for x in t if x["strategy"] == "bull_put_spread")
    opened = client.post("/api/paper", json={"trade": spread}).json()
    assert opened["status"] == "open" and opened["entry_value"] < 0  # credit received
    closed = client.post(f"/api/paper/{opened['id']}/close").json()
    assert closed["status"] == "closed"
    summary = client.get("/api/paper").json()
    assert summary["positions"][0]["status"] == "closed"
    # Lower the slider: opening a spread is now refused
    client.post("/api/profile/risk", json={"risk_level": 2})
    assert client.post("/api/paper", json={"trade": spread}).status_code == 403


def test_screen_save_and_list(client):
    r = client.post("/api/screen", json={"criteria": {"scope": "all", "max_price": 120}, "save": True, "name": "cheap"}).json()
    assert r["saved"]["name"] == "cheap"
    assert all(x["price"] <= 120 for x in r["results"])
    assert client.get("/api/screens").json()["screens"][0]["name"] == "cheap"


def test_chat_offline(client):
    r = client.post("/api/chat", json={"messages": [{"role": "user", "content": "Tell me about Visa"}]}).json()
    assert r["mode"] == "rules" and "Visa" in r["reply"] and r["cards"]
    r = client.post("/api/chat", json={"messages": [{"role": "user", "content": "what are today's ideas"}]}).json()
    assert "ideas" in r["reply"].lower()
    assert client.post("/api/chat", json={"messages": []}).status_code == 400


def test_unknown_ticker_404(client):
    assert client.get("/api/ticker/ZZZZ").status_code == 404


def test_index_served(client):
    r = client.get("/")
    assert r.status_code == 200 and "Charlie" in r.text
