(() => {
  const $ = (id) => document.getElementById(id);
  const A = window.JarvisAdmin = {
    $,
    fmt: Jarvis.fmt,
    state: null,
    streaming: false,
    currentTab: "overview",
    currentFeature: null,
    featData: { features: [], categories: {}, errors: [] },
    tabs: {},
    titles: {},
    tab(id, def) { A.tabs[id] = def; if (def.title) A.titles[id] = def.title; },
    isOn(id) { const el = $(`tab-${id}`); return !!el && el.classList.contains("on"); },
    renderFeatureBar() {},
  };

  A.api = async (method, url, body) => {
    const opts = { method, headers: { "X-Jarvis-Request": "1" }, credentials: "same-origin" };
    if (body !== undefined) { opts.headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(body); }
    const r = await fetch(url, opts);
    if (r.status === 401) { A.showLogin(); throw new Error("Sessione scaduta"); }
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(data.detail || `Errore ${r.status}`);
    return data;
  };

  A.toast = (msg, err) => {
    const d = document.createElement("div");
    d.textContent = msg; if (err) d.className = "err";
    $("toast").appendChild(d); setTimeout(() => d.remove(), 4500);
  };

  A.flash = (id) => { const s = $(id); if (s) { s.classList.add("show"); setTimeout(() => s.classList.remove("show"), 1200); } };

  A.showLogin = () => { $("login").style.display = "flex"; $("app").classList.remove("show"); };

  const typing = () => {
    const el = document.activeElement;
    return !!el && ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName) && el.type !== "button";
  };

  A.onState = (s) => {
    if (s.asset_version && window.JARVIS_ASSET_V && s.asset_version !== window.JARVIS_ASSET_V && !typing()) {
      location.reload();
      return;
    }
    A.state = s;
    Object.values(A.tabs).forEach((t) => { if (t.onState) t.onState(s); });
  };

  A.showApp = (user) => {
    $("login").style.display = "none"; $("app").classList.add("show");
    $("who").textContent = `Connesso come ${user}`;
    if (!A.streaming) { A.streaming = true; Jarvis.connectState("/api/stream", A.onState, (ok) => $("link").classList.toggle("show", !ok)); }
    A.loadFeatures().then(() => {
      const h = location.hash.slice(1);
      if (h.startsWith("f/")) A.openFeature(h.slice(2)); else if (h) A.openTab(h);
    });
  };

  A.session = () => {
    try { return window.sessionStorage; } catch (e) { console.warn("Memoria di sessione non disponibile", e); return null; }
  };

  A.openTab = (tab, fid) => {
    const { featData } = A;
    if (!fid) { const f = featData.features.find((x) => x.panel === tab); A.currentFeature = f ? f.id : null; } else A.currentFeature = fid;
    const memo = A.session();
    if (!$(`tab-${tab}`)) {
      const stale = featData.features.some((x) => x.panel === tab);
      if (stale && memo && memo.getItem("jarvis-reload") !== tab) { memo.setItem("jarvis-reload", tab); location.hash = tab; location.reload(); return; }
      tab = "overview";
    } else if (memo) memo.removeItem("jarvis-reload");
    const previous = A.tabs[A.currentTab];
    if (A.currentTab !== tab && previous && previous.leave) previous.leave();
    A.currentTab = tab;
    document.querySelectorAll("nav a[data-tab]").forEach((x) => x.classList.toggle("on",
      A.currentFeature ? x.dataset.feature === A.currentFeature : x.dataset.tab === tab));
    document.querySelectorAll(".tab").forEach((x) => x.classList.toggle("on", x.id === `tab-${tab}`));
    const feat = A.currentFeature && featData.features.find((x) => x.id === A.currentFeature);
    $("title").textContent = feat ? feat.name : (A.titles[tab] || tab);
    A.renderFeatureBar();
    const def = A.tabs[tab];
    if (def && def.load) def.load(feat);
    history.replaceState(null, "", tab === "feature" && A.currentFeature ? `#f/${A.currentFeature}` : `#${tab}`);
    window.scrollTo({ top: 0 });
  };

  A.start = () => {
    document.querySelectorAll("nav a[data-tab]").forEach((a) => { A.titles[a.dataset.tab] = a.querySelector(".lb").textContent; });
    document.querySelector("nav").addEventListener("click", (e) => {
      const a = e.target.closest("a[data-tab]"); if (!a) return;
      if (a.dataset.feature) A.openFeature(a.dataset.feature); else A.openTab(a.dataset.tab);
    });
    $("login-form").addEventListener("submit", async (e) => {
      e.preventDefault(); $("login-err").textContent = "";
      try { const r = await A.api("POST", "/api/auth/login", { username: $("u").value, password: $("p").value }); $("p").value = ""; A.showApp(r.user); }
      catch (err) { $("login-err").textContent = err.message; }
    });
    $("logout").addEventListener("click", async () => { await A.api("POST", "/api/auth/logout").catch(() => {}); location.reload(); });
    Object.values(A.tabs).forEach((t) => { if (t.init) t.init(); });
    fetch("/api/auth/me").then((r) => r.ok ? r.json() : null).then((d) => d ? A.showApp(d.user) : A.showLogin());
  };
})();
