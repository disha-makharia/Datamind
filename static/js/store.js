// Chats and settings, saved in the browser (localStorage) so they survive a refresh.
const CHATS_KEY = "datamind.chats.v1";
const SETTINGS_KEY = "datamind.settings.v1";

function load(key, fallback) {
  try {
    const v = localStorage.getItem(key);
    return v ? JSON.parse(v) : fallback;
  } catch {
    return fallback;
  }
}
function save(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
    return true;
  } catch {
    return false;
  }
}

export const settings = Object.assign(
  { theme: "system", debug: true, autoChart: true },
  load(SETTINGS_KEY, {}),
);
export const saveSettings = () => save(SETTINGS_KEY, settings);

let chats = load(CHATS_KEY, []);

export const uid = () => Math.random().toString(36).slice(2, 9) + Date.now().toString(36);

function persist() {
  if (save(CHATS_KEY, chats)) return;
  // storage full: drop heavy detail from older answers and retry
  for (const c of chats) {
    for (const m of c.messages) {
      if (!m.resp) continue;
      delete m.resp.rag_chunks;
      if (m.resp.result?.rows?.length > 50) m.resp.result.rows = m.resp.result.rows.slice(0, 50);
    }
  }
  save(CHATS_KEY, chats);
}

export const listChats = () => [...chats].sort((a, b) => b.updated - a.updated);
export const getChat = (id) => chats.find((c) => c.id === id);

export function createChat() {
  const chat = { id: uid(), title: "New chat", updated: Date.now(), messages: [] };
  chats.push(chat);
  persist();
  return chat;
}
export function renameChat(id, title) {
  const c = getChat(id);
  if (c && title.trim()) { c.title = title.trim().slice(0, 80); persist(); }
}
export function deleteChat(id) {
  chats = chats.filter((c) => c.id !== id);
  persist();
}
export function clearChats() {
  chats = [];
  persist();
}
export function addMessage(chatId, msg) {
  const c = getChat(chatId);
  c.messages.push(msg);
  if (c.messages.length === 1) c.title = msg.q.length > 60 ? msg.q.slice(0, 57) + "…" : msg.q;
  c.updated = Date.now();
  persist();
}
export function updateMessage(chatId, msgId, patch) {
  const c = getChat(chatId);
  const m = c?.messages.find((x) => x.id === msgId);
  if (m) { Object.assign(m, patch); c.updated = Date.now(); persist(); }
}
