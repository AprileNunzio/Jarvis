(() => {
  const A = window.JarvisAdmin, { $, fmt } = A;
  const GENDER = { m: "maschile", f: "femminile" };
  const ENGINE = { kokoro: "Kokoro · naturale · offline", online: "Online · naturalissima", piper: "Piper · offline" };
  let voiceData = null, voiceAudio = null, searchTimer = null;

  const voiceSub = (v) => [GENDER[v.gender], v.engine === "piper" ? `${ENGINE.piper} · qualità ${v.quality}` : v.multi ? "Online · multilingue, parla anche italiano" : ENGINE[v.engine], v.locale || voiceData.langs[v.lang] || v.lang].filter(Boolean).join(" · ");

  async function loadVoices() {
    try { voiceData = await A.api("GET", "/api/voices"); } catch (e) { $("vo-list").innerHTML = `<div class="faint">${fmt.esc(e.message)}</div>`; return; }
    const langs = [...new Set(voiceData.voices.map((v) => v.lang))];
    if ($("vo-lang").options.length !== langs.length + 1) {
      $("vo-lang").innerHTML = `<option value="">Tutte le lingue</option>` + langs.map((l) => `<option value="${l}" ${l === "it" ? "selected" : ""}>${fmt.esc(voiceData.langs[l] || l)}</option>`).join("");
    }
    renderVoices();
  }

  function voiceItem(d, v, inOrder) {
    return `<div class="cat-item"><div>
        <div class="nm">${v.preferred ? "★ " : ""}${fmt.esc(v.name)} <span class="faint mono" style="font-size:11px">${fmt.esc(v.id)}</span></div>
        <div class="nt">${voiceSub(v)}${v.size_mb ? ` · ${v.size_mb} MB` : ""}${v.downloading ? " · download in corso…" : v.installed && v.engine !== "online" ? " · ✓ pronta" : ""}</div></div>
      <div class="actions" style="justify-content:flex-end">
        <button class="btn sm" data-vpref="${fmt.esc(v.id)}" data-vlang="${fmt.esc(v.lang)}" title="${v.preferred ? "Torna alla scelta automatica" : `Usa questa voce quando Jarvis parla ${fmt.esc((d.langs[v.lang] || v.lang).toLowerCase())}`}">${v.preferred ? "★" : "☆"}</button>
        ${v.installed ? `<button class="btn sm" data-play="${fmt.esc(v.id)}" title="Ascolta">▶</button>` : ""}
        ${v.downloadable && !v.installed ? `<button class="btn sm primary" data-vdl="${fmt.esc(v.id)}">Scarica</button>` : ""}
        <button class="btn sm" data-vadd="${fmt.esc(v.id)}" ${inOrder.has(v.id) ? "disabled" : ""}>+ Priorità</button>
        ${v.downloadable && v.installed && v.id !== d.fallback ? `<button class="btn sm danger" data-vdel="${fmt.esc(v.id)}" title="Elimina">✕</button>` : ""}</div></div>`;
  }

  function renderVoices() {
    const d = voiceData;
    $("vo-order").innerHTML = d.order.map((v, i) => A.prioItem(v.id, i, `${v.name} · ${v.id}`,
      voiceSub(v) + (v.installed ? "" : ' · <span style="color:var(--amber)">non disponibile — verrà saltata</span>') + (v.safety ? " · riserva di sicurezza, sempre in coda" : ""),
      !v.installed, v.safety)).join("");
    $("vo-note").textContent = d.kokoro_online ? "" : "Il motore Kokoro non risponde: le voci Kokoro vengono saltate finché non torna attivo.";
    const c = d.counts || {};
    $("vo-summary").textContent = `${d.voices.length} voci in ${Object.keys(d.langs).length} lingue · ${c.italiano || 0} in italiano · Kokoro ${c.kokoro || 0} · Piper ${c.piper || 0} · online ${c.online || 0}` +
      (d.online_enabled ? "" : " · voci online disattivate (o edge-tts non ancora installato)") + (d.auto_download ? " · download automatico attivo" : "");
    const lang = $("vo-lang").value, eng = $("vo-engine").value, q = $("vo-search").value.trim().toLowerCase();
    const inOrder = new Set(d.order.filter((v) => !v.safety).map((v) => v.id));
    const shown = d.voices.filter((v) => (!lang || v.lang === lang || v.multi) && (!eng || v.engine === eng) &&
      (!q || `${v.name} ${v.id} ${voiceSub(v)} ${d.langs[v.lang] || ""}`.toLowerCase().includes(q)));
    $("vo-list").innerHTML = shown.slice(0, 250).map((v) => voiceItem(d, v, inOrder)).join("");
  }

  async function saveVoices(orderList) {
    try { voiceData = await A.api("PUT", "/api/voices", { order: orderList }); renderVoices(); } catch (e) { A.toast(e.message, true); loadVoices(); }
  }

  async function play(t) {
    t.disabled = true;
    try {
      const r = await fetch("/api/voices/preview", { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json", "X-Jarvis-Request": "1" },
        body: JSON.stringify({ voice: t.dataset.play, text: $("vo-text").value.trim() }) });
      if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || `Errore ${r.status}`);
      if (voiceAudio) voiceAudio.pause();
      voiceAudio = new Audio(URL.createObjectURL(await r.blob())); voiceAudio.play();
    } catch (err) { A.toast(err.message, true); } finally { t.disabled = false; }
  }

  async function prefer(t) {
    const v = voiceData.voices.find((x) => x.id === t.dataset.vpref);
    try { voiceData = await A.api("PUT", "/api/voices/language", { lang: t.dataset.vlang, voice: v && v.preferred ? "" : t.dataset.vpref }); renderVoices();
      A.toast(v && v.preferred ? "Scelta automatica ripristinata" : `${v ? v.name : "Voce"} sarà usata per ${(voiceData.langs[t.dataset.vlang] || t.dataset.vlang).toLowerCase()}${v && v.downloadable && !v.installed ? " (download avviato)" : ""}`); }
    catch (err) { A.toast(err.message, true); }
  }

  async function download(id) {
    try { await A.api("POST", "/api/voices/download", { voice: id }); A.toast("Download della voce avviato"); } catch (err) { A.toast(err.message, true); }
  }

  async function addToOrder(id) {
    const current = voiceData.order.filter((v) => !v.safety).map((v) => v.id);
    await saveVoices([...current, id]);
    const v = voiceData.voices.find((x) => x.id === id);
    if (v && v.downloadable && !v.installed && confirm(`${v.name} non è ancora scaricata (${v.size_mb} MB). Scaricarla ora?`)) await download(v.id);
  }

  function init() {
    A.makeSortable($("vo-order"), (items) => saveVoices(items));
    $("vo-reset").addEventListener("click", () => saveVoices([]).then(() => A.toast("Ordine predefinito ripristinato")));
    $("vo-lang").addEventListener("change", renderVoices);
    $("vo-engine").addEventListener("change", renderVoices);
    $("vo-search").addEventListener("input", () => { clearTimeout(searchTimer); searchTimer = setTimeout(renderVoices, 150); });
    $("vo-list").addEventListener("click", async (e) => {
      const t = e.target.closest("button"); if (!t) return;
      if (t.dataset.play) await play(t);
      if (t.dataset.vpref) await prefer(t);
      if (t.dataset.vdl) await download(t.dataset.vdl);
      if (t.dataset.vadd) await addToOrder(t.dataset.vadd);
      if (t.dataset.vdel && confirm(`Eliminare la voce ${t.dataset.vdel}?`)) { try { voiceData = await A.api("DELETE", `/api/voices/${encodeURIComponent(t.dataset.vdel)}`); renderVoices(); } catch (err) { A.toast(err.message, true); } }
    });
  }

  function onState(s) {
    const vp = s.voice_pull;
    if (!vp) return;
    $("vo-pull").textContent = `${vp.name}: ${vp.status}${vp.percent ? ` — ${vp.percent}%` : ""}`;
    const sig = `${vp.name}|${vp.status}`;
    if (sig !== window.__vpullSig) { window.__vpullSig = sig; if (A.isOn("voices") && /completato|errore/.test(vp.status)) loadVoices(); }
  }

  A.tab("voices", { title: "Voci", init, load: loadVoices, onState });
})();
