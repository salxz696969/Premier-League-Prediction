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

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/* Fetch JSON from our server. While the server is still starting it answers
   503 "loading": wait for it (the start-up screen shows progress) and retry.
   A dropped connection is retried a few times before giving up. */
async function api(path) {
  for (let attempt = 0; ; attempt++) {
    let res;
    try {
      res = await fetch(path);
    } catch {
      if (attempt < 3) { await sleep(600 * (attempt + 1)); continue; }
      throw new Error("Can't reach the app server. Is it still running?");
    }
    let body = null;
    try { body = await res.json(); } catch { /* not JSON, e.g. a proxy error page */ }
    if (res.status === 503 && body?.loading) { await whenReady(); continue; }
    if (!res.ok) throw new Error(body?.error || `The server answered ${res.status} ${res.statusText}`.trim());
    if (body === null) throw new Error("The server sent an answer that couldn't be read");
    return body;
  }
}

/* ------------------------------------------------------------ start-up */
let readyPromise;
function whenReady() {
  return (readyPromise ??= (async () => {
    const boot = $("#boot");
    const showTimer = setTimeout(() => { boot.hidden = false; }, 250); // no flash when already ready
    for (;;) {
      let st;
      try {
        const res = await fetch("/healthz", { cache: "no-store" });
        st = await res.json();
      } catch {
        st = { status: "offline" };
      }
      if (st.status === "ok") break;
      renderBoot(st);
      if (st.status === "error") { clearTimeout(showTimer); boot.hidden = false; await new Promise(() => {}); }
      await sleep(400);
    }
    clearTimeout(showTimer);
    if (!boot.hidden) {
      renderBoot({ status: "loading", done: BOOT_STEPS.length, total: BOOT_STEPS.length });
      await sleep(250);
      boot.classList.add("leaving");
      await sleep(420);
      boot.hidden = true;
    }
  })());
}
const BOOT_STEPS = ["Loading matches and features", "Training the model with player data", "Loading the results",
  "Preparing matches, tables and players", "Preparing the evaluation and the report"];
function renderBoot(st) {
  const done = st.done ?? 0, total = st.total ?? BOOT_STEPS.length;
  $("#boot-fill").style.width = `${Math.max(4, ((done + (st.status === "loading" && done < total ? 0.5 : 0)) / total) * 100)}%`;
  $("#boot-steps").innerHTML = BOOT_STEPS.map((step, i) => `<li class="${i < done ? "done" : i === done ? "now" : ""}"><span class="boot-dot" aria-hidden="true">${i < done ? CHECK : ""}</span>${esc(step)}</li>`).join("");
  const sub = $("#boot-sub");
  if (st.status === "offline") sub.textContent = "Can't reach the app server yet. Retrying…";
  else if (st.status === "error") sub.textContent = `Start-up failed: ${st.error}. Check the terminal for details.`;
  else sub.textContent = "Getting everything ready. This takes about 15 to 30 seconds.";
  $("#boot").classList.toggle("failed", st.status === "error");
  $("#boot-retry").hidden = st.status !== "error";
}

/* ------------------------------------------------------------ skeletons */
const skLine = (w, cls = "") => `<span class="sk ${cls}" style="width:${w}%"></span>`;
function skeletonHTML(spec) {
  const [kind, a = 6, b = 6] = spec.split(":");
  const n = +a, cols = +b;
  const rep = (k, f) => Array.from({ length: k }, (_, i) => f(i)).join("");
  const w = (i, base = 55, span = 35) => base + ((i * 37) % span);
  switch (kind) {
    case "chart": return `<div class="sk sk-block" style="height:${n}px"></div>`;
    case "tiles": return `<div class="sk-tiles">${rep(n, () => `<div class="sk-tile">${skLine(40, "big")}${skLine(70)}</div>`)}</div>`;
    case "chips": return `<div class="sk-chips">${rep(n, (i) => `<span class="sk sk-chip" style="width:${60 + ((i * 29) % 50)}px"></span>`)}</div>`;
    case "lines": return `<div class="sk-lines">${rep(n, (i) => skLine(w(i)))}</div>`;
    case "bars": return `<div class="sk-lines">${rep(n, (i) => `<div class="sk-row">${skLine(10)}${skLine(100 - i * 12, "bar")}</div>`)}</div>`;
    case "rows": return rep(n, (i) => `<div class="sk-row">${skLine(4)}<span class="sk sk-circle"></span>${skLine(w(i, 30, 25))}${skLine(28, "bar")}</div>`);
    case "players": return rep(n, (i) => `<div class="sk-row tall"><span class="sk sk-circle big"></span><span class="sk-stack">${skLine(w(i, 35, 30))}${skLine(25, "thin")}</span>${skLine(8)}${skLine(8)}${skLine(8)}</div>`);
    case "matches": return `<div class="card day">${skLine(30, "head")}${rep(n, (i) => `<div class="sk-match"><span class="sk-side home">${skLine(w(i, 45, 40))}<span class="sk sk-circle"></span></span><span class="sk sk-score"></span><span class="sk-side">${"<span class=\"sk sk-circle\"></span>"}${skLine(w(i + 3, 45, 40))}</span></div>`)}</div>`;
    case "trows": return `<tbody>${rep(n, (i) => `<tr class="sk-tr">${rep(cols, (j) => `<td>${skLine(j === 1 ? w(i, 50, 40) : 60)}</td>`)}</tr>`)}</tbody>`;
    case "doc": return `<div class="sk-lines doc">${skLine(55, "big")}${rep(3, (p) => `${skLine(35, "head")}${rep(5, (i) => skLine(i === 4 ? 60 : 92 + (i % 2) * 6))}`)}</div>`;
    case "slide": return `<div class="sk sk-block slide"></div>`;
    case "sheet": return `<div class="sk-sheet"><div class="sk-score-board"><span class="sk sk-circle huge"></span><span class="sk sk-goals"></span><span class="sk sk-circle huge"></span></div>${skLine(100, "tabs")}<div class="card-lite">${rep(6, (i) => `<div class="sk-row">${skLine(8)}${skLine(30)}${skLine(8)}</div>${skLine(100, "thin")}`)}</div><div class="card-lite">${rep(3, (i) => skLine(w(i)))}</div></div>`;
    default: return "";
  }
}
function paintSkeletons(root) {
  for (const el of $$("[data-sk]", root)) {
    if (!el.children.length && !el.textContent.trim()) el.innerHTML = skeletonHTML(el.dataset.sk);
  }
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
function hbars(container, rows, { format = (v) => v, domain, labelWidth = 200, rowHeight = 34, ariaLabel = "", allowStack = true } = {}) {
  const stacked = allowStack && container.clientWidth < 560;
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
      // Shorten labels that don't fit their column (e.g. small slides)
      const room = labelWidth - 14;
      if (label.getComputedTextLength && label.getComputedTextLength() > room) {
        let t = r.label;
        while (t.length > 3 && label.getComputedTextLength() > room) { t = t.slice(0, -1); label.textContent = `${t.trimEnd()}…`; }
      }
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
const views = ["predict", "matches", "players", "teams", "models", "evaluation", "data", "report", "slides", "about"];
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
    const view = $(`#view-${name}`);
    $(".load-error", view)?.remove();
    paintSkeletons(view);
    view.setAttribute("aria-busy", "true");
    ({ predict: initPredict, teams: initTeams, models: initModels, evaluation: initEvaluation, matches: initMatches, players: initPlayers, data: initData, report: initReport, slides: initSlides, about: async () => {} })[name]()
      .catch((err) => showLoadError(view, name, err))
      .finally(() => view.removeAttribute("aria-busy"));
  } else {
    redraw[name]?.();
  }
}
const redraw = {};

/* A page that failed to load says why and offers to try again. */
function showLoadError(view, name, err) {
  console.warn(err);
  $$("[data-sk]", view).forEach((el) => { if ($(".sk", el)) el.innerHTML = ""; });
  const box = document.createElement("div");
  box.className = "load-error card";
  box.setAttribute("role", "alert");
  box.innerHTML = `<p><b>This page couldn't load.</b><br><span class="muted">${esc(err.message)}</span></p><button type="button" class="button">Try again</button>`;
  $("button", box).addEventListener("click", () => { loaded.delete(name); current = null; box.remove(); route(); });
  (view.querySelector(".hero") || view.firstElementChild).after(box);
  view.classList.add("failed");
  $("button", box).addEventListener("click", () => view.classList.remove("failed"));
}

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
  Object.assign(BADGES, o.badges);
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
  $("#xg-switch").addEventListener("click", (ev) => {
    const b = ev.target.closest("button");
    if (!b) return;
    xgSide = b.dataset.side;
    drawXg();
  });
  await runPredict();
}

async function runPredict() {
  const home = $("#home-team").value, away = $("#away-team").value;
  $("#home-crest").innerHTML = crest(home, "large");
  $("#away-crest").innerHTML = crest(away, "large");
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
  renderExplain(p);
  redraw.predict = () => explainData && renderExplain(explainData.p);
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
  Object.assign(BADGES, (await overview()).badges);
  teamsData = await api("/api/teams");
  const ranking = teamsData.ranking;
  const lo = Math.min(...ranking.map((r) => r.elo)) - 60, hi = Math.max(...ranking.map((r) => r.elo));
  $("#ranking").innerHTML = ranking
    .map((r, i) => `<li title="Last season: ${r.position ? ordinal(r.position) : "–"}"><span class="rank">${i + 1}</span><span class="name">${crest(r.team, "small")}<span>${BADGES[r.team] ? teamName(BADGES[r.team]) : esc(r.team)}</span></span><span class="track"><span class="fill" style="width:${((r.elo - lo) / (hi - lo)) * 100}%"></span></span><span class="num">${Math.round(r.elo)}</span></li>`)
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
  if (name === d.bookmaker) return css("--book");
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
    [d.bookmaker, css("--book"), false],
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

  // Extra data experiment (Poisson model, same test seasons)
  if (d.extended) {
    $("#extended-card").hidden = false;
    const ext = d.extended.filter((r) => r.model === "Poisson goals model" || r.feature_set === "Bookmaker");
    const label = (r) => (r.feature_set === "Bookmaker" ? "Bookmaker (Bet365)" : r.feature_set === "Base (49 features)" ? "Base features" : `Base ${r.feature_set}`);
    hbars($("#extended-chart"), ext.map((r) => ({
      label: label(r),
      value: r.accuracy,
      color: r.feature_set === "Bookmaker" ? css("--book") : r.feature_set.includes("Base") ? css("--draw") : css("--home"),
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
    color: r.model.startsWith("Original") ? css("--text-2") : r.model === d.baseline ? css("--draw") : r.model === d.bookmaker ? css("--book") : css("--home"),
  })), { format: (v) => pct(v, 1), domain: [0, 0.7], labelWidth: 190, rowHeight: 28, ariaLabel: "Accuracy on version 1's test matches" });
}

/* ------------------------------------------------------------- seasons */
let seasonData, matchLimit = 40;
const CHECK = '<svg viewBox="0 0 12 12"><path d="M2.5 6.5l2.3 2.3 4.7-5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>';
const CROSS = '<svg viewBox="0 0 12 12"><path d="M3 3l6 6M9 3l-6 6" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>';

/* ------------------------------------------------- how it's calculated */
let explainData, xgSide = "home";
const smart = (v) => (v == null ? "–" : Math.abs(v) >= 100 ? v.toFixed(0) : Math.abs(v) >= 10 ? v.toFixed(1) : v.toFixed(2));

function renderExplain(p) {
  const e = p.explain;
  if (!e) return;
  explainData = { e, p };
  $("#explain-card").hidden = false;
  const sw = $$("#xg-switch button");
  sw[0].textContent = `${p.home} goals`;
  sw[1].textContent = `${p.away} goals`;
  drawXg();

  // Step 2: goal distributions
  const lh = e.sides.home.expected_goals, la = e.sides.away.expected_goals;
  $("#dist-home-label").textContent = `${p.home}: λ = ${num(lh, 2)} expected goals`;
  $("#dist-away-label").textContent = `${p.away}: λ = ${num(la, 2)} expected goals`;
  goalBars($("#dist-home"), e.goal_probs.home, css("--home"), p.home);
  goalBars($("#dist-away"), e.goal_probs.away, css("--away"), p.away);
  $("#poisson-example").innerHTML =
    `Example: chance ${esc(p.home)} scores exactly 2 = ${num(lh, 2)}<sup>2</sup> × e<sup>−${num(lh, 2)}</sup> ÷ 2! = ` +
    `${num(lh * lh, 3)} × ${num(Math.exp(-lh), 3)} ÷ 2 = <strong>${pct(e.goal_probs.home[2], 1)}</strong>`;

  // Step 3: score grid
  const g = e.grid, max = Math.max(...g.flat());
  const region = (h, a) => (h > a ? "--home" : h === a ? "--draw" : "--away");
  let html = `<div class="sg-axis-side">${esc(p.home)} goals</div><div class="sg-main"><div class="sg-axis-top">${esc(p.away)} goals</div><table class="score-table"><thead><tr><th></th>`;
  for (let a = 0; a < g[0].length; a++) html += `<th scope="col">${a}</th>`;
  html += "</tr></thead><tbody>";
  g.forEach((row, h) => {
    html += `<tr><th scope="row">${h}</th>`;
    row.forEach((v, a) => {
      const strength = Math.round(12 + (v / max) * 60);
      html += `<td style="background:color-mix(in srgb, var(${region(h, a)}) ${strength}%, var(--surface))" title="${h}-${a}: ${pct(v, 2)}"><span>${h}-${a}</span>${pct(v, 1)}</td>`;
    });
    html += "</tr>";
  });
  html += "</tbody></table></div>";
  $("#score-grid").innerHTML = html;
  const [ph, pd, pa] = pct3([e.outcome.H, e.outcome.D, e.outcome.A]);
  $("#grid-example").innerHTML = `1-0 = ${pct(e.goal_probs.home[1], 1)} × ${pct(e.goal_probs.away[0], 1)} = <strong>${pct(g[1][0], 1)}</strong>`;
  $("#grid-sums").innerHTML = [
    ["--home", `Add up the blue cells (${esc(p.home)} more goals)`, ph, `${p.home} win`],
    ["--draw", "Add up the grey diagonal (same goals)", pd, "Draw"],
    ["--away", `Add up the red cells (${esc(p.away)} more goals)`, pa, `${p.away} win`],
  ].map(([c, how, v, what]) => `<div class="sum"><i style="background:var(${c})"></i><span class="how">${how}</span><span class="eq">= <strong>${v}</strong> ${esc(what)}</span></div>`).join("");
  $("#grid-note").textContent = `The grid shows scores up to 5-5 (${pct(e.grid_total_shown, 1)} of all chances). The sums also include rarer scores up to 10 goals each. These are exactly the percentages at the top of the page.`;

  // Elo
  const el_ = e.elo, diff = el_.home + el_.home_advantage - el_.away;
  $("#elo-formula").innerHTML =
    `Elo expected score for ${esc(p.home)} = 1 ÷ (1 + 10<sup>−(${num(el_.home, 0)} + ${num(el_.home_advantage, 0)} home advantage − ${num(el_.away, 0)}) ÷ 400</sup>) ` +
    `= 1 ÷ (1 + 10<sup>${num(-diff / 400, 3)}</sup>) = <strong>${num(el_.expected_home_score, 3)}</strong>`;
}

function drawXg() {
  if (!explainData) return;
  const { e, p } = explainData;
  const d = e.sides[xgSide];
  const team = xgSide === "home" ? p.home : p.away;
  $$("#xg-switch button").forEach((b) => b.setAttribute("aria-pressed", b.dataset.side === xgSide));
  moveThumb($("#xg-switch"));
  $("#xg-intro").innerHTML = `In an average Premier League match, the ${xgSide} team scores <strong>${num(d.baseline, 2)}</strong> goals. That's the model's starting point. Each input then multiplies it up or down for ${esc(team)}:`;

  const rows = d.items.map((it) => ({
    label: it.label,
    detail: `${smart(it.value)} <span class="vs">vs average ${smart(it.average)}</span>`,
    factor: it.factor,
  }));
  rows.push({ label: `${d.other_count} smaller inputs together`, detail: "", factor: Math.exp(d.other_contribution) });
  if (Math.abs(d.indicator_contribution) > 1e-9) rows.push({ label: "Player-data flags (seasons without player data)", detail: "", factor: Math.exp(d.indicator_contribution) });
  const maxLog = Math.max(...rows.map((r) => Math.abs(Math.log(r.factor))), 1e-6);
  const color = xgSide === "home" ? "--home" : "--away";
  $("#xg-factors").innerHTML =
    `<div class="factor start"><span class="f-label">Starting point (average ${xgSide} team)</span><span class="f-detail"></span><span class="f-bar"></span><span class="f-val">${num(d.baseline, 2)}</span></div>` +
    rows.map((r) => {
      const w = (Math.abs(Math.log(r.factor)) / maxLog) * 50;
      const up = r.factor >= 1;
      return `<div class="factor"><span class="f-label">${esc(r.label)}</span><span class="f-detail">${r.detail}</span>
        <span class="f-bar"><span class="f-mid"></span><span class="f-fill ${up ? "up" : "down"}" style="width:${w}%;${up ? "left:50%" : `right:50%`}"></span></span>
        <span class="f-val ${up ? "up" : "down"}">${up ? "▲" : "▼"} ×${r.factor.toFixed(3)}</span></div>`;
    }).join("") +
    `<div class="factor total"><span class="f-label">Expected goals for ${esc(team)}</span><span class="f-detail"></span><span class="f-bar"></span><span class="f-val" style="color:var(${color})">${num(d.expected_goals, 2)}</span></div>`;
  const factors = [d.baseline, ...rows.map((r) => r.factor)];
  $("#xg-formula").innerHTML = `${factors.map((f, i) => (i === 0 ? num(f, 2) : f.toFixed(3))).join(" × ")} = <strong>${num(d.expected_goals, 2)}</strong>`;
  $("#xg-table").innerHTML =
    `<thead><tr><th>Input</th><th>Value</th><th>Average</th><th>Spread</th><th>z</th><th>Weight</th><th>Effect</th></tr></thead><tbody>` +
    d.items.map((it) => `<tr><td>${esc(it.label)}</td><td>${smart(it.value)}</td><td>${smart(it.average)}</td><td>${smart(it.spread)}</td><td>${it.z.toFixed(2)}</td><td>${it.weight.toFixed(4)}</td><td>×${it.factor.toFixed(3)}</td></tr>`).join("") +
    `</tbody>`;
}

function goalBars(container, probs, color, team) {
  const { svg, width, height } = svgFor(container, 150);
  svg.setAttribute("aria-label", `Chance of ${team} scoring 0 to 6 goals`);
  const n = probs.length, gap = 8, bw = (width - gap * (n - 1)) / n, top = 18, bottom = 22;
  const max = Math.max(...probs);
  probs.forEach((p, k) => {
    const h = ((height - top - bottom) * p) / max, x = k * (bw + gap), y = height - bottom - h;
    if (h >= 4) el("path", { d: `M${x},${height - bottom}v${-(h - 4)}a4,4 0 0 1 4,-4h${bw - 8}a4,4 0 0 1 4,4v${h - 4}z`, fill: color }, svg);
    else if (h > 0.5) el("rect", { x, y, width: bw, height: h, fill: color }, svg);
    const t = el("text", { x: x + bw / 2, y: y - 5, "text-anchor": "middle", class: "value-label" }, svg);
    t.textContent = p > 0 && p < 0.005 ? "<1%" : pct(p, 0);
    const l = el("text", { x: x + bw / 2, y: height - 6, "text-anchor": "middle" }, svg);
    l.textContent = k === n - 1 ? `${k}` : k;
    const hit = el("rect", { x, y: 0, width: bw, height, class: "hit" }, svg);
    hit.addEventListener("pointermove", (ev) => tip.show(`<strong>${esc(team)} scores ${k}</strong><br>${pct(p, 1)}`, ev.clientX, ev.clientY));
    hit.addEventListener("pointerleave", () => tip.hide());
  });
}

/* ---------------------------------------------------------- evaluation */
let evalData, evalEntry, calibOutcome = "H", sampleIndex = 0;
const OUT_NAME = { H: "Home win", D: "Draw", A: "Away win" };

async function initEvaluation() {
  evalData = await api("/api/evaluation");
  const pick = $("#eval-model");
  pick.innerHTML = evalData.entries.map((e) => `<option value="${esc(e.key)}">${esc(shortName(e.label))} · ${esc(e.period.split(" (")[0])}</option>`).join("");
  pick.value = evalData.entries.some((e) => e.key === "recent:app") ? "recent:app" : evalData.entries[0].key;
  pick.addEventListener("change", drawEvaluation);
  $("#calib-switch").addEventListener("click", (ev) => {
    const b = ev.target.closest("button");
    if (!b) return;
    calibOutcome = b.dataset.outcome;
    drawCalibration();
  });
  $("#another-match").addEventListener("click", () => {
    sampleIndex = (sampleIndex + 1) % evalData.samples.length;
    drawWorked();
  });
  sampleIndex = 0;
  drawEvaluation();
  redraw.evaluation = drawEvaluation;
}

const samePeriod = (entry, keyPart) => evalData.entries.find((e) => e.period === entry.period && e.key.includes(keyPart));

function drawEvaluation() {
  evalEntry = evalData.entries.find((e) => e.key === $("#eval-model").value);
  const e = evalEntry;
  $("#eval-period").textContent = `Tested on ${e.matches.toLocaleString("en")} matches, ${e.period}`;
  const macroP = e.per_class.reduce((a, c) => a + c.precision, 0) / 3;
  const macroR = e.per_class.reduce((a, c) => a + c.recall, 0) / 3;
  $("#eval-tiles").innerHTML = [
    [pct(e.accuracy, 1), `Accuracy (95% range ${pct(e.accuracy_low, 1)} to ${pct(e.accuracy_high, 1)})`],
    [e.macro_f1.toFixed(3), "F1 score (macro average)"],
    [e.macro_auc.toFixed(3), "AUC (0.5 = guessing, 1 = perfect)"],
    [e.rps.toFixed(4), "RPS (lower is better)"],
  ].map(([v, l]) => `<div class="tile"><span class="tile-value">${v}</span><span class="tile-label">${esc(l)}</span></div>`).join("");

  // Classification report (same layout as scikit-learn's classification_report)
  const total = e.per_class.reduce((a, c) => a + c.support, 0);
  const row = (name, p, r, f, n, cls = "") => `<tr class="${cls}"><td>${name}</td><td>${p == null ? "" : p.toFixed(3)}</td><td>${r == null ? "" : r.toFixed(3)}</td><td>${f.toFixed(3)}</td><td>${n.toLocaleString("en")}</td></tr>`;
  const wP = e.per_class.reduce((a, c) => a + c.precision * c.support, 0) / total;
  const wR = e.per_class.reduce((a, c) => a + c.recall * c.support, 0) / total;
  $("#class-report").innerHTML =
    `<thead><tr><th>Outcome</th><th>Precision</th><th>Recall</th><th>F1 score</th><th>Support</th></tr></thead><tbody>` +
    e.per_class.map((c) => row(OUT_NAME[c.outcome], c.precision, c.recall, c.f1, c.support)).join("") +
    row("Accuracy", null, null, e.accuracy, total, "sep") +
    row("Macro average", macroP, macroR, e.macro_f1, total) +
    row("Weighted average", wP, wR, e.weighted_f1, total) + `</tbody>`;

  // Confusion matrix
  const cm = e.confusion, labels = evalData.outcomes;
  let html = `<div class="confusion"><span></span>${labels.map((l) => `<span class="hdr">Picked: ${OUT_NAME[l]}</span>`).join("")}`;
  cm.forEach((r, i) => {
    const rowTotal = r.reduce((a, b) => a + b, 0);
    html += `<span class="rowhdr">Real: ${OUT_NAME[labels[i]]}</span>`;
    r.forEach((v, j) => {
      const share = rowTotal ? v / rowTotal : 0;
      const color = i === j ? "--good" : "--draw";
      html += `<span class="cell" style="background:color-mix(in srgb, var(${color}) ${Math.round(12 + share * 70)}%, var(--surface));color:${i === j && share > 0.55 ? "#fff" : "var(--text)"}">${v.toLocaleString("en")}<small>${pct(share)} of row</small></span>`;
    });
  });
  html += `<span></span><span class="axis">Green = correct (the diagonal). Correct total: ${cm.reduce((a, r, i) => a + r[i], 0).toLocaleString("en")} of ${total.toLocaleString("en")} = ${pct(e.accuracy, 1)}</span></div>`;
  $("#eval-confusion").innerHTML = html;
  const draw = e.per_class.find((c) => c.outcome === "D");
  $("#draw-note").textContent = `${pct(e.actual_share.D)} of matches were draws, but the model picked a draw for ${pct(e.predicted_share.D, 1)} of matches, because a draw is almost never the single most likely result. That's why draw recall is ${draw.recall.toFixed(3)}. The draw chance is still in its probabilities (see calibration).`;

  drawCalibration();
  drawMetricList();
  drawWorked();
  drawWalkForward();
}

function drawCalibration() {
  const e = evalEntry;
  $$("#calib-switch button").forEach((b) => b.setAttribute("aria-pressed", b.dataset.outcome === calibOutcome));
  moveThumb($("#calib-switch"));
  const book = samePeriod(e, "Bookmaker") || samePeriod(e, "book");
  const series = [{ name: shortName(e.label), color: css("--home"), pts: e.calibration[calibOutcome] }];
  if (book && book !== e) series.push({ name: "Bookmaker (Bet365)", color: css("--book"), pts: book.calibration[calibOutcome] });
  $("#calib-legend").innerHTML = series.map((s) => `<span><i style="background:${s.color}"></i>${esc(s.name)}</span>`).concat('<span><i class="dashed"></i>Perfect</span>').join("");
  lineChart($("#calibration"), series.map((s) => ({ name: s.name, color: s.color, points: s.pts.map((q) => ({ x: q.predicted, y: q.actual })) })), {
    height: 260, markers: true, diagonal: true, xDomain: [0, 1], yDomain: [0, 1],
    xTicks: [0, 0.2, 0.4, 0.6, 0.8, 1], xTickFormat: (v) => pct(v), yFormat: (v) => pct(v), gapAfter: 0.5,
    tipTitle: (q) => `${OUT_NAME[calibOutcome]}: predicted ≈ ${pct(q.x)}`, ariaLabel: "Calibration chart",
  });
}

function drawMetricList() {
  const e = evalEntry;
  const base = samePeriod(e, "Baseline") || samePeriod(e, "baseline");
  const book = samePeriod(e, "Bookmaker") || samePeriod(e, "book");
  const s = e.actual_share;
  const uniformRps = s.H * ((1 / 3 - 1) ** 2 + (2 / 3 - 1) ** 2) / 2 + s.D * ((1 / 3) ** 2 + (2 / 3 - 1) ** 2) / 2 + s.A * ((1 / 3) ** 2 + (2 / 3) ** 2) / 2;
  const metrics = [
    { name: "Log loss", key: "log_loss", d: 3, lower: true, guess: Math.log(3),
      formula: "average of  −ln(probability given to what actually happened)",
      what: "Rewards giving a high probability to what happened, and punishes confident mistakes very hard (saying 5% for something that happens costs −ln 0.05 = 3.0)." },
    { name: "Brier score", key: "brier", d: 3, lower: true, guess: 2 / 3,
      formula: "average of  (p_home − y_home)² + (p_draw − y_draw)² + (p_away − y_away)²     (y = 1 for what happened, 0 otherwise)",
      what: "The squared distance between the predicted probabilities and the real result. 0 = perfect." },
    { name: "Ranked Probability Score (RPS)", key: "rps", d: 4, lower: true, guess: uniformRps,
      formula: "average of  ½ × [ (P_home − Y_home)² + (P_home + P_draw − Y_home − Y_draw)² ]",
      what: "Like Brier, but it knows home win → draw → away win is an ordered scale, so predicting a draw when the home team wins is less wrong than predicting an away win. The standard score in football research (Constantinou & Fenton, 2012)." },
    { name: "AUC (area under the ROC curve)", key: "macro_auc", d: 3, lower: false, guess: 0.5,
      formula: "chance that a random match WITH the outcome got a higher probability for it than a random match WITHOUT it",
      what: `0.5 = no better than guessing, 1 = perfect. Per outcome: home win ${e.auc[0].toFixed(3)}, draw ${e.auc[1].toFixed(3)}, away win ${e.auc[2].toFixed(3)}. Draws are the hardest to tell apart.` },
  ];
  $("#metric-list").innerHTML = metrics.map((m) => {
    const cmp = [[shortName(e.label), e[m.key], true], book && book !== e ? ["Bookmaker", book[m.key]] : null, base && base !== e ? ["Always home win", base[m.key]] : null, ["Random guess (⅓ each)", m.guess]].filter(Boolean);
    return `<div class="metric">
      <div class="metric-head"><h3>${m.name}</h3><span class="dir">${m.lower ? "lower is better" : "higher is better"}</span></div>
      <p class="metric-what">${esc(m.what)}</p>
      <p class="formula small">${esc(m.formula)}</p>
      <div class="metric-cmp">${cmp.map(([n, v, me]) => `<span class="${me ? "me" : ""}"><b>${v.toFixed(m.d)}</b>${esc(n)}</span>`).join("")}</div>
    </div>`;
  }).join("");
}

function drawWorked() {
  if (!evalData.samples.length) { $("#worked").innerHTML = '<p class="muted">No saved predictions.</p>'; return; }
  const m = evalData.samples[sampleIndex];
  const P = [m.prob.H, m.prob.D, m.prob.A], o = ["H", "D", "A"].indexOf(m.result), Y = [0, 1, 2].map((i) => (i === o ? 1 : 0));
  const pick = P.indexOf(Math.max(...P));
  const names = [`${m.home} win`, "Draw", `${m.away} win`];
  const ll = -Math.log(P[o]);
  const brier = P.reduce((a, p, i) => a + (p - Y[i]) ** 2, 0);
  const c1 = P[0] - Y[0], c2 = P[0] + P[1] - Y[0] - Y[1], rps = (c1 ** 2 + c2 ** 2) / 2;
  const f = (v) => v.toFixed(3);
  $("#worked").innerHTML = `
    <div class="worked-match"><span class="date">${fmtDate(m.date, { day: "numeric", month: "long", year: "numeric" })} · ${m.season} (test season)</span>
      <span class="wm-teams">${esc(m.home)} <strong>${m.score}</strong> ${esc(m.away)}</span>
      <span class="muted">Prediction made before kick-off: ${names.map((n, i) => `${esc(n)} <strong>${pct(P[i], 1)}</strong>`).join(" · ")}</span></div>
    <ol class="worked-steps">
      <li><b>Accuracy:</b> the model's pick was <em>${esc(names[pick])}</em> (highest probability). It ended <em>${esc(names[o])}</em>, so this match counts as <strong>${pick === o ? "correct (1)" : "wrong (0)"}</strong>.</li>
      <li><b>Log loss:</b> −ln(probability given to ${esc(names[o])}) = −ln(${f(P[o])}) = <strong>${f(ll)}</strong></li>
      <li><b>Brier:</b> (${f(P[0])} − ${Y[0]})² + (${f(P[1])} − ${Y[1]})² + (${f(P[2])} − ${Y[2]})² = <strong>${f(brier)}</strong></li>
      <li><b>RPS:</b> ½ × [ (${f(P[0])} − ${Y[0]})² + (${f(P[0] + P[1])} − ${Y[0] + Y[1]})² ] = ½ × [ ${f(c1 ** 2)} + ${f(c2 ** 2)} ] = <strong>${f(rps)}</strong></li>
    </ol>
    <p class="footnote">Doing this for all ${evalEntry.matches.toLocaleString("en")} test matches and taking the average gives the numbers above (the sample shown is from the model the app uses, 2018-19 to 2025-26). Match ${sampleIndex + 1} of ${evalData.samples.length} random test matches.</p>`;
}

function drawWalkForward() {
  const recent = evalEntry.period.startsWith("2018");
  const folds = evalData.folds.filter((f) => !recent || f.test >= "2018-19");
  const first = 2000, last = 2025, rowH = 26, left = 150, right = 120;
  const { svg, width } = svgFor($("#walk-forward"), folds.length * rowH + 30);
  svg.setAttribute("aria-label", "Walk-forward training and test seasons");
  const narrow = width < 560;
  const L = narrow ? 70 : left, R = narrow ? 8 : right;
  const X = (y) => L + ((y - first) / (last - first + 1)) * (width - L - R);
  const cw = X(1) - X(0);
  folds.forEach((f, i) => {
    const y = i * rowH + 4, test = +f.test.slice(0, 4);
    const lab = el("text", { x: L - 10, y: y + rowH / 2 - 2, "text-anchor": "end", "dominant-baseline": "middle" }, svg);
    lab.textContent = narrow ? f.test.slice(2) : `Test ${f.test}`;
    el("rect", { x: X(2001), y: y + 3, width: X(test) - X(2001) - 1, height: rowH - 10, rx: 3, fill: css("--draw"), opacity: 0.55 }, svg);
    el("rect", { x: X(test), y: y + 3, width: cw - 1, height: rowH - 10, rx: 3, fill: css("--home") }, svg);
    if (!narrow) {
      const t = el("text", { x: width - R + 10, y: y + rowH / 2 - 2, "dominant-baseline": "middle" }, svg);
      t.textContent = `${f.train_matches.toLocaleString("en")} → 380`;
    }
    const hit = el("rect", { x: 0, y, width, height: rowH, class: "hit" }, svg);
    hit.addEventListener("pointermove", (ev) => tip.show(`<strong>Predicting ${f.test}</strong><br>Trained on ${f.train_from} to ${f.train_to}: ${f.train_matches.toLocaleString("en")} matches<br>Tested on 380 matches it had never seen`, ev.clientX, ev.clientY));
    hit.addEventListener("pointerleave", () => tip.hide());
  });
  for (const yv of [2001, 2006, 2011, 2016, 2021, 2025]) {
    const t = el("text", { x: X(yv) + cw / 2, y: folds.length * rowH + 22, "text-anchor": "middle" }, svg);
    t.textContent = `'${String(yv).slice(2)}`;
  }
}

/* ---------------------------------------------------------------- data */
const dataState = { key: null, page: 0, size: 50, sort: "", dir: "asc", q: "", season: "", team: "", hidden: {} };
let datasets = [], dataToken = 0, searchTimer;

async function initData() {
  ({ datasets } = await api("/api/datasets"));
  $("#dataset-grid").innerHTML = datasets.map((d) => `
    <button type="button" class="dataset" role="listitem" data-key="${d.key}" aria-pressed="false">
      <span class="ds-kind ${d.kind}">${d.kind === "raw" ? "As downloaded" : "Built by this project"}</span>
      <span class="ds-name">${esc(d.name)}</span>
      <span class="ds-source">${esc(d.source)}</span>
    </button>`).join("");
  $("#dataset-grid").addEventListener("click", (e) => {
    const b = e.target.closest(".dataset");
    if (b) selectDataset(b.dataset.key);
  });
  $("#data-search").addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => { dataState.q = $("#data-search").value; dataState.page = 0; loadData(); }, 250);
  });
  $("#data-season").addEventListener("change", () => { dataState.season = $("#data-season").value; dataState.page = 0; loadData(); });
  $("#data-team").addEventListener("change", () => { dataState.team = $("#data-team").value; dataState.page = 0; loadData(); });
  $("#data-size").addEventListener("change", () => { dataState.size = +$("#data-size").value; dataState.page = 0; loadData(); });
  $("#data-prev").addEventListener("click", () => { dataState.page -= 1; loadData(); });
  $("#data-next").addEventListener("click", () => { dataState.page += 1; loadData(); });
  $("#cols-all").addEventListener("click", () => { dataState.hidden[dataState.key] = new Set(); renderTable(); });
  $("#cols-reset").addEventListener("click", () => { delete dataState.hidden[dataState.key]; renderTable(); });
  $("#columns-list").addEventListener("change", (e) => {
    const box = e.target.closest("input");
    if (!box) return;
    const hidden = dataState.hidden[dataState.key];
    box.checked ? hidden.delete(box.value) : hidden.add(box.value);
    renderTable();
  });
  $("#data-table").addEventListener("click", (e) => {
    const th = e.target.closest("th[data-col]");
    if (!th) return;
    const col = th.dataset.col;
    dataState.dir = dataState.sort === col && dataState.dir === "asc" ? "desc" : "asc";
    dataState.sort = col;
    dataState.page = 0;
    loadData();
  });
  await selectDataset("matches");
}

async function selectDataset(key) {
  Object.assign(dataState, { key, page: 0, sort: "", dir: "asc", q: "", season: "", team: "" });
  $("#data-search").value = "";
  $$("#dataset-grid .dataset").forEach((b) => b.setAttribute("aria-pressed", b.dataset.key === key));
  const d = datasets.find((x) => x.key === key);
  $("#dataset-info").innerHTML = `
    <div class="di-main"><h2>${esc(d.name)}</h2><p class="muted">${esc(d.description)}</p></div>
    <dl class="di-facts">
      <div><dt>Source</dt><dd>${d.source_url ? `<a href="${d.source_url}" target="_blank" rel="noopener">${esc(d.source)}</a>` : esc(d.source)}</dd></div>
      ${d.licence ? `<div><dt>Licence</dt><dd>${esc(d.licence)}</dd></div>` : ""}
      <div><dt>File in the project</dt><dd><code>${esc(d.file)}</code></dd></div>
      <div><dt>Rows</dt><dd id="di-rows">…</dd></div>
    </dl>`;
  await loadData(true);
}

function dataQuery() {
  const p = new URLSearchParams({ dataset: dataState.key, page: dataState.page, size: dataState.size, dir: dataState.dir });
  for (const k of ["sort", "q", "season", "team"]) if (dataState[k]) p.set(k, dataState[k]);
  return p.toString();
}

let dataResult;
async function loadData(fresh = false) {
  const token = ++dataToken;
  $("#data-table-wrap").classList.add("loading");
  try {
    const r = await api(`/api/data?${dataQuery()}`);
    if (token !== dataToken) return;
    dataResult = r;
    dataState.page = r.page;
    if (fresh) {
      $("#data-season").innerHTML = `<option value="">All seasons</option>` + r.seasons.map((s) => `<option>${esc(s)}</option>`).join("");
      $("#data-team").innerHTML = `<option value="">All teams</option>` + r.teams.map((t) => `<option>${esc(t)}</option>`).join("");
      $("#data-season").hidden = !r.seasons.length;
      $("#data-team").hidden = !r.teams.length;
      $("#di-rows").textContent = `${r.total.toLocaleString("en")} × ${r.columns.length} columns`;
    }
    if (!dataState.hidden[dataState.key]) dataState.hidden[dataState.key] = new Set(r.columns.slice(14).map((c) => c.name));
    renderTable();
  } catch (err) {
    if (token === dataToken) toast(err.message);
  } finally {
    if (token === dataToken) $("#data-table-wrap").classList.remove("loading");
  }
}

function formatCell(v, numeric) {
  if (v === null || v === undefined) return '<span class="na">–</span>';
  if (v === true) return "✓";
  if (v === false) return '<span class="na">✗</span>';
  if (numeric && typeof v === "number" && !Number.isInteger(v)) return String(+v.toFixed(3));
  return esc(v);
}

function renderTable() {
  const r = dataResult, hidden = dataState.hidden[dataState.key] || new Set();
  const cols = r.columns.map((c, i) => ({ ...c, i })).filter((c) => !hidden.has(c.name));
  $("#columns-list").innerHTML = r.columns.map((c) => `<label><input type="checkbox" value="${esc(c.name)}" ${hidden.has(c.name) ? "" : "checked"}> ${esc(c.name)}</label>`).join("");
  const arrow = (c) => (dataState.sort === c ? (dataState.dir === "asc" ? " ▲" : " ▼") : "");
  $("#data-table").innerHTML =
    `<thead><tr>${cols.map((c) => `<th data-col="${esc(c.name)}" class="${c.numeric ? "num" : ""}" aria-sort="${dataState.sort === c.name ? (dataState.dir === "asc" ? "ascending" : "descending") : "none"}" title="Sort by ${esc(c.name)}">${esc(c.name)}${arrow(c.name)}</th>`).join("")}</tr></thead>` +
    `<tbody>${r.rows.length ? r.rows.map((row) => `<tr>${cols.map((c) => `<td class="${c.numeric ? "num" : ""}">${formatCell(row[c.i], c.numeric)}</td>`).join("")}</tr>`).join("")
      : `<tr><td class="empty" colspan="${cols.length}">No rows match these filters.</td></tr>`}</tbody>`;
  const from = r.matching ? r.page * r.size + 1 : 0, to = Math.min(r.matching, (r.page + 1) * r.size);
  $("#data-count").textContent = `Rows ${from.toLocaleString("en")}–${to.toLocaleString("en")} of ${r.matching.toLocaleString("en")}` + (r.matching !== r.total ? ` (filtered from ${r.total.toLocaleString("en")})` : "") + ` · ${cols.length} of ${r.columns.length} columns shown`;
  $("#data-page").textContent = `Page ${r.page + 1} of ${r.pages.toLocaleString("en")}`;
  $("#data-prev").disabled = r.page <= 0;
  $("#data-next").disabled = r.page >= r.pages - 1;
  $("#data-download").href = `/api/data.csv?${dataQuery()}`;
  $("#data-download").textContent = `Download CSV (${r.matching.toLocaleString("en")} rows)`;
}

/* -------------------------------------------------------- report/slides */
let storyPromise;
const story = () => (storyPromise ??= api("/api/story"));

async function initReport() {
  const st = await story();
  const article = $("#report");
  article.innerHTML = st.report_html;
  article.querySelectorAll("img").forEach((img) => { img.loading = "lazy"; img.decoding = "async"; });
  article.querySelectorAll("table").forEach((t) => {
    const wrap = document.createElement("div");
    wrap.className = "table-wrap";
    t.parentNode.insertBefore(wrap, t);
    wrap.appendChild(t);
    t.classList.add("table", "report-table");
    // Right-align columns that only contain numbers
    const rows = [...t.rows];
    for (let c = 0; c < (rows[0]?.cells.length || 0); c++) {
      const cells = rows.slice(1).map((r) => r.cells[c]).filter(Boolean);
      const numeric = cells.length && cells.every((td) => /^[\s×≈\-–+]*[\d.,]+\s*%?\s*(\(.*\))?$/.test(td.textContent.trim()) || !td.textContent.trim());
      if (numeric) rows.forEach((r) => r.cells[c]?.classList.add("num"));
    }
  });
  const heads = [...article.querySelectorAll("h2")];
  $("#report-toc").innerHTML = `<p class="section-label">Contents</p><ul>${heads.map((h) => `<li><a href="#report" data-target="${h.id}">${esc(h.textContent)}</a></li>`).join("")}</ul>`;
  $("#report-toc").addEventListener("click", (e) => {
    const a = e.target.closest("a[data-target]");
    if (!a) return;
    e.preventDefault();
    document.getElementById(a.dataset.target)?.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" });
  });
  $("#print-report").addEventListener("click", () => window.print());
}

let deck = [], slideIndex = 0;
const slideColor = (c) => ({ home: css("--home"), away: css("--away"), muted: css("--draw"), aqua: "#1baf7a", violet: css("--book") }[c] || css("--home"));

async function initSlides() {
  const st = await story();
  deck = st.slides;
  $("#slide-strip").innerHTML = deck.map((sl, i) => `<li><button type="button" data-i="${i}"><span class="n">${i + 1}</span>${esc(sl.title)}</button></li>`).join("");
  $("#slide-strip").addEventListener("click", (e) => { const b = e.target.closest("button[data-i]"); if (b) showSlide(+b.dataset.i); });
  $("#slide-prev").addEventListener("click", () => showSlide(slideIndex - 1));
  $("#slide-next").addEventListener("click", () => showSlide(slideIndex + 1));
  $("#notes-toggle").addEventListener("change", () => { $("#slide-notes").hidden = !$("#notes-toggle").checked; });
  $("#present").addEventListener("click", () => {
    const stage = $("#stage");
    (stage.requestFullscreen || stage.webkitRequestFullscreen)?.call(stage);
    stage.focus();
  });
  document.addEventListener("fullscreenchange", () => showSlide(slideIndex));
  $("#stage").addEventListener("click", (e) => {
    if (!document.fullscreenElement) return;
    const r = e.currentTarget.getBoundingClientRect();
    showSlide(slideIndex + (e.clientX > r.left + r.width / 3 ? 1 : -1));
  });
  document.addEventListener("keydown", (e) => {
    if (current !== "slides" || e.target.closest("input, select, textarea")) return;
    const next = ["ArrowRight", "PageDown", " "].includes(e.key), prev = ["ArrowLeft", "PageUp"].includes(e.key);
    if (next || prev || e.key === "Home" || e.key === "End") {
      e.preventDefault();
      showSlide(e.key === "Home" ? 0 : e.key === "End" ? deck.length - 1 : slideIndex + (next ? 1 : -1));
    }
  });
  redraw.slides = () => showSlide(slideIndex);
  showSlide(0);
}

function showSlide(i) {
  slideIndex = Math.max(0, Math.min(deck.length - 1, i));
  const sl = deck[slideIndex];
  const stage = $("#stage");
  stage.innerHTML = slideHTML(sl);
  stage.setAttribute("aria-label", `Slide ${slideIndex + 1} of ${deck.length}: ${sl.title}`);
  stage.querySelector(".sl")?.classList.add("enter");
  $("#slide-count").textContent = `${slideIndex + 1} / ${deck.length}`;
  $("#slide-prev").disabled = slideIndex === 0;
  $("#slide-next").disabled = slideIndex === deck.length - 1;
  $("#slide-notes").innerHTML = `<p class="section-label">What to say</p><p>${esc(sl.notes || "")}</p>`;
  $$("#slide-strip button").forEach((b) => b.setAttribute("aria-current", +b.dataset.i === slideIndex ? "true" : "false"));
  const chartBox = stage.querySelector(".sl-chart-box");
  if (chartBox && sl.chart) drawSlideChart(chartBox, sl.chart);
}

function slideHTML(sl) {
  const dark = sl.kind === "title" || sl.kind === "closing";
  const head = `<p class="sl-kicker">${esc(sl.kicker || "")}</p><h2 class="sl-title">${esc(sl.title)}</h2>`;
  const body = (lines, cls = "") => (lines && lines.length ? `<ul class="sl-body ${cls}">${lines.map((t) => `<li>${esc(t)}</li>`).join("")}</ul>` : "");
  let inner = "";
  switch (sl.kind) {
    case "title":
      inner = `<div class="sl-center"><p class="sl-kicker">${esc(sl.kicker)}</p><h2 class="sl-hero">${esc(sl.title)}</h2><p class="sl-sub">${esc(sl.subtitle)}</p></div>`;
      break;
    case "closing":
      inner = `${head}<ol class="sl-takeaways">${sl.body.map((t, i) => `<li><span class="sl-num">${i + 1}</span>${esc(t)}</li>`).join("")}</ol>`;
      break;
    case "stats":
      inner = `${head}<div class="sl-stats">${sl.stats.map((x, i) => `<div class="sl-card"><span class="sl-stat ${i === 0 ? "accent" : ""}">${esc(x.value)}</span><span class="sl-label">${esc(x.label)}</span></div>`).join("")}</div>${body(sl.body)}`;
      break;
    case "cards":
      inner = `${head}<div class="sl-cards c${sl.cards.length > 4 ? 3 : 2}">${sl.cards.map((c, i) => `<div class="sl-card"><p class="sl-card-title"><span class="sl-dot">${i + 1}</span>${esc(c.title)}</p><p class="sl-card-text">${esc(c.text)}</p></div>`).join("")}</div>${body(sl.body, "small")}`;
      break;
    case "statement": {
      const marks = [["✗", "bad"], ["✓", "good"], ["✓", "accent"]];
      inner = `${head}<div class="sl-points">${sl.body.map((t, i) => `<div class="sl-card sl-point"><span class="sl-mark ${marks[i][1]}">${marks[i][0]}</span>${esc(t)}</div>`).join("")}</div>`;
      break;
    }
    case "chart":
      inner = `${head}<div class="sl-chart"><div class="sl-card"><div class="legend sl-legend"></div><div class="chart sl-chart-box"></div></div>${body(sl.body)}</div>`;
      break;
    case "steps":
      inner = `${head}<div class="sl-steps">${sl.steps.map((x, i) => `<div class="sl-card"><p class="sl-step-title">${esc(x.title)}</p><p class="sl-step-text">${esc(x.text)}</p></div>${i < sl.steps.length - 1 ? '<span class="sl-arrow">→</span>' : ""}`).join("")}</div>`;
      break;
    case "table":
      {
        const compare = sl.table.columns.length === 3;
        const num = (i) => (!compare && i > 0 ? "num" : "");
        inner = `${head}<div class="sl-table ${compare ? "compare" : ""}"><table><thead><tr>${sl.table.columns.map((c, i) => `<th class="${num(i)}">${esc(c)}</th>`).join("")}</tr></thead><tbody>${sl.table.rows.map((r) => `<tr>${r.map((c, i) => `<td class="${num(i)}">${esc(c)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>${body(sl.body, "small")}`;
      }
      break;
    case "sources":
      inner = `${head}<div class="sl-card sl-sources">${body(sl.body)}</div>`;
      break;
  }
  return `<div class="sl ${dark ? "dark" : ""} kind-${sl.kind}">${inner}<div class="sl-footer"><span>Premier League Predictor</span><span>${sl.number}</span></div></div>`;
}

function drawSlideChart(box, chart) {
  const fmt = chart.format === "percent" ? (v) => pct(v, 1) : (v) => Math.round(v).toLocaleString("en");
  if (chart.type === "bar") {
    box.parentElement.querySelector(".sl-legend").remove();
    // Rows share the box's height so the chart always fits inside the slide.
    const rowHeight = Math.max(12, Math.min(40, (box.clientHeight - 10) / chart.categories.length));
    hbars(box, chart.categories.map((c, i) => ({ label: c, value: chart.values[i], color: slideColor((chart.highlight || {})[c] || "muted") })), {
      format: fmt, domain: [chart.min, chart.max], labelWidth: Math.min(220, box.clientWidth * 0.32), rowHeight,
      ariaLabel: "Slide chart", allowStack: false,
    });
  } else {
    const series = chart.series.map((sr) => ({
      name: sr.name, color: slideColor(sr.color), dashed: sr.dashed,
      points: sr.values.map((v, i) => (v == null ? null : { x: i, y: v })).filter(Boolean),
    }));
    box.parentElement.querySelector(".sl-legend").innerHTML = series.map((sr) => `<span><i class="${sr.dashed ? "dashed" : ""}" style="background:${sr.color}"></i>${esc(sr.name)}</span>`).join("");
    lineChart(box, series, {
      height: Math.max(60, box.clientHeight - 4 || 300), markers: chart.categories.length < 20, gapAfter: 1,
      yDomain: [chart.min, chart.max], yFormat: chart.format === "percent" ? (v) => pct(v) : (v) => Math.round(v),
      xTicks: chart.categories.map((_, i) => i), xTickFormat: (i) => chart.categories[i] ?? "",
      tipTitle: (p) => chart.categories[p.x], ariaLabel: "Slide chart",
    });
  }
}

/* ------------------------------------------------------ custom dropdown */
// Every <select> gets a styled button + list. The real <select> stays (hidden)
// and keeps the value, so all other code keeps using select.value / "change".
const VALUE = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value");
let openSelect = null;

function enhanceSelect(sel) {
  if (sel.dataset.enhanced) return;
  sel.dataset.enhanced = "1";
  const wrap = document.createElement("span");
  wrap.className = "cs";
  if (sel.closest(".team-pick")) wrap.classList.add("large");
  const button = document.createElement("button");
  button.type = "button";
  button.className = "cs-button";
  button.setAttribute("role", "combobox");
  button.setAttribute("aria-haspopup", "listbox");
  button.setAttribute("aria-expanded", "false");
  button.setAttribute("aria-label", sel.getAttribute("aria-label") || "Choose");
  button.innerHTML = '<span class="cs-text"></span><svg class="cs-chev" viewBox="0 0 12 12" aria-hidden="true"><path d="M3 4.5l3 3 3-3" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  const pop = document.createElement("div");
  pop.className = "cs-pop";
  pop.setAttribute("role", "listbox");
  pop.hidden = true;
  sel.parentNode.insertBefore(wrap, sel);
  wrap.append(sel, button, pop);
  sel.classList.add("cs-native");
  sel.tabIndex = -1;
  sel.setAttribute("aria-hidden", "true");

  let active = -1, search = "";
  const options = () => [...sel.options];
  const refresh = () => {
    const o = sel.options[sel.selectedIndex];
    $(".cs-text", button).textContent = o ? o.textContent : "";
    wrap.hidden = sel.hidden;
    button.disabled = sel.disabled;
  };
  const render = () => {
    const list = options();
    const filter = search.toLowerCase();
    const searchBox = list.length > 12 ? `<input class="cs-search" type="search" placeholder="Search" aria-label="Search options" value="${esc(search)}">` : "";
    pop.innerHTML = searchBox + `<div class="cs-list">${list.map((o, i) => (!filter || o.textContent.toLowerCase().includes(filter))
      ? `<div class="cs-opt${o.selected ? " sel" : ""}" role="option" id="${sel.id || "cs"}-o${i}" data-i="${i}" aria-selected="${o.selected}">${esc(o.textContent)}<svg viewBox="0 0 12 12" aria-hidden="true"><path d="M2.5 6.5l2.3 2.3 4.7-5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg></div>` : "").join("")}</div>`;
    const input = $(".cs-search", pop);
    if (input) {
      input.addEventListener("input", () => { search = input.value; render(); const i2 = $(".cs-search", pop); i2.focus(); i2.setSelectionRange(i2.value.length, i2.value.length); });
      input.addEventListener("keydown", keys);
    }
  };
  const visible = () => $$(".cs-opt", pop);
  const highlight = (k) => {
    const items = visible();
    if (!items.length) return;
    active = (k + items.length) % items.length;
    items.forEach((it, j) => it.classList.toggle("active", j === active));
    items[active].scrollIntoView({ block: "nearest" });
    button.setAttribute("aria-activedescendant", items[active].id);
  };
  const choose = (i) => {
    if (i !== sel.selectedIndex) {
      sel.selectedIndex = i;
      sel.dispatchEvent(new Event("change", { bubbles: true }));
    }
    refresh();
    close(true);
  };
  const open = () => {
    if (openSelect && openSelect !== close) openSelect();
    search = "";
    render();
    pop.hidden = false;
    wrap.classList.add("open");
    button.setAttribute("aria-expanded", "true");
    const r = button.getBoundingClientRect();
    pop.classList.toggle("up", innerHeight - r.bottom < 300 && r.top > innerHeight - r.bottom);
    highlight(Math.max(0, visible().findIndex((it) => +it.dataset.i === sel.selectedIndex)));
    ($(".cs-search", pop) || button).focus();
    openSelect = close;
  };
  function close(focus) {
    pop.hidden = true;
    wrap.classList.remove("open");
    button.setAttribute("aria-expanded", "false");
    button.removeAttribute("aria-activedescendant");
    if (openSelect === close) openSelect = null;
    if (focus === true) button.focus();
  }
  function keys(e) {
    const items = visible();
    if (e.key === "ArrowDown") { e.preventDefault(); pop.hidden ? open() : highlight(active + 1); }
    else if (e.key === "ArrowUp") { e.preventDefault(); pop.hidden ? open() : highlight(active - 1); }
    else if (e.key === "Home" && !pop.hidden) { e.preventDefault(); highlight(0); }
    else if (e.key === "End" && !pop.hidden) { e.preventDefault(); highlight(items.length - 1); }
    else if ((e.key === "Enter" || (e.key === " " && e.target === button)) ) { e.preventDefault(); pop.hidden ? open() : items[active] && choose(+items[active].dataset.i); }
    else if (e.key === "Escape" && !pop.hidden) { e.preventDefault(); close(true); }
    else if (e.key === "Tab" && !pop.hidden) { close(); }
    else if (e.target === button && e.key.length === 1 && /\S/.test(e.key)) {
      const k = options().findIndex((o) => o.textContent.toLowerCase().startsWith(e.key.toLowerCase()));
      if (k >= 0) { if (pop.hidden) choose(k); else highlight(visible().findIndex((it) => +it.dataset.i === k)); }
    }
  }
  button.addEventListener("click", () => (pop.hidden ? open() : close(true)));
  button.addEventListener("keydown", keys);
  pop.addEventListener("click", (e) => { const it = e.target.closest(".cs-opt"); if (it) choose(+it.dataset.i); });
  pop.addEventListener("mousemove", (e) => { const it = e.target.closest(".cs-opt"); if (it) highlight(visible().indexOf(it)); });
  sel.addEventListener("change", refresh);
  Object.defineProperty(sel, "value", { configurable: true, get() { return VALUE.get.call(this); }, set(v) { VALUE.set.call(this, v); refresh(); } });
  new MutationObserver(refresh).observe(sel, { childList: true, subtree: true, attributes: true, attributeFilter: ["hidden", "disabled"] });
  refresh();
}
document.addEventListener("pointerdown", (e) => { if (openSelect && !e.target.closest(".cs")) openSelect(); });
window.addEventListener("resize", () => openSelect && openSelect());
new MutationObserver(() => $$("select:not([data-enhanced])").forEach(enhanceSelect)).observe(document.body, { childList: true, subtree: true });

/* ------------------------------------------------------------ football */
// Club crest when we have one (img), else a disc in the club colour with its code.
const badgeHTML = (b, size = "") => `<span class="badge ${b.logo ? "logo" : ""} ${size}" style="--c:${b.color};--ink:${b.ink}" title="${esc(b.name)}" aria-hidden="true">${b.logo ? `<img src="${esc(b.logo)}" alt="" decoding="async">` : ""}<span class="code">${esc(b.code)}</span></span>`;
const BADGES = {};
// Full club name, swapped for the short one ("Man City") on small screens.
const teamName = (b) => (b.short && b.short !== b.name ? `<span class="long">${esc(b.name)}</span><span class="short" aria-hidden="true">${esc(b.short)}</span>` : esc(b.name));
const crest = (team, size) => (BADGES[team] ? badgeHTML(BADGES[team], size) : "");
// A crest that fails to load falls back to the coloured disc.
document.addEventListener("error", (e) => { if (e.target.matches?.(".badge.logo img")) { e.target.parentNode.classList.remove("logo"); e.target.remove(); } }, true);
const formPill = (r) => `<span class="pill ${r}" title="${{ W: "Win", D: "Draw", L: "Loss" }[r]}">${r}</span>`;
const fmtDate = (d, opts = { weekday: "long", day: "numeric", month: "long", year: "numeric" }) => new Date(`${d}T12:00:00`).toLocaleDateString("en-GB", opts);
const COMP_NAMES = { premier_league: "Premier League", fa_cup: "FA Cup", league_cup: "League Cup", champions_league: "Champions League", europa_league: "Europa League" };
const stagger = (html, i) => html.replace(/^<(\w+)/, `<$1 style="--i:${Math.min(i, 20)}"`);

function matchRow(m, i = 0) {
  const played = m.home_goals != null;
  const hw = played && m.home_goals > m.away_goals, aw = played && m.away_goals > m.home_goals;
  const pred = m.prediction;
  let predHTML = "";
  if (pred) {
    const ok = pred.pick === m.result;
    predHTML = `<span class="mr-pred" title="Model before kick-off: home ${pct(pred.H)}, draw ${pct(pred.D)}, away ${pct(pred.A)}">
      <span class="mini"><span style="width:${pred.H * 100}%;background:var(--home)"></span><span style="width:${pred.D * 100}%;background:var(--draw)"></span><span style="width:${pred.A * 100}%;background:var(--away)"></span></span>
      <span class="mark ${ok ? "ok" : "no"}" role="img" aria-label="${ok ? "Model was right" : "Model was wrong"}">${ok ? CHECK : CROSS}</span></span>`;
  }
  const tag = m.id != null ? "button" : "div";
  return `<${tag} ${m.id != null ? `type="button" data-match="${m.id}"` : ""} class="match-row ${m.id != null ? "clickable" : ""}" style="--i:${Math.min(i, 20)}">
    <span class="mr-team home ${aw ? "lost" : ""}"><span class="mr-name">${teamName(m.home)}</span>${badgeHTML(m.home)}</span>
    <span class="mr-score">${played ? `<b>${m.home_goals}</b><i>-</i><b>${m.away_goals}</b>` : "<i>v</i>"}<small>${esc(m.note || m.round || "FT")}</small></span>
    <span class="mr-team away ${hw ? "lost" : ""}">${badgeHTML(m.away)}<span class="mr-name">${teamName(m.away)}</span></span>
    ${predHTML}
  </${tag}>`;
}

function groupByDate(list) {
  const groups = [];
  for (const m of list) {
    if (!groups.length || groups[groups.length - 1].date !== m.date) groups.push({ date: m.date, items: [] });
    groups[groups.length - 1].items.push(m);
  }
  return groups;
}

/* ---------- Matches page */
const mc = { season: null, comp: "premier_league", view: "fixtures", round: null, rounds: [], dir: 0 };

async function initMatches() {
  const ov = await api("/api/football/overview");
  $("#mc-season").innerHTML = ov.seasons.map((x) => `<option>${x}</option>`).join("");
  mc.season = ov.seasons[0];
  $("#mc-season").value = mc.season;
  $("#mc-season").addEventListener("change", async () => { mc.season = $("#mc-season").value; mc.round = null; await loadComps(); });
  $("#mc-comps").addEventListener("click", (e) => {
    const b = e.target.closest(".chip");
    if (!b) return;
    mc.comp = b.dataset.comp; mc.round = null; mc.dir = 0;
    $$("#mc-comps .chip").forEach((c) => c.setAttribute("aria-pressed", c === b));
    if (mc.comp !== "premier_league") setView("fixtures");
    $("#mc-view").hidden = mc.comp !== "premier_league";
    loadFixtures();
  });
  $("#mc-view").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) setView(b.dataset.v); });
  $("#mc-prev").addEventListener("click", () => stepRound(-1));
  $("#mc-next").addEventListener("click", () => stepRound(1));
  $("#mc-round").addEventListener("change", () => { const k = $("#mc-round").value; mc.dir = mc.rounds.findIndex((r) => r.key === k) > mc.rounds.findIndex((r) => r.key === mc.round) ? 1 : -1; mc.round = k; loadFixtures(); });
  $("#mc-list").addEventListener("click", (e) => { const r = e.target.closest("[data-match]"); if (r) openSheet({ type: "match", id: +r.dataset.match }); });
  $("#mc-league").addEventListener("click", (e) => { const r = e.target.closest("[data-team]"); if (r) openSheet({ type: "team", name: r.dataset.team, season: mc.season }); });
  enableSwipe($("#mc-list"), (d) => stepRound(d));
  await loadComps();
  redraw.matches = () => moveThumb($("#mc-view"));
}

async function loadComps() {
  const ov = await api(`/api/football/overview?season=${encodeURIComponent(mc.season)}`);
  if (!ov.competitions.some((c) => c.key === mc.comp)) mc.comp = "premier_league";
  $("#mc-comps").innerHTML = ov.competitions.map((c) => `<button type="button" class="chip comp ${c.key}" data-comp="${c.key}" aria-pressed="${c.key === mc.comp}"><span class="comp-dot"></span>${esc(c.name)}</button>`).join("");
  $("#mc-view").hidden = mc.comp !== "premier_league";
  moveThumb($("#mc-view"));
  if (mc.view === "table") loadTable(); else loadFixtures();
}

function setView(v) {
  mc.view = v;
  $$("#mc-view button").forEach((b) => b.setAttribute("aria-pressed", b.dataset.v === v));
  moveThumb($("#mc-view"));
  $("#mc-fixtures").hidden = v !== "fixtures";
  $("#mc-table").hidden = v !== "table";
  if (v === "table") loadTable(); else loadFixtures();
}

function stepRound(d) {
  const i = mc.rounds.findIndex((r) => r.key === mc.round) + d;
  if (i < 0 || i >= mc.rounds.length) return;
  mc.dir = d; mc.round = mc.rounds[i].key; loadFixtures();
}

let fixturesToken = 0;
async function loadFixtures() {
  const token = ++fixturesToken;
  const q = new URLSearchParams({ season: mc.season, competition: mc.comp });
  if (mc.round) q.set("round", mc.round);
  const busy = setTimeout(() => $("#mc-list").classList.add("busy"), 150);
  let r;
  try {
    r = await api(`/api/football/matches?${q}`);
  } catch (err) {
    if (token === fixturesToken) toast(err.message);
    return;
  } finally {
    clearTimeout(busy);
    if (token === fixturesToken) $("#mc-list").classList.remove("busy");
  }
  if (token !== fixturesToken) return;
  mc.rounds = r.rounds; mc.round = r.rounds[r.round_index].key;
  const label = (x) => (x.matchweek ? `Matchweek ${x.matchweek} · ${fmtDate(x.start, { day: "numeric", month: "short" })}${x.end !== x.start ? `–${fmtDate(x.end, { day: "numeric", month: "short" })}` : ""}` : x.label);
  $("#mc-round").innerHTML = r.rounds.map((x) => `<option value="${esc(x.key)}">${esc(label(x))}</option>`).join("");
  $("#mc-round").value = mc.round;
  $("#mc-prev").disabled = r.round_index === 0;
  $("#mc-next").disabled = r.round_index === r.rounds.length - 1;
  const list = $("#mc-list");
  list.classList.remove("from-left", "from-right", "stagger");
  void list.offsetWidth;
  list.innerHTML = groupByDate(r.matches).map((g) => `<div class="card day"><p class="day-head">${fmtDate(g.date)}<span>${esc(COMP_NAMES[mc.comp])}</span></p>${g.items.map((m, i) => matchRow(m, i)).join("")}</div>`).join("");
  list.classList.add(mc.dir > 0 ? "from-right" : mc.dir < 0 ? "from-left" : "stagger");
}

async function loadTable() {
  if (!$("#mc-league tr:not(.sk-tr)")) $("#mc-league").innerHTML = skeletonHTML("trows:20:6");
  $("#mc-league").classList.add("busy");
  let t;
  try {
    t = await api(`/api/football/table?season=${encodeURIComponent(mc.season)}`);
  } catch (err) {
    toast(err.message);
    return;
  } finally {
    $("#mc-league").classList.remove("busy");
  }
  const n = t.table.length;
  $("#mc-league").innerHTML = `<thead><tr><th>#</th><th class="t-team">Team</th><th>P</th><th class="hide-s">W</th><th class="hide-s">D</th><th class="hide-s">L</th><th class="hide-s">Goals</th><th>GD</th><th>Pts</th><th class="t-form">Form</th></tr></thead><tbody class="stagger">` +
    t.table.map((r, i) => `<tr data-team="${esc(r.team.name)}" style="--i:${Math.min(i, 20)}" class="${r.position <= 4 ? "zone-top" : r.position > n - 3 ? "zone-bottom" : ""}" tabindex="0">
      <td class="t-pos">${r.position}</td><td class="t-team"><span class="t-team-in">${badgeHTML(r.team, "small")}<span>${teamName(r.team)}</span></span></td>
      <td>${r.played}</td><td class="hide-s">${r.won}</td><td class="hide-s">${r.drawn}</td><td class="hide-s">${r.lost}</td><td class="hide-s">${r.gf}:${r.ga}</td>
      <td>${r.gd > 0 ? "+" : ""}${r.gd}</td><td class="t-pts">${r.points}</td><td class="t-form">${r.form.map(formPill).join("")}</td></tr>`).join("") + "</tbody>";
  $$("#mc-league tr[data-team]").forEach((tr) => tr.addEventListener("keydown", (e) => { if (e.key === "Enter") tr.click(); }));
}

/* ---------- Swipe (touch) to change round, 1:1 with the finger */
function enableSwipe(el, onSwipe) {
  let x0 = null, y0 = 0, dx = 0, locked = null;
  el.addEventListener("pointerdown", (e) => { if (e.pointerType !== "touch") return; x0 = e.clientX; y0 = e.clientY; dx = 0; locked = null; });
  el.addEventListener("pointermove", (e) => {
    if (x0 == null) return;
    dx = e.clientX - x0;
    if (locked == null && Math.hypot(dx, e.clientY - y0) > 10) locked = Math.abs(dx) > Math.abs(e.clientY - y0);
    if (locked) el.style.transform = `translateX(${dx * 0.6}px)`;
  });
  const end = () => {
    if (x0 == null) return;
    el.style.transform = "";
    if (locked && Math.abs(dx) > 70) onSwipe(dx < 0 ? 1 : -1);
    x0 = null;
  };
  el.addEventListener("pointerup", end);
  el.addEventListener("pointercancel", end);
}

/* ---------- Sheet (match / team / player details) */
const sheet = { stack: [] };

function openSheet(item, push = true) {
  if (push) sheet.stack.push(item);
  const el = $("#sheet"), bd = $("#sheet-backdrop");
  if (el.hidden) {
    el.hidden = false; bd.hidden = false;
    void el.offsetWidth;
    el.classList.add("open"); bd.classList.add("open");
    document.body.classList.add("sheet-open");
  }
  $("#sheet-back").hidden = sheet.stack.length < 2;
  const body = $("#sheet-body");
  body.innerHTML = `<div class="sheet-loading" aria-busy="true">${skeletonHTML("sheet")}</div>`;
  body.scrollTop = 0;
  ({ match: renderMatchSheet, team: renderTeamSheet, player: renderPlayerSheet })[item.type](item).catch((err) => {
    body.innerHTML = `<div class="load-error"><p><b>Couldn't load this.</b><br><span class="muted">${esc(err.message)}</span></p><button type="button" class="button">Try again</button></div>`;
    $("button", body).addEventListener("click", () => openSheet(item, false));
  });
  $("#sheet-close").focus({ preventScroll: true });
}

function closeSheet() {
  const el = $("#sheet"), bd = $("#sheet-backdrop");
  el.classList.remove("open"); bd.classList.remove("open");
  el.style.transform = "";
  document.body.classList.remove("sheet-open");
  sheet.stack = [];
  setTimeout(() => { if (!el.classList.contains("open")) { el.hidden = true; bd.hidden = true; } }, 420);
}

function initSheet() {
  $("#sheet-close").addEventListener("click", closeSheet);
  $("#sheet-backdrop").addEventListener("click", closeSheet);
  $("#sheet-back").addEventListener("click", () => { sheet.stack.pop(); openSheet(sheet.stack[sheet.stack.length - 1], false); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !$("#sheet").hidden && !openSelect) closeSheet(); });
  $("#sheet-body").addEventListener("click", (e) => {
    const t = e.target.closest("[data-open]");
    if (!t) return;
    const [type, a, b] = t.dataset.open.split("|");
    openSheet(type === "match" ? { type, id: +a } : type === "team" ? { type, name: a, season: b } : { type, key: a });
  });
  // Drag the bar down to dismiss (phones): follows the finger, then springs back or closes.
  const bar = $("#sheet-bar"), el = $("#sheet");
  let y0 = null, dy = 0, t0 = 0;
  bar.addEventListener("pointerdown", (e) => { if (e.target.closest("button") || !matchMedia("(max-width: 640px)").matches) return; y0 = e.clientY; dy = 0; t0 = performance.now(); bar.setPointerCapture(e.pointerId); el.classList.add("dragging"); });
  bar.addEventListener("pointermove", (e) => { if (y0 == null) return; dy = Math.max(0, e.clientY - y0); el.style.transform = `translateY(${dy}px)`; });
  const end = () => {
    if (y0 == null) return;
    el.classList.remove("dragging");
    const v = dy / Math.max(1, performance.now() - t0);
    y0 = null;
    if (dy > 140 || v > 0.6) closeSheet(); else el.style.transform = "";
  };
  bar.addEventListener("pointerup", end);
  bar.addEventListener("pointercancel", end);
}

function sheetTabs(tabs, active) {
  return `<div class="segmented small sheet-tabs" role="group" aria-label="Sections"><span class="segmented-thumb" aria-hidden="true"></span>${tabs.map(([k, l]) => `<button type="button" data-tab="${k}" aria-pressed="${k === active}">${l}</button>`).join("")}</div>`;
}
function wireTabs(root, render) {
  const seg = $(".sheet-tabs", root);
  seg.addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    $$("button", seg).forEach((x) => x.setAttribute("aria-pressed", x === b));
    moveThumb(seg);
    render(b.dataset.tab);
  });
  requestAnimationFrame(() => moveThumb(seg));
}

function pointsChip(p) {
  const cls = p >= 10 ? "great" : p >= 6 ? "good" : p >= 3 ? "ok" : "low";
  return `<span class="pts ${cls}" title="FPL points">${p}</span>`;
}

async function renderMatchSheet(item) {
  const m = await api(`/api/football/match?id=${item.id}`);
  const c = m.card;
  const body = $("#sheet-body");
  const hw = c.home_goals > c.away_goals, aw = c.away_goals > c.home_goals;
  body.innerHTML = `
    <div class="scoreboard">
      <p class="sb-meta">Premier League · ${esc(m.season)} · ${fmtDate(c.date)}</p>
      <div class="sb-main">
        <button type="button" class="sb-team" data-open="team|${esc(c.home.name)}|${esc(m.season)}">${badgeHTML(c.home, "large")}<span class="${aw ? "lost" : ""}">${esc(c.home.name)}</span></button>
        <div class="sb-score"><span class="sb-goals">${c.home_goals}<i>-</i>${c.away_goals}</span><span class="sb-status">Full time${c.ht ? ` · HT ${c.ht}` : ""}</span></div>
        <button type="button" class="sb-team" data-open="team|${esc(c.away.name)}|${esc(m.season)}">${badgeHTML(c.away, "large")}<span class="${hw ? "lost" : ""}">${esc(c.away.name)}</span></button>
      </div>
      ${m.referee ? `<p class="sb-meta">Referee: ${esc(m.referee)}</p>` : ""}
    </div>
    ${sheetTabs([["overview", "Overview"], ["lineups", "Line-ups"], ["prediction", "Prediction"], ["h2h", "Head-to-head"]], "overview")}
    <div class="sheet-panel" id="sheet-panel"></div>`;
  const panel = $("#sheet-panel");
  const draw = (tab) => {
    panel.classList.remove("panel-in"); void panel.offsetWidth; panel.classList.add("panel-in");
    if (tab === "overview") {
      const rows = m.stats.map((st) => {
        const h = st.home ?? 0, a = st.away ?? 0, tot = h + a || 1;
        return `<div class="stat"><span class="sv ${h > a ? "lead" : ""}" style="--c:${c.home.color};--ink:${c.home.ink}">${st.home ?? "–"}</span><span class="st-label">${esc(st.label)}</span><span class="sv ${a > h ? "lead" : ""}" style="--c:${c.away.color};--ink:${c.away.ink}">${st.away ?? "–"}</span>
          <span class="sbar home"><span data-w="${(h / tot) * 100}" style="--c:${c.home.color}"></span></span><span class="sbar away"><span data-w="${(a / tot) * 100}" style="--c:${c.away.color}"></span></span></div>`;
      }).join("");
      const b = m.before;
      const formRow = (side) => `<div class="form-line">${badgeHTML(c[side], "small")}<span class="form-pills">${b.form[side].map((f) => `<button type="button" class="pill ${f.res}" data-open="match|${f.id}" title="${f.home ? "v" : "at"} ${esc(f.opponent.name)} ${f.score}">${f.res}</button>`).join("") || '<span class="muted">No earlier matches</span>'}</span></div>`;
      panel.innerHTML = `<div class="card-lite"><p class="section-label">Match stats</p><div class="stats">${rows}</div></div>
        <div class="card-lite"><p class="section-label">Before kick-off</p>
          <div class="facts"><div><span class="muted">Elo rating</span><b>${Math.round(b.elo.home)}</b><b>${Math.round(b.elo.away)}</b></div>
          <div><span class="muted">League position</span><b>${b.position.home ? ordinal(b.position.home) : "–"}</b><b>${b.position.away ? ordinal(b.position.away) : "–"}</b></div></div>
          <p class="section-label" style="margin-top:14px">Form (last 5, tap for the match)</p>${formRow("home")}${formRow("away")}</div>`;
      requestAnimationFrame(() => requestAnimationFrame(() => $$(".sbar span", panel).forEach((s_, i) => { s_.style.transitionDelay = `${i * 30}ms`; s_.style.width = `${s_.dataset.w}%`; })));
    } else if (tab === "lineups") {
      if (!m.lineups) { panel.innerHTML = `<p class="empty-note">Line-ups come from Fantasy Premier League data, which starts in 2016-17.</p>`; return; }
      const L = m.lineups;
      const playerDot = (p, team) => `<button type="button" class="pdot" data-open="player|${esc(p.key)}" title="${esc(p.name)}: ${p.minutes} min, ${p.points} FPL pts">
        <span class="pshirt" style="--c:${team.color};--ink:${team.ink}">${esc(p.position)}</span>${pointsChip(p.points)}
        <span class="pname">${esc(p.short)}${p.goals ? ` <span class="ev">${"⚽".repeat(Math.min(p.goals, 3))}</span>` : ""}${p.red ? ' <span class="booking red"></span>' : p.yellow ? ' <span class="booking yellow"></span>' : ""}</span></button>`;
      const half = (side) => L[side].lines.filter((l) => l.length).map((l) => `<div class="pline">${l.map((p) => playerDot(p, c[side])).join("")}</div>`).join("");
      const subs = (side) => L[side].subs.map((p) => `<button type="button" class="sub" data-open="player|${esc(p.key)}">${pointsChip(p.points)}<span>${esc(p.name)}</span><span class="muted">${p.minutes}'</span></button>`).join("") || '<span class="muted">None</span>';
      const best = [L.home.best, L.away.best].filter(Boolean).sort((x, y) => y.points - x.points)[0];
      panel.innerHTML = `<div class="pitch-head"><span>${badgeHTML(c.home, "small")} ${esc(L.home.formation)}</span><span>${esc(L.away.formation)} ${badgeHTML(c.away, "small")}</span></div>
        <div class="pitch"><div class="pitch-lines" aria-hidden="true"></div><div class="phalf top">${half("home")}</div><div class="phalf bottom">${half("away")}</div></div>
        ${best ? `<p class="best">Most FPL points: <button type="button" class="link" data-open="player|${esc(best.key)}">${esc(best.name)}</button> ${pointsChip(best.points)}</p>` : ""}
        <div class="grid-2 tight"><div><p class="section-label">${esc(c.home.name)} substitutes</p><div class="subs">${subs("home")}</div></div><div><p class="section-label">${esc(c.away.name)} substitutes</p><div class="subs">${subs("away")}</div></div></div>
        <p class="footnote">Starting elevens and positions from Fantasy Premier League data; badges show FPL points earned in this match.</p>`;
      fixPitchOrder(panel);
    } else if (tab === "prediction") {
      const pr = c.prediction, bk = m.bookmaker;
      const names = { H: `${c.home.name} win`, D: "Draw", A: `${c.away.name} win` };
      const bar = (p, label) => { const [ph, pd, pa] = pct3([p.H, p.D, p.A]); return `<div class="pbar-row"><span class="muted">${label}</span><div class="prob-bar small"><span class="seg home" style="width:calc(${p.H * 100}% - 1.34px)"></span><span class="seg draw" style="width:calc(${p.D * 100}% - 1.34px)"></span><span class="seg away" style="width:calc(${p.A * 100}% - 1.34px)"></span></div><span class="pbar-nums"><b class="home-ink">${ph}</b> · ${pd} · <b class="away-ink">${pa}</b></span></div>`; };
      panel.innerHTML = pr ? `<div class="card-lite">
          <p class="verdict ${pr.pick === c.result ? "ok" : "no"}">${pr.pick === c.result ? CHECK : CROSS}<span>The model's pick was <b>${esc(names[pr.pick])}</b>; it ended <b>${esc(names[c.result])}</b>.</span></p>
          ${bar(pr, "Our model (before kick-off)")}${bk ? bar(bk, "Bookmaker (Bet365)") : ""}
          <p class="footnote">Made by a model trained only on earlier seasons (walk-forward test), so it never saw this match.</p></div>`
        : `<p class="empty-note">Predictions exist for the test seasons 2014-15 to 2025-26. Earlier seasons were used to train the model.${bk ? "" : ""}</p>${bk ? `<div class="card-lite">${bar(bk, "Bookmaker (Bet365)")}</div>` : ""}`;
    } else {
      panel.innerHTML = m.h2h.length ? `<div class="card-lite"><p class="section-label">Last ${m.h2h.length} league meetings</p>${m.h2h.map((g, i) => `<button type="button" class="h2h" data-open="match|${g.id}" style="--i:${i}"><span class="muted">${esc(g.season)}</span><span class="h2h-teams">${badgeHTML(g.home, "small")} <b>${g.home_goals}-${g.away_goals}</b> ${badgeHTML(g.away, "small")}</span><span class="muted">${fmtDate(g.date, { day: "numeric", month: "short", year: "numeric" })}</span></button>`).join("")}</div>`
        : `<p class="empty-note">These teams hadn't met in the league since 2000-01 before this match.</p>`;
    }
  };
  wireTabs(body, draw);
  draw("overview");
}

function fixPitchOrder(panel) {
  // The away half shows its lines from forwards (middle) down to goalkeeper (bottom).
  const bottom = $(".phalf.bottom", panel);
  const lines = $$(".pline", bottom);
  lines.reverse().forEach((l) => bottom.appendChild(l));
}

async function renderTeamSheet(item) {
  const t = await api(`/api/football/team?name=${encodeURIComponent(item.name)}&season=${encodeURIComponent(item.season)}`);
  const r = t.row;
  const body = $("#sheet-body");
  body.innerHTML = `
    <div class="team-head" style="--c:${t.team.color}">
      ${badgeHTML(t.team, "xlarge")}
      <div><h2>${esc(t.team.name)}</h2><p class="muted">${t.manager ? `Manager: ${esc(t.manager)}` : "Manager: not in the data for this season"}</p></div>
      <select id="team-season" aria-label="Season">${t.seasons.map((x) => `<option ${x === t.season ? "selected" : ""}>${x}</option>`).join("")}</select>
    </div>
    <div class="tiles four">
      <div class="tile"><span class="tile-value">${ordinal(r.position)}</span><span class="tile-label">League position</span></div>
      <div class="tile"><span class="tile-value">${r.points}</span><span class="tile-label">Points</span></div>
      <div class="tile"><span class="tile-value small-text">${r.won}-${r.drawn}-${r.lost}</span><span class="tile-label">Won-drawn-lost</span></div>
      <div class="tile"><span class="tile-value small-text">${r.gf}:${r.ga}</span><span class="tile-label">Goals for : against</span></div>
    </div>
    <div class="card-lite"><p class="section-label">Form (last 5 league matches)</p><div class="form-pills big">${r.form.map(formPill).join("")}</div>
      <p class="section-label" style="margin-top:14px">Elo rating through the season</p><div class="chart" id="team-elo"></div></div>
    ${t.top_players.length ? `<div class="card-lite"><p class="section-label">Top players (FPL points)</p>${t.top_players.map((p, i) => `<button type="button" class="player-mini" data-open="player|${esc(p.key)}" style="--i:${i}"><span class="avatar" style="--c:${t.team.color};--ink:${t.team.ink}">${esc(initials(p.name))}</span><span class="pm-name"><span class="nm">${esc(p.name)}</span><small>${esc(p.position)} · ${p.apps} apps · ${p.goals} goals · ${p.assists} assists</small></span>${pointsChip(p.points)}</button>`).join("")}</div>` : ""}
    <div class="card-lite"><p class="section-label">All matches this season (${t.results.length})</p><div class="team-results">${t.results.map((m, i) => `<div class="tr-row"><span class="comp-tag ${m.competition}">${esc(m.competition === "premier_league" ? "PL" : m.competition_name)}</span>${matchRow(m, i).replace('class="match-row', `${m.id != null ? `data-open="match|${m.id}" ` : ""}class="match-row compact`)}</div>`).join("")}</div>
      <p class="footnote">${esc(t.manager_note)}</p></div>`;
  $("#team-season").addEventListener("change", () => openSheet({ type: "team", name: t.team.name, season: $("#team-season").value }));
  lineChart($("#team-elo"), [{ name: "Elo", color: t.team.color, points: t.elo.map((e, i) => ({ x: i, y: e.elo, label: e.date })) }], {
    height: 160, yFormat: (v) => Math.round(v), xTicks: [], tipTitle: (p) => t.elo[p.x].date, ariaLabel: "Elo rating through the season",
  });
}

const initials = (name) => name.split(/\s+/).filter(Boolean).map((w) => w[0]).slice(0, 2).join("").toUpperCase();

async function renderPlayerSheet(item) {
  const p = await api(`/api/football/player?key=${encodeURIComponent(item.key)}`);
  const body = $("#sheet-body");
  body.innerHTML = `
    <div class="team-head" style="--c:${p.team.color}">
      <span class="avatar xlarge" style="--c:${p.team.color};--ink:${p.team.ink}">${esc(initials(p.name))}</span>
      <div><h2>${esc(p.name)}</h2><p class="muted"><button type="button" class="link" data-open="team|${esc(p.team.name)}|${esc(p.seasons[0].season)}">${esc(p.team.name)}</button> · ${esc({ GK: "Goalkeeper", DEF: "Defender", MID: "Midfielder", FWD: "Forward" }[p.position] || p.position)} · FPL price £${p.price}m</p></div>
    </div>
    <div class="tiles four">
      <div class="tile"><span class="tile-value">${p.career.apps}</span><span class="tile-label">Appearances</span></div>
      <div class="tile"><span class="tile-value">${p.career.goals}</span><span class="tile-label">Goals</span></div>
      <div class="tile"><span class="tile-value">${p.career.assists}</span><span class="tile-label">Assists</span></div>
      <div class="tile"><span class="tile-value">${p.career.points}</span><span class="tile-label">FPL points</span></div>
    </div>
    <div class="card-lite"><p class="section-label">Season by season (Premier League, 2016-17 onwards)</p>
      <div class="table-wrap"><table class="table numbers season-table"><thead><tr><th>Season</th><th>Team</th><th>Apps</th><th>Min</th><th>G</th><th>A</th><th>Pts</th><th>Infl/90</th></tr></thead><tbody>
      ${p.seasons.map((x) => `<tr><td>${x.season}</td><td><span class="t-team-in" title="${esc(x.team)}">${badgeHTML(x.team_badge, "small")}<span class="hide-narrow">${esc(x.team)}</span></span></td><td>${x.apps}</td><td>${x.minutes.toLocaleString("en")}</td><td>${x.goals}</td><td>${x.assists}</td><td>${x.points}</td><td>${num(x.influence, 1)}</td></tr>`).join("")}
      </tbody></table></div>
      <p class="section-label" style="margin-top:14px">Influence per 90 minutes</p><div class="chart" id="player-infl"></div></div>
    <div class="card-lite"><p class="section-label">Latest matches</p>${p.recent.map((g, i) => `<button type="button" class="h2h" data-open="match|${g.id}" style="--i:${i}"><span class="pill ${g.res}">${g.res}</span><span class="h2h-teams">${g.home ? "v" : "at"} ${badgeHTML(g.opponent, "small")} ${esc(g.opponent.name)} <b>${g.score}</b></span><span class="muted">${g.minutes}' ${g.goals ? `· ${g.goals}G` : ""}${g.assists ? ` · ${g.assists}A` : ""}</span>${pointsChip(g.points)}</button>`).join("")}</div>`;
  hbars($("#player-infl"), p.influence_by_season.map((x) => ({ label: x.season, value: x.influence, color: p.team.color })), { format: (v) => v.toFixed(1), labelWidth: 80, rowHeight: 26, ariaLabel: "Influence per 90 by season", allowStack: false });
}

/* ---------- Players page */
const pl = { season: null, team: "", pos: "", q: "", sort: "points", page: 0, rows: [] };
let plToken = 0, plTimer;

async function initPlayers() {
  const first = await api("/api/football/players?season=");
  const seasons = first.seasons;
  $("#pl-season").innerHTML = seasons.map((x) => `<option>${x}</option>`).join("");
  pl.season = seasons[0];
  $("#pl-season").value = pl.season;
  $("#pl-season").addEventListener("change", () => { pl.season = $("#pl-season").value; pl.team = ""; loadPlayers(true); });
  $("#pl-team").addEventListener("change", () => { pl.team = $("#pl-team").value; loadPlayers(true); });
  $("#pl-sort").addEventListener("change", () => { pl.sort = $("#pl-sort").value; loadPlayers(true); });
  $("#pl-search").addEventListener("input", () => { clearTimeout(plTimer); plTimer = setTimeout(() => { pl.q = $("#pl-search").value.trim(); loadPlayers(true); }, 250); });
  $("#pl-pos").addEventListener("click", (e) => { const b = e.target.closest(".chip"); if (!b) return; pl.pos = b.dataset.pos; $$("#pl-pos .chip").forEach((c) => c.setAttribute("aria-pressed", c === b)); loadPlayers(true); });
  $("#pl-more").addEventListener("click", () => { pl.page += 1; loadPlayers(false); });
  $("#pl-list").addEventListener("click", (e) => { const r = e.target.closest("[data-player]"); if (r) openSheet({ type: "player", key: r.dataset.player }); });
  await loadPlayers(true);
}

async function loadPlayers(fresh) {
  const token = ++plToken;
  if (fresh) pl.page = 0;
  const q = new URLSearchParams({ season: pl.season, team: pl.team, position: pl.pos, q: pl.q, sort: pl.sort, page: pl.page });
  const busy = setTimeout(() => $("#pl-list").classList.add("busy"), 150);
  let r;
  try {
    r = await api(`/api/football/players?${q}`);
  } catch (err) {
    if (token === plToken) toast(err.message);
    return;
  } finally {
    clearTimeout(busy);
    if (token === plToken) $("#pl-list").classList.remove("busy");
  }
  if (token !== plToken) return;
  if (fresh) {
    const keep = pl.team;
    $("#pl-team").innerHTML = `<option value="">All teams</option>` + r.teams.map((t) => `<option>${esc(t)}</option>`).join("");
    $("#pl-team").value = keep;
  }
  const rows = r.players.map((p, i) => `<button type="button" class="pl-row" data-player="${esc(p.key)}" style="--i:${Math.min(i, 20)}">
    <span class="avatar" style="--c:${p.team_badge.color};--ink:${p.team_badge.ink}">${esc(initials(p.name))}</span>
    <span class="pl-name"><span class="nm">${esc(p.name)}</span><small>${badgeHTML(p.team_badge, "tiny")} ${teamName(p.team_badge)} · ${esc(p.position)}</small></span>
    <span class="num">${p.apps}</span><span class="num">${p.goals}</span><span class="num">${p.assists}</span>
    <span class="num hide-s">${p.minutes.toLocaleString("en")}</span><span class="num hide-s">${num(p.influence, 1)}</span><span class="num">${pointsChip(p.points)}</span></button>`).join("");
  const list = $("#pl-list");
  if (fresh) { list.classList.remove("stagger"); void list.offsetWidth; list.innerHTML = rows; list.classList.add("stagger"); }
  else list.insertAdjacentHTML("beforeend", rows);
  const shown = Math.min(r.total, (r.page + 1) * r.size);
  $("#pl-count").textContent = r.total ? `Showing ${shown.toLocaleString("en")} of ${r.total.toLocaleString("en")} players` : "No players match.";
  $("#pl-more").hidden = shown >= r.total;
}

/* ---------------------------------------------------------------- boot */
window.addEventListener("hashchange", route);
let resizeTimer;
window.addEventListener("resize", () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => {
    moveThumb($(".chrome .segmented"));
    if (loaded.has("models")) moveThumb($("#metric-switch"));
    if (loaded.has("evaluation")) moveThumb($("#calib-switch"));
    moveThumb($("#xg-switch"));
    redraw[current]?.();
  }, 120);
});
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => redraw[current]?.());
document.fonts?.ready.then(() => moveThumb($(".chrome .segmented")));
$$("select").forEach(enhanceSelect);
initSheet();
$("#boot-retry").addEventListener("click", () => location.reload());
route(); // pages show skeletons; their requests wait until the server is ready
whenReady();
