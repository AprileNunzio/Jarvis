(() => {
  const A = window.JarvisAdmin, { $, fmt } = A;
  let loaded = false, timer = null;

  function local() {
    if (window.JarvisSfx) return Promise.resolve(window.JarvisSfx);
    return new Promise((ok) => { const s = document.createElement("script"); s.src = "/static/shared/sfx.js"; s.onload = () => ok(window.JarvisSfx); document.head.appendChild(s); });
  }

  function render(d) {
    const st = d.state;
    const until = st.dnd && st.dnd.until ? ` fino alle ${new Date(st.dnd.until * 1000).toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit" })}` : "";
    $("sn-status").textContent = `${st.enabled ? "Attivi" : "Disattivati"} · volume ${st.volume}% · tema ${st.theme} · sottofondo ${d.ambients[st.ambient] || st.ambient}`
      + ` · ${st.dnd ? `NON DISTURBARE${until}` : st.quiet ? `orario di silenzio (${st.quiet_start}-${st.quiet_end}, ${st.level === "mute" ? "muto" : "attenuato"})` : `silenzio ${st.quiet_mode === "off" ? "mai" : `dalle ${st.quiet_start} alle ${st.quiet_end}`}`}`;
    if (loaded) return;
    loaded = true;
    $("sn-grid").innerHTML = d.sounds.map((s) => `<div class="sn-item" data-name="${fmt.esc(s.name)}"><div><b>${fmt.esc(s.label)}</b>
      <div class="faint">${fmt.esc(s.category)}${s.urgent ? " · suona anche in silenzio" : ""}</div></div>
      <div><button class="btn sm" data-here>Qui</button> <button class="btn sm" data-there>Sul display</button></div></div>`).join("");
    $("sn-amb").innerHTML = '<span class="faint">Sottofondo qui:</span>' + Object.entries(d.ambients).map(([k, v]) => `<button class="btn sm" data-amb="${k}">${fmt.esc(v)}</button>`).join("");
  }

  async function load() { try { render(await A.api("GET", "/api/sounds")); } catch (e) { $("sn-status").textContent = e.message; } }

  function init() {
    $("sn-grid").addEventListener("click", async (e) => {
      const item = e.target.closest("[data-name]"); if (!item) return;
      const name = item.dataset.name;
      if (e.target.closest("[data-here]")) (await local()).play(name);
      if (e.target.closest("[data-there]")) { const r = await A.api("POST", `/api/sounds/play/${name}`); A.toast(r.message); }
    });
    $("sn-amb").addEventListener("click", async (e) => {
      const b = e.target.closest("[data-amb]"); if (!b) return;
      (await local()).ambient(b.dataset.amb, 0.25);
    });
    document.querySelectorAll("#tab-sounds [data-dnd]").forEach((b) => b.addEventListener("click", async () => {
      const v = b.dataset.dnd;
      let body = { off: v === "off" };
      if (v === "60") body = { minutes: 60 };
      if (v === "night") { const n = new Date(), t = new Date(n); t.setHours(7, 0, 0, 0); if (t <= n) t.setDate(t.getDate() + 1); body = { minutes: (t - n) / 60000 }; }
      if (v === "always") body = {};
      const r = await A.api("POST", "/api/sounds/dnd", body); A.toast(r.message); load();
    }));
  }

  A.tab("sounds", {
    title: "Suoni", init,
    load() { load(); clearInterval(timer); timer = setInterval(() => { if (A.isOn("sounds")) load(); }, 15000); },
    leave() { clearInterval(timer); if (window.JarvisSfx) window.JarvisSfx.ambient("none"); },
  });
})();
