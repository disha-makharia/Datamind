// All communication with the FastAPI backend lives here.
const BASE = location.protocol.startsWith("http") ? "" : "http://127.0.0.1:8000";
const OFFLINE = "Can't reach the DataMind server. Start it with: uvicorn main:app --reload";

export class ApiError extends Error {}

// signed out or session expired: go to the sign-in page
function toLogin() {
  location.href = "/login";
  return new ApiError("Please sign in again.");
}

async function request(path, opts = {}) {
  let res;
  try {
    res = await fetch(BASE + path, { credentials: "same-origin", ...opts });
  } catch (e) {
    if (e.name === "AbortError") throw e;
    throw new ApiError(OFFLINE);
  }
  if (res.status === 401) throw toLogin();
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = typeof body.detail === "string" ? body.detail : `Server returned ${res.status}`;
    throw new ApiError(detail);
  }
  return body;
}

const enc = encodeURIComponent;

export const api = {
  me: () => request("/auth/me"),
  logout: () => request("/auth/logout", { method: "POST" }),
  health: () => request("/health"),
  tables: () => request("/tables"),
  preview: (table, limit = 100) => request(`/tables/${enc(table)}/preview?limit=${limit}`),
  dropTable: (table) => request(`/tables/${enc(table)}`, { method: "DELETE" }),
  documents: () => request("/documents"),
  searchDocs: (q, k = 6) => request(`/documents/search?q=${enc(q)}&k=${k}`),
  deleteDoc: (name) => request(`/documents/${enc(name)}`, { method: "DELETE" }),
  upload(kind, file) {
    const fd = new FormData();
    fd.append("file", file);
    return request(`/upload/${kind}`, { method: "POST", body: fd });
  },
};

/**
 * Ask a question and receive live agent progress via Server-Sent Events.
 * onStep({node, trace, plan, elapsed}) fires as each agent finishes.
 * Resolves with the full response when the "done" event arrives.
 */
export async function askStream(question, debug, { onStep, signal } = {}) {
  let res;
  try {
    res = await fetch(BASE + "/ask/stream", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, debug }),
      signal,
    });
  } catch (e) {
    if (e.name === "AbortError") throw e;
    throw new ApiError(OFFLINE);
  }
  if (res.status === 401) throw toLogin();
  if (!res.ok) {
    const b = await res.json().catch(() => ({}));
    throw new ApiError(typeof b.detail === "string" ? b.detail : `Server returned ${res.status}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
    let cut;
    while ((cut = buffer.indexOf("\n\n")) >= 0) {
      const raw = buffer.slice(0, cut);
      buffer = buffer.slice(cut + 2);
      let event = "message", data = "";
      for (const line of raw.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data += line.slice(5).trim();
      }
      const payload = data ? JSON.parse(data) : {};
      if (event === "step") onStep?.(payload);
      else if (event === "done") return payload;
      else if (event === "error") throw new ApiError(payload.detail || "The agents failed to answer");
    }
  }
  throw new ApiError("The connection closed before the answer arrived. Check the server terminal for errors.");
}
