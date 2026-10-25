// Light/dark switch for the landing and sign-in pages.
// Uses the same saved setting as the app (localStorage "datamind.settings.v1" -> theme),
// so choosing dark on one page makes every DataMind page dark.
(() => {
  const KEY = "datamind.settings.v1";
  const mq = matchMedia("(prefers-color-scheme: dark)");
  const read = () => { try { return JSON.parse(localStorage.getItem(KEY) || "{}"); } catch { return {}; } };
  const write = (s) => { try { localStorage.setItem(KEY, JSON.stringify(s)); } catch { /* private mode */ } };
  const effective = () => {
    const t = read().theme;
    return t === "light" || t === "dark" ? t : (mq.matches ? "dark" : "light");
  };

  // same icons as the app's theme button
  const svg = (d) => `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${d}</svg>`;
  const MOON = svg('<path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"/>');
  const SUN = svg('<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>');

  function paint() {
    const btn = document.getElementById("theme-toggle");
    if (!btn) return;
    const dark = effective() === "dark";
    btn.innerHTML = dark ? SUN : MOON;
    btn.title = dark ? "Switch to light theme" : "Switch to dark theme";
    btn.setAttribute("aria-label", btn.title);
  }
  function apply() {
    const t = read().theme;
    if (t === "light" || t === "dark") document.documentElement.dataset.theme = t;
    else delete document.documentElement.dataset.theme;
    paint();
  }

  document.addEventListener("click", (e) => {
    if (!e.target.closest("#theme-toggle")) return;
    const s = read();                       // keep the app's other settings
    s.theme = effective() === "dark" ? "light" : "dark";
    write(s);
    apply();
  });
  mq.addEventListener("change", paint);
  addEventListener("storage", (e) => { if (e.key === KEY) apply(); });   // other open tabs
  apply();
})();
