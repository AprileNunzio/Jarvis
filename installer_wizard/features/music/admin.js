(() => {
  const A = window.JarvisAdmin, { $, fmt } = A;

  function badge(m) {
    const st = m.step || {};
    if (!m.enabled) return '<span class="badge">disattivato</span>';
    if (st.status === "failed") return `<span class="badge down">errore</span> <span class="faint" style="font-size:12px">${fmt.esc(st.error || "")} — nuovo tentativo automatico</span>`;
    return m.installed && st.status !== "running" ? '<span class="badge ok">attivo</span>' : '<span class="badge warn">installazione in corso…</span>';
  }

  function nowPlaying(np) {
    if (!np.title) return '<div class="faint">In questo momento non c\'è musica riconosciuta.</div>';
    return `<div class="row" style="gap:14px; align-items:flex-start">${np.cover ? `<img src="${fmt.esc(np.cover)}" style="width:84px;height:84px;border-radius:10px;object-fit:cover">` : ""}
          <div><div style="font-size:16px">${fmt.esc(np.title)}</div><div style="color:var(--cyan)">${fmt.esc(np.artist || "")}</div>
          <div class="faint" style="font-size:12px">${fmt.esc([np.album, np.year, np.genre, np.label].filter(Boolean).join(" · "))}</div>
          ${np.bio && np.bio.text ? `<div class="dim" style="font-size:12px; margin-top:6px">${fmt.esc(np.bio.text)}</div>` : ""}</div></div>`;
  }

  async function loadMusic() {
    let m; try { m = await A.api("GET", "/api/music"); } catch (e) { $("mu-body").textContent = e.message; return; }
    $("mu-body").innerHTML = `<div class="row" style="justify-content:space-between; flex-wrap:wrap; margin-bottom:12px">
        <label class="switch"><input type="checkbox" id="mu-on" ${m.enabled ? "checked" : ""}> Riconosci la musica che ascolto</label><span>${badge(m)}</span></div>`
      + nowPlaying(m.now_playing || {})
      + (m.history.length ? `<div class="panel-title" style="margin-top:16px">Ascoltati di recente</div>` + m.history.map((h) => `<div style="font-size:13px; padding:3px 0">${fmt.esc(h.title)} <span class="faint">— ${fmt.esc(h.artist || "")} · ${new Date(h.at * 1000).toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit" })}</span></div>`).join("") : "");
  }

  function init() {
    $("mu-body").addEventListener("change", async (e) => {
      if (e.target.id !== "mu-on") return;
      try { await A.api("PUT", "/api/music", { enabled: e.target.checked }); A.toast(e.target.checked ? "Riconoscimento musicale attivato" : "Riconoscimento musicale disattivato"); loadMusic(); setTimeout(loadMusic, 15000); }
      catch (err) { A.toast(err.message, true); }
    });
  }

  function onState(s) {
    const sig = (s.now_playing && s.now_playing.key) || "";
    if (sig === window.__npSig) return;
    window.__npSig = sig;
    if (A.isOn("music")) loadMusic();
  }

  A.tab("music", { title: "Musica", init, load: loadMusic, onState });
})();
