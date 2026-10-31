"use strict";

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const state = { meta: null, profile: null, risk: 2, chat: [], loaded: {} };

// ---------------------------------------------------------------- helpers
// One UI, two backends: the local server over fetch, or (static demo) the same Python
// handlers running in Pyodide, exposed by static.js as window.charlieStatic.
async function api(path, opts = {}) {
  if (window.charlieStatic) {
    let data = null;
    if (opts.body instanceof FormData) data = Object.fromEntries([...opts.body].filter(([, v]) => typeof v === "string"));
    else if (typeof opts.body === "string") data = JSON.parse(opts.body);
    const r = await window.charlieStatic.request(opts.method || "GET", path, data);
    if (r.status >= 400) throw Object.assign(new Error(r.body.detail || `Request failed (${r.status})`), { status: r.status });
    return r.body;
  }
  const res = await fetch(path, opts);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw Object.assign(new Error(body.detail || `Request failed (${res.status})`), { status: res.status });
  return body;
}
const postJSON = (path, data) => api(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
// A real minus sign (UX30), and no sign at all on an amount that rounds to $0.
const money = (x, d = 0) => {
  if (x === null || x === undefined) return "—";
  const s = Math.abs(x).toLocaleString(undefined, { minimumFractionDigits: d, maximumFractionDigits: d });
  return (x < 0 && /[1-9]/.test(s) ? "−$" : "$") + s;
};
// Rendered by code on every trade surface (CLAUDE.md hard rule).
const NFA = "Not financial advice. Paper trading only.";
const nfa = () => `<p class="nfa">${NFA}</p>`;
// UX48: "Dec 11, 2026". The date part is read as local parts, so a US time zone never slips it a day.
function fmtDate(d) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(d ?? ""));
  if (!m) return String(d ?? "");
  return new Date(+m[1], +m[2] - 1, +m[3]).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}
// A real minus on percentages too (showcase P3), and no sign when it rounds to 0%.
const pct = (x, d = 0) => { if (x === null || x === undefined) return "—"; const s = Math.abs(x * 100).toFixed(d); return (x < 0 && /[1-9]/.test(s) ? "−" : "") + s + "%"; };
function toast(msg, ms = 2600) {
  const t = $("#toast"); t.textContent = msg; t.classList.remove("hidden");
  clearTimeout(toast._t); toast._t = setTimeout(() => t.classList.add("hidden"), ms);
}
function md(text) {
  const lines = esc(text).split("\n");
  let html = "", inList = false;
  for (let line of lines) {
    line = line.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").replace(/`([^`]+)`/g, "<code>$1</code>").replace(/(^|\s)_(.+?)_(?=\s|$|[.,])/g, "$1<em>$2</em>");
    if (/^\s*[-*] /.test(line)) {
      if (!inList) { html += "<ul class='tight'>"; inList = true; }
      html += `<li>${line.replace(/^\s*[-*] /, "")}</li>`;
    } else {
      if (inList) { html += "</ul>"; inList = false; }
      if (line.trim()) html += `<p>${line}</p>`;
    }
  }
  return html + (inList ? "</ul>" : "");
}

// ---------------------------------------------------------------- charts
// Charts are drawn at their rendered width (UX5): a placeholder <div class="chart"> holds the data, and
// drawChart() writes an SVG whose viewBox matches the box, so the 12px labels stay 12px on a phone.
const chartData = {};
function chartSlot(kind, data) {
  const id = `g${Math.random().toString(36).slice(2, 8)}`;
  chartData[id] = { kind, data };
  return `<div class="chart" data-chart="${id}"></div>`;
}
const chartObserver = typeof ResizeObserver === "function" ? new ResizeObserver((entries) => entries.forEach((e) => drawChart(e.target))) : null;
function drawCharts(root = document) {
  $$(".chart[data-chart]", root).forEach((el) => {
    drawChart(el);
    if (chartObserver && !el.dataset.watched) { el.dataset.watched = "1"; chartObserver.observe(el); }
  });
}
function drawChart(el) {
  const c = chartData[el.dataset.chart]; if (!c) return;
  const w = Math.round(el.clientWidth); if (!w || Number(el.dataset.w) === w) return;
  el.dataset.w = w;
  el.innerHTML = c.kind === "payoff" ? payoffSVG(c.data, w) : sparkSVG(c.data, w);
}

function payoffAt(trade, px) {
  let pnl = 0;
  for (const leg of trade.legs) {
    const sign = leg.action === "buy" ? 1 : -1;
    if (leg.instrument === "stock") pnl += sign * (px - leg.price) * leg.qty;
    else {
      const intrinsic = leg.instrument === "call" ? Math.max(0, px - leg.strike) : Math.max(0, leg.strike - px);
      pnl += sign * (intrinsic - leg.price) * 100 * leg.qty;
    }
  }
  if (trade.strategy === "covered_call" || trade.strategy === "collar") pnl += (px - trade.spot) * 100 * trade.contracts;
  return pnl;
}
// P&L with its sign (UX18): "+$83", "−$3,174", or "$0" for the baseline.
const signedMoney = (v) => (Math.round(v) === 0 ? "$0" : (v > 0 ? "+" : "−") + money(Math.abs(v)));
const payoffRange = (t) => [t.spot * 0.7, t.spot * 1.3];
function payoffSVG(trade, W = 520) {
  const H = W < 480 ? 112 : 160, padR = 8, top = 14, bottom = 24, gap = 8;
  const [lo, hi] = payoffRange(trade), N = 80;
  const pts = [];
  for (let i = 0; i <= N; i++) { const px = lo + (hi - lo) * i / N; pts.push([px, payoffAt(trade, px)]); }
  const ys = pts.map((p) => p[1]);
  let yMin = Math.min(...ys, 0), yMax = Math.max(...ys, 0);
  if (yMax - yMin < 1) { yMax += 1; yMin -= 1; }
  // P&L labels sit in a left gutter, price labels under the x-axis, so the two never share a corner.
  const yLabs = [[0, "$0"]];
  if (Math.round(yMax) !== 0) yLabs.push([yMax, signedMoney(yMax)]);
  if (Math.round(yMin) !== 0) yLabs.push([yMin, signedMoney(yMin)]);
  const padL = gap + 4 + Math.max(...yLabs.map(([, s]) => s.length)) * 7.2;
  const X = (px) => padL + (px - lo) / (hi - lo) * (W - padL - padR);
  const Y = (v) => top + (yMax - v) / (yMax - yMin) * (H - top - bottom);
  const path = pts.map((p, i) => `${i ? "L" : "M"}${X(p[0]).toFixed(1)},${Y(p[1]).toFixed(1)}`).join("");
  const area = (sel) => {
    const poly = pts.map((p) => [X(p[0]), Y(sel(p[1]))]);
    return `M${X(lo)},${Y(0)}` + poly.map((p) => `L${p[0].toFixed(1)},${p[1].toFixed(1)}`).join("") + `L${X(hi)},${Y(0)}Z`;
  };
  const be = trade.breakeven && trade.breakeven > lo && trade.breakeven < hi
    ? `<circle class="be" cx="${X(trade.breakeven).toFixed(1)}" cy="${Y(0).toFixed(1)}" r="4.5"/>` : "";
  // Keep the $0 label; drop an extreme label that would sit within 15px of it.
  const shown = yLabs.filter(([v], i) => i === 0 || Math.abs(Y(v) - Y(0)) >= 15);
  const yText = shown.map(([v, s]) => `<text class="y-label" x="${(padL - gap).toFixed(1)}" y="${(Y(v) + 4).toFixed(1)}" text-anchor="end">${s}</text>`).join("");
  return `<svg class="payoff" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="Profit and loss at expiration, from ${signedMoney(yMin)} to ${signedMoney(yMax)}, for ${esc(trade.symbol)} prices from ${money(lo)} to ${money(hi)}">
    <path class="gain-area" d="${area((v) => Math.max(v, 0))}"/>
    <path class="loss-area" d="${area((v) => Math.min(v, 0))}"/>
    <line class="zero" x1="${padL}" x2="${W - padR}" y1="${Y(0)}" y2="${Y(0)}"/>
    <line class="axis" x1="${padL}" x2="${W - padR}" y1="${H - bottom}" y2="${H - bottom}"/>
    <line class="spot" x1="${X(trade.spot)}" x2="${X(trade.spot)}" y1="${top - 4}" y2="${H - bottom}"/>
    <path class="curve" d="${path}"/>${be}${yText}
    <text class="x-label" x="${padL}" y="${H - 6}">${money(lo)}</text>
    <text class="x-label" x="${W - padR}" y="${H - 6}" text-anchor="end">${money(hi)}</text>
  </svg>`;
}
function sparkSVG(hist, W = 640) {
  const H = 110, c = hist.map((h) => h.close), lo = Math.min(...c), hi = Math.max(...c);
  const d = c.map((v, i) => `${i ? "L" : "M"}${(i / (c.length - 1) * W).toFixed(1)},${(H - 20 - (v - lo) / (hi - lo || 1) * (H - 40)).toFixed(1)}`).join("");
  return `<svg class="payoff" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="Price history from ${money(lo)} to ${money(hi)}"><path class="curve" d="${d}"/>
    <text x="2" y="12">${money(hi)}</text><text x="2" y="${H - 4}">${money(lo)}</text></svg>`;
}

// ---------------------------------------------------------------- trade + idea rendering
// Max loss happens at $0 only for trades that own (or must buy) the stock unprotected.
const AT_ZERO = new Set(["shares", "cash_secured_put", "covered_call"]);
const lcFirst = (s) => (/^[A-Z][a-z]/.test(s) ? s[0].toLowerCase() + s.slice(1) : s);
function metric(k, v, cls = "", help = "") {
  return `<div class="metric ${cls}"><div class="k">${k}</div><div class="v">${v}</div>${help ? `<div class="h">${help}</div>` : ""}</div>`;
}
function heroMetrics(t) {  // UX3: the three numbers a new investor needs, same weight, no red alarm
  return `<div class="metrics hero-m">
    ${t.pop ? metric("Chance of profit", pct(t.pop)) : metric("Money tied up", money(t.capital_required))}
    ${metric("Max profit", t.max_profit === null ? "Unlimited" : money(t.max_profit), "gain")}
    ${metric("Max loss", money(t.max_loss), "loss", AT_ZERO.has(t.strategy) ? "if it hits $0" : "worst case")}
  </div>`;
}
function moreMetrics(t) {
  const m = [["Breakeven", t.breakeven ? money(t.breakeven, 2) : "—"], ["Money tied up", money(t.capital_required)]];
  if (t.net_premium !== null) m.push([t.net_premium >= 0 ? "Credit per share" : "Cost per share", money(Math.abs(t.net_premium), 2)]);
  if (t.annualized) m.push(["Yearly rate (if max profit)", pct(t.annualized)]);
  else if (t.return_on_risk) m.push(["Reward : risk", `${t.return_on_risk.toFixed(2)} : 1`]);
  if (t.dte) m.push(["Days until expiry", t.dte]);
  if (t.expected_move) m.push(["Typical move by expiry", money(t.expected_move, 2)]);
  return `<div class="metrics">${m.map(([k, v]) => metric(k, v)).join("")}</div>`;
}
function chartBlock(t) {  // the legend keeps "today" and breakeven readable above the chart
  return `<div class="chart-legend"><span class="key-spot">Today <b>${money(t.spot, 2)}</b></span><span class="key-be">Breakeven <b>${t.breakeven ? money(t.breakeven, 2) : "—"}</b></span><span class="wide-only">Profit or loss at expiration</span></div>
    ${chartSlot("payoff", t)}
    <p class="chart-cap">Shown for ${esc(t.symbol)} between ${money(payoffRange(t)[0])} and ${money(payoffRange(t)[1])} at expiry.</p>`;
}
function planTicket(t, { nested = false } = {}) {  // nested: already inside a <details>, so no second one
  return `<div class="two-col">
      <div><h3>Plan</h3><ul class="tight">${t.management.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div>
      <div><h3>Order details (for paper practice)</h3><div class="ticket">${esc(t.ticket.join("\n"))}</div></div>
    </div>
    ${nested ? `<h3>${esc(t.explainer_title || t.label)}</h3>` : `<details><summary>${esc(t.explainer_title || t.label)}</summary>`}<div class="edu">${esc(t.learn)}<br><br><b>Risk:</b> ${esc(t.risk)}</div>${nested ? "" : "</details>"}`;
}
function tradeTag(t) {
  return `<span class="strategy-tag">${esc(t.label)}${t.contracts ? ` · ${t.contracts} contract${t.contracts > 1 ? "s" : ""}` : ""}${t.shares ? ` · ${t.shares} shares` : ""}${t.expiry ? ` · expires ${esc(fmtDate(t.expiry))}` : ""}</span>`;
}
function keepTrade(t) {
  const id = `t${Math.random().toString(36).slice(2, 8)}`;
  window._trades = window._trades || {}; window._trades[id] = t;
  return id;
}
function tradeActions(id) {
  return `<div class="actions">
      <button class="primary" data-paper="${id}">Paper trade this</button>
      <button class="ghost" data-copy="${id}">Copy trade details</button>
    </div>`;
}
// The full trade (drawer, screener rows): headline numbers, chart, then every detail.
function tradeBlock(t, { withActions = true } = {}) {
  const id = keepTrade(t);
  return `
    ${tradeTag(t)}
    ${heroMetrics(t)}
    ${chartBlock(t)}
    <details><summary>More numbers</summary>${moreMetrics(t)}</details>
    ${planTicket(t)}
    ${withActions ? tradeActions(id) : ""}
    ${nfa()}`;
}
// Phone (UX34): "Score 76 · A"; wider screens: "Charlie score 76/100 · A". The aria-label carries the full words.
function gradeLabel(ch) { return `<span class="gword">Charlie score </span><span class="gcap">Score </span>${ch.score}<span class="gout">/100</span> · ${ch.grade}`; }
// Idea card (UX4): collapsed by default; plan, risks and order details are one tap away.
function ideaCard(idea) {
  const a = idea.analysis, t = idea.trade, th = idea.thesis, ch = a.charlie, id = keepTrade(t);
  return `<article class="card">
    <div class="card-head">
      <div>
        <div class="card-title"><span class="rank" aria-hidden="true">${idea.rank}</span>${esc(a.name)}<span class="sym">${esc(a.symbol)} · ${money(a.quote.price, 2)}</span></div>
        <div class="card-sub">${esc(a.domain_label || "")} · ${esc(ch.lynch_category)}</div>
      </div>
      <button class="grade ${ch.grade}" data-ticker="${a.symbol}" title="Munger-style checklist score. Open for the full breakdown."
        aria-label="Charlie score ${ch.score} out of 100, grade ${ch.grade}. Open details for ${esc(a.name)}."><span class="gscore">${gradeLabel(ch)}</span><span class="gmore">Details</span></button>
    </div>
    <div class="chips why-chips">${th.why_you.map((w) => `<span class="chip">✓ ${esc(w)}</span>`).join("")}</div>
    ${th.summary.length ? `<p class="thesis">${esc(th.summary[0])}</p>` : ""}
    ${tradeTag(t)}
    ${heroMetrics(t)}
    ${chartBlock(t)}
    ${t.management.length ? `<p class="exit-line"><b>Exit plan:</b> ${esc(t.management[0])}</p>` : ""}
    ${tradeActions(id)}
    <details class="more"><summary>Plan, risks and order details</summary>
      ${moreMetrics(t)}
      ${planTicket(t, { nested: true })}
      <div class="two-col">
        <div><h3>Why this one</h3><ul class="tight">${(th.summary.length > 1 ? th.summary.slice(1) : th.summary).map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div>
        <div><h3>Invert: what could go wrong</h3><ul class="tight flags">${th.inversion.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div>
      </div>
      <h3>Charlie score breakdown</h3>${factorBars(ch)}<p class="muted small">Financials: ${esc(ch.data_source === "mock" ? "sample numbers, not real filings" : ch.data_source)}</p>
      <p class="quote">${esc(th.munger)}</p>
    </details>
    ${nfa()}
  </article>`;
}
function factorBars(ch) {
  return `<div class="factors">${ch.factors.map((f) => `
    <div class="factor"><span>${esc(f.key[0].toUpperCase() + f.key.slice(1))}</span><div class="bar"><span data-bar="${Number(f.score) || 0}"></span></div><b class="num">${f.score}</b>
    <div class="why">${esc(f.reason)}</div></div>`).join("")}</div>`;
}
// Friendly states (UX14): skeletons while loading, one plain sentence and Try again on failure.
function skeletonCards(n = 3, label = "Running the checklist on your circle…") {
  return `<div role="status"><span class="sr-only">${esc(label)}</span>${Array.from({ length: n }, () => `<div class="card skeleton" aria-hidden="true">
    <div class="sk t1"></div><div class="sk t2"></div><div class="sk blk"></div><div class="sk chart-sk"></div></div>`).join("")}</div>`;
}
function errorState(text, err, retryAttr) {
  // 4xx messages from the handlers are already plain English; anything else stays in "Technical details".
  const plain = err && err.status >= 400 && err.status < 500 && err.message;
  return `<div class="panel state error" role="alert"><div class="icon" aria-hidden="true">!</div>
    <p>${esc(plain || text)}</p><button type="button" class="primary" ${retryAttr}>Try again</button>
    ${!plain && err && !window.charlieStatic ? `<details><summary>Technical details</summary>${esc(err.message)}</details>` : ""}</div>`;
}
const retries = {};
// Bar widths are set through the DOM, not inline style attributes, so the CSP needs no 'unsafe-inline' (CHL-PS1).
new MutationObserver(() => $$("[data-bar]").forEach((el) => { el.style.width = `${el.dataset.bar}%`; el.removeAttribute("data-bar"); }))
  .observe(document.body, { childList: true, subtree: true });
function retryButton(fn) { const id = `r${Math.random().toString(36).slice(2, 8)}`; retries[id] = fn; return `data-retry="${id}"`; }

// ---------------------------------------------------------------- tabs
const RISK_TABS = ["today", "screener", "learn"];  // where the risk slider changes what you see
function showTab(name) {
  $$(".tabs button").forEach((b) => {
    const on = b.dataset.tab === name;
    b.classList.toggle("active", on); b.setAttribute("aria-selected", String(on)); b.tabIndex = on ? 0 : -1;
  });
  $(`.tabs button[data-tab="${name}"]`)?.scrollIntoView({ block: "nearest", inline: "nearest" });
  $$(".tab").forEach((s) => s.classList.toggle("active", s.id === `tab-${name}`));
  $("#risk-row").classList.toggle("hidden", !RISK_TABS.includes(name));
  history.replaceState(null, "", `#${name}`);
  ({ today: loadIdeas, profile: renderProfile, screener: initScreener, paper: loadPaper, learn: renderLearn, chat: openChat }[name] || (() => {}))();
}

// ---------------------------------------------------------------- today
// UX28: one line in the hero (phones) so the first screen carries a real number; it scrolls to card 1.
function topIdea(idea) {
  const el = $("#hero-top-idea");
  if (!el) return;
  el.classList.toggle("hidden", !idea);
  if (!idea) return;
  const t = idea.trade;
  el.innerHTML = `Top idea today: <b>${esc(idea.analysis.symbol)}</b> · ${t.pop ? `${pct(t.pop)} chance of profit` : `${money(t.capital_required)} tied up`} · max loss ${money(t.max_loss)} <span aria-hidden="true">›</span>`;
}
async function loadIdeas(refresh = false) {
  const box = $("#ideas");
  box.innerHTML = skeletonCards(Number($("#idea-count").value) || 3);
  try {
    const r = await api(`/api/ideas?risk=${state.risk}&count=${$("#idea-count").value}${refresh ? "&refresh=true" : ""}`);
    $("#today-sub").innerHTML = `${state.status?.static ? "Sample market day: " : ""}${esc(fmtDate(r.date))} · <b>${esc(r.risk_label)}</b>: ${esc(r.risk_plain || r.risk_blurb)}`;
    setDataBadge(r.data_source);
    box.innerHTML = r.ideas.length ? r.ideas.map(ideaCard).join("") : `<div class="panel state"><p>${esc(r.note)}</p></div>`;
    topIdea(r.ideas[0]);
    drawCharts(box);
    $("#ideas-skipped").innerHTML = r.skipped.length
      ? `<details><summary>Considered ${r.considered} companies. Why some didn't make it</summary><ul class="tight">${r.skipped.map((s) => `<li><b>${esc(s.symbol)}</b>: ${esc(s.reason)}</li>`).join("")}</ul></details>` : "";
  } catch (e) {
    box.innerHTML = errorState("Couldn't load ideas. Check your connection and try again.", e, retryButton(() => loadIdeas(refresh)));
  }
  loadTrackRecord();
}
// M1.13: past ideas graded at today's price, next to SPY over the same days. The stock's move, not a trade's P&L.
const signedPct = (x) => (x === null || x === undefined) ? "—" : `${x > 0 ? "+" : x < 0 ? "−" : ""}${Math.abs(x * 100).toFixed(1)}%`;
const TRACK_SHOWN = 6;  // newer ideas show; older ones fold behind "Show older ideas"
function trackItem(it) {
  const be = it.above_breakeven === null ? "" : `<span class="be-chip ${it.above_breakeven ? "above" : "below"}">${it.above_breakeven ? "Above" : "Below"} breakeven <span class="num">${money(it.breakeven, 2)}</span></span>`;
  return `<li class="track-item" title="${esc(it.outcome)}">
    <div class="ti-head"><b>${esc(it.symbol)}</b> <span class="muted small">${esc(it.label)}</span><span class="ti-date muted small num">Idea on ${esc(fmtDate(it.date))}</span></div>
    <div class="ti-grid">
      <span><span>Then → now</span><b class="num">${money(it.entry_price, 2)} → ${money(it.price_today, 2)}</b></span>
      <span><span>Stock</span><b class="num ${signCls(it.underlying_move_pct)}">${signedPct(it.underlying_move_pct)}</b></span>
      <span><span>SPY<span class="wide-only">, same days</span></span><b class="num">${signedPct(it.spy_move_pct)}</b></span>
    </div>
    ${be}<span class="sr-only">${esc(it.outcome)}</span>
  </li>`;
}
let trackSeq = 0;
async function loadTrackRecord() {
  const box = $("#track-body"), seq = ++trackSeq;
  if (!box) return;
  let r;
  try { r = await api("/api/track-record"); } catch (e) {
    if (seq === trackSeq) box.innerHTML = errorState("Couldn't load past ideas. Check your connection and try again.", e, retryButton(loadTrackRecord));
    return;
  }
  if (seq !== trackSeq) return;
  $("#track-sample").classList.toggle("hidden", !r.sample);
  if (!r.items.length) {
    box.innerHTML = `<div class="panel state track-empty"><p>No past ideas yet. Come back tomorrow.</p><p class="muted small">Each day's ideas are kept here and checked against SPY.</p>${nfa()}</div>`;
    return;
  }
  const s = r.summary, shown = r.items.slice(0, TRACK_SHOWN), older = r.items.slice(TRACK_SHOWN);
  box.innerHTML = `<div class="panel track-panel">
    <p class="track-sum"><b>${s.above_breakeven} of ${s.count}</b> past ideas are above breakeven today. Average stock move <b class="num">${signedPct(s.avg_underlying_move_pct)}</b>; SPY over the same days <b class="num">${signedPct(s.avg_spy_move_pct)}</b>.</p>
    <ul class="track-list">${shown.map(trackItem).join("")}</ul>
    ${older.length ? `<details class="track-older"><summary>Show ${older.length} older idea${older.length === 1 ? "" : "s"}</summary><ul class="track-list">${older.map(trackItem).join("")}</ul></details>` : ""}
    <p class="muted small track-note">${r.sample ? "Sample data: the engine's ideas on simulated prices from past days. " : ""}Options aren't re-priced, so this isn't a trade's profit or loss. Past moves don't predict future ones.</p>
    ${nfa()}
  </div>`;
}
// Where the numbers came from, in the header badge. Prices and fundamentals are labeled separately,
// so live prices next to demo earnings never read as fully live (CHL-R2, CHL-R4).
function dataBadge(src, fundamentals) {
  src = src || "";
  if (/^mock/i.test(src)) return { text: window.charlieStatic ? "Sample data" : "Demo data", mock: true,
    title: "Simulated prices, not real market data. Do not use these numbers to trade." };
  if (/^mixed/i.test(src)) return { text: "Mixed data", mock: true,
    title: `Live prices (delayed) except demo prices for ${(src.match(/demo prices for ([^;)]+)/) || [, "some names"])[1]}. Today's ideas leave those names out.` };
  if (/^live/i.test(src)) return fundamentals === "demo"
    ? { text: "Live prices · demo fundamentals", mock: false,
        title: "Prices are live, delayed about 15 minutes. The company financials behind the Charlie scores are demo numbers, not real filings." }
    : { text: "Delayed data", mock: false, title: "Live prices, delayed about 15 minutes." };
  return null;  // nothing analyzed: keep whatever the badge says
}
function setDataBadge(src) {
  const d = dataBadge(src, state.status?.data?.fundamentals); if (!d) return;
  const b = $("#data-badge");
  b.textContent = d.text; b.title = d.title; b.classList.toggle("mock", d.mock);
}

// ---------------------------------------------------------------- profile
function setWhose(saved, name) {  // the hero's "whose ideas" line (copy spec §1)
  const el = $("#profile-nudge");
  if (window.charlieStatic && !saved)  // the demo starts as the fictional sample person, not a blank profile
    el.textContent = `Showing ideas for ${name.replace(/\s*\(sample\)$/, "")}, a fictional sample person.`;
  else if (saved) el.textContent = "Showing ideas for your profile.";
  else el.innerHTML = `Showing a starter circle. <a href="#profile" data-goto="profile">Add your resume</a> to make it yours.`;
}
async function loadProfile() {
  const r = await api("/api/profile");
  state.profile = r.profile;
  state.risk = r.profile.risk_level;
  setWhose(r.saved, r.profile.name || "");
  syncRisk();
  const f = $("#profile-form"), i = r.intake || {};
  f.resume_text.dataset.ph ??= f.resume_text.placeholder;
  f.resume_text.placeholder = f.resume_text.dataset.ph;
  if (i.interests !== undefined) {
    f.interests.value = i.interests || ""; f.brands.value = i.brands || ""; f.holdings.value = i.holdings || "";
    f.capital.value = i.capital || 25000; f.risk_level.value = i.risk_level || 2;
    if (i.resume_chars) f.resume_text.placeholder = `Saved resume on file (${i.resume_chars.toLocaleString()} characters). Paste again to replace.`;
  }
}
function renderProfile() {
  const p = state.profile; if (!p) return;
  $("#profile-view").innerHTML = `
    <h2>${!p.name ? "Your circle" : / \(sample\)$/.test(p.name) ? esc(p.name.replace(/ \(sample\)$/, "")) + "'s circle (sample)" : esc(p.name) + "'s circle"}</h2>
    <p>${esc(p.summary)}</p>
    <div class="callout small">${esc(p.caution)}</div>
    ${p.domains.map((d) => `<div class="domain">
      <div class="row gap"><b class="grow">${esc(d.label)}</b><span class="muted small">ETF ${esc(d.etf)}</span></div>
      <div class="bar" title="familiarity ${d.familiarity}"><span data-bar="${Number(d.familiarity) || 0}"></span></div>
      <div class="muted small">${esc(d.blurb)}</div>
      <div class="chips">${d.evidence.map((e) => `<span class="chip">${esc(e)}</span>`).join("")}</div>
    </div>`).join("")}
    <h3>Companies you're positioned to understand</h3>
    <div class="chips">${p.tickers.map((t) => `<button class="chip" data-ticker="${t.symbol}" title="${esc(t.why.join("; "))}">${esc(t.symbol)} · ${esc(t.name)}</button>`).join("")}</div>
    <p class="muted small">Capital ${money(p.capital)} · Risk level ${p.risk_level} · Holdings ${Object.keys(p.holdings).length ? esc(Object.entries(p.holdings).map(([k, v]) => `${k} ${v}`).join(", ")) : "none"} · Built with ${esc(p.source)}</p>`;
}
async function submitProfile(e) {
  e.preventDefault();
  const f = e.target, fd = new FormData(f);
  fd.set("use_ai", f.use_ai.checked ? "true" : "false");
  if (!f.resume.files.length || window.charlieStatic) fd.delete("resume");
  const btn = f.querySelector('button[type="submit"]');
  btn.disabled = true; btn.textContent = "Building…";  // R11: no double submits while it runs
  $("#profile-status").textContent = "Reading your resume and building your circle…";
  if (window.charlieStatic && !engineReady)
    toast("Loading Charlie's engine (about 6 MB). On a phone this can take up to a minute. It's faster next time.", 6000);
  try {
    const r = await api("/api/profile", { method: "POST", body: fd });
    state.profile = r.profile; state.risk = r.profile.risk_level; syncRisk();
    $("#profile-status").innerHTML = `Done. Your circle is below, and Today now shows ideas for it. <button type="button" class="link-btn" data-goto="today">See today's ideas</button>`;
    setWhose(true);
    renderProfile(); toast("Profile saved. Today's ideas are updated.");
  } catch (err) { $("#profile-status").textContent = err.message; }
  finally { btn.disabled = false; btn.textContent = "Build my profile"; }
}

// ---------------------------------------------------------------- risk slider
function syncRisk() {
  const lvl = state.risk, r = state.meta?.risk_levels?.[lvl];
  $("#risk").value = lvl;
  $("#risk").setAttribute("aria-valuetext", `${lvl}, ${r ? r.label : ""}`);
  const pill = $("#risk-label"); pill.textContent = r ? r.label : lvl;
  pill.className = `pill l${lvl}`; pill.title = r ? (r.plain || r.blurb) : "";
}
async function onRisk() {
  state.risk = Number($("#risk").value); syncRisk();
  try { await postJSON("/api/profile/risk", { risk_level: state.risk }); if (state.profile) state.profile.risk_level = state.risk; } catch (e) { toast(e.message); }
  const active = $(".tabs button.active").dataset.tab;
  if (active === "today") loadIdeas();
  if (active === "learn") renderLearn();
  if (state.loaded.screener) syncStrategyChips();
  if (active === "screener") runScreen();
}

// ---------------------------------------------------------------- screener
const HIDDEN_FILTERS = { max_price: "", min_pop: "", min_annualized: "", min_iv: "", max_iv: "", dte_min: "25", dte_max: "55", delta: "" };
function initScreener() {
  if (state.loaded.screener) return; state.loaded.screener = true;
  const chip = (name, value, label, extra = "") => `<label class="chip chip-check"><input type="checkbox" name="${name}" value="${value}"> ${esc(label)}${extra}</label>`;
  $("#domain-select").innerHTML = state.meta.domains.map((d) => chip("domains", d.key, d.label)).join("");
  $("#strategy-select").innerHTML = Object.entries(state.meta.strategies).sort((a, b) => a[1].min_level - b[1].min_level)
    .map(([k, s]) => chip("strategies", k, s.label, `<span class="need hidden"> (needs level ${s.min_level})</span>`)).join("");
  syncStrategyChips(true);
  loadSavedScreens();
  runScreen();  // UX9: results on first open, no click needed
}
// UX19: the trade types the risk slider allows are ticked by default; the rest are disabled and say why.
function syncStrategyChips(first = false) {
  $$("#strategy-select input[name=strategies]").forEach((o) => {
    const need = state.meta.strategies[o.value].min_level, blocked = need > state.risk;
    if (blocked) o.checked = false;
    else if (first || o.disabled) o.checked = true;  // newly allowed types start ticked
    o.disabled = blocked;
    o.closest("label").classList.toggle("disabled", blocked);
    o.closest("label").querySelector(".need").classList.toggle("hidden", !blocked);
  });
  // UX35: phones show only the allowed chips, plus one line on the rest (CSS shows it under 600px).
  const locked = $$("#strategy-select input[name=strategies]:disabled").length;
  $("#strategy-locked").textContent = `${locked} more trade type${locked === 1 ? " unlocks" : "s unlock"} at higher risk levels. Move the risk slider to see ${locked === 1 ? "it" : "them"}.`;
  $("#strategy-locked").classList.toggle("hidden", !locked);
}
// UX19: on a phone the form folds into one summary row after a run, so results come first.
function screenSummary() {
  const c = readCriteria(), f = $("#screen-form");
  const scope = c.scope === "list" ? `${c.symbols.length} ticker${c.symbols.length === 1 ? "" : "s"}` : f.scope.selectedOptions[0].text;
  const parts = [scope];
  if (c.min_score !== null) parts.push(`score ${c.min_score}+`);
  parts.push(`${c.strategies.length} trade type${c.strategies.length === 1 ? "" : "s"}`);
  if (c.max_capital !== null) parts.push(`up to ${money(c.max_capital)}`);
  $("#screen-summary-text").textContent = parts.join(" · ");
}
function foldScreenForm(folded) {  // CSS folds it only under 600px
  $("#tab-screener").classList.toggle("screen-folded", folded);
  if (folded) screenSummary();
}
function countHiddenFilters() {
  const f = $("#screen-form");
  const n = Object.entries(HIDDEN_FILTERS).filter(([k, d]) => f[k].value !== d).length
    + $$("input[name=domains]:checked", f).length + (f.exclude_red_flags.checked ? 1 : 0);
  $("#more-filters > summary").textContent = n ? `More filters (${n} set)` : "More filters";
}
function readCriteria() {
  const f = $("#screen-form"); const c = {};
  const num = (n) => (f[n].value === "" ? null : Number(f[n].value));
  c.scope = f.scope.value;
  c.symbols = c.scope === "list" ? f.symbols.value.split(/[\s,]+/).filter(Boolean).map((s) => s.toUpperCase()) : [];
  c.domains = $$("input[name=domains]:checked", f).map((o) => o.value);
  c.strategies = $$("input[name=strategies]:checked", f).map((o) => o.value);
  for (const n of ["min_score", "max_price", "min_pop", "max_capital", "min_annualized", "min_iv", "max_iv", "dte_min", "dte_max", "delta"]) c[n] = num(n);
  c.exclude_red_flags = f.exclude_red_flags.checked;
  return c;
}
function writeCriteria(c) {
  const f = $("#screen-form");
  f.scope.value = (c.symbols || []).length && c.scope === "circle" ? "list" : c.scope || "circle";
  f.symbols.value = (c.symbols || []).join(", ");
  $("#symbols-field").classList.toggle("hidden", f.scope.value !== "list");
  $$("input[name=domains]", f).forEach((o) => { o.checked = (c.domains || []).includes(o.value); });
  $$("input[name=strategies]", f).forEach((o) => { o.checked = !o.disabled && (!(c.strategies || []).length || c.strategies.includes(o.value)); });
  for (const n of ["min_score", "max_price", "min_pop", "max_capital", "min_annualized", "min_iv", "max_iv", "dte_min", "dte_max", "delta"]) f[n].value = c[n] ?? "";
  f.exclude_red_flags.checked = !!c.exclude_red_flags;
  countHiddenFilters();
}
const orList = (xs) => (xs.length < 3 ? xs.join(" or ") : `${xs.slice(0, -1).join(", ")} or ${xs[xs.length - 1]}`);
async function runScreen(e, save = false) {
  e && e.preventDefault();
  const box = $("#screen-results");
  box.innerHTML = `<div class="panel skeleton" role="status"><span class="sr-only">Finding trades…</span><div class="sk t1" aria-hidden="true"></div><div class="sk blk" aria-hidden="true"></div></div>`;
  const name = $("#screen-form").save_name.value.trim();
  try {
    const r = await postJSON("/api/screen", { criteria: readCriteria(), risk: state.risk, save, name });
    setDataBadge(r.data_source);
    if (r.saved) { toast(`Saved "${r.saved.name}".`); loadSavedScreens(); }
    window._screen = r.results;
    const u = r.unknown_symbols || [];
    const unknown = u.length ? `<p class="callout small">Charlie doesn't cover ${esc(orList(u))} yet, so ${u.length > 1 ? "they were" : "it was"} skipped.</p>` : "";
    const label = (s) => state.meta.strategies[s].label;
    const demoPrice = (x) => (x.price_source === "mock" && /^mixed/.test(r.data_source) ? " · demo price" : "");
    const pop = (x) => (x.trade.pop ? pct(x.trade.pop) : "—");
    // UX17: trades with no chance-of-profit estimate (shares) show the money they tie up instead of a dash.
    const firstCell = (x) => (x.trade.pop ? ["Chance of profit", pct(x.trade.pop)] : ["Money tied up", money(x.trade.capital_required)]);
    const maxp = (x) => (x.trade.max_profit === null ? "Unlimited" : money(x.trade.max_profit));
    box.innerHTML = unknown + (r.results.length ? `<p class="muted small results-line">${r.total} trade${r.total === 1 ? "" : "s"} match. ${r.filtered_out} compan${r.filtered_out === 1 ? "y" : "ies"} didn't pass your filters. Searched: ${esc(r.strategies.map(label).join(", "))}.</p>
      <div class="row-cards">${r.results.map((x, i) => `<button type="button" class="row-card" data-row="${i}">
        <span class="rc-top"><span><b>${esc(x.symbol)}</b> <span class="muted small">${esc(x.trade.label)}</span></span><span class="muted small num">Score ${x.score}</span></span>
        <span class="rc-grid"><span><span>${firstCell(x)[0]}</span><b>${firstCell(x)[1]}</b></span><span><span>Max profit</span><b>${maxp(x)}</b></span><span><span>Max loss</span><b>${money(x.trade.max_loss)}</b></span></span>
      </button>`).join("")}</div>
      <div class="table-wrap has-cards"><table><thead><tr><th>Stock</th><th>Trade type</th><th class="num">Score</th><th class="num">Price swings (IV)</th><th class="num">Max loss</th><th class="num">Max profit</th><th class="num">Chance of profit</th><th class="num">Yearly rate</th><th>Expires</th></tr></thead><tbody>
      ${r.results.map((x, i) => `<tr class="clickable" data-row="${i}"><td><b>${esc(x.symbol)}</b> <span class="muted small num">${money(x.price, 2)}</span><div class="muted small sector" title="${esc(x.domain_label || "")}">${esc(x.domain_label || "")}${demoPrice(x)}</div></td><td class="nowrap">${esc(x.trade.label)}</td><td class="num">${x.score}</td><td class="num">${x.iv ? pct(x.iv) : "—"}</td><td class="num">${money(x.trade.max_loss)}</td><td class="num">${maxp(x)}</td><td class="num">${pop(x)}</td><td class="num">${x.trade.annualized ? pct(x.trade.annualized) : "—"}</td><td class="nowrap">${x.trade.expiry ? esc(fmtDate(x.trade.expiry)) : "—"}</td></tr>`).join("")}
      </tbody></table></div>${nfa()}` : `<div class="panel state"><p>No trades match these filters. Try loosening one, or move the risk slider up to search more trade types.</p></div>`);
    foldScreenForm(true);
  } catch (err) { box.innerHTML = errorState("Couldn't run this screen. Check your connection and try again.", err, retryButton(() => runScreen())); }
}
async function loadSavedScreens() {
  const r = await api("/api/screens");
  window._saved = r.screens;
  $("#saved-screens").innerHTML = r.screens.length ? `<span class="muted small">Saved:</span>` + r.screens.map((s, i) => `<button type="button" class="chip" data-saved="${i}">${esc(s.name)}</button>`).join("") : "";
}

// ---------------------------------------------------------------- chat
// Keep the input above the fixed footer on every screen (UX1): the panel fills what's left of the viewport.
function sizeChat() {
  const wrap = $(".chat-wrap"); if (!wrap.offsetParent) return;
  const top = wrap.getBoundingClientRect().top + scrollY, foot = $("#footer-disclaimer").offsetHeight;
  wrap.style.height = `${Math.max(340, innerHeight - top - foot - 16)}px`;
}
function openChat() { sizeChat(); if (matchMedia("(hover: hover)").matches) $("#chat-input").focus(); }
function renderChatMsg(role, text, cards = []) {
  const div = document.createElement("div");
  div.className = `msg ${role === "user" ? "user" : "bot"}`;
  div.innerHTML = role === "user" ? esc(text) : md(text) + cards.map((t) => {
    const id = keepTrade(t);
    return `<div class="mini"><b>${esc(t.symbol)} · ${esc(t.label)}</b>${t.expiry ? ` · expires ${esc(fmtDate(t.expiry))}` : ""}<br>Max loss ${money(t.max_loss)} · Breakeven ${t.breakeven ? money(t.breakeven, 2) : "—"}${t.pop ? ` · ${pct(t.pop)} chance of profit` : ""}
      <div class="actions"><button class="ghost" data-paper="${id}">Paper trade</button><button class="ghost" data-ticker="${esc(t.symbol)}">Details</button></div>${nfa()}</div>`;
  }).join("");
  $("#chat-log").appendChild(div); div.scrollIntoView({ behavior: "smooth", block: "end" });
  return div;
}
async function sendChat(text) {
  if (!text.trim()) return;
  state.chat.push({ role: "user", content: text });
  const mine = renderChatMsg("user", text);
  const pending = renderChatMsg("bot", "");
  pending.innerHTML = `<span class="typing" aria-hidden="true"><span></span><span></span><span></span></span><span class="sr-only">Charlie is typing…</span>`;
  try {
    const r = await postJSON("/api/chat", { messages: state.chat });
    pending.remove();
    state.chat.push({ role: "assistant", content: r.reply });
    renderChatMsg("bot", r.reply, r.cards);
    $("#chat-mode").textContent = r.mode === "claude" ? "Answered by Claude using Charlie's tools."
      : window.charlieStatic ? "Demo mode: rule-based answers on sample data." : "Offline mode (rule-based). Add ANTHROPIC_API_KEY for full conversation.";
  } catch (e) {
    state.chat.pop();
    const plain = e.status >= 400 && e.status < 500 ? e.message : "Charlie couldn't answer just now.";
    pending.innerHTML = `<p>${esc(plain)}</p><button type="button" class="ghost" ${retryButton(() => { mine.remove(); pending.remove(); sendChat(text); })}>Try again</button>`;
  }
}

// ---------------------------------------------------------------- paper
async function paperTrade(t, btn) {
  if (btn) btn.disabled = true;
  const opened = () => { if (btn) { btn.textContent = "Opened ✓"; btn.setAttribute("aria-label", "Paper trade opened"); } };
  try {
    const r = await postJSON("/api/paper", { trade: t });
    opened();
    const msg = `Paper trade opened: ${t.symbol} ${lcFirst(t.label)}. It's in your Paper portfolio.`;
    if (r.warning) toast(`${msg} ${r.warning}`, 7000);
    else toast(msg, 3500);
  } catch (e) {
    if (e.status === 409) { opened(); toast(`${e.message} It's in your Paper portfolio.`, 4000); }
    else { if (btn) btn.disabled = false; toast(e.message); }
  }
}
async function closePaper(pid) {
  try {
    const p = await api(`/api/paper/${pid}/close`, { method: "POST" });
    toast(`Closed ${p.symbol} ${lcFirst(p.trade.label)}. Paper P&L: ${p.pnl > 0 ? "+" : ""}${money(p.pnl, 2)}`, 4000);
  } catch (err) { toast(err.message); }
  loadPaper();
}
const signCls = (x) => (x > 0 ? "up" : x < 0 ? "down" : "");
async function loadPaper() {
  let r;
  try { r = await api("/api/paper"); } catch (e) {
    $("#paper-stats").innerHTML = "";
    $("#paper-list").innerHTML = errorState("Couldn't load your paper portfolio. Check your connection and try again.", e, retryButton(loadPaper));
    return;
  }
  const stat = (k, v, cls = "") => `<div class="metric ${cls}"><div class="k">${k}</div><div class="v">${v}</div></div>`;
  // UX23: no stats while there's nothing to measure; the empty state's button sits high instead.
  // UX30: win rate only once a trade has closed (a $0 scratch close counts, and shows "—").
  const closedCount = r.positions.filter((p) => p.status === "closed").length;
  $("#alert-explainer").hidden = !r.positions.length; // UX42: name the alert chips once there is a trade to flag
  $("#paper-stats").innerHTML = !r.positions.length ? "" : stat("Open positions", r.open_count) + stat("Open P&L", money(r.open_pnl), signCls(r.open_pnl)) +
    stat("Realized P&L", money(r.realized_pnl), signCls(r.realized_pnl)) + stat("Most you could lose (open trades)", money(r.capital_at_risk)) + (closedCount ? stat("Win rate (closed)", r.win_rate === null ? "—" : pct(r.win_rate)) : "") +
    (r.scratch ? stat("Scratch ($0) closes", r.scratch) : "");
  // UX30: a credit reads as money received, never as a negative entry.
  const entryText = (p) => (p.entry_value < 0 ? `You received ${money(-p.entry_value)}` : `You paid ${money(p.entry_value)}`);
  const nowText = (p) => (p.current_value < 0 ? `${p.status === "open" ? "Cost to close" : "Closed for"} ${money(-p.current_value)}`
    : `${p.status === "open" ? "Worth" : "Closed at"} ${money(p.current_value)}`);
  // M1.13: exit-plan alerts, one chip per rule that fired; the message is the chip's title and, on phones, a line below.
  const ALERT_LABEL = { take_profit: "Take profit?", time: "Near expiry", breakeven: "Below breakeven" };
  const chips = (p, srText = true) => (p.alerts || []).map((a) => `<span class="alert-chip" data-alert="${esc(a.type)}" title="${esc(a.message)}">${esc(ALERT_LABEL[a.type] || a.type)}${srText ? `<span class="sr-only">: ${esc(a.message)}</span>` : ""}</span>`).join("");
  const alertBlock = (p) => (p.alerts?.length ? `<div class="alert-row">${chips(p, false)}</div><ul class="alert-msgs">${p.alerts.map((a) => `<li>${esc(a.message)}</li>`).join("")}</ul>` : "");
  const closeBtn = (p) => (p.status === "open" ? `<button class="ghost" data-close="${p.id}" aria-label="Close paper trade ${esc(p.symbol)} ${esc(p.trade.label.toLowerCase())}">Close trade</button>` : "");
  $("#paper-list").innerHTML = r.positions.length ? `
    <div class="pos-cards">${r.positions.map((p) => `<div class="pos-card">
      <div class="rc-top"><span><b>${esc(p.symbol)}</b> <span class="muted small">${esc(p.trade.label)}</span></span><span class="muted small">${esc(p.status)}</span></div>
      ${alertBlock(p)}
      <div class="small muted rc-money">${entryText(p)} · ${nowText(p)}</div>
      <div class="rc-grid"><span><span>P&L</span><b class="pos-pnl ${signCls(p.pnl)} num">${money(p.pnl)}</b></span><span><span>% of max profit</span><b class="num">${p.pct_of_max_profit === null ? "—" : pct(p.pct_of_max_profit)}</b></span><span><span>${p.trade.expiry ? "Expires" : "Opened"}</span><b class="num">${esc(fmtDate(p.trade.expiry || p.opened))}</b></span></div>
      ${closeBtn(p) ? `<div class="actions">${closeBtn(p)}</div>` : ""}</div>`).join("")}</div>
    <div class="table-wrap has-cards"><table><thead><tr><th>Opened</th><th>Stock</th><th>Trade type</th><th class="num">Entry</th><th class="num">Now</th><th class="num">P&L</th><th class="num">% of max profit</th><th>Status</th><th><span class="sr-only">Actions</span></th></tr></thead><tbody>
    ${r.positions.map((p) => `<tr><td class="num nowrap">${esc(fmtDate(p.opened))}</td><td><b>${esc(p.symbol)}</b></td><td>${esc(p.trade.label)}${p.trade.expiry ? `<div class="muted small nowrap">expires ${esc(fmtDate(p.trade.expiry))}</div>` : ""}</td><td class="num">${entryText(p)}</td><td class="num">${nowText(p)}</td>
      <td class="num pos-pnl ${signCls(p.pnl)}">${money(p.pnl)}</td><td class="num">${p.pct_of_max_profit === null ? "—" : pct(p.pct_of_max_profit)}</td><td>${esc(p.status)}${p.alerts?.length ? `<div class="alert-row">${chips(p)}</div>` : ""}</td>
      <td>${closeBtn(p)}</td></tr>`).join("")}
    </tbody></table></div><details class="small muted"><summary>How P&L is counted</summary>For a trade you paid for, P&L is what it's worth now minus what you paid. For a credit, it's what you received minus what it costs to close. Covered calls track only the option leg.</details>${nfa()}`
    : `<div class="panel state"><div class="icon" aria-hidden="true">$</div><h2>No paper trades yet</h2>
       <p>Pick an idea on Today and tap Paper trade this to practice with pretend money.</p>
       <button type="button" class="primary" data-goto="today">See today's ideas</button></div>`;
}

// ---------------------------------------------------------------- learn
function renderLearn() {
  const m = state.meta; if (!m) return;
  $("#learn").innerHTML = `
    <div class="grid2">
      <div class="panel">
        <h2>How Charlie picks ideas</h2>
        <ol>
          <li><b>Circle of competence.</b> Start with industries you work in, read about, and buy from (Munger, Buffett, Peter Lynch).</li>
          <li><b>Quality.</b> High returns on capital and real free cash flow. "Over the long term, it's hard for a stock to earn a much better return than the business which underlies it earns."</li>
          <li><b>Moat.</b> High and <i>steady</i> margins suggest a durable advantage.</li>
          <li><b>Balance sheet.</b> Low debt, no heavy dilution. Leverage is how smart people go broke.</li>
          <li><b>Margin of safety.</b> Free-cash-flow yield versus Treasuries, and how far Mr. Market has marked the price down.</li>
          <li><b>Invert.</b> Every idea lists what would make it fail, and red flags cost points.</li>
          <li><b>Few bets, sized by risk.</b> 1-3 ideas a day, one per sector, sized by the slider, never by how confident you feel.</li>
        </ol>
        <div class="callout small">Knowing an industry helps you <i>find</i> ideas. It doesn't make them safe: studies find people judge familiar companies as less risky than they really are. That's why position size comes from the risk slider, not your familiarity score.</div>
      </div>
      <div class="panel">
        <h2>The risk slider</h2>
        <div class="ladder">${Object.entries(m.risk_levels).map(([k, v]) => `<div class="rung l${k} ${Number(k) === state.risk ? "current" : ""}"><div class="n">${k}</div><div><b>${esc(v.label)}</b> <span class="muted small">· max ${pct(v.max_risk_pct)} of capital at risk per defined-risk trade</span><div class="small">${esc(v.blurb)}</div></div></div>`).join("")}</div>
        <p class="muted small">Never on any level: selling uncovered calls, or same-week (0DTE) options, where research has documented heavy retail losses.</p>
      </div>
    </div>
    <h2 class="mt-lg">Strategies, from safest to riskiest</h2>
    <div class="cards learn-cards">${Object.entries(m.strategies).sort((a, b) => a[1].min_level - b[1].min_level).map(([k, s]) => `<div class="card"><div class="card-head"><div class="card-title sm">${esc(s.label)}</div><span class="pill l${s.min_level}">Level ${s.min_level}+</span></div><p>${esc(s.learn)}</p><p class="small"><b>Best when:</b> ${esc(s.outlook)} · <b>Risk:</b> ${esc(s.risk)}</p></div>`).join("")}</div>
    <h2 class="mt-lg">Words you'll see</h2>
    <div class="panel small"><ul class="tight">
      <li><b>Strike:</b> the price the option lets you buy (call) or sell (put) at.</li>
      <li><b>Expiry / DTE:</b> when the option ends; DTE is days to expiry.</li>
      <li><b>Premium / credit / debit:</b> the option's price. Selling collects a credit; buying pays a debit. Quoted per share; one contract = 100 shares.</li>
      <li><b>Delta:</b> roughly how much the option moves per $1 in the stock, and a rough odds-of-finishing-in-the-money gauge. A 0.20-delta put is ~20% likely to end in the money.</li>
      <li><b>IV (implied volatility):</b> how big a move the market is pricing in. High IV means fatter premiums <i>and</i> more risk.</li>
      <li><b>Assignment:</b> when the option is exercised against you and you buy (puts) or sell (calls) the shares.</li>
      <li><b>Chance of profit:</b> a model estimate from option prices, not a promise.</li>
    </ul></div>`;
}

// ---------------------------------------------------------------- ticker drawer (UX11: a real modal dialog)
let drawerOpener = null;
function openDrawer(title) {
  const drawer = $("#drawer");
  if (drawer.classList.contains("hidden")) drawerOpener = document.activeElement;
  $("#drawer-title").innerHTML = title;
  drawer.classList.remove("hidden");
  document.body.style.overflow = "hidden";
  $(".drawer-inner").scrollTop = 0;
  $("#drawer-close").focus();
}
function closeDrawer() {
  const drawer = $("#drawer"); if (drawer.classList.contains("hidden")) return;
  drawer.classList.add("hidden");
  document.body.style.overflow = "";
  if (drawerOpener && document.contains(drawerOpener)) drawerOpener.focus();
  drawerOpener = null;
}
async function openTicker(sym) {
  openDrawer(`${esc(sym)}`);
  const body = $("#drawer-body"); body.innerHTML = skeletonCards(1, `Loading ${sym}…`);
  try {
    const d = await api(`/api/ticker/${encodeURIComponent(sym)}?risk=${state.risk}`);
    const ch = d.charlie, f = d.fundamentals;
    $("#drawer-title").innerHTML = `${esc(d.name)} <span class="sym">${esc(d.symbol)} · <span class="num">${money(d.quote.price, 2)}</span> (${d.quote.change_pct >= 0 ? "+" : ""}${d.quote.change_pct}%)</span><span class="grade ${ch.grade}">${gradeLabel(ch)}</span>`;
    const src = d.quote.source === "mock" ? "Sample data, not real market prices" : `Delayed prices from ${esc(d.quote.source)}`;
    body.innerHTML = `
      <p class="src-line">${esc(d.domain_label || "")} · ${esc(ch.lynch_category)} · ${src}</p>
      ${chartSlot("spark", d.history)}
      ${d.history.length ? `<div class="muted small">${esc(fmtDate(d.history[0].date))} to ${esc(fmtDate(d.history[d.history.length - 1].date))}</div>` : ""}
      <div class="chips">${(d.familiarity_why.length ? d.familiarity_why : ["Outside your stated circle"]).map((w) => `<span class="chip">${esc(w)}</span>`).join("")}</div>
      <h3>Munger checklist</h3>${factorBars(ch)}
      ${ch.red_flags.length ? `<h3>Red flags (inversion)</h3><ul class="tight flags">${ch.red_flags.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}
      <div class="metrics">
        ${[["Return on capital", pct(f.roic)], ["Gross margin", pct(f.gross_margin)], ["Operating margin", pct(f.op_margin)], ["Free-cash yield", pct(f.fcf_yield, 1)], ["Debt to equity", f.debt_to_equity?.toFixed?.(1) ?? "—"], ["Revenue growth", pct(f.rev_growth)], ["Price to earnings", f.pe ?? "—"], ["Expected price swings (IV)", d.atm_iv ? pct(d.atm_iv) : "—"]].map(([k, v]) => metric(k, v)).join("")}
      </div>
      <p class="muted small">Financials: ${f.source === "mock" ? "sample numbers, illustrative and not real filings." : esc(f.source)}${f.fiscal_year ? ` (FY${f.fiscal_year})` : ""}</p>
      <h2 class="mt-lg">Ways to express it at your risk level</h2>
      ${nfa()}
      ${d.trades.map((t) => `<div class="card"><div class="card-title sm">${esc(t.label)}</div>${tradeBlock(t)}</div>`).join("") || "<p>No trade fits your capital and risk level for this stock.</p>"}
      ${d.blocked.length ? `<details><summary>Not available (and why)</summary><ul class="tight">${d.blocked.map((b) => `<li><b>${esc(b.label)}</b>: ${esc(b.reason)}</li>`).join("")}</ul></details>` : ""}`;
    drawCharts(body);
  } catch (e) { body.innerHTML = errorState("Couldn't load this company. Try again.", e, retryButton(() => openTicker(sym))); }
}
function openScreenRow(x) {
  openDrawer(`${esc(x.name)} <span class="sym">${esc(x.symbol)}</span>`);
  $("#drawer-body").innerHTML = `<p><button class="link" data-ticker="${esc(x.symbol)}">Full company analysis →</button></p><div class="card">${tradeBlock(x.trade)}</div>`;
  drawCharts($("#drawer-body"));
}

// ---------------------------------------------------------------- boot
document.addEventListener("click", (e) => {
  const el = e.target.closest("[data-tab],[data-goto],[data-ticker],[data-paper],[data-copy],[data-close],[data-q],[data-row],[data-saved],[data-retry]");
  if (!el) return;
  if (el.dataset.tab) return showTab(el.dataset.tab);
  if (el.dataset.goto) { e.preventDefault(); return showTab(el.dataset.goto); }
  if (el.dataset.retry) return retries[el.dataset.retry]?.();
  if (el.dataset.ticker) return openTicker(el.dataset.ticker);
  if (el.dataset.paper) return paperTrade(window._trades[el.dataset.paper], el);
  if (el.dataset.copy) { navigator.clipboard?.writeText(window._trades[el.dataset.copy].ticket.join("\n")); return toast("Trade details copied."); }
  if (el.dataset.close) return closePaper(el.dataset.close);
  if (el.dataset.q) return sendChat(el.dataset.q);
  if (el.dataset.row) return openScreenRow(window._screen[Number(el.dataset.row)]);
  if (el.dataset.saved) { writeCriteria(window._saved[Number(el.dataset.saved)].criteria); return runScreen(); }
});
$("#hero-top-idea").addEventListener("click", (e) => {
  e.preventDefault();
  const card = $("#ideas .card");
  if (card) { card.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" }); card.querySelector("[data-ticker]")?.focus({ preventScroll: true }); }
});
$("#drawer-close").onclick = closeDrawer;
$("#drawer").addEventListener("click", (e) => { if (e.target.id === "drawer") closeDrawer(); });
document.addEventListener("keydown", (e) => {
  const drawerOpen = !$("#drawer").classList.contains("hidden");
  if (e.key === "Escape") {
    if (drawerOpen) return closeDrawer();
    if (!$("#ack").classList.contains("hidden") && state.acked) return closeAck();
  }
  if (e.key === "Tab" && drawerOpen) {  // keep focus inside the dialog
    const f = $$('button, [href], input, select, textarea, summary, [tabindex]:not([tabindex="-1"])', $("#drawer")).filter((x) => !x.disabled && x.offsetParent);
    if (!f.length) return;
    const first = f[0], last = f[f.length - 1];
    if (e.shiftKey && (document.activeElement === first || !$("#drawer").contains(document.activeElement))) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && (document.activeElement === last || !$("#drawer").contains(document.activeElement))) { e.preventDefault(); first.focus(); }
  }
});
$("#risk").addEventListener("change", onRisk);
$("#risk").addEventListener("input", () => { state.risk = Number($("#risk").value); syncRisk(); });
$("#refresh-ideas").onclick = () => loadIdeas(true);
$("#idea-count").onchange = () => loadIdeas();
$("#profile-form").addEventListener("submit", submitProfile);
$("#screen-form").addEventListener("submit", (e) => runScreen(e));
$("#screen-form").addEventListener("input", countHiddenFilters);
$("#edit-filters").onclick = () => { foldScreenForm(false); $("#screen-form").scope.focus(); };
$("#screen-form").scope.addEventListener("change", (e) => {
  $("#symbols-field").classList.toggle("hidden", e.target.value !== "list");
  if (e.target.value === "list") $("#screen-form").symbols.focus();
});
$("#save-screen").onclick = () => { if (!$("#screen-form").save_name.value.trim()) return toast("Give the screen a name first."); runScreen(null, true); };
$("#chat-form").addEventListener("submit", (e) => { e.preventDefault(); const v = $("#chat-input").value; $("#chat-input").value = ""; sendChat(v); });
$("#refresh-paper").onclick = loadPaper;
window.addEventListener("resize", () => { if ($("#tab-chat").classList.contains("active")) sizeChat(); });
$("#delete-profile").onclick = async () => {
  const where = window.charlieStatic ? "this browser" : "this computer";
  const what = window.charlieStatic ? "profile, resume, saved screens, paper trades and saved ideas"
    : "profile, resume, saved screens, paper trades, saved ideas and saved market data";
  if (!confirm(`Delete all your Charlie data from ${where}? This removes your ${what}. You can't undo this.`)) return;
  try {
    await api("/api/profile?all=true", { method: "DELETE" });
    $("#profile-form").reset(); await loadProfile(); renderProfile();
    state.loaded.screener && loadSavedScreens();
    toast(`Done. Your ${what} are deleted.`, 4000);
  } catch (err) { toast(err.message); }
};
let engineReady = false;
// Static demo: say so while a control waits for the engine, so nothing looks dead.
window.addEventListener("charlie:engine", (e) => {
  engineReady = e.detail.ready && !e.detail.error;
  $("#engine-status").classList.toggle("hidden", e.detail.ready);
  if (e.detail.error) toast("Charlie's engine couldn't load. Check your connection and reload the page.", 5000);
});
$("#use-sample").onclick = async () => {  // demo only: show the fictional resume behind the sample ideas
  const text = await window.charlieStatic?.sampleResume();
  if (text) { const t = $("#profile-form").resume_text; t.value = text; t.focus(); }
};
$("#reset-demo").onclick = () => {
  try { Object.keys(localStorage).filter((k) => k.startsWith("charlie:")).forEach((k) => localStorage.removeItem(k)); } catch (_) {}
  location.reload();
};
// Tab bar keyboard support (ARIA tabs pattern): arrows move between tabs, Home/End jump.
$(".tabs").addEventListener("keydown", (e) => {
  const tabs = $$(".tabs button"), i = tabs.indexOf(document.activeElement);
  const next = { ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: tabs.length - 1 }[e.key];
  if (i < 0 || next === undefined) return;
  e.preventDefault();
  const t = tabs[(next + tabs.length) % tabs.length];
  t.focus(); showTab(t.dataset.tab);
});
// Ack modal (UX8): plain bullets first, the full legal text one tap away. The footer's Read more reopens it.
let ackOpener = null;
function openAck(fromFooter) {
  ackOpener = fromFooter ? document.activeElement : null;
  $("#ack-details").open = !!fromFooter;
  $("#ack-btn").textContent = fromFooter ? "Close" : "Got it, show me ideas";
  $("#ack").classList.remove("hidden");
  (fromFooter ? $("#ack-details > summary") : $("#ack-btn")).focus();
}
function closeAck() {
  try { localStorage.setItem("charlie-ack", "1"); } catch (_) {}
  state.acked = true;
  $("#ack").classList.add("hidden");
  ackOpener?.focus(); ackOpener = null;
}
$("#read-more").onclick = () => openAck(true);
$("#ack-btn").onclick = closeAck;

async function boot() {
  try {
    const [meta, status] = await Promise.all([api("/api/meta"), api("/api/status")]);
    state.meta = meta; state.status = status;
    $("#ack-text").textContent = meta.disclaimer;
    if (status.static) $("#ack-data").textContent = "Everything here is sample data.";
    try { state.acked = localStorage.getItem("charlie-ack") === "1"; } catch (_) {}
    if (!state.acked) openAck(false);
    $("#chat-mode").textContent = status.static ? "Demo mode: rule-based answers on sample data."
      : status.llm ? "Claude is connected." : "Offline mode (rule-based). Add ANTHROPIC_API_KEY for full conversation.";
    if (status.static) {  // no uploads or Claude in the demo; show the sample banner, back link and reset
      $$(".server-only").forEach((el) => el.classList.add("hidden"));
      $$(".static-only").forEach((el) => el.classList.remove("hidden"));
      document.body.classList.add("is-static");
    }
    await loadProfile();
    renderProfile();
    const tab = location.hash.slice(1);
    showTab(["today", "profile", "screener", "chat", "paper", "learn"].includes(tab) ? tab : "today");
    // Static demo: the first screen came from prebuilt answers; load the engine once it has painted.
    requestAnimationFrame(() => setTimeout(() => window.charlieStatic?.start(), 50));
  } catch (e) { $("#ideas").innerHTML = errorState("Charlie couldn't start. Check your connection and try again.", e, retryButton(boot)); }
}
boot();
