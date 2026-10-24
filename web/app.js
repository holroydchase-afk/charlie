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
    if (r.status >= 400) throw new Error(r.body.detail || `Request failed (${r.status})`);
    return r.body;
  }
  const res = await fetch(path, opts);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || `Request failed (${res.status})`);
  return body;
}
const postJSON = (path, data) => api(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const money = (x, d = 0) => (x === null || x === undefined) ? "—" : (x < 0 ? "-$" : "$") + Math.abs(x).toLocaleString(undefined, { minimumFractionDigits: d, maximumFractionDigits: d });
// Rendered by code on every trade surface (CLAUDE.md hard rule).
const NFA = "Not financial advice. Paper trading only.";
const nfa = () => `<p class="nfa">${NFA}</p>`;
const pct = (x, d = 0) => (x === null || x === undefined) ? "—" : `${(x * 100).toFixed(d)}%`;
function toast(msg) {
  const t = $("#toast"); t.textContent = msg; t.classList.remove("hidden");
  clearTimeout(toast._t); toast._t = setTimeout(() => t.classList.add("hidden"), 2600);
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

// ---------------------------------------------------------------- payoff chart
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
function payoffSVG(trade) {
  const W = 520, H = 160, pad = 28;
  const lo = trade.spot * 0.7, hi = trade.spot * 1.3, N = 80;
  const pts = [];
  for (let i = 0; i <= N; i++) { const px = lo + (hi - lo) * i / N; pts.push([px, payoffAt(trade, px)]); }
  const ys = pts.map((p) => p[1]);
  let yMin = Math.min(...ys, 0), yMax = Math.max(...ys, 0);
  if (yMax - yMin < 1) { yMax += 1; yMin -= 1; }
  const X = (px) => pad + (px - lo) / (hi - lo) * (W - 2 * pad);
  const Y = (v) => 10 + (yMax - v) / (yMax - yMin) * (H - 30);
  const path = pts.map((p, i) => `${i ? "L" : "M"}${X(p[0]).toFixed(1)},${Y(p[1]).toFixed(1)}`).join("");
  const area = (sel) => {
    const poly = pts.map((p) => [X(p[0]), Y(sel(p[1]))]);
    return `M${X(lo)},${Y(0)}` + poly.map((p) => `L${p[0].toFixed(1)},${p[1].toFixed(1)}`).join("") + `L${X(hi)},${Y(0)}Z`;
  };
  return `<svg class="payoff" viewBox="0 0 ${W} ${H}" role="img" aria-label="Profit and loss at expiration">
    <path class="gain-area" d="${area((v) => Math.max(v, 0))}"/>
    <path class="loss-area" d="${area((v) => Math.min(v, 0))}"/>
    <line class="zero" x1="${pad}" x2="${W - pad}" y1="${Y(0)}" y2="${Y(0)}"/>
    <line class="spot" x1="${X(trade.spot)}" x2="${X(trade.spot)}" y1="6" y2="${H - 20}"/>
    <path class="curve" d="${path}"/>
    <text x="${X(trade.spot) + 4}" y="14">today $${trade.spot.toFixed(0)}</text>
    <text x="${pad}" y="${H - 4}">$${lo.toFixed(0)}</text>
    <text x="${W - pad - 30}" y="${H - 4}">$${hi.toFixed(0)}</text>
    <text x="${W - pad - 70}" y="${Y(yMax) + 10}">${money(yMax)}</text>
    <text x="${W - pad - 70}" y="${Y(yMin) - 2}">${money(yMin)}</text>
  </svg><div class="muted small">Profit/loss at expiration across stock prices (−30% to +30%).</div>`;
}

// ---------------------------------------------------------------- trade + idea rendering
function tradeMetrics(t) {
  const m = [
    ["Max loss", money(t.max_loss), "loss"],
    ["Max profit", t.max_profit === null ? "Unlimited" : money(t.max_profit), "gain"],
    ["Breakeven", t.breakeven ? money(t.breakeven, 2) : "—"],
    ["Chance of profit", t.pop ? pct(t.pop) : "—"],
    ["Capital tied up", money(t.capital_required)],
  ];
  if (t.net_premium !== null) m.push([t.net_premium >= 0 ? "Credit / share" : "Debit / share", money(Math.abs(t.net_premium), 2)]);
  if (t.annualized) m.push(["Annualized (if max profit)", pct(t.annualized)]);
  else if (t.return_on_risk) m.push(["Reward : risk", `${t.return_on_risk.toFixed(2)} : 1`]);
  if (t.dte) m.push(["Days to expiry", t.dte]);
  if (t.expected_move) m.push(["Expected move (±1σ)", money(t.expected_move, 2)]);
  return `<div class="metrics">${m.map(([k, v, c]) => `<div class="metric ${c || ""}"><div class="k">${k}</div><div class="v">${v}</div></div>`).join("")}</div>`;
}
function factorBars(ch) {
  return `<div class="factors">${ch.factors.map((f) => `
    <div class="factor"><span>${esc(f.key[0].toUpperCase() + f.key.slice(1))}</span><div class="bar"><span style="width:${f.score}%"></span></div><b>${f.score}</b>
    <div class="why">${esc(f.reason)}</div></div>`).join("")}</div>`;
}
function tradeBlock(t, { withActions = true } = {}) {
  const id = `t${Math.random().toString(36).slice(2, 8)}`;
  window._trades = window._trades || {}; window._trades[id] = t;
  return `
    <span class="strategy-tag">${esc(t.label)}${t.contracts ? ` · ${t.contracts} contract${t.contracts > 1 ? "s" : ""}` : ""}${t.shares ? ` · ${t.shares} shares` : ""}${t.expiry ? ` · exp ${t.expiry}` : ""}</span>
    ${tradeMetrics(t)}
    ${payoffSVG(t)}
    <div class="two-col">
      <div><h3>Plan</h3><ul class="tight">${t.management.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div>
      <div><h3>Order ticket (for your broker, after paper practice)</h3><div class="ticket">${esc(t.ticket.join("\n"))}</div></div>
    </div>
    <details><summary>What is a ${esc(t.label.toLowerCase())}?</summary><div class="edu">${esc(t.learn)}<br><br><b>Risk:</b> ${esc(t.risk)}</div></details>
    ${withActions ? `<div class="actions">
      <button class="primary" data-paper="${id}">Paper trade this</button>
      <button class="ghost" data-copy="${id}">Copy ticket</button>
    </div>` : ""}
    ${nfa()}`;
}
function ideaCard(idea) {
  const a = idea.analysis, t = idea.trade, th = idea.thesis, ch = a.charlie;
  return `<article class="card">
    <div class="card-head">
      <div>
        <div class="card-title">${idea.rank}. ${esc(a.name)}<span class="sym">${esc(a.symbol)} · ${money(a.quote.price, 2)}</span></div>
        <div class="muted small">${esc(a.domain_label || "")} · ${esc(ch.lynch_category)}</div>
      </div>
      <button class="grade ${ch.grade} link-like" data-ticker="${a.symbol}" title="Charlie score: Munger-style checklist">Charlie ${ch.score} · ${ch.grade}</button>
    </div>
    <div class="chips">${th.why_you.map((w) => `<span class="chip">✓ ${esc(w)}</span>`).join("")}</div>
    ${tradeBlock(t)}
    <div class="two-col">
      <div><h3>Why this one</h3><ul class="tight">${th.summary.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div>
      <div><h3>Invert: what could go wrong</h3><ul class="tight flags">${th.inversion.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div>
    </div>
    <details><summary>Charlie score breakdown</summary>${factorBars(ch)}<p class="muted small">Fundamentals: ${esc(ch.data_source)}</p></details>
    <p class="muted small"><em>${esc(th.munger)}</em></p>
    ${nfa()}
  </article>`;
}

// ---------------------------------------------------------------- tabs
function showTab(name) {
  $$(".tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  $(`.tabs button[data-tab="${name}"]`)?.scrollIntoView({ block: "nearest", inline: "nearest" });
  $$(".tab").forEach((s) => s.classList.toggle("active", s.id === `tab-${name}`));
  history.replaceState(null, "", `#${name}`);
  ({ today: loadIdeas, profile: renderProfile, screener: initScreener, paper: loadPaper, learn: renderLearn, chat: () => $("#chat-input").focus() }[name] || (() => {}))();
}

// ---------------------------------------------------------------- today
async function loadIdeas(refresh = false) {
  const box = $("#ideas");
  box.innerHTML = `<div class="spinner">Running the checklist on your circle…</div>`;
  try {
    const r = await api(`/api/ideas?risk=${state.risk}&count=${$("#idea-count").value}${refresh ? "&refresh=true" : ""}`);
    $("#today-sub").innerHTML = `${esc(r.date)} · <b>${esc(r.risk_label)}</b>: ${esc(r.risk_blurb)}`;
    setDataBadge(r.data_source);
    box.innerHTML = r.ideas.length ? r.ideas.map(ideaCard).join("") : `<div class="panel">${esc(r.note)}</div>`;
    $("#ideas-skipped").innerHTML = r.skipped.length
      ? `<details><summary>Considered ${r.considered} names. Why some didn't make it</summary><ul class="tight">${r.skipped.map((s) => `<li><b>${esc(s.symbol)}</b>: ${esc(s.reason)}</li>`).join("")}</ul></details>` : "";
  } catch (e) { box.innerHTML = `<div class="panel">Couldn't load ideas: ${esc(e.message)}</div>`; }
}
function setDataBadge(src) {
  const b = $("#data-badge"); const mock = /mock/i.test(src || "");
  b.textContent = mock ? "Demo data" : "Delayed data"; b.classList.toggle("mock", mock);
  b.title = mock ? "Live data sources unreachable, showing simulated prices. Do not use these numbers to trade." : src;
}

// ---------------------------------------------------------------- profile
async function loadProfile() {
  const r = await api("/api/profile");
  state.profile = r.profile;
  state.risk = r.profile.risk_level;
  $("#profile-nudge").classList.toggle("hidden", r.saved);
  if (window.charlieStatic && !r.saved)  // the demo starts as the fictional sample person, not a blank profile
    $("#nudge-lead").textContent = `These ideas are for ${r.profile.name.replace(/\s*\(sample\)$/, "")}, a fictional sample person.`;
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
    <h2>${p.name ? esc(p.name) + "'s circle" : "Your circle"}</h2>
    <p>${esc(p.summary)}</p>
    <div class="callout small">${esc(p.caution)}</div>
    ${p.domains.map((d) => `<div class="domain">
      <div class="row gap"><b class="grow">${esc(d.label)}</b><span class="muted small">ETF ${esc(d.etf)}</span></div>
      <div class="bar" title="familiarity ${d.familiarity}"><span style="width:${d.familiarity}%"></span></div>
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
  $("#profile-status").textContent = "Reading your resume and building your circle…";
  try {
    const r = await api("/api/profile", { method: "POST", body: fd });
    state.profile = r.profile; state.risk = r.profile.risk_level; syncRisk();
    $("#profile-status").textContent = `Done. Read ${r.resume_chars.toLocaleString()} characters.`;
    $("#profile-nudge").classList.add("hidden");
    renderProfile(); toast("Profile saved. Today's ideas are updated.");
  } catch (err) { $("#profile-status").textContent = err.message; }
}

// ---------------------------------------------------------------- risk slider
function syncRisk() {
  const lvl = state.risk, r = state.meta?.risk_levels?.[lvl];
  $("#risk").value = lvl;
  const pill = $("#risk-label"); pill.textContent = r ? r.label : lvl;
  pill.className = `pill l${lvl}`; pill.title = r ? r.blurb : "";
}
async function onRisk() {
  state.risk = Number($("#risk").value); syncRisk();
  try { await postJSON("/api/profile/risk", { risk_level: state.risk }); if (state.profile) state.profile.risk_level = state.risk; } catch (e) { toast(e.message); }
  const active = $(".tabs button.active").dataset.tab;
  if (active === "today") loadIdeas();
  if (active === "learn") renderLearn();
}

// ---------------------------------------------------------------- screener
function initScreener() {
  if (state.loaded.screener) return; state.loaded.screener = true;
  $("#domain-select").innerHTML = state.meta.domains.map((d) => `<option value="${d.key}">${esc(d.label)}</option>`).join("");
  $("#strategy-select").innerHTML = Object.entries(state.meta.strategies).map(([k, s]) => `<option value="${k}">${esc(s.label)} (L${s.min_level}+)</option>`).join("");
  loadSavedScreens();
}
function readCriteria() {
  const f = $("#screen-form"); const c = {};
  const num = (n) => (f[n].value === "" ? null : Number(f[n].value));
  c.scope = f.scope.value;
  c.symbols = f.symbols.value.split(/[\s,]+/).filter(Boolean).map((s) => s.toUpperCase());
  if (c.symbols.length && c.scope === "circle") c.scope = "list";
  c.domains = [...f.domains.selectedOptions].map((o) => o.value);
  c.strategies = [...f.strategies.selectedOptions].map((o) => o.value);
  for (const n of ["min_score", "max_price", "min_pop", "max_capital", "min_annualized", "min_iv", "max_iv", "dte_min", "dte_max", "delta"]) c[n] = num(n);
  c.exclude_red_flags = f.exclude_red_flags.checked;
  return c;
}
function writeCriteria(c) {
  const f = $("#screen-form");
  f.scope.value = c.scope || "circle"; f.symbols.value = (c.symbols || []).join(", ");
  for (const o of f.domains.options) o.selected = (c.domains || []).includes(o.value);
  for (const o of f.strategies.options) o.selected = (c.strategies || []).includes(o.value);
  for (const n of ["min_score", "max_price", "min_pop", "max_capital", "min_annualized", "min_iv", "max_iv", "dte_min", "dte_max", "delta"]) f[n].value = c[n] ?? "";
  f.exclude_red_flags.checked = !!c.exclude_red_flags;
}
async function runScreen(e, save = false) {
  e && e.preventDefault();
  const box = $("#screen-results"); box.innerHTML = `<div class="spinner">Screening…</div>`;
  const name = $("#screen-form").save_name.value.trim();
  try {
    const r = await postJSON("/api/screen", { criteria: readCriteria(), risk: state.risk, save, name });
    setDataBadge(r.data_source);
    if (r.saved) { toast(`Saved "${r.saved.name}"`); loadSavedScreens(); }
    window._screen = r.results;
    box.innerHTML = r.results.length ? `<p class="muted small">${r.total} matching trades (${r.filtered_out} stocks filtered out) · strategies searched: ${r.strategies.map((s) => state.meta.strategies[s].label).join(", ")}</p>
      <div class="table-wrap"><table><thead><tr><th>Stock</th><th>Strategy</th><th class="num">Score</th><th class="num">Price</th><th class="num">IV</th><th class="num">Max loss</th><th class="num">Max profit</th><th class="num">Prob. profit</th><th class="num">Annualized</th><th>Expiry</th></tr></thead><tbody>
      ${r.results.map((x, i) => `<tr class="clickable" data-row="${i}"><td><b>${esc(x.symbol)}</b><div class="muted small">${esc(x.domain_label || "")}</div></td><td>${esc(x.trade.label)}</td><td class="num">${x.score}</td><td class="num">${money(x.price, 2)}</td><td class="num">${x.iv ? pct(x.iv) : "—"}</td><td class="num">${money(x.trade.max_loss)}</td><td class="num">${x.trade.max_profit === null ? "∞" : money(x.trade.max_profit)}</td><td class="num">${x.trade.pop ? pct(x.trade.pop) : "—"}</td><td class="num">${x.trade.annualized ? pct(x.trade.annualized) : "—"}</td><td>${esc(x.trade.expiry || "—")}</td></tr>`).join("")}
      </tbody></table></div>` : `<div class="panel">No trades match. Loosen a filter or raise the risk slider to search more strategies.</div>`;
  } catch (err) { box.innerHTML = `<div class="panel">${esc(err.message)}</div>`; }
}
async function loadSavedScreens() {
  const r = await api("/api/screens");
  window._saved = r.screens;
  $("#saved-screens").innerHTML = r.screens.length ? `<span class="muted small">Saved:</span>` + r.screens.map((s, i) => `<button type="button" class="chip" data-saved="${i}">${esc(s.name)}</button>`).join("") : "";
}

// ---------------------------------------------------------------- chat
function renderChatMsg(role, text, cards = []) {
  const div = document.createElement("div");
  div.className = `msg ${role === "user" ? "user" : "bot"}`;
  div.innerHTML = role === "user" ? esc(text) : md(text) + cards.map((t) => {
    const id = `c${Math.random().toString(36).slice(2, 8)}`; window._trades = window._trades || {}; window._trades[id] = t;
    return `<div class="mini"><b>${esc(t.symbol)} · ${esc(t.label)}</b>${t.expiry ? ` · ${esc(t.expiry)}` : ""}<br>Max loss ${money(t.max_loss)} · Breakeven ${t.breakeven ? money(t.breakeven, 2) : "—"}${t.pop ? ` · ${pct(t.pop)} chance of profit` : ""}
      <div class="actions"><button class="ghost" data-paper="${id}">Paper trade</button><button class="ghost" data-ticker="${esc(t.symbol)}">Details</button></div>${nfa()}</div>`;
  }).join("");
  $("#chat-log").appendChild(div); div.scrollIntoView({ behavior: "smooth", block: "end" });
  return div;
}
async function sendChat(text) {
  if (!text.trim()) return;
  state.chat.push({ role: "user", content: text });
  renderChatMsg("user", text);
  const pending = renderChatMsg("bot", "Thinking…");
  try {
    const r = await postJSON("/api/chat", { messages: state.chat });
    pending.remove();
    state.chat.push({ role: "assistant", content: r.reply });
    renderChatMsg("bot", r.reply, r.cards);
    $("#chat-mode").textContent = r.mode === "claude" ? "Answered by Claude using Charlie's tools."
      : window.charlieStatic ? "Demo mode: rule-based answers on sample data." : "Offline mode (rule-based). Add ANTHROPIC_API_KEY for full conversation.";
  } catch (e) { pending.innerHTML = esc(e.message); state.chat.pop(); }
}

// ---------------------------------------------------------------- paper
async function paperTrade(t) {
  try { await postJSON("/api/paper", { trade: t }); toast(`Paper trade opened: ${t.symbol} ${t.label}`); }
  catch (e) { toast(e.message); }
}
async function loadPaper() {
  const r = await api("/api/paper");
  const stat = (k, v, cls = "") => `<div class="metric ${cls}"><div class="k">${k}</div><div class="v">${v}</div></div>`;
  $("#paper-stats").innerHTML = stat("Open positions", r.open_count) + stat("Open P&L", money(r.open_pnl), r.open_pnl >= 0 ? "gain" : "loss") +
    stat("Realized P&L", money(r.realized_pnl), r.realized_pnl >= 0 ? "gain" : "loss") + stat("Max capital at risk", money(r.capital_at_risk)) + stat("Win rate (closed)", r.win_rate === null ? "—" : pct(r.win_rate));
  $("#paper-list").innerHTML = r.positions.length ? `<div class="table-wrap"><table><thead><tr><th>Opened</th><th>Stock</th><th>Strategy</th><th class="num">Entry</th><th class="num">Now</th><th class="num">P&L</th><th class="num">% of max profit</th><th>Status</th><th></th></tr></thead><tbody>
    ${r.positions.map((p) => `<tr><td>${esc(p.opened.slice(0, 10))}</td><td><b>${esc(p.symbol)}</b></td><td>${esc(p.trade.label)}${p.trade.expiry ? `<div class="muted small">exp ${esc(p.trade.expiry)}</div>` : ""}</td><td class="num">${money(p.entry_value)}</td><td class="num">${money(p.current_value)}</td>
      <td class="num pos-pnl ${p.pnl >= 0 ? "up" : "down"}">${money(p.pnl)}</td><td class="num">${p.pct_of_max_profit === null ? "—" : pct(p.pct_of_max_profit)}</td><td>${esc(p.status)}</td>
      <td>${p.status === "open" ? `<button class="ghost" data-close="${p.id}">Close</button>` : ""}</td></tr>`).join("")}
    </tbody></table></div><p class="muted small">Entry/Now are the signed value of the position (credits received show as negative). P&L = Now − Entry. Covered calls track only the option leg.</p>`
    : `<div class="panel">No paper trades yet. Use <b>Paper trade this</b> on any idea to practice without real money.</div>`;
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
    <h2 style="margin-top:24px">Strategies, from safest to riskiest</h2>
    <div class="cards">${Object.entries(m.strategies).sort((a, b) => a[1].min_level - b[1].min_level).map(([k, s]) => `<div class="card"><div class="card-head"><div class="card-title">${esc(s.label)}</div><span class="pill l${s.min_level}">Level ${s.min_level}+</span></div><p>${esc(s.learn)}</p><p class="small"><b>Best when:</b> ${esc(s.outlook)} · <b>Risk:</b> ${esc(s.risk)}</p></div>`).join("")}</div>
    <h2 style="margin-top:24px">Words you'll see</h2>
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

// ---------------------------------------------------------------- ticker drawer
function sparkline(hist) {
  if (!hist.length) return "";
  const W = 640, H = 120, c = hist.map((h) => h.close), lo = Math.min(...c), hi = Math.max(...c);
  const d = c.map((v, i) => `${i ? "L" : "M"}${(i / (c.length - 1) * W).toFixed(1)},${(H - 8 - (v - lo) / (hi - lo || 1) * (H - 16)).toFixed(1)}`).join("");
  return `<svg class="payoff" viewBox="0 0 ${W} ${H}"><path class="curve" d="${d}"/><text x="2" y="12">$${hi.toFixed(0)}</text><text x="2" y="${H - 2}">$${lo.toFixed(0)}</text></svg>
    <div class="muted small">${esc(hist[0].date)} to ${esc(hist[hist.length - 1].date)}</div>`;
}
async function openTicker(sym) {
  const drawer = $("#drawer"); drawer.classList.remove("hidden");
  const body = $("#drawer-body"); body.innerHTML = `<div class="spinner">Loading ${esc(sym)}…</div>`;
  try {
    const d = await api(`/api/ticker/${encodeURIComponent(sym)}?risk=${state.risk}`);
    const ch = d.charlie, f = d.fundamentals;
    body.innerHTML = `
      <div class="card-head"><div><div class="card-title">${esc(d.name)}<span class="sym">${esc(d.symbol)} · ${money(d.quote.price, 2)} (${d.quote.change_pct >= 0 ? "+" : ""}${d.quote.change_pct}%)</span></div>
      <div class="muted small">${esc(d.domain_label || "")} · ${esc(ch.lynch_category)} · data: ${esc(d.quote.source)}</div></div>
      <span class="grade ${ch.grade}">Charlie ${ch.score} · ${ch.grade}</span></div>
      ${nfa()}
      ${sparkline(d.history)}
      <div class="chips">${(d.familiarity_why.length ? d.familiarity_why : ["Outside your stated circle"]).map((w) => `<span class="chip">${esc(w)}</span>`).join("")}</div>
      <h3>Munger checklist</h3>${factorBars(ch)}
      ${ch.red_flags.length ? `<h3>Red flags (inversion)</h3><ul class="tight flags">${ch.red_flags.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}
      <div class="metrics">
        ${[["ROIC", pct(f.roic)], ["Gross margin", pct(f.gross_margin)], ["Op. margin", pct(f.op_margin)], ["FCF yield", pct(f.fcf_yield, 1)], ["Debt/Equity", f.debt_to_equity?.toFixed?.(1) ?? "—"], ["Revenue growth", pct(f.rev_growth)], ["P/E", f.pe ?? "—"], ["ATM IV", d.atm_iv ? pct(d.atm_iv) : "—"]].map(([k, v]) => `<div class="metric"><div class="k">${k}</div><div class="v">${v}</div></div>`).join("")}
      </div>
      <p class="muted small">Fundamentals: ${esc(f.source)}${f.fiscal_year ? ` (FY${f.fiscal_year})` : ""}${f.source === "mock" ? " — illustrative approximations, not real filings." : ""}</p>
      <h2 style="margin-top:20px">Ways to express it at your risk level</h2>
      ${d.trades.map((t) => `<div class="card" style="margin-bottom:12px"><div class="card-title" style="font-size:16px">${esc(t.label)}</div>${tradeBlock(t)}</div>`).join("") || "<p>No structure fits your capital and risk level for this stock.</p>"}
      ${d.blocked.length ? `<details><summary>Not available (and why)</summary><ul class="tight">${d.blocked.map((b) => `<li><b>${esc(b.label)}</b>: ${esc(b.reason)}</li>`).join("")}</ul></details>` : ""}`;
  } catch (e) { body.innerHTML = `<p>${esc(e.message)}</p>`; }
}

// ---------------------------------------------------------------- boot
document.addEventListener("click", (e) => {
  const el = e.target.closest("[data-tab],[data-goto],[data-ticker],[data-paper],[data-copy],[data-close],[data-q],[data-row],[data-saved]");
  if (!el) return;
  if (el.dataset.tab) return showTab(el.dataset.tab);
  if (el.dataset.goto) { e.preventDefault(); return showTab(el.dataset.goto); }
  if (el.dataset.ticker) return openTicker(el.dataset.ticker);
  if (el.dataset.paper) return paperTrade(window._trades[el.dataset.paper]);
  if (el.dataset.copy) { navigator.clipboard?.writeText(window._trades[el.dataset.copy].ticket.join("\n")); return toast("Ticket copied"); }
  if (el.dataset.close) return api(`/api/paper/${el.dataset.close}/close`, { method: "POST" }).then(loadPaper).catch((err) => toast(err.message));
  if (el.dataset.q) return sendChat(el.dataset.q);
  if (el.dataset.row) {
    const x = window._screen[Number(el.dataset.row)];
    $("#drawer").classList.remove("hidden");
    $("#drawer-body").innerHTML = `<div class="card-title">${esc(x.name)}<span class="sym">${esc(x.symbol)}</span></div><p><button class="link" data-ticker="${esc(x.symbol)}">Full analysis →</button></p>${tradeBlock(x.trade)}`;
    return;
  }
  if (el.dataset.saved) { writeCriteria(window._saved[Number(el.dataset.saved)].criteria); return runScreen(); }
});
$("#drawer-close").onclick = () => $("#drawer").classList.add("hidden");
$("#drawer").addEventListener("click", (e) => { if (e.target.id === "drawer") $("#drawer").classList.add("hidden"); });
document.addEventListener("keydown", (e) => { if (e.key === "Escape") $("#drawer").classList.add("hidden"); });
$("#risk").addEventListener("change", onRisk);
$("#risk").addEventListener("input", () => { state.risk = Number($("#risk").value); syncRisk(); });
$("#refresh-ideas").onclick = () => loadIdeas(true);
$("#idea-count").onchange = () => loadIdeas();
$("#profile-form").addEventListener("submit", submitProfile);
$("#screen-form").addEventListener("submit", (e) => runScreen(e));
$("#save-screen").onclick = () => { if (!$("#screen-form").save_name.value.trim()) return toast("Name the screen first"); runScreen(null, true); };
$("#chat-form").addEventListener("submit", (e) => { e.preventDefault(); const v = $("#chat-input").value; $("#chat-input").value = ""; sendChat(v); });
$("#refresh-paper").onclick = loadPaper;
$("#delete-profile").onclick = async () => {
  if (!confirm("Delete your saved profile and resume text from this computer? Paper trades are kept.")) return;
  try {
    await api("/api/profile", { method: "DELETE" });
    $("#profile-form").reset(); await loadProfile(); renderProfile();
    toast("Profile and resume deleted");
  } catch (err) { toast(err.message); }
};
// Static demo: say so while a control waits for the engine, so nothing looks dead.
window.addEventListener("charlie:engine", (e) => {
  $("#engine-status").classList.toggle("hidden", e.detail.ready);
  if (e.detail.error) toast("Charlie's engine couldn't load. Check your connection and try again.");
});
$("#reset-demo").onclick = () => {
  try { Object.keys(localStorage).filter((k) => k.startsWith("charlie:")).forEach((k) => localStorage.removeItem(k)); } catch (_) {}
  location.reload();
};
$("#footer-disclaimer").onclick = (e) => e.currentTarget.classList.toggle("open");
$("#ack-btn").onclick = () => { try { localStorage.setItem("charlie-ack", "1"); } catch (_) {} $("#ack").classList.add("hidden"); };

(async function boot() {
  try {
    const [meta, status] = await Promise.all([api("/api/meta"), api("/api/status")]);
    state.meta = meta;
    $("#footer-disclaimer").textContent = meta.disclaimer;
    $("#ack-text").textContent = meta.disclaimer;
    let acked = false; try { acked = localStorage.getItem("charlie-ack") === "1"; } catch (_) {}
    if (!acked) $("#ack").classList.remove("hidden");
    $("#chat-mode").textContent = status.static ? "Demo mode: rule-based answers on sample data."
      : status.llm ? "Claude is connected." : "Offline mode (rule-based). Add ANTHROPIC_API_KEY for full conversation.";
    if (status.static) {  // no uploads or Claude in the demo; show the sample banner, back link and reset
      $$(".server-only").forEach((el) => el.classList.add("hidden"));
      $$(".static-only").forEach((el) => el.classList.remove("hidden"));
    }
    await loadProfile();
    renderProfile();
    const tab = location.hash.slice(1);
    showTab(["today", "profile", "screener", "chat", "paper", "learn"].includes(tab) ? tab : "today");
    // Static demo: the first screen came from prebuilt answers; load the engine once it has painted.
    requestAnimationFrame(() => setTimeout(() => window.charlieStatic?.start(), 50));
  } catch (e) { $("#ideas").innerHTML = `<div class="panel">Couldn't start: ${esc(e.message)}</div>`; }
})();
