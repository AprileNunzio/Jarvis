(() => {
  const A = window.JarvisAdmin, { $, fmt } = A;
  let currentPlaylists = [];

  function badge(m) {
    const st = m.step || {};
    if (!m.enabled) return '<span class="badge">disattivato</span>';
    if (st.status === "failed") return `<span class="badge down">errore</span> <span class="faint" style="font-size:12px">${fmt.esc(st.error || "")} - nuovo tentativo</span>`;
    return m.installed && st.status !== "running" ? '<span class="badge ok">attivo</span>' : '<span class="badge warn">installazione...</span>';
  }

  function nowPlaying(np) {
    if (!np.title) return '<div class="faint">Nessuna musica ambientale rilevata.</div>';
    return `<div class="row" style="gap:14px; align-items:flex-start">${np.cover ? `<img src="${fmt.esc(np.cover)}" style="width:84px;height:84px;border-radius:10px;object-fit:cover">` : ""}
          <div><div style="font-size:16px">${fmt.esc(np.title)}</div><div style="color:var(--cyan)">${fmt.esc(np.artist || "")}</div>
          <div class="faint" style="font-size:12px">${fmt.esc([np.album, np.year, np.genre, np.label].filter(Boolean).join(" - "))}</div></div></div>`;
  }

  function renderPlaylists() {
    const container = $("mu-playlists-body");
    if (!currentPlaylists.length) {
      container.innerHTML = "Nessuna playlist creata.";
      return;
    }
    container.innerHTML = currentPlaylists.map((p, i) => 
      `<div style="display:flex; justify-content:space-between; align-items:center; padding: 6px 0; border-bottom: 1px solid var(--border);">
         <div><strong>${fmt.esc(p.name)}</strong> <span class="faint">(${p.tracks ? p.tracks.length : 0} brani)</span></div>
         <button class="btn del-pl-btn" data-idx="${i}" style="padding: 2px 6px; background: var(--red); color: #fff; border: none; border-radius: 4px; cursor: pointer; font-size: 12px;">Elimina</button>
       </div>`
    ).join("");
    
    document.querySelectorAll(".del-pl-btn").forEach(btn => {
      btn.addEventListener("click", async (e) => {
        const idx = parseInt(e.target.getAttribute("data-idx"), 10);
        currentPlaylists.splice(idx, 1);
        await savePlaylists(currentPlaylists);
        renderPlaylists();
      });
    });
  }

  async function loadPlaylists() {
    try {
      currentPlaylists = await A.api("GET", "/api/music/playlists");
      if (!Array.isArray(currentPlaylists)) currentPlaylists = [];
      renderPlaylists();
    } catch (err) {
      $("mu-playlists-body").textContent = "Errore di rete.";
    }
  }

  async function savePlaylists(pl) {
    try {
      await A.api("POST", "/api/music/playlists", pl);
      A.toast("Playlist aggiornate", false);
    } catch (err) {
      A.toast(err.message, true);
    }
  }

  async function loadMusic() {
    let m;
    try { m = await A.api("GET", "/api/music"); } 
    catch (e) { $("mu-body").textContent = e.message; return; }
    
    $("mu-body").innerHTML = `<div class="row" style="justify-content:space-between; flex-wrap:wrap; margin-bottom:12px">
        <label class="switch"><input type="checkbox" id="mu-on" ${m.enabled ? "checked" : ""}> Attiva Microfono</label><span>${badge(m)}</span></div>`
      + nowPlaying(m.now_playing || {});
  }

  function init() {
    $("mu-body").addEventListener("change", async (e) => {
      if (e.target.id !== "mu-on") return;
      try { 
        await A.api("PUT", "/api/music", { enabled: e.target.checked }); 
        A.toast(e.target.checked ? "Ambientale attivato" : "Ambientale disattivato"); 
        loadMusic(); 
      } catch (err) { A.toast(err.message, true); }
    });

    const createBtn = $("mu-create-playlist-btn");
    if (createBtn) {
      createBtn.addEventListener("click", async () => {
        const inp = $("mu-new-playlist-name");
        const val = inp.value.trim();
        if (!val) return;
        currentPlaylists.push({ name: val, tracks: [] });
        inp.value = "";
        await savePlaylists(currentPlaylists);
        renderPlaylists();
      });
    }

    const autoOn = $("mu-auto-on");
    if (autoOn) {
      const saved = localStorage.getItem("jarvis_music_auto") === "true";
      autoOn.checked = saved;
      autoOn.addEventListener("change", (e) => {
        localStorage.setItem("jarvis_music_auto", e.target.checked);
        A.toast(e.target.checked ? "Auto-Organizer Attivato" : "Auto-Organizer Disattivato");
      });
    }
  }

  function onState(s) {
    const sig = (s.now_playing && s.now_playing.key) || "";
    if (sig === window.__npSig) return;
    window.__npSig = sig;
    if (A.isOn("music")) loadMusic();
  }

  A.tab("music", { title: "Musica", init, load: () => { loadMusic(); loadPlaylists(); }, onState });
})();
