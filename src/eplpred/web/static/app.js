/* Premier League Predictor — front end (no libraries, works offline). */
"use strict";

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const SVG = "http://www.w3.org/2000/svg";

const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const pct = (v, d = 0) => (v == null ? "–" : `${(v * 100).toFixed(d)}%`);
const num = (v, d = 1) => (v == null ? "–" : Number(v).toFixed(d));
/* Round three shares to whole percents that always add up to 100
   (largest remainder), so 64.6 / 20.7 / 14.7 never shows as 65 + 21 + 15 = 101. */
function pct3(values) {
  const raw = values.map((v) => v * 100);
  const out = raw.map(Math.floor);
  const order = raw.map((v, i) => [v - Math.floor(v), i]).sort((a, b) => b[0] - a[0]);
  const missing = 100 - out.reduce((a, b) => a + b, 0);
  for (let k = 0; k < missing; k++) out[order[k][1]] += 1;
  return out.map((v) => `${v}%`);
}
const ordinal = (n) => {
  const s = ["th", "st", "nd", "rd"], v = n % 100;
  return n + (s[(v - 20) % 10] || s[v] || s[0]);
};
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

async function api(path) {
  const res = await fetch(path);
  const body = await res.json();
  if (!res.ok) throw new Error(body.error || res.statusText);
  return body;
}

/* ---------------------------------------------------------------- toast */
let toastTimer;
function toast(message) {
  const t = $("#toast");
  t.textContent = message;
  t.hidden = false;
  t.style.animation = "none";
  void t.offsetWidth; // restart the enter animation
  t.style.animation = "";
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (t.hidden = true), 2600);
}

/* -------------------------------------------------------------- tooltip */
const tip = {
  el: null,
  show(html, x, y) {
    this.el ??= $("#tooltip");
    this.el.innerHTML = html;
    this.el.hidden = false;
    const r = this.el.getBoundingClientRect();
    let left = x + 14, top = y + 14;
    if (left + r.width > innerWidth - 8) left = x - r.width - 14;
    if (top + r.height > innerHeight - 8) top = y - r.height - 14;
    this.el.style.left = `${Math.max(8, left)}px`;
    this.el.style.top = `${Math.max(8, top)}px`;
  },
  hide() { if (this.el) this.el.hidden = true; },
};
const tipRow = (color, key, val) =>
  `<div class="row"><span class="key">${color ? `<i style="background:${color}"></i>` : ""}${esc(key)}</span><span class="val">${val}</span></div>`;

/* -------------------------------------------------------- svg helpers */
function el(tag, attrs = {}, parent) {
  const node = document.createElementNS(SVG, tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  if (parent) parent.appendChild(node);
  return node;
}
function svgFor(container, height) {
  container.innerHTML = "";
  const width = Math.max(280, container.clientWidth);
  const svg = el("svg", { viewBox: `0 0 ${width} ${height}`, width, height, role: "img" }, container);
  return { svg, width, height };
}
function niceTicks(lo, hi, count = 5) {
  const span = hi - lo || 1;
  const step0 = span / count;
  const mag = 10 ** Math.floor(Math.log10(step0));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => span / s <= count) || 10 * mag;
  const ticks = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) ticks.push(+v.toFixed(10));
  return ticks;
}
function roundedBar(x, y, w, h, r = 4) {
  // Rounded only at the data end (right side), square at the baseline.
  r = Math.min(r, h / 2, Math.max(w, 0));
  return `M${x},${y}h${w - r}a${r},${r} 0 0 1 ${r},${r}v${h - 2 * r}a${r},${r} 0 0 1 ${-r},${r}h${-(w - r)}z`;
}

/* Horizontal bar chart: rows = [{label, value, color, tip}].
   In narrow containers the label sits above its bar so it's never cut off. */
function hbars(container, rows, { format = (v) => v, domain, labelWidth = 200, rowHeight = 34, ariaLabel = "" } = {}) {
  const stacked = container.clientWidth < 560;
  const rowH = stacked ? 40 : rowHeight;
  const height = rows.length * rowH + 8;
  const { svg, width } = svgFor(container, height);
  svg.setAttribute("aria-label", ariaLabel);
  const [lo, hi] = domain || [0, Math.max(...rows.map((r) => r.value))];
  const left = stacked ? 0 : labelWidth;
  const plotW = width - left - 64;
  const x = (v) => ((v - lo) / (hi - lo || 1)) * plotW;
  rows.forEach((r, i) => {
    const y = i * rowH + 4;
    const g = el("g", {}, svg);
    const w = Math.max(2, x(r.value));
    if (stacked) {
      const label = el("text", { x: 0, y: y + 12 }, g);
      label.textContent = r.label;
      el("path", { d: roundedBar(0, y + 19, w, 12), fill: r.color, class: "bar" }, g);
      const vt = el("text", { x: w + 8, y: y + 25, "dominant-baseline": "middle", class: "value-label" }, g);
      vt.textContent = format(r.value);
    } else {
      const label = el("text", { x: labelWidth - 12, y: y + rowH / 2, "text-anchor": "end", "dominant-baseline": "middle" }, g);
      label.textContent = r.label;
      el("path", { d: roundedBar(labelWidth, y + 7, w, rowH - 14), fill: r.color, class: "bar" }, g);
      const vt = el("text", { x: labelWidth + w + 8, y: y + rowH / 2, "dominant-baseline": "middle", class: "value-label" }, g);
      vt.textContent = format(r.value);
    }
    const hit = el("rect", { x: 0, y, width, height: rowH, class: "hit" }, g);
    hit.addEventListener("pointermove", (e) => tip.show(r.tip || `<strong>${esc(r.label)}</strong><br>${format(r.value)}`, e.clientX, e.clientY));
    hit.addEventListener("pointerleave", () => tip.hide());
  });
}

/* Line chart with crosshair tooltip.
   series = [{name, color, dashed, points:[{x, y, label?}]}]; x is a number (time ms or index). */
function lineChart(container, series, { height = 300, yFormat = (v) => v, xTicks, xTickFormat, yDomain, tipTitle, ariaLabel = "", markers = false, gapAfter = Infinity, diagonal = false, xDomain } = {}) {
  const { svg, width } = svgFor(container, height);
  svg.setAttribute("aria-label", ariaLabel);
  const m = { top: 12, right: 16, bottom: 30, left: 48 };
  const all = series.flatMap((s) => s.points);
  if (!all.length) return;
  const xs = all.map((p) => p.x), ys = all.map((p) => p.y);
  const [x0, x1] = xDomain || [Math.min(...xs), Math.max(...xs)];
  let [y0, y1] = yDomain || [Math.min(...ys), Math.max(...ys)];
  if (!yDomain) { const pad = (y1 - y0) * 0.08 || 1; y0 -= pad; y1 += pad; }
  const X = (v) => m.left + ((v - x0) / (x1 - x0 || 1)) * (width - m.left - m.right);
  const Y = (v) => m.top + (1 - (v - y0) / (y1 - y0 || 1)) * (height - m.top - m.bottom);

  const grid = el("g", { class: "grid" }, svg);
  for (const t of niceTicks(y0, y1, 4)) {
    el("line", { x1: m.left, x2: width - m.right, y1: Y(t), y2: Y(t) }, grid);
    const tx = el("text", { x: m.left - 8, y: Y(t), "text-anchor": "end", "dominant-baseline": "middle" }, svg);
    tx.textContent = yFormat(t);
  }
  const ticks = xTicks || niceTicks(x0, x1, 6);
  const maxLabels = Math.max(2, Math.floor((width - m.left - m.right) / 64));
  const every = Math.ceil(ticks.length / maxLabels);
  ticks.forEach((t, i) => {
    if (i % every) return;
    const tx = el("text", { x: X(t), y: height - 8, "text-anchor": "middle" }, svg);
    tx.textContent = xTickFormat ? xTickFormat(t) : t;
  });
  el("line", { x1: m.left, x2: width - m.right, y1: height - m.bottom, y2: height - m.bottom, class: "axis-line" }, svg);
  if (diagonal) el("line", { x1: X(x0), y1: Y(y0), x2: X(x1), y2: Y(y1), stroke: css("--text-3"), "stroke-dasharray": "4 4", "stroke-width": 1 }, svg);

  for (const s of series) {
    let d = "", prev = null;
    for (const p of s.points) {
      d += `${prev && p.x - prev.x <= gapAfter ? "L" : "M"}${X(p.x).toFixed(1)},${Y(p.y).toFixed(1)}`;
      prev = p;
    }
    el("path", { d, fill: "none", stroke: s.color, "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round", "stroke-dasharray": s.dashed ? "5 4" : "none" }, svg);
    if (markers) for (const p of s.points) el("circle", { cx: X(p.x), cy: Y(p.y), r: 4, fill: s.color, stroke: css("--surface"), "stroke-width": 2 }, svg);
  }

  // Crosshair + tooltip: nearest x across all series.
  const cross = el("line", { y1: m.top, y2: height - m.bottom, class: "crosshair", visibility: "hidden" }, svg);
  const dots = series.map((s) => el("circle", { r: 5, fill: s.color, stroke: css("--surface"), "stroke-width": 2, visibility: "hidden" }, svg));
  const hit = el("rect", { x: m.left, y: 0, width: width - m.left - m.right, height, class: "hit" }, svg);
  const sorted = series.map((s) => [...s.points].sort((a, b) => a.x - b.x));
  const nearest = (pts, xv) => {
    let lo = 0, hi = pts.length - 1;
    if (!pts.length) return null;
    while (lo < hi) { const mid = (lo + hi) >> 1; if (pts[mid].x < xv) lo = mid + 1; else hi = mid; }
    const a = pts[Math.max(0, lo - 1)], b = pts[lo];
    const p = Math.abs(a.x - xv) <= Math.abs(b.x - xv) ? a : b;
    return Math.abs(p.x - xv) <= gapAfter ? p : null;
  };
  hit.addEventListener("pointermove", (e) => {
    const box = svg.getBoundingClientRect();
    const px = ((e.clientX - box.left) / box.width) * width;
    const xv = x0 + ((px - m.left) / (width - m.left - m.right)) * (x1 - x0);
    const found = sorted.map((pts) => nearest(pts, xv));
    const anchor = found.find(Boolean);
    if (!anchor) return;
    cross.setAttribute("x1", X(anchor.x)); cross.setAttribute("x2", X(anchor.x));
    cross.setAttribute("visibility", "visible");
    found.forEach((p, i) => {
      if (!p) return dots[i].setAttribute("visibility", "hidden");
      dots[i].setAttribute("cx", X(p.x)); dots[i].setAttribute("cy", Y(p.y)); dots[i].setAttribute("visibility", "visible");
    });
    const rows = series.map((s, i) => (found[i] ? tipRow(s.color, s.name, yFormat(found[i].y)) : "")).join("");
    tip.show(`<strong>${esc(tipTitle ? tipTitle(anchor) : anchor.x)}</strong>${rows}`, e.clientX, e.clientY);
  });
  hit.addEventListener("pointerleave", () => {
    tip.hide(); cross.setAttribute("visibility", "hidden"); dots.forEach((d) => d.setAttribute("visibility", "hidden"));
  });
}

/* ------------------------------------------------------------- router */
const views = ["predict", "teams", "models", "seasons", "about"];
const loaded = new Set();
let current = null;

function moveThumb(group) {
  const active = $('[aria-current="page"], [aria-pressed="true"]', group);
  const thumb = $(".segmented-thumb", group);
  if (!active || !thumb) return;
  thumb.style.width = `${active.offsetWidth}px`;
  thumb.style.transform = `translateX(${active.offsetLeft}px)`;
}

function route() {
  const name = views.includes(location.hash.slice(1)) ? location.hash.slice(1) : "predict";
  if (name === current) return;
  current = name;
  for (const v of $$(".view")) v.hidden = v.dataset.view !== name;
  $$(".chrome .segmented a").forEach((a) => (a.dataset.view === name ? a.setAttribute("aria-current", "page") : a.removeAttribute("aria-current")));
  moveThumb($(".chrome .segmented"));
  $(`.chrome .segmented a[data-view="${name}"]`)?.scrollIntoView({ block: "nearest", inline: "nearest" });
  window.scrollTo({ top: 0 });
  if (!loaded.has(name)) {
    loaded.add(name);
    ({ predict: initPredict, teams: initTeams, models: initModels, seasons: initSeasons, about: async () => {} })[name]().catch((err) => toast(err.message));
  } else {
    redraw[name]?.();
  }
}
const redraw = {};

/* ------------------------------------------------------------ overview */
let overviewPromise;
const overview = () => (overviewPromise ??= api("/api/overview"));

/* ------------------------------------------------------------- predict */
let predictToken = 0;

async function initPredict() {
  const o = await overview();
  $$('[data-bind="matches"]').forEach((n) => (n.textContent = o.matches.toLocaleString("en")));
  const options = o.teams_now.map((t) => `<option>${esc(t)}</option>`).join("");
  $("#home-team").innerHTML = options;
  $("#away-team").innerHTML = options;
  [$("#home-team").value, $("#away-team").value] = o.default_fixture;
  let shown = [...o.default_fixture]; // the fixture currently in the two boxes
  const onPick = (changed, other) => () => {
    // Picking the team that's already on the other side swaps the two.
    if (changed.value === other.value) {
      other.value = changed === $("#home-team") ? shown[0] : shown[1];
      toast("Swapped home and away");
    }
    shown = [$("#home-team").value, $("#away-team").value];
    runPredict();
  };
  $("#home-team").addEventListener("change", onPick($("#home-team"), $("#away-team")));
  $("#away-team").addEventListener("change", onPick($("#away-team"), $("#home-team")));
  $("#swap").addEventListener("click", () => {
    const h = $("#home-team"), a = $("#away-team");
    [h.value, a.value] = [a.value, h.value];
    shown = [h.value, a.value];
    $("#swap").classList.toggle("turned");
    runPredict();
  });
  await runPredict();
}

async function runPredict() {
  const home = $("#home-team").value, away = $("#away-team").value;
  if (home === away) { toast("Pick two different teams"); return; }
  const token = ++predictToken; // newer requests win, older answers are ignored
  const card = $("#result");
  card.classList.add("loading");
  try {
    const p = await api(`/api/predict?home=${encodeURIComponent(home)}&away=${encodeURIComponent(away)}`);
    if (token !== predictToken) return;
    renderPrediction(p);
  } catch (err) {
    if (token === predictToken) toast(err.message);
  } finally {
    if (token === predictToken) card.classList.remove("loading");
  }
}

function renderPrediction(p) {
  const { H, D, A } = p.probabilities;
  const [ph, pd, pa] = pct3([H, D, A]);
  $("#p-home").textContent = ph;
  $("#p-draw").textContent = pd;
  $("#p-away").textContent = pa;
  $("#l-home").textContent = `${p.home} win`;
  $("#l-away").textContent = `${p.away} win`;
  const segs = $$("#prob-bar .seg");
  [H, D, A].forEach((v, i) => (segs[i].style.width = `calc(${(v * 100).toFixed(2)}% - 1.34px)`));
  $("#prob-bar").setAttribute("aria-label", `${p.home} win ${ph}, draw ${pd}, ${p.away} win ${pa}`);
  $("#xg-home").textContent = num(p.expected_goals.home, 2);
  $("#xg-away").textContent = num(p.expected_goals.away, 2);

  const maxP = Math.max(...p.top_scores.map((s) => s.probability));
  $("#scores").innerHTML = p.top_scores
    .map((s) => `<li><span class="score">${esc(s.score)}</span><span class="mini-track"><span class="mini-fill" data-w="${(s.probability / maxP) * 100}"></span></span><span class="pct">${pct(s.probability, 1)}</span></li>`)
    .join("");
  requestAnimationFrame(() => $$("#scores .mini-fill").forEach((f) => (f.style.width = `${f.dataset.w}%`)));

  const h = p.home_stats, a = p.away_stats;
  const pos = (v) => (v == null ? "–" : ordinal(Math.round(v)));
  const rows = [
    ["Elo rating", h.elo, a.elo, (v) => num(v, 0), 1],
    ["Points per game, last 5", h.form, a.form, (v) => num(v, 1), 1],
    ["Points per game, last 5 home / away games", h.venue_form, a.venue_form, (v) => num(v, 1), 1],
    ["League position now", h.position, a.position, pos, -1],
    ["Last season", h.promoted ? 21 : h.prev_position, a.promoted ? 21 : a.prev_position, null, -1],
    ["Goals scored per game", h.goals_for, a.goals_for, (v) => num(v, 2), 1],
    ["Goals conceded per game", h.goals_against, a.goals_against, (v) => num(v, 2), -1],
    ["Share of shots on target", h.sot_share, a.sot_share, (v) => pct(v), 1],
    ["Starting XI strength (FPL influence)", h.xi_influence, a.xi_influence, (v) => num(v, 0), 1],
    ["Starting XI price (FPL, £m)", h.xi_value, a.xi_value, (v) => num(v, 1), 1],
    ["Top-5 players not starting", h.key_missing, a.key_missing, (v) => num(v, 0), -1],
  ].filter((r) => r[1] != null || r[2] != null);
  const html = [`<div class="compare-row compare-head"><span class="home-ink">${esc(p.home)}</span><span class="label"></span><span class="v right away-ink">${esc(p.away)}</span></div>`];
  for (const [label, hv, av, fmt, dir] of rows) {
    const better = hv == null || av == null || hv === av ? 0 : (hv - av) * dir > 0 ? 1 : -1;
    const f = fmt || ((v) => (v === 21 ? "Promoted" : pos(v)));
    html.push(`<div class="compare-row"><span class="v ${better === 1 ? "better home" : ""}">${f(hv)}</span><span class="label">${esc(label)}</span><span class="v right ${better === -1 ? "better away" : ""}">${f(av)}</span></div>`);
  }
  $("#compare").innerHTML = html.join("");
  renderLineups(p);
  const h2h = p.h2h_meetings
    ? `Head-to-head: ${p.home} took ${num(p.h2h_home_ppg, 1)} points per game from the last ${p.h2h_meetings} meetings. `
    : "These teams haven't met recently. ";
  $("#predict-footnote").textContent = `${h2h}Model: ${p.model}, using data up to ${p.as_of}.`;
}

function renderLineups(p) {
  const card = $("#lineup-card");
  card.hidden = !p.home_lineup;
  if (!p.home_lineup) return;
  const max = Math.max(...[p.home_lineup, p.away_lineup].flatMap((l) => l.players.map((x) => x.influence_p90 || 0)));
  const side = (team, l, cls) => `
    <div class="lineup">
      <p class="section-label ${cls}">${esc(team)}</p>
      <ol>${l.players.map((x) => `<li><span class="pname">${esc(x.name)}</span><span class="track"><span class="fill ${cls}-fill" style="width:${((x.influence_p90 || 0) / max) * 100}%"></span></span><span class="num">${x.influence_p90 == null ? "new" : num(x.influence_p90, 1)}</span></li>`).join("")}</ol>
      ${l.missing.length ? `<p class="missing">Not in this XI: ${l.missing.map(esc).join(", ")}</p>` : ""}
    </div>`;
  $("#lineups").innerHTML = side(p.home, p.home_lineup, "home") + side(p.away, p.away_lineup, "away");
}

/* --------------------------------------------------------------- teams */
const selected = new Map(); // team -> colour slot (colour follows the team, not its rank)
let teamsData;

async function initTeams() {
  teamsData = await api("/api/teams");
  const ranking = teamsData.ranking;
  const lo = Math.min(...ranking.map((r) => r.elo)) - 60, hi = Math.max(...ranking.map((r) => r.elo));
  $("#ranking").innerHTML = ranking
    .map((r, i) => `<li title="Last season: ${r.position ? ordinal(r.position) : "–"}"><span class="rank">${i + 1}</span><span class="name">${esc(r.team)}</span><span class="track"><span class="fill" style="width:${((r.elo - lo) / (hi - lo)) * 100}%"></span></span><span class="num">${Math.round(r.elo)}</span></li>`)
    .join("");
  $("#team-chips").innerHTML = ranking
    .map((r) => `<button type="button" class="chip" aria-pressed="false" data-team="${esc(r.team)}"><span class="swatch"></span>${esc(r.team)}</button>`)
    .join("");
  $("#team-chips").addEventListener("click", (e) => {
    const chip = e.target.closest(".chip");
    if (!chip) return;
    const team = chip.dataset.team;
    if (selected.has(team)) selected.delete(team);
    else if (selected.size >= 4) return toast("Up to 4 teams at a time");
    else selected.set(team, [0, 1, 2, 3].find((s) => ![...selected.values()].includes(s)));
    drawElo();
  });
  ranking.slice(0, 3).forEach((r, i) => selected.set(r.team, i));
  await drawElo();
  redraw.teams = drawElo;
}

const eloCache = new Map();
async function drawElo() {
  for (const chip of $$("#team-chips .chip")) {
    const slot = selected.get(chip.dataset.team);
    chip.setAttribute("aria-pressed", slot != null);
    $(".swatch", chip).style.background = slot != null ? seriesColor(slot) : "";
  }
  const need = [...selected.keys()].filter((t) => !eloCache.has(t));
  if (need.length) {
    const res = await api(`/api/elo?${need.map((t) => `team=${encodeURIComponent(t)}`).join("&")}`);
    for (const [t, pts] of Object.entries(res.series)) eloCache.set(t, pts);
  }
  const series = [...selected.entries()].map(([team, slot]) => ({
    name: team,
    color: seriesColor(slot),
    points: eloCache.get(team).map((p) => ({ x: Date.parse(p.date), y: p.elo, label: p.date })),
  }));
  if (!series.length) { $("#elo-chart").innerHTML = '<p class="muted">Pick a team above.</p>'; return; }
  const years = [];
  for (let y = 2001; y <= 2026; y += 1) years.push(Date.UTC(y, 0, 1));
  lineChart($("#elo-chart"), series, {
    height: innerWidth > 860 ? 420 : 300,
    yFormat: (v) => Math.round(v),
    xTicks: years,
    xTickFormat: (t) => `'${String(new Date(t).getUTCFullYear()).slice(2)}`,
    gapAfter: 150 * 864e5,
    tipTitle: (p) => new Date(p.x).toLocaleDateString("en-GB", { month: "short", year: "numeric" }),
    ariaLabel: `Elo rating over time for ${series.map((s) => s.name).join(", ")}`,
  });
}
function seriesColor(slot) {
  return [css("--home"), css("--away"), "#1baf7a", "#8b7fe8"][slot];
}

/* -------------------------------------------------------------- models */
let modelsData, metric = "accuracy";
const METRICS = {
  accuracy: { label: "Accuracy", note: "Share of matches where the most likely result happened. Higher is better.", fmt: (v) => pct(v, 1), higher: true },
  rps: { label: "RPS", note: "Ranked Probability Score, the standard football metric. Lower is better.", fmt: (v) => v.toFixed(4), higher: false },
  log_loss: { label: "Log loss", note: "Punishes confident wrong predictions. Lower is better.", fmt: (v) => v.toFixed(3), higher: false },
};
const shortName = (m) => m.replace(" (Bet365, benchmark)", " (Bet365)").replace(" (logistic regression)", "").replace("Baseline: home-win rate", "Always home win");

async function initModels() {
  modelsData = await api("/api/models");
  const o = await overview();
  $("#model-tiles").innerHTML = [
    [pct(o.best_accuracy, 1), `Our best model (${o.best_model.replace(" model", "")})`],
    [pct(o.bookmaker_accuracy, 1), "Bookmaker, the benchmark"],
    [pct(o.baseline_accuracy, 1), "Always pick the home team"],
    [o.test_matches.toLocaleString("en"), "Test matches, never seen in training"],
  ].map(([v, l]) => `<div class="tile"><span class="tile-value">${v}</span><span class="tile-label">${esc(l)}</span></div>`).join("");

  const sw = $("#metric-switch");
  sw.addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    metric = b.dataset.metric;
    drawModels();
  });
  drawModels();
  redraw.models = drawModels;
}

function colorForModel(name) {
  const d = modelsData;
  if (name === d.best_model) return css("--home");
  if (name === d.bookmaker) return css("--away");
  return css("--draw");
}

function drawModels() {
  const d = modelsData, M = METRICS[metric];
  $$("#metric-switch button").forEach((b) => b.setAttribute("aria-pressed", b.dataset.metric === metric));
  moveThumb($("#metric-switch"));
  $("#metric-note").textContent = M.note;

  const rows = [...d.overall].sort((a, b) => (M.higher ? b[metric] - a[metric] : a[metric] - b[metric]));
  const vals = rows.map((r) => r[metric]);
  const lo = Math.min(...vals), hi = Math.max(...vals);
  hbars($("#model-bars"), rows.map((r) => ({
    label: shortName(r.model),
    value: r[metric],
    color: colorForModel(r.model),
    tip: `<strong>${esc(r.model)}</strong>${tipRow(null, "Accuracy", pct(r.accuracy, 1))}${tipRow(null, "RPS", r.rps.toFixed(4))}${tipRow(null, "Log loss", r.log_loss.toFixed(3))}${tipRow(null, "Matches", r.matches.toLocaleString("en"))}`,
  })), {
    format: M.fmt,
    domain: M.higher ? [0, Math.max(0.6, hi * 1.05)] : [lo - (hi - lo) * 0.6, hi],
    labelWidth: 190,
    ariaLabel: `${M.label} by model`,
  });

  // Season by season
  const seasons = [...new Set(d.by_season.map((r) => r.season_label))];
  const pick = [
    [d.best_model, css("--home"), false],
    [d.bookmaker, css("--away"), false],
    [d.baseline, css("--text-3"), true],
  ];
  const series = pick.map(([model, color, dashed]) => ({
    name: shortName(model), color, dashed,
    points: d.by_season.filter((r) => r.model === model).map((r) => ({ x: seasons.indexOf(r.season_label), y: r.accuracy })),
  }));
  $("#season-legend").innerHTML = series.map((s) => `<span><i class="${s.dashed ? "dashed" : ""}" style="background:${s.color}"></i>${esc(s.name)}</span>`).join("");
  lineChart($("#season-chart"), series, {
    height: 280, markers: true, gapAfter: 1,
    yDomain: [0.35, 0.65], yFormat: (v) => pct(v),
    xTicks: seasons.map((_, i) => i), xTickFormat: (i) => seasons[i]?.slice(2),
    tipTitle: (p) => seasons[p.x],
    ariaLabel: "Accuracy per test season",
  });

  // Importance
  const imp = d.importance;
  hbars($("#importance"), imp.map((r) => ({ label: r.feature, value: r.importance, color: css("--home") })), {
    format: (v) => v.toFixed(4), labelWidth: 250, rowHeight: 28, ariaLabel: "Feature importance",
  });

  // Confusion matrix
  const names = { H: "Home win", D: "Draw", A: "Away win" };
  const cm = d.confusion.matrix;
  let html = `<div class="confusion"><span></span>${d.confusion.labels.map((l) => `<span class="hdr">${names[l]}</span>`).join("")}`;
  cm.forEach((row, i) => {
    const total = row.reduce((a, b) => a + b, 0);
    html += `<span class="rowhdr">${names[d.confusion.labels[i]]}</span>`;
    row.forEach((v) => {
      const share = total ? v / total : 0;
      const ink = share > 0.5 ? "#fff" : "var(--text)";
      html += `<span class="cell" style="background:color-mix(in srgb, var(--home) ${Math.round(share * 100)}%, var(--fill));color:${ink}">${pct(share)}<small>${v.toLocaleString("en")}</small></span>`;
    });
  });
  html += `<span></span><span class="axis">Predicted →  ·  rows: what actually happened</span></div>`;
  $("#confusion").innerHTML = html;

  // Calibration
  const cal = Object.entries(d.calibration_home_win).map(([model, pts]) => ({
    name: shortName(model), color: colorForModel(model),
    points: pts.map((p) => ({ x: p.predicted, y: p.actual, n: p.n })),
  }));
  $("#calib-legend").innerHTML = cal.map((s) => `<span><i style="background:${s.color}"></i>${esc(s.name)}</span>`).concat('<span><i class="dashed"></i>Perfect</span>').join("");
  lineChart($("#calibration"), cal, {
    height: 260, markers: true, diagonal: true, xDomain: [0, 1], yDomain: [0, 1],
    xTicks: [0, 0.2, 0.4, 0.6, 0.8, 1], xTickFormat: (v) => pct(v), yFormat: (v) => pct(v),
    gapAfter: 0.5, tipTitle: (p) => `Predicted ≈ ${pct(p.x)}`,
    ariaLabel: "Calibration of home-win probabilities",
  });

  // Extra data experiment (Poisson model, same test seasons)
  if (d.extended) {
    $("#extended-card").hidden = false;
    const ext = d.extended.filter((r) => r.model === "Poisson goals model" || r.feature_set === "Bookmaker");
    const label = (r) => (r.feature_set === "Bookmaker" ? "Bookmaker (Bet365)" : r.feature_set === "Base (49 features)" ? "Base features" : `Base ${r.feature_set}`);
    hbars($("#extended-chart"), ext.map((r) => ({
      label: label(r),
      value: r.accuracy,
      color: r.feature_set === "Bookmaker" ? css("--away") : r.feature_set.includes("Base") ? css("--draw") : css("--home"),
      tip: `<strong>${esc(label(r))}</strong>${tipRow(null, "Accuracy", pct(r.accuracy, 1))}${tipRow(null, "RPS", r.rps.toFixed(4))}${
        r.rps_change == null ? "" : tipRow(null, "RPS change", `${r.rps_change > 0 ? "+" : ""}${r.rps_change.toFixed(4)}`)}`,
    })), { format: (v) => pct(v, 1), domain: [0, 0.6], labelWidth: 190, rowHeight: 30, ariaLabel: "Accuracy with extra data" });
    const pl = ext.find((r) => r.feature_set === "+ players"), fa = ext.find((r) => r.feature_set === "+ fatigue");
    $("#extended-note").textContent = pl && fa
      ? `Player data helped a little (RPS ${pl.rps_change.toFixed(4)}, 95% range ${pl.rps_change_low.toFixed(4)} to ${pl.rps_change_high.toFixed(4)}). Fatigue data from cup, European and international matches did not (RPS +${fa.rps_change.toFixed(4)}). The app uses base + player features.`
      : "";
  }

  // Original comparison
  const orig = [...d.original].sort((a, b) => b.accuracy - a.accuracy);
  hbars($("#original"), orig.map((r) => ({
    label: r.model.startsWith("Original") ? "Version 1 (random forest)" : shortName(r.model),
    value: r.accuracy,
    color: r.model.startsWith("Original") ? css("--text-2") : r.model === d.baseline ? css("--draw") : r.model === d.bookmaker ? css("--away") : css("--home"),
  })), { format: (v) => pct(v, 1), domain: [0, 0.7], labelWidth: 190, rowHeight: 28, ariaLabel: "Accuracy on version 1's test matches" });
}

/* ------------------------------------------------------------- seasons */
let seasonData, matchLimit = 40;
const CHECK = '<svg viewBox="0 0 12 12"><path d="M2.5 6.5l2.3 2.3 4.7-5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>';
const CROSS = '<svg viewBox="0 0 12 12"><path d="M3 3l6 6M9 3l-6 6" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>';

async function initSeasons() {
  const { seasons } = await api("/api/seasons");
  const pick = $("#season-pick");
  pick.innerHTML = [...seasons].reverse().map((s) => `<option value="${s.label}">${s.label}${s.tested ? "" : " (table only)"}</option>`).join("");
  pick.addEventListener("change", loadSeason);
  $("#team-filter").addEventListener("change", () => { matchLimit = 40; drawMatches(); });
  $("#show-more").addEventListener("click", () => { matchLimit += 60; drawMatches(); });
  await loadSeason();
}

async function loadSeason() {
  const label = $("#season-pick").value;
  seasonData = await api(`/api/season?label=${encodeURIComponent(label)}`);
  if (seasonData.label !== $("#season-pick").value) return;
  const s = seasonData, total = s.outcomes.H + s.outcomes.D + s.outcomes.A;
  const tiles = [
    [s.table[0].team, `Champions, ${s.table[0].points} points`, true],
    [num(s.goals_per_match, 2), "Goals per match"],
    [pct(s.outcomes.H / total), "Home wins"],
    s.matches ? [pct(s.accuracy, 1), `Model accuracy (bookmaker ${pct(s.book_accuracy, 1)})`] : ["–", "Not a test season (used for training)"],
  ];
  $("#season-tiles").innerHTML = tiles.map(([v, l, small]) => `<div class="tile"><span class="tile-value ${small ? "small-text" : ""}">${esc(v)}</span><span class="tile-label">${esc(l)}</span></div>`).join("");
  const n = s.table.length;
  $("#league-table").innerHTML = `<thead><tr><th>#</th><th>Team</th><th>P</th><th>W</th><th>D</th><th>L</th><th>GD</th><th>Pts</th></tr></thead><tbody>${s.table
    .map((r) => `<tr class="${r.position <= 4 ? "zone-top" : r.position > n - 3 ? "zone-bottom" : ""}"><td>${r.position}</td><td>${esc(r.team)}</td><td>${r.played}</td><td>${r.won}</td><td>${r.drawn}</td><td>${r.lost}</td><td>${r.gd > 0 ? "+" : ""}${r.gd}</td><td>${r.points}</td></tr>`)
    .join("")}</tbody>`;
  const filter = $("#team-filter");
  filter.innerHTML = `<option value="">All teams</option>` + s.table.map((r) => r.team).sort().map((t) => `<option>${esc(t)}</option>`).join("");
  $("#team-filter-wrap").hidden = !s.matches;
  matchLimit = 40;
  drawMatches();
}

function drawMatches() {
  const s = seasonData, list = $("#match-list");
  if (!s.matches) {
    list.innerHTML = "";
    $("#matches-note").textContent = "Seasons before 2014-15 were only used for training, so there are no honest predictions to show.";
    $("#show-more").hidden = true;
    return;
  }
  const team = $("#team-filter").value;
  const rows = s.matches.filter((m) => !team || m.home === team || m.away === team);
  const right = rows.filter((m) => m.predicted === m.result).length;
  $("#matches-note").textContent = `Made before kick-off by a model trained only on earlier seasons. ${right} of ${rows.length} right (${pct(right / rows.length)}).`;
  list.innerHTML = rows.slice(0, matchLimit).map((m) => {
    const ok = m.predicted === m.result;
    const label = { H: `${m.home} win`, D: "Draw", A: `${m.away} win` }[m.predicted];
    return `<li class="match" title="Model's pick: ${esc(label)}">
      <div class="teams"><div class="line"><span class="names">${esc(m.home)} <span class="score">${esc(m.score)}</span> ${esc(m.away)}</span></div><span class="date">${m.date}</span></div>
      <div><div class="mini" aria-label="Home ${pct(m.prob.H)}, draw ${pct(m.prob.D)}, away ${pct(m.prob.A)}"><span style="width:${m.prob.H * 100}%;background:var(--home)"></span><span style="width:${m.prob.D * 100}%;background:var(--draw)"></span><span style="width:${m.prob.A * 100}%;background:var(--away)"></span></div>
      <div class="mini-labels">${pct3([m.prob.H, m.prob.D, m.prob.A]).map((v) => `<span>${v}</span>`).join("")}</div></div>
      <span class="mark ${ok ? "ok" : "no"}" role="img" aria-label="${ok ? "Correct" : "Wrong"}">${ok ? CHECK : CROSS}</span></li>`;
  }).join("");
  $("#show-more").hidden = rows.length <= matchLimit;
}

/* ---------------------------------------------------------------- boot */
window.addEventListener("hashchange", route);
let resizeTimer;
window.addEventListener("resize", () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => {
    moveThumb($(".chrome .segmented"));
    if (loaded.has("models")) moveThumb($("#metric-switch"));
    redraw[current]?.();
  }, 120);
});
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => redraw[current]?.());
document.fonts?.ready.then(() => moveThumb($(".chrome .segmented")));
route();
