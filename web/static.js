"use strict";
// Static demo: run the charlie package in Pyodide and hand app.js a backend with the same
// routes as the local server. Load this before app.js. Everything is saved in this browser's
// localStorage; the only network calls are Pyodide itself and this site's charlie.zip.
// ?pyodide=<base url> overrides where Pyodide loads from (local testing); ?date=YYYY-MM-DD pins the day.
(function () {
  const params = new URLSearchParams(location.search);
  const base = params.get("pyodide") || "https://cdn.jsdelivr.net/pyodide/v0.28.3/full/";
  const day = params.get("date") || new Date().toLocaleDateString("en-CA");

  function storage() {
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
  const ready = (async () => {
    await loadScript(base + "pyodide.js");
    const py = await loadPyodide({ indexURL: base });
    py.unpackArchive(await (await fetch("charlie.zip")).arrayBuffer(), "zip");
    const browser = py.pyimport("charlie.browser");
    browser.init(storage(), day);
    return browser;
  })();
  window.charlieStatic = {
    ready,
    async request(method, path, body) {
      const browser = await ready;
      return JSON.parse(browser.request(method, path, "{}", JSON.stringify(body ?? null)));
    },
  };
})();
