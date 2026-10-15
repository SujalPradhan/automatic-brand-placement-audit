// Charts for the landing page (benchmark.json) and the game pages (game-<tag>.json). Inline SVG, no libraries.
const NS = "http://www.w3.org/2000/svg";
const el = (tag, attrs = {}, parent) => {
  const n = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  if (parent) parent.appendChild(n);
  return n;
};
const tip = document.createElement("div");
tip.className = "tip";
tip.hidden = true;
document.body.appendChild(tip);
const moveTip = (e) => {
  tip.style.left = Math.min(e.clientX + 14, window.innerWidth - 270) + "px";
  tip.style.top = e.clientY + 14 + "px";
};
const hover = (node, html) => {
  node.addEventListener("pointerenter", (e) => { tip.innerHTML = html; tip.hidden = false; moveTip(e); });
  node.addEventListener("pointermove", moveTip);
  node.addEventListener("pointerleave", () => { tip.hidden = true; });
};
const mmss = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
const TIER = { Partner: "var(--t1)", Sponsor: "var(--t2)", Supporter: "var(--t3)", Other: "var(--s1)" };
const TIER_LABEL = { Partner: "FIFA Partner (top tier)", Sponsor: "World Cup Sponsor", Supporter: "Regional supporter" };

/* Landing: 100% stacked bars, screen time vs goal moments, by tier, for each game */
function tierBars(root, games) {
  const rows = [];
  for (const g of Object.values(games)) {
    rows.push({ label: g.short, sub: "All sponsor screen time", key: "share_visible_pct", g });
    rows.push({ label: "", sub: "Seconds around goals", key: "share_key_moment_pct", g });
  }
  const W = 760, L = 190, R = 20, bh = 26, gap = 10, T = 8;
  const GAME_GAP = 14;  // extra space between games (two bars each)
  const H = T + rows.length * (bh + gap) + Math.floor((rows.length - 1) / 2) * GAME_GAP + 30;
  const x = (v) => L + (v / 100) * (W - L - R);
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, width: W, height: H, role: "img",
    "aria-label": "Share of sponsor screen time and of goal-moment seconds by sponsor tier, for each game" }, root);
  rows.forEach((r, i) => {
    const y = T + i * (bh + gap) + Math.floor(i / 2) * GAME_GAP;
    if (r.label) el("text", { x: 0, y: y + 11, class: "lbl" }, svg).textContent = r.label;
    el("text", { x: 0, y: y + (r.label ? 25 : 17) }, svg).textContent = r.sub;
    let acc = 0;
    for (const t of ["Partner", "Sponsor", "Supporter"]) {
      const v = (r.g.tiers[t] || {})[r.key] || 0;
      if (v <= 0) continue;
      const w = x(acc + v) - x(acc);
      const rect = el("rect", { x: x(acc) + 1, y, width: Math.max(0, w - 2), height: bh, fill: TIER[t], rx: 3 }, svg);
      hover(rect, `<b>${r.g.short}</b> · ${TIER_LABEL[t]}<br>${v}% of ${r.key === "share_visible_pct" ? "sponsor screen time" : "goal-moment seconds"}`);
      if (w > 44) {
        const tx = el("text", { x: x(acc) + w / 2, y: y + bh / 2 + 4, "text-anchor": "middle", class: "on-bar" }, svg);
        tx.textContent = Math.round(v) + "%";
      }
      acc += v;
    }
  });
  for (let v = 0; v <= 100; v += 25) {
    el("text", { x: x(v), y: H - 6, "text-anchor": "middle" }, svg).textContent = v + "%";
  }
}

/* Game: dumbbell of each brand's share of screen time vs share of goal moments */
function dumbbell(root, brands, minSeconds = 8) {
  const rows = brands.filter((b) => b.visible_s >= minSeconds).sort((a, b) => b.share_key_moment_pct - a.share_key_moment_pct || b.share_visible_pct - a.share_visible_pct);
  const W = 760, L = 150, R = 70, rowH = 26, T = 10, H = T + rows.length * rowH + 30;
  const max = Math.ceil(Math.max(...rows.flatMap((r) => [r.share_visible_pct, r.share_key_moment_pct])) / 5) * 5;
  const x = (v) => L + (v / max) * (W - L - R);
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, width: W, height: H, role: "img",
    "aria-label": "Each brand's share of sponsor screen time against its share of goal-moment seconds" }, root);
  for (let v = 0; v <= max; v += 5) {
    el("line", { x1: x(v), x2: x(v), y1: T, y2: H - 24, class: "grid" }, svg);
    el("text", { x: x(v), y: H - 8, "text-anchor": "middle" }, svg).textContent = v + "%";
  }
  rows.forEach((r, i) => {
    const y = T + i * rowH + rowH / 2;
    el("text", { x: L - 12, y: y + 4, "text-anchor": "end", class: "lbl" }, svg).textContent = r.name;
    const a = x(r.share_visible_pct), b = x(r.share_key_moment_pct);
    el("line", { x1: a, x2: b, y1: y, y2: y, stroke: "var(--ink-3)", "stroke-width": 2 }, svg);
    el("circle", { cx: a, cy: y, r: 6, fill: "var(--s1)", stroke: "var(--surface)", "stroke-width": 2 }, svg);
    el("circle", { cx: b, cy: y, r: 6, fill: "var(--s2)", stroke: "var(--surface)", "stroke-width": 2 }, svg);
    const d = r.share_key_moment_pct - r.share_visible_pct;
    if (Math.abs(d) >= 6) el("text", { x: Math.max(a, b) + 12, y: y + 4, class: "lbl" }, svg).textContent = (d > 0 ? "+" : "") + d.toFixed(0) + " pts";
    hover(el("rect", { x: 0, y: y - rowH / 2, width: W, height: rowH, fill: "transparent" }, svg),
      `<b>${r.name}</b> · ${TIER_LABEL[r.tier] || r.tier}<br>${r.share_visible_pct}% of screen time (${r.visible_s} s)<br>${r.share_key_moment_pct}% of goal moments (${r.key_moment_s} s)`);
  });
}

/* Game: every brand's seconds on screen, ticks coloured by tier, goal windows shaded */
function timeline(root, brands, moments, duration) {
  const rows = brands.filter((b) => b.visible_s >= 3).sort((a, b) => b.visible_s - a.visible_s);
  const W = 960, L = 140, R = 44, rowH = 20, T = 30, H = T + rows.length * rowH + 28;
  const x = (t) => L + (t / duration) * (W - L - R);
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, width: W, height: H, role: "img",
    "aria-label": "Second-by-second timeline of every sponsor detected, with goal windows shaded" }, root);
  moments.forEach((m) => {
    hover(el("rect", { x: x(m.start), y: T - 4, width: x(m.end) - x(m.start), height: rows.length * rowH + 4, fill: "var(--moment)" }, svg),
      `<b>${m.label}</b><br>${mmss(m.start)}–${mmss(m.end)} of the video`);
    el("text", { x: x(m.start) + 2, y: T - 10, class: "lbl small" }, svg).textContent = m.label.replace("Penalty shootout", "Shootout").replace(/ \(.*\)/, "").replace("Goal ", "");
  });
  const step = duration <= 180 ? 15 : duration > 1800 ? 600 : 120;
  for (let t = 0; t <= duration; t += step) el("text", { x: x(t), y: H - 6, "text-anchor": "middle" }, svg).textContent = mmss(t);
  rows.forEach((r, i) => {
    const y = T + i * rowH;
    el("line", { x1: L, x2: W - R, y1: y + rowH - 1, y2: y + rowH - 1, class: "grid" }, svg);
    el("text", { x: L - 10, y: y + 14, "text-anchor": "end", class: "lbl" }, svg).textContent = r.name;
    el("text", { x: W - R + 6, y: y + 14 }, svg).textContent = r.visible_s + "s";
    r.timeline.forEach(([t]) => {
      hover(el("rect", { x: x(t), y: y + 3, width: Math.max(2, x(t + 1) - x(t) - 0.5), height: rowH - 7, fill: TIER[r.tier] || "var(--ink-3)", rx: 1 }, svg),
        `<b>${r.name}</b> at ${mmss(t)}`);
    });
  });
}

function brandTable(root, brands) {
  const rows = [...brands].sort((a, b) => b.visible_s - a.visible_s);
  root.innerHTML = `<table><thead><tr><th>Brand</th><th>Tier</th><th>Home</th><th>Seconds on screen</th><th>Appearances</th><th>Share of screen time</th><th>Goal-moment seconds</th><th>Avg. frame covered</th></tr></thead><tbody>${
    rows.map((r) => `<tr><td>${r.name}</td><td class="nw"><span class="dot" style="background:${TIER[r.tier]}"></span>${r.tier}</td><td>${r.country}</td><td class="n">${r.visible_s}</td><td class="n">${r.appearances}</td><td class="n">${r.share_visible_pct}%</td><td class="n">${r.key_moment_s}</td><td class="n">${r.mean_area_pct.toFixed(2)}%</td></tr>`).join("")
  }</tbody></table>`;
}

function accuracyTable(root, scores) {
  const fmt = (x) => x == null ? "—" : x.toFixed(2);
  const rate = (x) => x && x.of ? x.found / x.of : null;  // from the counts, avoiding double rounding
  const ci = (c) => c && c[0] != null ? `<span class="muted"> (${fmt(c[0])}–${fmt(c[1])})</span>` : "";
  const label = { ocr: "On-device OCR (Apple Vision)", vi: "Google Video Intelligence", fused: "Both combined" };
  // Quality bands: recall good >= 0.80, fair >= 0.50; precision good >= 0.95, fair >= 0.85 (stated in the legend)
  const band = (v, good, fair) => v == null ? "" : v >= good ? "good" : v >= fair ? "fair" : "weak";
  const cell = (v, good, fair, extra = "") => {
    const b = band(v, good, fair);
    return `<td class="n${b ? " q-" + b : ""}"${b ? ` title="${b[0].toUpperCase() + b.slice(1)}"` : ""}>${fmt(v)}${extra}</td>`;
  };
  let html = `<table><thead><tr><th>Method</th><th>Game</th><th>Board recall</th><th>Large boards</th><th>Small / distant</th><th>Precision</th></tr></thead><tbody>`;
  for (const m of ["ocr", "vi", "fused"]) {
    Object.entries(scores).forEach(([tag, s], i) => {
      const r = s[m];
      html += `<tr${m === "fused" ? ' class="strong"' : ""}><td>${i === 0 ? label[m] : ""}</td><td>${s.short || tag}</td>
        ${cell(rate(r.board_all), 0.8, 0.5, ci(r.board_all.ci95))}${cell(rate(r.board_L), 0.8, 0.5)}${cell(rate(r.board_S), 0.8, 0.5)}
        ${cell(r.precision.precision, 0.95, 0.85, `<span class="muted"> (${r.precision.verified}/${r.precision.detected})</span>`)}</tr>`;
    });
  }
  root.innerHTML = html + "</tbody></table>";
}

/* Cost page: cost for 100,000 hours per option, bar to the low price and a line out to the high price */
function costBars(root, d) {
  const rows = [...d.options].sort((a, b) => b.usd_high - a.usd_high || b.usd_low - a.usd_low);
  const W = 760, L = 280, R = 100, rowH = 30, T = 8, H = T + rows.length * rowH + 30;
  const max = Math.ceil(Math.max(...rows.map((r) => r.usd_high)) / 200000) * 200000;
  const x = (v) => L + (v / max) * (W - L - R);
  const bandOf = (r) => r.usd_high <= d.bands.good_max_usd ? "good" : r.usd_high <= d.bands.fair_max_usd ? "fair" : "weak";
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, width: W, height: H, role: "img",
    "aria-label": "Cost to audit 100,000 hours of video for each option, highest first" }, root);
  for (let v = 0; v <= max; v += 200000) {
    el("line", { x1: x(v), x2: x(v), y1: T, y2: H - 24, class: "grid" }, svg);
    el("text", { x: x(v), y: H - 8, "text-anchor": "middle" }, svg).textContent = v === 0 ? "$0" : "$" + v / 1000 + "k";
  }
  const short = { apple_fullframe: "Apple, full frame only", apple_8w: "Apple, 8 workers", apple_4w: "Apple, 4 workers",
    gemini: "Gemini Flash-Lite", cloud_vision: "Cloud Vision text", rekognition: "AWS Rekognition video (price only)", rekognition_text: "AWS Rekognition text (price only)",
    vi: "Video Intelligence logos", apple_vi: "Apple + Video Intelligence" };
  rows.forEach((r, i) => {
    const y = T + i * rowH + rowH / 2;
    el("text", { x: L - 12, y: y + 4, "text-anchor": "end", class: "lbl" }, svg).textContent = short[r.id] || r.name;
    el("rect", { x: L, y: y - 8, width: Math.max(3, x(r.usd_low) - L), height: 16, rx: 3, fill: `var(--bar-${bandOf(r)})` }, svg);
    if (r.usd_high > r.usd_low) {
      el("line", { x1: x(r.usd_low), x2: x(r.usd_high), y1: y, y2: y, stroke: "var(--ink)", "stroke-width": 2 }, svg);
      el("line", { x1: x(r.usd_high), x2: x(r.usd_high), y1: y - 6, y2: y + 6, stroke: "var(--ink)", "stroke-width": 2 }, svg);
    }
    el("text", { x: x(r.usd_high) + 8, y: y + 4, class: "lbl" }, svg).textContent = r.usd_low === r.usd_high ? "$" + Math.round(r.usd_low / 1000) + "k"
      : "$" + Math.round(r.usd_low / 1000) + "k–" + Math.round(r.usd_high / 1000) + "k";
    hover(el("rect", { x: 0, y: y - rowH / 2, width: W, height: rowH, fill: "transparent" }, svg),
      `<b>${r.name}</b><br>$${r.usd_low.toLocaleString()}${r.usd_high > r.usd_low ? " to $" + r.usd_high.toLocaleString() : ""} for 100,000 hours<br>${r.basis}`);
  });
}

const page = (document.querySelector("[data-page]") || {}).dataset?.page;
const fail = (err) => document.querySelectorAll(".chart").forEach((c) => { c.textContent = "Chart data could not be loaded: " + err.message; });
if (page === "landing") {
  fetch("benchmark.json").then((r) => r.json()).then((d) => {
    tierBars(document.getElementById("tiers"), d.games);
    accuracyTable(document.getElementById("accuracy"), d.scores);
  }).catch(fail);
} else if (page === "cost") {
  fetch("cost_model.json").then((r) => r.json()).then((d) => costBars(document.getElementById("costbars"), d)).catch(fail);
} else if (page) {
  fetch(`game-${page}.json`).then((r) => r.json()).then((d) => {
    const brands = Object.values(d.brands);
    dumbbell(document.getElementById("dumbbell"), brands, d.duration < 300 ? 3 : 8);  // short clips: fewer seconds per brand
    timeline(document.getElementById("timeline"), brands, d.moments, d.duration);
    brandTable(document.getElementById("brands"), brands);
  }).catch(fail);
}
