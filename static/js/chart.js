// Small dependency-free SVG charts (bar / line), so charts work offline too.
import { esc, compact, fmt } from "./components.js";

const TIME_RE = /(^|_)(date|day|week|month|mon|year|yr|qtr|quarter|period|time)($|_)/i;
const ID_RE = /(^|_)id$/i;

/** Decide whether a SQL result can be charted, and how. Returns null if not. */
export function chartSpec(result) {
  if (!result?.columns?.length || !result.rows || result.rows.length < 2) return null;
  const { columns, rows } = result;
  const isNum = columns.map((_, i) => rows.every((r) => r[i] === null || typeof r[i] === "number"));

  // label column: prefer a "name"-like text column, then any text column, then a time-like number
  let labelIdx = columns.findIndex((c, i) => !isNum[i] && /name|title|label/i.test(c));
  if (labelIdx < 0) labelIdx = columns.findIndex((c, i) => !isNum[i] && !ID_RE.test(c));
  if (labelIdx < 0) labelIdx = columns.findIndex((c, i) => !isNum[i]);
  if (labelIdx < 0) labelIdx = columns.findIndex((c) => TIME_RE.test(c));
  if (labelIdx < 0) return null;

  const series = columns
    .map((name, i) => ({ name, i }))
    .filter(({ name, i }) => i !== labelIdx && isNum[i] && !ID_RE.test(name) && !TIME_RE.test(name))
    .slice(0, 4);
  if (!series.length) return null;

  const labelName = columns[labelIdx];
  const sample = rows.slice(0, 60);
  const labels = sample.map((r) => String(r[labelIdx] ?? "").replace(/T00:00:00.*$/, ""));
  const timeLike = TIME_RE.test(labelName) || labels.every((l) => /^\d{4}-\d{2}/.test(l));

  return {
    labelName,
    labels,
    timeLike,
    truncated: rows.length > sample.length,
    series: series.map((s) => ({ name: s.name, values: sample.map((r) => Number(r[s.i] ?? 0)) })),
    defaultType: timeLike && sample.length > 2 ? "line" : "bar",
  };
}

function niceTicks(min, max, count = 5) {
  if (min === max) max = min + 1;
  const raw = (max - min) / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const norm = raw / mag;
  const step = (norm < 1.5 ? 1 : norm < 3 ? 2 : norm < 7 ? 5 : 10) * mag;
  const lo = Math.floor(min / step) * step;
  const hi = Math.ceil(max / step) * step;
  const ticks = [];
  for (let v = lo; v <= hi + step / 2; v += step) ticks.push(+v.toFixed(10));
  return ticks;
}

const shorten = (s, n) => (s.length > n ? s.slice(0, n - 1) + "…" : s);

/** Draw the chart into `host`. type: "bar" | "line". */
export function drawChart(host, spec, type) {
  // draw at the real on-screen width so text stays readable on phones
  const W = Math.round(Math.max(300, Math.min(960, host.clientWidth - 28 || 760)));
  const H = W < 520 ? 240 : 320;
  const n = spec.labels.length;
  const longLabels = spec.labels.some((l) => l.length > 8) && n > (W < 520 ? 2 : 4);
  const m = { t: 18, r: 14, b: longLabels ? 84 : 40, l: W < 520 ? 48 : 64 };
  const iw = W - m.l - m.r, ih = H - m.t - m.b;

  const all = spec.series.flatMap((s) => s.values);
  const ticks = niceTicks(Math.min(0, ...all), Math.max(0, ...all));
  const lo = ticks[0], hi = ticks[ticks.length - 1];
  const y = (v) => m.t + ih - ((v - lo) / (hi - lo || 1)) * ih;
  const band = iw / n;
  const cx = (i) => m.l + band * i + band / 2;

  let g = "";
  for (const t of ticks) {
    g += `<line class="grid" x1="${m.l}" x2="${W - m.r}" y1="${y(t)}" y2="${y(t)}"/>`;
    g += `<text class="tick" x="${m.l - 8}" y="${y(t) + 4}" text-anchor="end">${esc(compact(t))}</text>`;
  }
  const every = Math.max(1, Math.ceil(n / (iw / (longLabels ? 26 : 56))));
  spec.labels.forEach((l, i) => {
    if (i % every) return;
    const yPos = H - m.b + 18;
    g += longLabels
      ? `<text class="tick" transform="translate(${cx(i)},${yPos - 6}) rotate(-38)" text-anchor="end">${esc(shorten(l, 16))}</text>`
      : `<text class="tick" x="${cx(i)}" y="${yPos}" text-anchor="middle">${esc(shorten(l, 12))}</text>`;
  });
  g += `<line class="axis" x1="${m.l}" x2="${W - m.r}" y1="${y(0)}" y2="${y(0)}"/>`;

  let marks = "";
  const k = spec.series.length;
  if (type === "bar") {
    const gw = Math.min(band * 0.72, 64 * k);
    const bw = gw / k;
    spec.series.forEach((s, si) => {
      s.values.forEach((v, i) => {
        const x = cx(i) - gw / 2 + si * bw;
        const top = Math.min(y(v), y(0));
        const h = Math.max(1, Math.abs(y(v) - y(0)));
        marks += `<rect class="mark s${si}" x="${x + 1}" y="${top}" width="${Math.max(1, bw - 2)}" height="${h}" rx="2"/>`;
      });
    });
  } else {
    spec.series.forEach((s, si) => {
      const d = s.values.map((v, i) => `${i ? "L" : "M"}${cx(i)},${y(v)}`).join(" ");
      marks += `<path class="line s${si}" d="${d}"/>`;
      if (n <= 40) s.values.forEach((v, i) => { marks += `<circle class="dot s${si}" cx="${cx(i)}" cy="${y(v)}" r="3.5"/>`; });
    });
  }

  let hits = "";
  for (let i = 0; i < n; i++) {
    hits += `<rect class="hit" data-i="${i}" x="${m.l + band * i}" y="${m.t}" width="${band}" height="${ih}"/>`;
  }

  const legend = k > 1
    ? `<div class="legend">${spec.series.map((s, si) => `<span><i class="s${si}"></i>${esc(s.name)}</span>`).join("")}</div>`
    : "";
  const label = `${spec.series.map((s) => s.name).join(", ")} by ${spec.labelName}`;

  host.innerHTML = `${legend}<div class="chart-box">
    <svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(type)} chart of ${esc(label)}">${g}${marks}${hits}</svg>
    <div class="chart-tip" hidden></div></div>`;

  const tip = host.querySelector(".chart-tip");
  const svg = host.querySelector("svg");
  host.querySelectorAll(".hit").forEach((el) => {
    el.addEventListener("mouseenter", () => {
      const i = +el.dataset.i;
      tip.innerHTML = `<strong>${esc(spec.labels[i])}</strong>` +
        spec.series.map((s, si) => `<span><i class="s${si}"></i>${esc(s.name)}: ${esc(fmt(s.values[i]))}</span>`).join("");
      tip.hidden = false;
      const box = svg.getBoundingClientRect();
      const px = (cx(i) / W) * box.width;
      tip.style.left = `${Math.min(Math.max(px, 70), box.width - 70)}px`;
      el.classList.add("on");
    });
    el.addEventListener("mouseleave", () => { tip.hidden = true; el.classList.remove("on"); });
  });
}
