"use strict";
// Static demo: run the charlie package in Pyodide and hand app.js a backend with the same
// routes as the local server. Load this before app.js. Everything is saved in this browser's
// localStorage; the only network calls are Pyodide itself and this site's own files.
//
// First screen (M1.3): prebuilt.json holds the sample person's answers for every risk level,
// made by the same Python at build time (a test proves they match). While the visitor hasn't
// changed anything (none of pre.invalid_if_keys stored), those answers are served instantly,
// before and after the engine is up. app.js calls start() after its first render so Pyodide doesn't compete with it.
// ?pyodide=<base url> overrides where Pyodide loads from (local testing); ?date=YYYY-MM-DD pins the day.
(function () {
  const params = new URLSearchParams(location.search);
  const base = params.get("pyodide") || "https://cdn.jsdelivr.net/pyodide/v0.28.3/full/";
  const SAMPLE_RISK_KEY = "charlie:kv:sample_risk";

  function openStorage() {
    try { const s = window.localStorage; s.setItem("charlie:probe", "1"); s.removeItem("charlie:probe"); return s; }
    catch (_) {  // private mode or blocked storage: keep data for this visit only
      const m = new Map();
      return { getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, String(v)), removeItem: (k) => m.delete(k) };
    }
  }
  function loadScript(src) {
    return new Promise((ok, fail) => {
      const s = document.createElement("script");
      s.src = src; s.onload = ok; s.onerror = () => fail(new Error(`Couldn't load ${src}`));
      document.head.appendChild(s);
    });
  }
  const signal = (ready) => window.dispatchEvent(new CustomEvent("charlie:engine", { detail: { ready } }));

  const storage = openStorage();
  const prebuilt = fetch("prebuilt.json").then((r) => (r.ok ? r.json() : null)).catch(() => null)
    .then((pre) => (pre && (!params.get("date") || params.get("date") === pre.date) ? pre : null));
  let engine = null, booting = null;

  function start() {
    booting ??= (async () => {
      await loadScript(base + "pyodide.js");
      const py = await loadPyodide({ indexURL: base });
      py.unpackArchive(await (await fetch("charlie.zip")).arrayBuffer(), "zip");
      const pre = await prebuilt;
      const browser = py.pyimport("charlie.browser");
      browser.init(storage, params.get("date") || pre?.date || new Date().toLocaleDateString("en-CA"));
      engine = browser;
      signal(true);
      return browser;
    })().catch((e) => {
      booting = null;  // let the next click try again
      window.dispatchEvent(new CustomEvent("charlie:engine", { detail: { ready: true, error: String(e.message || e) } }));
      throw new Error("Charlie's engine couldn't load. Check your connection and try again.");
    });
    return booting;
  }

  function fromPrebuilt(pre, method, path, body) {
    if (!pre || pre.invalid_if_keys.some((k) => storage.getItem(k) !== null)) return null;
    const key = `${method} ${path}`;
    if (key === "POST /api/profile/risk") {  // mirrors Api.set_risk for the sample person
      const n = Math.max(1, Math.min(5, Math.round(Number(body?.risk_level)) || pre.default_risk));
      storage.setItem(SAMPLE_RISK_KEY, String(n));
      return pre.levels[n][key];
    }
    let level = pre.default_risk;
    try { level = JSON.parse(storage.getItem(SAMPLE_RISK_KEY)) ?? level; } catch (_) {}
    if (key === "POST /api/chat") {  // a starter chip as the first question: answered without the engine
      const messages = body?.messages;
      const first = Array.isArray(messages) && messages.length === 1 && messages[0].role === "user";
      return first ? pre.levels[level]?.chat?.[messages[0].content] ?? null : null;
    }
    return pre.common[key] ?? pre.levels[level]?.[key] ?? null;
  }

  window.charlieStatic = {
    start,
    sampleResume: async () => (await prebuilt)?.sample_resume ?? "",
    async request(method, path, body) {
      const hit = fromPrebuilt(await prebuilt, method, path, body);
      if (hit) return { status: 200, body: hit };
      if (!engine) signal(false);
      const browser = await start();
      return JSON.parse(browser.request(method, path, "{}", JSON.stringify(body ?? null)));
    },
  };
})();
