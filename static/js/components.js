// Reusable UI pieces: formatting, icons, agent pipeline, data table, SQL highlight, toasts, dialogs.

/* ------------------------------------------------------------ formatting */
export const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

export function fmt(v) {
  if (typeof v === "number") {
    if (!Number.isInteger(v)) return v.toLocaleString("en-IN", { maximumFractionDigits: 2 });
    return Math.abs(v) >= 10000 ? v.toLocaleString("en-IN") : String(v);
  }
  if (v === null || v === undefined) return "";
  return String(v).replace(/T00:00:00$/, "");
}

/** Compact Indian units for chart axes: 1.2 Cr, 34 L, 5K */
export function compact(v) {
  const a = Math.abs(v);
  const t = (x, d) => x.toFixed(d).replace(/\.0+$/, "");
  if (a >= 1e7) return `${t(v / 1e7, a >= 1e8 ? 0 : 1)} Cr`;
  if (a >= 1e5) return `${t(v / 1e5, a >= 1e6 ? 0 : 1)} L`;
  if (a >= 1e3) return `${t(v / 1e3, a >= 1e4 ? 0 : 1)}K`;
  return String(+v.toFixed(2));
}

export function timeAgo(ts) {
  const s = (Date.now() - ts) / 1000;
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return new Date(ts).toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}

export const plural = (n, word) => `${n.toLocaleString("en-IN")} ${word}${n === 1 ? "" : "s"}`;

/* ------------------------------------------------------------------ icons */
const PATHS = {
  plus: '<path d="M12 5v14M5 12h14"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
  chat: '<path d="M20 12a8 8 0 0 1-11.6 7.1L4 20l.9-4.4A8 8 0 1 1 20 12z"/>',
  database: '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/>',
  file: '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M14 3v6h6M8 13h8M8 17h5"/>',
  trash: '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>',
  pencil: '<path d="M4 20h4L19 9l-4-4L4 16z"/>',
  copy: '<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h8"/>',
  refresh: '<path d="M20 11a8 8 0 1 0-2.3 5.7M20 4v7h-7"/>',
  download: '<path d="M12 4v11m-5-5 5 5 5-5M5 20h14"/>',
  upload: '<path d="M12 16V5m-5 5 5-5 5 5M5 20h14"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  moon: '<path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"/>',
  menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
  x: '<path d="M6 6l12 12M18 6 6 18"/>',
  send: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  stop: '<rect x="7" y="7" width="10" height="10" rx="1.5" fill="currentColor" stroke="none"/>',
  settings: '<path d="M4 7h9M17 7h3M4 17h3M11 17h9"/><circle cx="15" cy="7" r="2"/><circle cx="9" cy="17" r="2"/>',
  keyboard: '<rect x="3" y="6" width="18" height="12" rx="2"/><path d="M7 10h.01M11 10h.01M15 10h.01M7 14h10"/>',
  edit: '<path d="M9 14 4 9l5-5M4 9h10a6 6 0 0 1 6 6v5"/>',
  check: '<path d="M5 12l5 5 9-10"/>',
  table: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 10h18M9 4v16"/>',
  chart: '<path d="M5 20V11M11 20V5M17 20v-6M3 20h18"/>',
  code: '<path d="M9 8l-4 4 4 4M15 8l4 4-4 4"/>',
  book: '<path d="M5 4h11a3 3 0 0 1 3 3v13H8a3 3 0 0 1-3-3z"/><path d="M5 17a3 3 0 0 1 3-3h11"/>',
  flow: '<circle cx="6" cy="6" r="2.5"/><circle cx="6" cy="18" r="2.5"/><circle cx="18" cy="12" r="2.5"/><path d="M6 8.5v7M8.3 7l7.4 4M8.3 17l7.4-4"/>',
  alert: '<path d="M12 4 2.5 20h19z"/><path d="M12 10v4M12 17h.01"/>',
  arrowUp: '<path d="M12 19V5m-6 6 6-6 6 6"/>',
};
export const icon = (name, size = 18) =>
  `<svg class="ic" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${PATHS[name] || ""}</svg>`;

/* --------------------------------------------------------- agent pipeline */
export const AGENTS = [
  { node: "supervisor", label: "Supervisor", color: "var(--a-sup)", role: "Plans the work" },
  { node: "data_agent", label: "Data", color: "var(--a-data)", role: "Picks tables" },
  { node: "sql_agent", label: "SQL", color: "var(--a-sql)", role: "Writes and runs SQL" },
  { node: "rag_agent", label: "RAG", color: "var(--a-rag)", role: "Searches documents" },
  { node: "interim_response", label: "Answer", color: "var(--a-resp)", role: "Writes the answer" },
];
const ORDER = AGENTS.map((a) => a.node);

export function initialStatus() {
  const s = {};
  for (const n of ORDER) s[n] = { state: "pending", detail: "Waiting" };
  s.supervisor = { state: "active", detail: "Planning" };
  return s;
}

const clean = (t) => t.replace(/^[^:]+:\s*/, "").replace(/[[\]']/g, "");

function detailFromTrace(node, line, plan) {
  if (node === "supervisor") return (plan?.intent || "planned").replace(/_/g, " ");
  if (node === "sql_agent") {
    const m = line.match(/(\d+) rows in (\d+) attempt/);
    return m ? `${plural(+m[1], "row")}, ${plural(+m[2], "attempt")}` : "Query failed";
  }
  if (node === "rag_agent") {
    const m = line.match(/(\d+) chunks/);
    return m ? `${plural(+m[1], "passage")} found` : clean(line);
  }
  if (node === "data_agent") {
    const m = line.match(/selected \[(.*?)\]/);
    return m ? m[1].replace(/'/g, "") : clean(line);
  }
  return "Answer written";
}

/** Apply one streamed step to the status map (mutates). */
export function applyStep(status, step) {
  const line = step.trace?.[0] || "";
  const failed = step.node === "sql_agent" && /failed/.test(line);
  status[step.node] = { state: failed ? "failed" : "done", detail: detailFromTrace(step.node, line, step.plan) };
  if (step.node === "supervisor" && step.plan) {
    if (!step.plan.needs_data) status.data_agent = status.sql_agent = { state: "skipped", detail: "Not needed" };
    if (!step.plan.needs_docs) status.rag_agent = { state: "skipped", detail: "Not needed" };
  }
  const next = ORDER.find((n) => status[n].state === "pending");
  if (next) status[next] = { state: "active", detail: "Working" };
}

/** Rebuild the final status from a saved response. */
export function finalStatus(resp) {
  const status = {};
  const trace = resp.trace || [];
  const prefix = { supervisor: "Supervisor", data_agent: "Data Agent", sql_agent: "SQL Agent",
                   rag_agent: "RAG Agent", interim_response: "Response" };
  for (const n of ORDER) {
    const line = trace.find((t) => t.startsWith(prefix[n] + ":"));
    if (!line) { status[n] = { state: "skipped", detail: "Not needed" }; continue; }
    const failed = n === "sql_agent" && resp.sql_error;
    status[n] = { state: failed ? "failed" : "done", detail: detailFromTrace(n, line, resp.plan) };
  }
  return status;
}

export function pipelineHTML(status) {
  return `<ol class="pipe" aria-label="Agent progress">${AGENTS.map((a) => {
    const s = status[a.node];
    return `<li class="node ${s.state}" style="--c:${a.color}" title="${esc(a.role)}: ${esc(s.detail)}">
      <span class="node-name">${a.label}</span><span class="node-detail">${esc(s.detail)}</span></li>`;
  }).join("")}</ol>`;
}

/* ------------------------------------------------------------- data table */
/** Sortable, filterable table element for {columns, rows}. */
export function dataTable({ columns, rows }, { filterable = true, maxHeight = 440 } = {}) {
  const wrap = document.createElement("div");
  wrap.className = "dt";
  const isNum = columns.map((_, i) => rows.length > 0 && rows.every((r) => r[i] === null || typeof r[i] === "number"));
  let sortCol = -1, sortDir = 1, query = "";

  wrap.innerHTML = `
    ${filterable && rows.length > 8 ? `<div class="dt-bar"><label class="field small">${icon("search", 16)}
      <input type="search" placeholder="Filter rows" aria-label="Filter rows"></label><span class="dt-count"></span></div>` : ""}
    <div class="dt-scroll" style="max-height:${maxHeight}px"><table><thead><tr>${columns.map((c, i) =>
      `<th class="${isNum[i] ? "num" : ""}" aria-sort="none"><button type="button" data-col="${i}">${esc(c)}<span class="sort"></span></button></th>`).join("")}
    </tr></thead><tbody></tbody></table></div>`;

  const tbody = wrap.querySelector("tbody");
  const count = wrap.querySelector(".dt-count");

  function render() {
    let view = rows;
    if (query) {
      const q = query.toLowerCase();
      view = rows.filter((r) => r.some((v) => String(v ?? "").toLowerCase().includes(q)));
    }
    if (sortCol >= 0) {
      view = [...view].sort((a, b) => {
        const x = a[sortCol], y = b[sortCol];
        if (x === y) return 0;
        if (x === null) return 1;
        if (y === null) return -1;
        return (isNum[sortCol] ? x - y : String(x).localeCompare(String(y))) * sortDir;
      });
    }
    tbody.innerHTML = view.length
      ? view.map((r) => `<tr>${r.map((v, i) => `<td class="${isNum[i] ? "num" : ""}">${esc(fmt(v))}</td>`).join("")}</tr>`).join("")
      : `<tr><td class="dt-empty" colspan="${columns.length}">No rows match "${esc(query)}"</td></tr>`;
    if (count) count.textContent = query ? `${view.length} of ${rows.length} rows` : `${rows.length} rows`;
  }

  wrap.querySelectorAll("th button").forEach((b) => b.addEventListener("click", () => {
    const c = +b.dataset.col;
    sortDir = sortCol === c ? -sortDir : 1;
    sortCol = c;
    wrap.querySelectorAll("th").forEach((th, i) => th.setAttribute("aria-sort",
      i === c ? (sortDir === 1 ? "ascending" : "descending") : "none"));
    render();
  }));
  wrap.querySelector(".dt-bar input")?.addEventListener("input", (e) => { query = e.target.value.trim(); render(); });
  render();
  return wrap;
}

/* ---------------------------------------------------------- SQL highlight */
const KW = /\b(SELECT|FROM|WHERE|GROUP|BY|ORDER|HAVING|LIMIT|JOIN|LEFT|RIGHT|INNER|OUTER|FULL|ON|AS|AND|OR|NOT|IN|IS|NULL|BETWEEN|LIKE|ILIKE|CASE|WHEN|THEN|ELSE|END|WITH|DISTINCT|UNION|ALL|DESC|ASC|OVER|PARTITION|USING|DATE|INTERVAL|EXTRACT|CAST|FILTER)\b/gi;
const FN = /\b([a-z_][a-z0-9_]*)(?=\()/gi;

export function highlightSQL(sql) {
  // tokenise strings first so keywords inside quotes are left alone
  return sql.split(/('(?:[^']|'')*')/g).map((part, i) => {
    if (i % 2) return `<span class="t-str">${esc(part)}</span>`;
    return esc(part)
      .replace(/\b(\d+(?:\.\d+)?)\b/g, '<span class="t-num">$1</span>')
      .replace(FN, '<span class="t-fn">$1</span>')
      .replace(KW, (k) => `<span class="t-kw">${k.toUpperCase()}</span>`);
  }).join("");
}

/* ----------------------------------------------------------- misc helpers */
export async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    toast("Copied to clipboard");
  } catch {
    toast("Couldn't copy. Select the text and copy it manually.", "err");
  }
}

export function downloadFile(name, text, type = "text/plain") {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([text], { type }));
  a.download = name;
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

export function toCSV({ columns, rows }) {
  const cell = (v) => {
    const s = String(v ?? "");
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  return [columns.map(cell).join(","), ...rows.map((r) => r.map(cell).join(","))].join("\n");
}

export function toast(message, kind = "ok") {
  const host = document.getElementById("toasts");
  const el = document.createElement("div");
  el.className = `toast ${kind}`;
  el.innerHTML = `${icon(kind === "err" ? "alert" : "check", 16)}<span>${esc(message)}</span>`;
  host.append(el);
  setTimeout(() => { el.classList.add("out"); setTimeout(() => el.remove(), 250); }, kind === "err" ? 5000 : 2600);
}

/** Promise-based confirm using the #confirm <dialog>. */
export function confirmBox(title, body, action = "Delete") {
  const dlg = document.getElementById("confirm");
  dlg.querySelector("h2").textContent = title;
  dlg.querySelector("p").textContent = body;
  dlg.querySelector("[value=ok]").textContent = action;
  dlg.returnValue = "";
  dlg.showModal();
  return new Promise((resolve) => dlg.addEventListener("close", () => resolve(dlg.returnValue === "ok"), { once: true }));
}
