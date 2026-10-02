(() => {
  const A = window.JarvisAdmin, { $, fmt } = A;

  async function loadCredentials() {
    const cfg = await A.api("GET", "/api/config");
    const id = cfg.editable.find((x) => x.key === "JARVIS_SPOTIFY_CLIENT_ID");
    if (id && document.activeElement !== $("sp-id")) $("sp-id").value = id.value;
    const sec = cfg.editable.find((x) => x.key === "JARVIS_SPOTIFY_CLIENT_SECRET");
    $("sp-secret").placeholder = sec && sec.set ? sec.value : "non impostato";
  }

  async function loadSpotify() {
    let d; try { d = await A.api("GET", "/api/spotify"); } catch (e) { A.toast(e.message, true); return; }
    $("sp-status").innerHTML = d.configured ? `<span class="badge ok">collegato</span> ${fmt.esc(d.user || "")} <span class="faint">${fmt.esc(d.status)}</span>`
      : d.has_credentials ? '<span class="badge warn">da collegare</span> Premi «Collega account».' : '<span class="badge">non configurato</span> Inserisci le credenziali dell\'app Spotify.';
    $("sp-redirect").textContent = d.redirect_uri;
    const n = d.now || {};
    $("sp-now").innerHTML = n.title ? `${n.cover ? `<img src="${fmt.esc(n.cover)}" style="width:64px;height:64px;border-radius:8px;float:left;margin-right:12px">` : ""}<div>${fmt.esc(n.title)}</div><div style="color:#1ed760">${fmt.esc(n.artist)}</div>` : "Nulla in riproduzione.";
    await loadCredentials();
  }

  function init() {
    $("sp-creds").addEventListener("submit", async (e) => {
      e.preventDefault();
      const body = { JARVIS_SPOTIFY_CLIENT_ID: $("sp-id").value.trim() };
      if ($("sp-secret").value.trim()) body.JARVIS_SPOTIFY_CLIENT_SECRET = $("sp-secret").value.trim();
      try { await A.api("PUT", "/api/config", body); $("sp-secret").value = ""; A.toast("Credenziali salvate"); loadSpotify(); } catch (err) { A.toast(err.message, true); }
    });
    $("sp-auth").addEventListener("click", async () => {
      try { const r = await A.api("POST", "/api/spotify/auth-url"); window.open(r.url, "_blank", "noopener"); $("sp-finish").style.display = "block"; } catch (err) { A.toast(err.message, true); }
    });
    $("sp-finish-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      try { const r = await A.api("POST", "/api/spotify/finish", { url: $("sp-url").value }); $("sp-url").value = ""; $("sp-finish").style.display = "none"; A.toast(`Spotify collegato${r.user ? `: ${r.user}` : ""}`); loadSpotify(); }
      catch (err) { A.toast(err.message, true); }
    });
    $("sp-off").addEventListener("click", async () => { if (!confirm("Scollegare l'account Spotify?")) return; try { await A.api("DELETE", "/api/spotify"); loadSpotify(); } catch (err) { A.toast(err.message, true); } });
  }

  A.tab("spotify", { title: "Spotify", init, load: loadSpotify });
})();
