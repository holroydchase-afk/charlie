"use strict";
// M1.1 spike: load Pyodide, unpack the charlie package, run today's ideas for the sample person.
// ?pyodide=<base url> overrides where Pyodide loads from (local testing); ?date=YYYY-MM-DD pins the day.
const PYODIDE_DEFAULT = "https://cdn.jsdelivr.net/pyodide/v0.28.3/full/";
const params = new URLSearchParams(location.search);
const base = params.get("pyodide") || PYODIDE_DEFAULT;
const day = params.get("date") || new Date().toLocaleDateString("en-CA");
const t0 = performance.now();
const marks = {};
const mark = (k) => { marks[k] = Math.round(performance.now() - t0); };
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const money = (x) => (x == null ? "—" : "$" + Math.round(x).toLocaleString());

function loadScript(src) {
  return new Promise((ok, fail) => {
    const s = document.createElement("script");
    s.src = src; s.onload = ok; s.onerror = () => fail(new Error(`Couldn't load ${src}`));
    document.head.appendChild(s);
  });
}

(async function run() {
  const status = document.getElementById("status");
  try {
    await loadScript(base + "pyodide.js");
    mark("script");
    const py = await loadPyodide({ indexURL: base });
    mark("runtime");
    const zip = await (await fetch("charlie.zip")).arrayBuffer();
    py.unpackArchive(zip, "zip");
    py.runPython("import charlie.demo");
    mark("import");
    const out = JSON.parse(py.runPython(`charlie.demo.ideas_json(${JSON.stringify(day)})`));
    mark("ideas");
    const warmStart = performance.now();
    py.runPython(`charlie.demo.ideas_json(${JSON.stringify(day)}, 3)`);
    marks.warm_ideas_ms = Math.round(performance.now() - warmStart);
    const r = out.result;
    status.textContent = `${r.date} · ${r.risk_label} · ${r.data_source}`;
    document.getElementById("ideas").innerHTML = r.ideas.map((i) => `
      <div class="idea"><b>${i.rank}. ${esc(i.analysis.name)} (${esc(i.trade.symbol)})</b> · Charlie ${i.analysis.charlie.score}<br>
      ${esc(i.trade.label)} · max loss ${money(i.trade.max_loss)} · breakeven $${i.trade.breakeven?.toFixed(2) ?? "—"}<br>
      <span class="muted">${esc(i.trade.disclaimer)}</span></div>`).join("");
    document.getElementById("timings").textContent =
      `Script ${marks.script} ms · runtime ready ${marks.runtime} ms · package imported ${marks.import} ms · ideas shown ${marks.ideas} ms · warm re-run ${marks.warm_ideas_ms} ms`;
    window.__spike = { ok: true, summary: out.summary, marks };
  } catch (e) {
    status.textContent = `Couldn't start the engine: ${e.message}`;
    window.__spike = { ok: false, error: String(e), marks };
  }
})();
