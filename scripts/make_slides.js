// Build docs/slides.pptx from docs/slides.json (written by scripts/06_make_report.py).
// Same content as the website's Slides page, styled like the website.
//
// Run:  node scripts/make_slides.js   (needs: npm install pptxgenjs, once)
"use strict";
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");

const ROOT = path.join(__dirname, "..");
const slides = JSON.parse(fs.readFileSync(path.join(ROOT, "docs", "slides.json"), "utf8"));
const OUT = path.join(ROOT, "docs", "slides.pptx");

// Website palette (src/eplpred/web/static/app.css)
const COL = {
  bg: "F5F5F7", surface: "FFFFFF", text: "1D1D1F", text2: "6E6E73", text3: "86868B",
  accent: "0071E3", home: "2A78D6", away: "D12F2F", muted: "A8A7A1", aqua: "1BAF7A", violet: "4A3AA7",
  good: "1A8A5C", dark: "000000", darkSurface: "1C1C1E", darkText2: "A1A1A6", line: "E5E5EA",
};
const THEME = {
  name: "Premier League Predictor",
  headFontFace: "Arial", bodyFontFace: "Arial",
  colors: { dk1: COL.text, lt1: COL.surface, dk2: COL.text2, lt2: COL.bg, accent1: COL.home, accent2: COL.away,
    accent3: COL.aqua, accent4: COL.muted, accent5: COL.violet, accent6: COL.accent, hlink: COL.accent, folHlink: COL.text2 },
};
const W = 13.333, H = 7.5, M = 0.6;

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";
pres.title = "Can we predict Premier League matches?";
pres.subject = "Data science project";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };

const footer = (dark) => ({ text: { text: "Premier League Predictor", options: { x: M, y: H - 0.45, w: 6, h: 0.3, fontSize: 10, color: dark ? COL.darkText2 : COL.text3, margin: 0 } } });
pres.defineSlideMaster({
  title: "CONTENT", background: { color: COL.bg },
  objects: [footer(false)],
  slideNumber: { x: W - M - 0.6, y: H - 0.45, w: 0.6, h: 0.3, fontSize: 10, color: COL.text3, align: "right" },
  placeholders: [],
});
pres.defineSlideMaster({
  title: "DARK", background: { color: COL.dark },
  objects: [footer(true)],
  slideNumber: { x: W - M - 0.6, y: H - 0.45, w: 0.6, h: 0.3, fontSize: 10, color: COL.darkText2, align: "right" },
});

function heading(slide, s, dark = false, y = 0.55) {
  slide.addText(s.kicker || "", { x: M, y, w: W - 2 * M, h: 0.4, fontSize: 16, bold: true, color: dark ? "2997FF" : COL.accent, margin: 0, isTextBox: true, objectName: "Kicker" });
  slide.addText(s.title, { x: M, y: y + 0.42, w: W - 2 * M, h: 0.95, fontSize: 36, bold: true, color: dark ? "FFFFFF" : COL.text, margin: 0, valign: "top", isTextBox: true, objectName: "Title", fit: "shrink" });
}
const shadow = () => ({ type: "outer", color: "000000", opacity: 0.08, blur: 8, offset: 2, angle: 90 });
function card(slide, x, y, w, h, name) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.18, fill: { color: COL.surface }, line: { color: COL.surface }, shadow: shadow(), objectName: name });
}
function bodyLines(slide, lines, x, y, w, h, opts = {}) {
  if (!lines || !lines.length) return;
  slide.addText(lines.map((t, i) => ({ text: t, options: { bullet: lines.length > 1 ? { indent: 18 } : false, breakLine: i < lines.length - 1, paraSpaceAfter: 6 } })),
    { x, y, w, h, fontSize: opts.fontSize || 16, color: opts.color || COL.text2, valign: "top", margin: 0, isTextBox: true, objectName: "Body" });
}
const colorOf = (c) => ({ home: COL.home, away: COL.away, muted: COL.muted, aqua: COL.aqua, violet: COL.violet }[c] || COL.home);

function addChart(slide, chart, x, y, w, h) {
  const percent = chart.format === "percent";
  const common = {
    x, y, w, h,
    catAxisLabelColor: COL.text2, valAxisLabelColor: COL.text2, catAxisLabelFontSize: 12, valAxisLabelFontSize: 11,
    catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt", dataLabelFontFace: "+mn-lt", legendFontFace: "+mn-lt",
    valGridLine: { color: "E5E5EA", size: 0.75 }, catGridLine: { style: "none" },
    valAxisMinVal: chart.min, valAxisMaxVal: chart.max,
    valAxisLabelFormatCode: percent ? "0%" : "#,##0", catAxisLineShow: false, valAxisLineShow: false,
  };
  if (chart.type === "bar") {
    const colors = chart.categories.map((c) => colorOf((chart.highlight || {})[c] || "muted"));
    slide.addChart(pres.charts.BAR, [{ name: "Accuracy", labels: chart.categories, values: chart.values }], {
      ...common, barDir: chart.horizontal ? "bar" : "col", chartColors: colors, barGapWidthPct: 45,
      showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: percent ? "0.0%" : "#,##0", dataLabelColor: COL.text, dataLabelFontSize: 12,
      catAxisOrientation: chart.horizontal ? "maxMin" : "minMax", showLegend: false, objectName: "Chart",
    });
  } else {
    slide.addChart(pres.charts.LINE, chart.series.map((s) => ({ name: s.name, labels: chart.categories, values: s.values.map((v) => (v == null ? null : v)) })), {
      ...common, chartColors: chart.series.map((s) => colorOf(s.color)), lineSize: 2.25, lineDataSymbol: "circle", lineDataSymbolSize: 5,
      lineDash: chart.series.map((s) => (s.dashed ? "dash" : "solid")),
      showLegend: true, legendPos: "t", legendFontSize: 12, legendColor: COL.text2, objectName: "Chart",
    });
  }
}

for (const s of slides) {
  const dark = s.kind === "title" || s.kind === "closing";
  const slide = pres.addSlide({ masterName: dark ? "DARK" : "CONTENT" });
  slide.addNotes(s.notes || "");

  if (s.kind === "title") {
    slide.addText(s.kicker, { x: M, y: 2.2, w: W - 2 * M, h: 0.45, fontSize: 20, bold: true, color: "2997FF", margin: 0, isTextBox: true, objectName: "Kicker" });
    slide.addText(s.title, { x: M, y: 2.7, w: W - 2 * M, h: 1.9, fontSize: 54, bold: true, color: "FFFFFF", margin: 0, valign: "top", isTextBox: true, objectName: "Title" });
    slide.addText(s.subtitle, { x: M, y: 4.75, w: W - 2 * M, h: 0.5, fontSize: 22, color: COL.darkText2, margin: 0, isTextBox: true, objectName: "Subtitle" });
    continue;
  }
  if (s.kind === "closing") {
    heading(slide, s, true, 0.9);
    s.body.forEach((t, i) => {
      const y = 2.6 + i * 1.25;
      slide.addShape(pres.shapes.OVAL, { x: M, y, w: 0.6, h: 0.6, fill: { color: "2997FF" }, line: { color: "2997FF" }, objectName: `Number ${i + 1}` });
      slide.addText(String(i + 1), { x: M, y, w: 0.6, h: 0.6, fontSize: 20, bold: true, color: "000000", align: "center", valign: "middle", margin: 0, isTextBox: true });
      slide.addText(t, { x: M + 0.9, y: y - 0.05, w: W - 2 * M - 0.9, h: 0.7, fontSize: 24, color: "FFFFFF", valign: "middle", margin: 0, isTextBox: true, objectName: `Takeaway ${i + 1}` });
    });
    continue;
  }

  heading(slide, s);
  const top = 2.15, avail = H - top - 0.75;

  if (s.kind === "stats") {
    const n = s.stats.length, gap = 0.35, cw = (W - 2 * M - gap * (n - 1)) / n, ch = 2.3;
    s.stats.forEach((st, i) => {
      const x = M + i * (cw + gap);
      card(slide, x, top, cw, ch, `Stat ${i + 1}`);
      slide.addText(st.value, { x: x + 0.3, y: top + 0.3, w: cw - 0.6, h: 1.0, fontSize: 48, bold: true, color: i === 0 ? COL.home : COL.text, margin: 0, isTextBox: true });
      slide.addText(st.label, { x: x + 0.3, y: top + 1.35, w: cw - 0.6, h: 0.8, fontSize: 15, color: COL.text2, margin: 0, valign: "top", isTextBox: true });
    });
    bodyLines(slide, s.body, M, top + ch + 0.4, W - 2 * M, avail - ch - 0.4);
  } else if (s.kind === "cards") {
    const n = s.cards.length, cols = n > 4 ? 3 : 2, rows = Math.ceil(n / cols), gap = 0.3;
    const bodyH = s.body && s.body.length ? 0.6 : 0;
    const cw = (W - 2 * M - gap * (cols - 1)) / cols, ch = (avail - bodyH - gap * (rows - 1)) / rows;
    s.cards.forEach((c, i) => {
      const x = M + (i % cols) * (cw + gap), y = top + Math.floor(i / cols) * (ch + gap);
      card(slide, x, y, cw, ch, `Card ${i + 1}`);
      slide.addShape(pres.shapes.OVAL, { x: x + 0.3, y: y + 0.3, w: 0.42, h: 0.42, fill: { color: COL.accent }, line: { color: COL.accent }, objectName: `Card ${i + 1} dot` });
      slide.addText(String(i + 1), { x: x + 0.3, y: y + 0.3, w: 0.42, h: 0.42, fontSize: 14, bold: true, color: "FFFFFF", align: "center", valign: "middle", margin: 0, isTextBox: true });
      slide.addText(c.title, { x: x + 0.9, y: y + 0.26, w: cw - 1.2, h: 0.5, fontSize: 19, bold: true, color: COL.text, margin: 0, valign: "middle", isTextBox: true, fit: "shrink" });
      slide.addText(c.text, { x: x + 0.3, y: y + 0.88, w: cw - 0.6, h: ch - 1.05, fontSize: 15, color: COL.text2, margin: 0, valign: "top", isTextBox: true });
    });
    if (bodyH) bodyLines(slide, s.body, M, H - 0.75 - bodyH + 0.1, W - 2 * M, bodyH - 0.1, { fontSize: 14 });
  } else if (s.kind === "statement") {
    const marks = [["✗", COL.away], ["✓", COL.good], ["✓", COL.accent]];
    s.body.forEach((t, i) => {
      const y = top + 0.2 + i * 1.45;
      card(slide, M, y, W - 2 * M, 1.15, `Point ${i + 1}`);
      slide.addShape(pres.shapes.OVAL, { x: M + 0.35, y: y + 0.27, w: 0.6, h: 0.6, fill: { color: marks[i][1] }, line: { color: marks[i][1] }, objectName: `Mark ${i + 1}` });
      slide.addText(marks[i][0], { x: M + 0.35, y: y + 0.27, w: 0.6, h: 0.6, fontSize: 22, bold: true, color: "FFFFFF", align: "center", valign: "middle", margin: 0, isTextBox: true });
      slide.addText(t, { x: M + 1.25, y: y + 0.17, w: W - 2 * M - 1.6, h: 0.8, fontSize: 22, color: COL.text, valign: "middle", margin: 0, isTextBox: true });
    });
  } else if (s.kind === "chart") {
    const bodyW = 3.6, cw = W - 2 * M - bodyW - 0.4;
    card(slide, M, top, cw, avail, "Chart card");
    addChart(slide, s.chart, M + 0.2, top + 0.15, cw - 0.4, avail - 0.3);
    bodyLines(slide, s.body, M + cw + 0.4, top + 0.1, bodyW, avail - 0.2, { fontSize: 16 });
  } else if (s.kind === "steps") {
    const n = s.steps.length, gap = 0.55, cw = (W - 2 * M - gap * (n - 1)) / n, ch = 3.0;
    s.steps.forEach((st, i) => {
      const x = M + i * (cw + gap);
      card(slide, x, top + 0.3, cw, ch, `Step ${i + 1}`);
      slide.addText(st.title, { x: x + 0.3, y: top + 0.6, w: cw - 0.6, h: 0.55, fontSize: 21, bold: true, color: COL.accent, margin: 0, isTextBox: true, fit: "shrink" });
      slide.addText(st.text, { x: x + 0.3, y: top + 1.3, w: cw - 0.6, h: ch - 1.2, fontSize: 17, color: COL.text, margin: 0, valign: "top", isTextBox: true });
      if (i < n - 1) slide.addText("→", { x: x + cw, y: top + 0.3 + ch / 2 - 0.3, w: gap, h: 0.6, fontSize: 26, color: COL.text3, align: "center", valign: "middle", margin: 0, isTextBox: true });
    });
  } else if (s.kind === "table") {
    const t = s.table, bodyH = s.body && s.body.length ? 1.0 : 0;
    const header = t.columns.map((c, i) => ({ text: c, options: { bold: true, color: COL.text2, fill: { color: "EDEDF0" }, align: i === 0 ? "left" : "right" } }));
    const rows = t.rows.map((r) => r.map((c, i) => ({ text: String(c), options: { color: COL.text, fill: { color: COL.surface }, align: i === 0 ? "left" : "right", bold: i === 0 } })));
    if (t.columns.length === 3) { // comparison table: right-align off, highlight the last column
      rows.forEach((r) => { r[1].options.align = "left"; r[2].options.align = "left"; r[2].options.color = COL.home; r[2].options.bold = true; });
      header[1].options.align = "left"; header[2].options.align = "left";
    }
    slide.addTable([header, ...rows], { x: M, y: top, w: W - 2 * M, fontSize: 16, fontFace: "Arial", border: { type: "solid", pt: 0.75, color: COL.line },
      rowH: Math.min(0.62, (avail - bodyH) / (rows.length + 1)), valign: "middle", margin: [0.06, 0.15, 0.06, 0.15], objectName: "Table" });
    if (bodyH) bodyLines(slide, s.body, M, H - 0.75 - bodyH, W - 2 * M, bodyH - 0.1, { fontSize: 15 });
  } else if (s.kind === "sources") {
    const half = Math.ceil(s.body.length / 2);
    card(slide, M, top, W - 2 * M, avail, "Sources card");
    bodyLines(slide, s.body.slice(0, half), M + 0.35, top + 0.35, (W - 2 * M) / 2 - 0.5, avail - 0.6, { fontSize: 15, color: COL.text });
    bodyLines(slide, s.body.slice(half), M + (W - 2 * M) / 2 + 0.15, top + 0.35, (W - 2 * M) / 2 - 0.5, avail - 0.6, { fontSize: 15, color: COL.text });
  }
}

(async () => {
  await pres.writeFile({ fileName: OUT });
  try {
    const { applyTheme } = require(process.env.PPTX_SKILL_THEME || path.join(__dirname, "apply_theme.js"));
    await applyTheme(OUT, THEME);
  } catch (err) {
    // The deck is complete without it; the theme only names the colours for PowerPoint's colour picker.
  }
  console.log(`Saved ${path.relative(ROOT, OUT)} (${slides.length} slides)`);
})();
