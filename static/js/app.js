// DataMind web app: routing, chats, live agent answers, data explorer, document search.
import { api, askStream } from "./api.js";
import * as store from "./store.js";
import {
  esc, fmt, icon, plural, timeAgo, AGENTS, initialStatus, applyStep, finalStatus, pipelineHTML,
  dataTable, highlightSQL, copyText, downloadFile, toCSV, toast, confirmBox,
} from "./components.js";
import { chartSpec, drawChart } from "./chart.js";

const $ = (s, root = document) => root.querySelector(s);
const $$ = (s, root = document) => [...root.querySelectorAll(s)];

const app = {
  view: "ask",
  chatId: null,
  running: null,        // { controller, chatId, msgId, status, started, timer }
  catalog: [],
  docs: [],
  health: null,
  table: null,
};

const EXAMPLES = [
  { title: "Numbers", colors: ["--a-data", "--a-sql"], items: [
    "Which product had the highest sales in 2025?",
    "What are the top 3 stores by revenue in 2025?",
    "Show monthly revenue for Fashion in 2025",
  ] },
  { title: "Numbers and reasons", colors: ["--a-sql", "--a-rag"], items: [
    "Why did Electronics sales in the West region drop in Q3 2025?",
    "Why did NovaSound X2 Earbuds have so many returns?",
    "Why did South region orders grow in 2025?",
  ] },
  { title: "Company policy", colors: ["--a-rag"], items: [
    "What is our return policy for electronics?",
    "What is the maximum discount a store manager can give?",
    "What happened during the Festive Dhamaka 2025 campaign?",
  ] },
];

/* ================================================================ icons */
function hydrateIcons(root = document) {
  $$("[data-icon]", root).forEach((el) => { el.outerHTML = icon(el.dataset.icon, 16); });
}
function setStaticIcons() {
  $("#new-chat").innerHTML = `${icon("plus")}New chat`;
  $("#open-sidebar").innerHTML = icon("menu", 20);
  $("#close-sidebar").innerHTML = icon("x", 20);
  $("#open-settings").innerHTML = icon("settings");
  $("#open-shortcuts").innerHTML = icon("keyboard");
  $("#sign-out").innerHTML = `<svg class="ic" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M15 4h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3M10 17l-5-5 5-5M5 12h11"/></svg>`;
  $$("dialog header .icon-btn").forEach((b) => { b.innerHTML = icon("x"); });
  hydrateIcons();
  setSendButton(false);
  updateThemeIcon();
}

/* ================================================================ theme */
const effectiveTheme = () => store.settings.theme === "system"
  ? (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")
  : store.settings.theme;

function applyTheme() {
  const t = store.settings.theme;
  if (t === "system") delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = t;
  updateThemeIcon();
}
function updateThemeIcon() {
  const dark = effectiveTheme() === "dark";
  $("#theme-toggle").innerHTML = icon(dark ? "sun" : "moon");
  $("#theme-toggle").title = dark ? "Switch to light theme" : "Switch to dark theme";
}
$("#theme-toggle").addEventListener("click", () => {
  store.settings.theme = effectiveTheme() === "dark" ? "light" : "dark";
  store.saveSettings();
  applyTheme();
});
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", updateThemeIcon);

/* ============================================================== routing */
function go(hash) {
  if (location.hash === hash) route();
  else location.hash = hash;
}

function route() {
  const [view = "chat", arg = ""] = location.hash.replace(/^#\/?/, "").split("/");
  closeSidebar();
  if (view === "data") {
    showView("data");
    renderTables(decodeURIComponent(arg));
  } else if (view === "docs") {
    showView("docs");
    renderDocs();
  } else {
    showView("ask");
    const id = arg && store.getChat(arg) ? arg : null;
    app.chatId = id;
    renderThread();
    renderChatList();
  }
}

function showView(name) {
  app.view = name;
  $$(".view").forEach((v) => { v.hidden = v.id !== `view-${name}`; });
  $$(".views a").forEach((a) => {
    if (a.dataset.view === name) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  });
  document.title = { ask: "DataMind", data: "Data · DataMind", docs: "Documents · DataMind" }[name];
}

window.addEventListener("hashchange", route);

/* ============================================================== sidebar */
function openSidebar() { $("#app").classList.add("nav-open"); $("#scrim").hidden = false; }
function closeSidebar() { $("#app").classList.remove("nav-open"); $("#scrim").hidden = true; }
$("#open-sidebar").addEventListener("click", openSidebar);
$("#close-sidebar").addEventListener("click", closeSidebar);
$("#scrim").addEventListener("click", closeSidebar);

$("#new-chat").addEventListener("click", newChat);
function newChat() {
  go("#/chat");
  setTimeout(() => $("#question").focus(), 0);
}

$("#chat-search").addEventListener("input", renderChatList);

function renderChatList() {
  const list = $("#chat-list");
  const q = $("#chat-search").value.trim().toLowerCase();
  const chats = store.listChats().filter((c) => c.messages.length &&
    (!q || c.title.toLowerCase().includes(q) || c.messages.some((m) => m.q.toLowerCase().includes(q))));

  if (!chats.length) {
    list.innerHTML = q
      ? `<p class="chat-empty">No chats match "${esc(q)}".</p>`
      : `<p class="chat-empty"><strong>No chats yet</strong>Your questions and answers are saved here in this browser.</p>`;
    return;
  }
  const startOfDay = new Date().setHours(0, 0, 0, 0);
  const groups = { Today: [], Yesterday: [], "Last 7 days": [], Older: [] };
  for (const c of chats) {
    const age = startOfDay - c.updated;
    const g = c.updated >= startOfDay ? "Today" : age < 864e5 ? "Yesterday" : age < 6 * 864e5 ? "Last 7 days" : "Older";
    groups[g].push(c);
  }
  list.innerHTML = Object.entries(groups).filter(([, cs]) => cs.length).map(([name, cs]) =>
    `<div class="chat-group">${name}</div>` + cs.map((c) => `
      <div class="chat-item ${c.id === app.chatId ? "active" : ""}" data-id="${c.id}">
        <a href="#/chat/${c.id}" title="${esc(c.title)}">${esc(c.title)}</a>
        <span class="row-actions">
          <button class="icon-btn" data-act="rename" aria-label="Rename chat" title="Rename">${icon("pencil", 15)}</button>
          <button class="icon-btn" data-act="delete" aria-label="Delete chat" title="Delete">${icon("trash", 15)}</button>
        </span>
      </div>`).join("")).join("");
}

$("#chat-list").addEventListener("click", async (e) => {
  const btn = e.target.closest("button[data-act]");
  if (!btn) return;
  const item = btn.closest(".chat-item");
  const id = item.dataset.id;
  if (btn.dataset.act === "rename") startRename(item, id);
  if (btn.dataset.act === "delete") deleteChat(id);
});

function startRename(item, id) {
  const chat = store.getChat(id);
  item.innerHTML = `<input value="${esc(chat.title)}" aria-label="Chat name">`;
  const input = $("input", item);
  input.focus();
  input.select();
  let done = false;
  const finish = (save) => {
    if (done) return;
    done = true;
    if (save) store.renameChat(id, input.value);
    renderChatList();
    if (id === app.chatId) renderChatHead();
  };
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") finish(true);
    if (e.key === "Escape") { e.stopPropagation(); finish(false); }
  });
  input.addEventListener("blur", () => finish(true));
}

async function deleteChat(id) {
  const chat = store.getChat(id);
  if (!chat) return;
  if (!(await confirmBox("Delete this chat?", `"${chat.title}" and its answers will be removed from this browser.`))) return;
  if (app.running?.chatId === id) app.running.controller.abort();
  store.deleteChat(id);
  toast("Chat deleted");
  if (app.chatId === id) go("#/chat");
  else renderChatList();
}

/* ============================================================== thread */
function renderChatHead() {
  const chat = app.chatId && store.getChat(app.chatId);
  const head = $("#thread .chat-head h1");
  if (chat && head) head.textContent = chat.title;
}

function renderThread() {
  const thread = $("#thread");
  const chat = app.chatId && store.getChat(app.chatId);
  thread.innerHTML = "";
  if (!chat || !chat.messages.length) {
    thread.append(welcomeEl());
    return;
  }
  const head = document.createElement("div");
  head.className = "chat-head";
  head.innerHTML = `<h1>${esc(chat.title)}</h1>
    <button class="btn ghost sm" data-act="export" title="Download this chat as Markdown">${icon("download", 16)}Export</button>
    <button class="btn ghost sm" data-act="delete" title="Delete this chat">${icon("trash", 16)}Delete</button>`;
  $("[data-act=export]", head).onclick = () => exportChat(chat);
  $("[data-act=delete]", head).onclick = () => deleteChat(chat.id);
  thread.append(head);
  for (const m of chat.messages) thread.append(messageEl(m));
  requestAnimationFrame(() => { thread.scrollTop = thread.scrollHeight; });
}

function welcomeEl() {
  const el = document.createElement("section");
  el.className = "welcome";
  const nTables = app.catalog.length;
  const nDocs = app.docs.length;
  el.innerHTML = `
    <h1>Ask your data a question</h1>
    <p class="lede">Type a question in plain English. DataMind plans the work, picks the right tables,
      writes and runs the SQL, and checks company documents for the reasons behind the numbers.</p>
    <div class="ready">
      <a href="#/data">${icon("database", 16)}<span><b>${nTables}</b> ${nTables === 1 ? "table" : "tables"} loaded</span></a>
      <a href="#/docs">${icon("file", 16)}<span><b>${nDocs}</b> ${nDocs === 1 ? "document" : "documents"} indexed</span></a>
    </div>
    <div class="examples">${EXAMPLES.map((g) => `
      <div><h2><span class="swatches">${g.colors.map((c) => `<i style="--c:var(${c})"></i>`).join("")}</span>${g.title}</h2>
      ${g.items.map((q) => `<button type="button">${esc(q)}</button>`).join("")}</div>`).join("")}
    </div>`;
  $$(".examples button", el).forEach((b) => b.addEventListener("click", () => ask(b.textContent)));
  return el;
}

function messageEl(m) {
  const el = document.createElement("article");
  el.className = "msg";
  el.dataset.id = m.id;
  el.innerHTML = `<header class="msg-q"><h2>${esc(m.q)}</h2><time datetime="${new Date(m.ts).toISOString()}">${timeAgo(m.ts)}</time></header>`;

  if (!m.resp && !m.error) {                       // still running
    const status = app.running?.msgId === m.id ? app.running.status : initialStatus();
    el.insertAdjacentHTML("beforeend", `<div class="live">${pipelineHTML(status)}</div>
      <p class="working">${icon("flow", 16)}<span>The agents are working on it</span><span class="elapsed">0.0 s</span></p>`);
    if (app.running?.msgId === m.id) app.running.el = el;
    return el;
  }
  if (m.error) {
    el.insertAdjacentHTML("beforeend", `
      <div class="alert" role="alert">${icon("alert")}<div><strong>${m.stopped ? "Stopped" : "Couldn't answer this question"}</strong><p>${esc(m.error)}</p></div></div>
      <div class="actions">
        <button class="btn ghost sm" data-act="retry">${icon("refresh", 16)}Try again</button>
        <button class="btn ghost sm" data-act="edit">${icon("edit", 16)}Edit question</button>
      </div>`);
    $("[data-act=retry]", el).onclick = () => ask(m.q);
    $("[data-act=edit]", el).onclick = () => editQuestion(m.q);
    return el;
  }
  renderAnswer(el, m);
  return el;
}

/* -------------------------------------------------------------- answer */
function renderAnswer(el, m) {
  const r = m.resp;
  const result = r.result && r.result.columns?.length ? r.result : null;
  const spec = result ? chartSpec(result) : null;
  const docs = r.documents || {};
  const chunks = r.rag_chunks || [];
  const attempts = r.sql_attempts || [];

  const tabs = [
    { id: "answer", label: "Answer", icon: "chat" },
    result && { id: "table", label: "Table", icon: "table", badge: result.row_count },
    spec && { id: "chart", label: "Chart", icon: "chart" },
    r.sql && { id: "sql", label: "SQL", icon: "code", badge: attempts.length > 1 ? `${attempts.length} tries` : null },
    docs.summary && { id: "sources", label: "Sources", icon: "book", badge: (docs.citations || []).length || chunks.length || null },
    { id: "agents", label: "Agents", icon: "flow" },
  ].filter(Boolean);

  el.insertAdjacentHTML("beforeend", `${pipelineHTML(finalStatus(r))}
    <div class="tabs" role="tablist" aria-label="Answer details">${tabs.map((t, i) => `
      <button role="tab" type="button" id="${m.id}-t-${t.id}" aria-controls="${m.id}-p-${t.id}" aria-selected="${i === 0}" tabindex="${i === 0 ? 0 : -1}" data-tab="${t.id}">
        ${icon(t.icon, 15)}${t.label}${t.badge ? `<span class="badge">${esc(t.badge)}</span>` : ""}</button>`).join("")}
    </div>
    ${tabs.map((t, i) => `<div class="tab-panel" role="tabpanel" id="${m.id}-p-${t.id}" aria-labelledby="${m.id}-t-${t.id}" data-panel="${t.id}" ${i ? "hidden" : ""}></div>`).join("")}
    <div class="actions">
      <button class="btn ghost sm" data-act="copy">${icon("copy", 16)}Copy answer</button>
      <button class="btn ghost sm" data-act="edit">${icon("edit", 16)}Edit question</button>
      <button class="btn ghost sm" data-act="rerun">${icon("refresh", 16)}Ask again</button>
      ${result ? `<button class="btn ghost sm" data-act="csv">${icon("download", 16)}Download CSV</button>` : ""}
      ${r.seconds ? `<span class="meta">Answered in ${r.seconds.toFixed(1)} s</span>` : ""}
    </div>`);

  const rendered = new Set();
  const renderers = {
    answer(p) {
      p.innerHTML = `<p class="answer-text">${esc(r.answer || "No answer was generated.")}</p>`;
      if (r.sql_error) p.insertAdjacentHTML("beforeend", `<p class="note">The SQL agent couldn't produce a working query. See the SQL tab for each attempt.</p>`);
      const cites = docs.citations || [];
      if (cites.length) {
        p.insertAdjacentHTML("beforeend", `<div class="cite-row">${icon("book", 15)}<span>Sources</span>${cites.map((c) =>
          `<button type="button" class="chip rag" data-goto="sources">${esc(c)}</button>`).join("")}</div>`);
      }
      if (spec && store.settings.autoChart) {
        const box = document.createElement("div");
        p.append(box);
        chartBlock(box, spec, m.id);
      }
    },
    table(p) {
      p.append(dataTable(result));
      if (result.truncated) p.insertAdjacentHTML("beforeend", `<p class="note">Showing the first ${result.row_count} rows. Ask a narrower question to see the rest.</p>`);
    },
    chart(p) { chartBlock(p, spec, m.id + "-full"); },
    sql(p) {
      p.innerHTML = `<div class="code"><pre><code>${highlightSQL(r.sql)}</code></pre>
        <button class="btn sm copy" type="button">${icon("copy", 15)}Copy</button></div>`;
      $(".copy", p).onclick = () => copyText(r.sql);
      if (attempts.length > 1 || r.sql_error) {
        p.insertAdjacentHTML("beforeend", `<div class="panel-title"><h3>How the SQL agent got there</h3></div>
          <ol class="attempts">${attempts.map((a) => `<li class="${a.ok ? "ok" : ""}">
            <strong>Attempt ${a.attempt}</strong>: ${a.ok ? `ran, ${plural(a.rows ?? 0, "row")}` : `rejected, <code>${esc((a.error || "").slice(0, 240))}</code>`}
          </li>`).join("")}</ol>`);
      }
      if (r.sql_error) p.insertAdjacentHTML("beforeend", `<div class="alert" style="margin-top:14px">${icon("alert")}<div><strong>Final error</strong><p>${esc(r.sql_error)}</p></div></div>`);
    },
    sources(p) {
      p.innerHTML = `<p class="answer-text" style="font-size:15.5px">${esc(docs.summary)}</p>`;
      if (chunks.length) {
        p.insertAdjacentHTML("beforeend", `<div class="panel-title"><h3>Passages the RAG agent retrieved</h3></div>
          <div class="passages">${chunks.map((c) => passageHTML(c)).join("")}</div>`);
      } else if (!store.settings.debug) {
        p.insertAdjacentHTML("beforeend", `<p class="note">Turn on "Show agent details" in Settings to see the retrieved passages.</p>`);
      }
    },
    agents(p) {
      const plan = r.plan || {};
      const colorOf = { Supervisor: "--a-sup", "Data Agent": "--a-data", "SQL Agent": "--a-sql", "RAG Agent": "--a-rag", Response: "--a-resp" };
      p.innerHTML = `
        <ol class="steps">${(r.trace || []).map((t) => {
          const [who, ...rest] = t.split(":");
          return `<li style="--c:var(${colorOf[who] || "--faint"})"><span><b>${esc(who)}</b>: ${esc(rest.join(":").trim())}</span></li>`;
        }).join("")}</ol>
        <div class="panel-title"><h3>Supervisor's plan</h3></div>
        <dl class="kv">
          <dt>Intent</dt><dd>${esc((plan.intent || "").replace(/_/g, " "))}</dd>
          ${plan.reasoning ? `<dt>Reasoning</dt><dd>${esc(plan.reasoning)}</dd>` : ""}
          ${plan.data_task ? `<dt>Task for SQL</dt><dd>${esc(plan.data_task)}</dd>` : ""}
          ${plan.doc_query ? `<dt>Document search</dt><dd>${esc(plan.doc_query)}</dd>` : ""}
          ${(plan.subtasks || []).length ? `<dt>Steps</dt><dd>${plan.subtasks.map(esc).join("<br>")}</dd>` : ""}
        </dl>
        ${(r.selected_tables || []).length ? `<div class="panel-title"><h3>Tables the Data agent chose</h3></div>
          <dl class="kv">${r.selected_tables.map((t) => `<dt>${esc(t.table)}</dt><dd>${esc((t.columns || []).join(", "))}${t.reason ? `<br><span class="muted">${esc(t.reason)}</span>` : ""}</dd>`).join("")}</dl>` : ""}`;
    },
  };

  const select = (id) => {
    $$(".tabs [role=tab]", el).forEach((b) => {
      const on = b.dataset.tab === id;
      b.setAttribute("aria-selected", on);
      b.tabIndex = on ? 0 : -1;
    });
    $$(".tab-panel", el).forEach((p) => { p.hidden = p.dataset.panel !== id; });
    const panel = $(`[data-panel="${id}"]`, el);
    if (!rendered.has(id)) { renderers[id](panel); rendered.add(id); }
  };
  select("answer");

  const tablist = $(".tabs", el);
  tablist.addEventListener("click", (e) => {
    const b = e.target.closest("[role=tab]");
    if (b) select(b.dataset.tab);
  });
  tablist.addEventListener("keydown", (e) => {
    if (!["ArrowRight", "ArrowLeft"].includes(e.key)) return;
    const btns = $$("[role=tab]", tablist);
    const i = btns.findIndex((b) => b.getAttribute("aria-selected") === "true");
    const next = btns[(i + (e.key === "ArrowRight" ? 1 : -1) + btns.length) % btns.length];
    select(next.dataset.tab);
    next.focus();
  });
  el.addEventListener("click", (e) => {
    const g = e.target.closest("[data-goto]");
    if (g) select(g.dataset.goto);
  });

  $("[data-act=copy]", el).onclick = () => copyText(r.answer || "");
  $("[data-act=edit]", el).onclick = () => editQuestion(m.q);
  $("[data-act=rerun]", el).onclick = () => ask(m.q);
  const csv = $("[data-act=csv]", el);
  if (csv) csv.onclick = () => downloadFile(`datamind_${slug(m.q)}.csv`, toCSV(result), "text/csv");
}

function chartBlock(host, spec, key) {
  let type = spec.defaultType;
  host.innerHTML = `<div class="panel-title">
      <h3>${esc(spec.series.map((s) => s.name).join(", "))} by ${esc(spec.labelName)}${spec.truncated ? "<small>first 60 rows</small>" : ""}</h3>
      <div class="segmented" role="group" aria-label="Chart type">
        <button type="button" data-type="bar">Bar</button><button type="button" data-type="line">Line</button>
      </div></div><div class="chart"></div>`;
  const draw = () => {
    $$(".segmented button", host).forEach((b) => b.setAttribute("aria-pressed", b.dataset.type === type));
    drawChart($(".chart", host), spec, type);
  };
  $$(".segmented button", host).forEach((b) => b.addEventListener("click", () => { type = b.dataset.type; draw(); }));
  draw();
  // redraw when the available width changes (window resize, sidebar, rotation)
  let lastW = $(".chart", host).clientWidth, pending;
  new ResizeObserver(() => {
    const w = $(".chart", host).clientWidth;
    if (!w || Math.abs(w - lastW) < 24) return;
    lastW = w;
    clearTimeout(pending);
    pending = setTimeout(draw, 120);
  }).observe($(".chart", host));
}

function passageHTML(c, terms = []) {
  let text = esc(c.text);
  for (const t of terms) {
    if (t.length < 3) continue;
    text = text.replace(new RegExp(`(${t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "gi"), "<mark>$1</mark>");
  }
  const pct = Math.max(0, Math.min(1, c.score)) * 100;
  return `<article class="passage"><header><strong>${esc(c.source)}, page ${c.page}</strong>
    <span class="score" title="Similarity ${c.score}"><i style="--w:${pct}%"></i>${Math.round(pct)}% match</span></header>
    <p>${text}</p></article>`;
}

const slug = (s) => s.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "").slice(0, 40) || "result";

/* ================================================================= ask */
function setSendButton(running) {
  const b = $("#send");
  b.classList.toggle("stop", running);
  b.innerHTML = icon(running ? "stop" : "arrowUp", 20);
  b.setAttribute("aria-label", running ? "Stop" : "Ask");
  b.title = running ? "Stop (Esc)" : "Ask (Enter)";
}

function editQuestion(q) {
  const ta = $("#question");
  ta.value = q;
  autoGrow();
  ta.focus();
  ta.setSelectionRange(q.length, q.length);
}

async function ask(question) {
  question = question.trim();
  if (!question) return;
  if (app.running) { toast("Wait for the current answer, or press Esc to stop it.", "err"); return; }

  let chat = app.chatId && store.getChat(app.chatId);
  if (!chat) {
    chat = store.createChat();
    app.chatId = chat.id;
    history.replaceState(null, "", `#/chat/${chat.id}`);
  }
  const msg = { id: store.uid(), q: question, ts: Date.now() };
  store.addMessage(chat.id, msg);

  const controller = new AbortController();
  const run = { controller, chatId: chat.id, msgId: msg.id, status: initialStatus(), started: performance.now(), el: null };
  app.running = run;
  setSendButton(true);
  renderThread();
  renderChatList();

  run.timer = setInterval(() => {
    const e = run.el && $(".elapsed", run.el);
    if (e) e.textContent = `${((performance.now() - run.started) / 1000).toFixed(1)} s`;
  }, 100);

  let patch;
  try {
    const resp = await askStream(question, store.settings.debug, {
      signal: controller.signal,
      onStep(step) {
        applyStep(run.status, step);
        const live = run.el && $(".live", run.el);
        if (live) live.innerHTML = pipelineHTML(run.status);
      },
    });
    patch = { resp };
  } catch (e) {
    patch = e.name === "AbortError"
      ? { error: "You stopped the agents before they finished. Ask again when you're ready.", stopped: true }
      : { error: e.message };
  } finally {
    clearInterval(run.timer);
    app.running = null;
    setSendButton(false);
  }
  store.updateMessage(chat.id, msg.id, patch);
  if (app.chatId === chat.id && app.view === "ask") {
    const old = $(`.msg[data-id="${msg.id}"]`);
    const fresh = messageEl({ ...msg, ...patch });
    if (old) old.replaceWith(fresh);
    fresh.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  renderChatList();
}

function stopRunning() {
  if (app.running) app.running.controller.abort();
}

/* composer */
const ta = $("#question");
function autoGrow() {
  ta.style.height = "auto";
  ta.style.height = Math.min(ta.scrollHeight, 200) + "px";
}
ta.addEventListener("input", autoGrow);
ta.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
    e.preventDefault();
    $("#composer").requestSubmit();
  } else if (e.key === "ArrowUp" && !ta.value) {
    const chat = app.chatId && store.getChat(app.chatId);
    const last = chat?.messages.at(-1)?.q;
    if (last) { e.preventDefault(); editQuestion(last); }
  }
});
$("#composer").addEventListener("submit", (e) => {
  e.preventDefault();
  if (app.running) { stopRunning(); return; }
  const q = ta.value;
  if (!q.trim()) { ta.focus(); return; }
  ta.value = "";
  autoGrow();
  ask(q);
});

function exportChat(chat) {
  const lines = [`# ${chat.title}`, "", `Exported from DataMind on ${new Date().toLocaleString("en-IN")}`, ""];
  for (const m of chat.messages) {
    lines.push(`## ${m.q}`, "");
    if (m.error) { lines.push(`> Error: ${m.error}`, ""); continue; }
    const r = m.resp;
    lines.push(r.answer || "", "");
    if (r.sql) lines.push("```sql", r.sql, "```", "");
    const res = r.result;
    if (res?.columns?.length) {
      lines.push(`| ${res.columns.join(" | ")} |`, `| ${res.columns.map(() => "---").join(" | ")} |`);
      for (const row of res.rows.slice(0, 30)) lines.push(`| ${row.map((v) => fmt(v)).join(" | ")} |`);
      if (res.rows.length > 30) lines.push(`\n_${res.rows.length - 30} more rows not shown_`);
      lines.push("");
    }
    if (r.documents?.summary) lines.push(`**From company documents:** ${r.documents.summary}`, "");
  }
  downloadFile(`${slug(chat.title)}.md`, lines.join("\n"), "text/markdown");
  toast("Chat exported as Markdown");
}

/* ============================================================ data view */
async function loadCatalog() {
  try { app.catalog = await api.tables(); }
  catch (e) { app.catalog = []; toast(e.message, "err"); }
}

$("#table-filter").addEventListener("input", () => renderTableCards());

function renderTableCards() {
  const q = $("#table-filter").value.trim().toLowerCase();
  const list = app.catalog.filter((t) => !q || t.table.includes(q) || t.columns.some((c) => c.name.includes(q)));
  $("#table-count").textContent = plural(app.catalog.length, "table");
  $("#table-cards").innerHTML = list.length ? list.map((t) => `
    <li><a class="card" href="#/data/${encodeURIComponent(t.table)}" ${t.table === app.table ? 'aria-current="true"' : ""}>
      <span class="card-top"><strong>${esc(t.table)}</strong>${t.uploaded ? '<span class="tag">Uploaded</span>' : ""}</span>
      <small>${plural(t.row_count, "row")}, ${plural(t.columns.length, "column")}</small></a></li>`).join("")
    : `<li class="chat-empty">${q ? `No tables match "${esc(q)}".` : "No tables loaded. Add a dataset below."}</li>`;
}

async function renderTables(selected) {
  if (!app.catalog.length) await loadCatalog();
  app.table = selected && app.catalog.some((t) => t.table === selected) ? selected : null;
  renderTableCards();
  const pane = $("#table-detail");
  if (!app.table) {
    pane.innerHTML = `<div class="empty-state">${icon("database", 36)}<h3>Pick a table to explore</h3>
      <p>See its columns, the values they hold, and a preview of the rows. The Data agent uses this same information to choose tables for your questions.</p></div>`;
    return;
  }
  const t = app.catalog.find((x) => x.table === app.table);
  pane.innerHTML = `
    <div class="detail-head">
      <div><h2>${esc(t.table)}</h2>
        <p>${plural(t.row_count, "row")}, ${plural(t.columns.length, "column")}${t.source ? `, from ${esc(t.source)}` : ""}</p></div>
      <div class="btns">
        <button class="btn primary" data-act="ask">${icon("chat", 16)}Ask about this table</button>
        <button class="btn danger" data-act="drop">${icon("trash", 16)}Remove</button>
      </div>
    </div>
    <div class="tabs" role="tablist">
      <button role="tab" type="button" aria-selected="true" data-tab="cols">${icon("table", 15)}Columns</button>
      <button role="tab" type="button" aria-selected="false" data-tab="rows">${icon("database", 15)}Preview rows</button>
    </div>
    <div data-panel="cols"></div><div data-panel="rows" hidden></div>`;

  $('[data-panel="cols"]', pane).innerHTML = `<div style="overflow-x:auto"><table class="col-list">
    <thead><tr><th>Column</th><th>Type</th><th>What it holds</th></tr></thead><tbody>
    ${t.columns.map((c) => `<tr><td>${esc(c.name)}</td><td><span class="type">${esc(c.type.toLowerCase())}</span></td><td>${columnInfo(c)}</td></tr>`).join("")}
    </tbody></table></div>`;

  let loaded = false;
  $$(".tabs [role=tab]", pane).forEach((b) => b.addEventListener("click", async () => {
    $$(".tabs [role=tab]", pane).forEach((x) => x.setAttribute("aria-selected", x === b));
    $$("[data-panel]", pane).forEach((p) => { p.hidden = p.dataset.panel !== b.dataset.tab; });
    if (b.dataset.tab === "rows" && !loaded) {
      loaded = true;
      const panel = $('[data-panel="rows"]', pane);
      panel.innerHTML = `<div class="skeleton"></div><div class="skeleton"></div><div class="skeleton" style="width:60%"></div>`;
      try {
        const p = await api.preview(t.table, 100);
        panel.innerHTML = "";
        panel.append(dataTable(p, { maxHeight: 560 }));
        panel.insertAdjacentHTML("beforeend", `<p class="note">First ${p.rows.length} of ${t.row_count.toLocaleString("en-IN")} rows. Click a column name to sort.</p>`);
      } catch (e) {
        panel.innerHTML = `<div class="alert">${icon("alert")}<div><strong>Couldn't load rows</strong><p>${esc(e.message)}</p></div></div>`;
        loaded = false;
      }
    }
  }));

  $("[data-act=ask]", pane).onclick = () => {
    go("#/chat");
    setTimeout(() => editQuestion(`Give me an overview of the ${t.table} table with its key totals`), 0);
  };
  const drop = $("[data-act=drop]", pane);
  if (drop) drop.onclick = async () => {
    const msg = t.uploaded
      ? "The table and its uploaded file will be deleted. Questions can no longer use it."
      : "The table will be removed. Its file is moved to data/removed/ and can be restored by moving it back.";
    if (!(await confirmBox(`Remove ${t.table}?`, msg, "Remove"))) return;
    try {
      await api.dropTable(t.table);
      toast(`Removed ${t.table}`);
      await loadCatalog();
      go("#/data");
      loadHealth();
    } catch (e) { toast(e.message, "err"); }
  };
}

function columnInfo(c) {
  if (c.values) return `<span class="vals">${c.values.map((v) => `<span class="chip">${esc(fmt(v))}</span>`).join("")}</span>`;
  if (c.examples) return `<span class="muted">${plural(c.distinct || 0, "distinct value")}, e.g. ${c.examples.map((v) => esc(fmt(v))).join(", ")}</span>`;
  if ("min" in c) return `<span class="muted">from ${esc(fmt(c.min))} to ${esc(fmt(c.max))}</span>`;
  return "";
}

/* ============================================================ docs view */
async function loadDocs() {
  try {
    const d = await api.documents();
    app.docs = d.documents || [];
  } catch { app.docs = []; }
}

function renderDocs() {
  $("#doc-count").textContent = plural(app.docs.length, "document");
  $("#doc-cards").innerHTML = app.docs.length ? app.docs.map((d) => `
    <li class="card doc-card">${icon("file", 18)}
      <div><strong>${esc(d.name.replace(/_/g, " ").replace(/\.(pdf|txt|md)$/i, ""))}</strong><small>${esc(d.name.split(".").pop().toUpperCase())}, ${plural(d.chunks, "passage")}</small></div>
      <button class="icon-btn" data-del="${esc(d.name)}" aria-label="Remove ${esc(d.name)}" title="Remove">${icon("trash", 16)}</button></li>`).join("")
    : `<li class="chat-empty"><strong>No documents indexed</strong>Add a PDF below, or run <code>python -m rag.ingest</code>.</li>`;
  if (!$("#doc-results").innerHTML) {
    $("#doc-results").innerHTML = `<div class="empty-state" style="margin-top:6vh">${icon("search", 32)}<h3>Search across ${plural(app.docs.length, "document")}</h3>
      <p>Results are ranked by meaning, not exact words, so "stock ran out" finds passages about stock-outs.</p></div>`;
  }
}

$("#doc-cards").addEventListener("click", async (e) => {
  const b = e.target.closest("[data-del]");
  if (!b) return;
  const name = b.dataset.del;
  if (!(await confirmBox("Remove this document?", `${name} will be deleted and removed from the search index.`, "Remove"))) return;
  try {
    await api.deleteDoc(name);
    toast(`Removed ${name}`);
    await loadDocs();
    renderDocs();
    loadHealth();
  } catch (err) { toast(err.message, "err"); }
});

$("#doc-search").addEventListener("submit", async (e) => {
  e.preventDefault();
  const q = $("#doc-query").value.trim();
  const out = $("#doc-results");
  if (q.length < 2) { $("#doc-query").focus(); return; }
  out.innerHTML = `<div class="skeleton"></div><div class="skeleton"></div><div class="skeleton" style="width:70%"></div>`;
  try {
    const { results } = await api.searchDocs(q, 6);
    const terms = q.split(/\s+/);
    out.innerHTML = results.length
      ? `<p class="results-head">${plural(results.length, "passage")} for "${esc(q)}"</p><div class="passages">${results.map((c) => passageHTML(c, terms)).join("")}</div>`
      : `<div class="empty-state">${icon("search", 32)}<h3>Nothing found</h3><p>No indexed document mentions anything close to "${esc(q)}".</p></div>`;
  } catch (err) {
    out.innerHTML = `<div class="alert">${icon("alert")}<div><strong>Search failed</strong><p>${esc(err.message)}</p></div></div>`;
  }
});

/* ============================================================== uploads */
function setupDrop(zone) {
  const input = $("input[type=file]", zone);
  const kind = zone.dataset.kind;
  const label = $("strong", zone);
  const original = label.textContent;

  zone.addEventListener("click", () => input.click());
  zone.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); input.click(); } });
  zone.addEventListener("dragover", (e) => { e.preventDefault(); zone.classList.add("over"); });
  zone.addEventListener("dragleave", () => zone.classList.remove("over"));
  zone.addEventListener("drop", (e) => {
    e.preventDefault();
    zone.classList.remove("over");
    if (e.dataTransfer.files[0]) upload(e.dataTransfer.files[0]);
  });
  input.addEventListener("change", () => { if (input.files[0]) upload(input.files[0]); input.value = ""; });

  async function upload(file) {
    zone.classList.add("busy");
    label.textContent = `Uploading ${file.name}…`;
    try {
      const r = await api.upload(kind, file);
      if (kind === "dataset") {
        toast(`Loaded ${r.file} as ${r.tables_created.join(", ")}`);
        await loadCatalog();
        go(`#/data/${encodeURIComponent(r.tables_created[0])}`);
      } else {
        toast(`Indexed ${r.file} (${plural(r.chunks_indexed, "passage")})`);
        await loadDocs();
        renderDocs();
      }
      loadHealth();
    } catch (e) {
      toast(e.message, "err");
    } finally {
      zone.classList.remove("busy");
      label.textContent = original;
    }
  }
}
$$(".drop").forEach(setupDrop);

/* ============================================================== status */
async function loadHealth() {
  const el = $("#status");
  try {
    app.health = await api.health();
    el.innerHTML = `<span class="dot on"></span><span title="${esc(app.health.provider)} ${esc(app.health.model)}">${esc(app.health.model)}</span>`;
  } catch {
    app.health = null;
    el.innerHTML = `<span class="dot off"></span><span>Server offline</span>`;
  }
}

/* ============================================================== account */
async function loadAccount() {
  try {
    const { user } = await api.me();
    $("#account-company").textContent = user.company;
    $("#account-user").textContent = `${user.name}, ${user.email}`;
    $("#account-initial").textContent = user.company.trim().charAt(0).toUpperCase();
    $("#account").hidden = false;
  } catch { /* not signed in: api.js already sends the browser to /login */ }
}
$("#sign-out").addEventListener("click", async () => {
  stopRunning();
  try { await api.logout(); } catch { /* signing out anyway */ }
  location.href = "/login";
});

/* ============================================================= settings */
const settingsDlg = $("#settings");
$("#open-settings").addEventListener("click", () => {
  $$("#theme-choice input").forEach((r) => { r.checked = r.value === store.settings.theme; });
  $("#set-debug").checked = store.settings.debug;
  $("#set-chart").checked = store.settings.autoChart;
  settingsDlg.showModal();
});
$$("#theme-choice input").forEach((r) => r.addEventListener("change", () => {
  store.settings.theme = r.value;
  store.saveSettings();
  applyTheme();
}));
$("#set-debug").addEventListener("change", (e) => { store.settings.debug = e.target.checked; store.saveSettings(); });
$("#set-chart").addEventListener("change", (e) => {
  store.settings.autoChart = e.target.checked;
  store.saveSettings();
  if (app.view === "ask" && !app.running) renderThread();
});
$("#clear-chats").addEventListener("click", async () => {
  settingsDlg.close();
  if (!(await confirmBox("Clear all chats?", "Every saved conversation in this browser will be removed. This can't be undone.", "Clear chats"))) return;
  stopRunning();
  store.clearChats();
  toast("All chats cleared");
  go("#/chat");
});
$("#open-shortcuts").addEventListener("click", () => $("#shortcuts").showModal());

/* ============================================================ shortcuts */
document.addEventListener("keydown", (e) => {
  const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement?.tagName);
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); newChat(); return; }
  if (e.key === "Escape" && app.running && !document.querySelector("dialog[open]")) { stopRunning(); return; }
  if (typing || document.querySelector("dialog[open]")) return;
  if (e.key === "/") { e.preventDefault(); if (app.view !== "ask") go(app.chatId ? `#/chat/${app.chatId}` : "#/chat"); setTimeout(() => ta.focus(), 0); }
  if (e.key === "?") { e.preventDefault(); $("#shortcuts").showModal(); }
});

/* ================================================================ start */
async function start() {
  setStaticIcons();
  applyTheme();
  renderChatList();
  route();
  await Promise.all([loadAccount(), loadHealth(), loadCatalog(), loadDocs()]);
  if (app.view === "ask" && !app.chatId) renderThread();   // refresh counts on the welcome screen
  if (app.view === "data") renderTables(app.table);
  if (app.view === "docs") renderDocs();
  setInterval(loadHealth, 30000);
}
start();
