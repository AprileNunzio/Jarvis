(() => {
  const A = window.JarvisAdmin, { $, fmt } = A;

  async function loadMaps() {
    let d; try { d = await A.api("GET", "/api/maps"); } catch (e) { A.toast(e.message, true); return; }
    $("mp-status").innerHTML = d.has_key ? `<span class="badge ok">Google Maps</span> traffico in tempo reale e mezzi pubblici <span class="faint">${fmt.esc(d.status)}</span>`
      : '<span class="badge warn">OpenStreetMap</span> percorsi e tempi senza traffico: aggiungi la chiave Google per il traffico.';
    const modes = { drive: "auto", transit: "mezzi", walk: "a piedi", bike: "bici", moto: "moto" };
    $("mp-people").innerHTML = d.people.length ? d.people.map((p) => `<div style="margin-bottom:8px"><b>${fmt.esc(p.name)}</b>
      ${p.commute ? ` · esce alle ${fmt.esc(p.commute)}${p.mode ? ` in ${fmt.esc(modes[p.mode] || p.mode)}` : ""}` : ""}
      <div class="faint" style="font-size:12px">${Object.entries(p.places).map(([k, v]) => `${fmt.esc(k)}: ${fmt.esc(v)}`).join(" · ") || "nessun indirizzo"}</div></div>`).join("")
      : "Nessuna persona ha ancora un lavoro o un tragitto: aggiungili nella sua scheda.";
    $("mp-places").innerHTML = d.places.length ? d.places.map((p) => `<div class="row" style="justify-content:space-between;margin-bottom:6px"><span><b>${fmt.esc(p.name)}</b> — ${fmt.esc(p.label)} <span class="faint">${fmt.esc(p.detail || "")}</span></span><button class="btn danger" data-del="${fmt.esc(p.name)}">✕</button></div>`).join("") : "Nessun luogo salvato.";
  }

  function routeHtml(r) {
    const traffic = r.delay != null ? (r.delay >= 3 ? `+${r.delay} min di traffico` : "traffico scorrevole") : "stima senza traffico";
    return `<div style="font-size:18px;color:var(--cyan)">${fmt.esc(r.duration)} ${fmt.esc(r.mode)} · ${fmt.esc(r.distance)}</div>
        <div>${traffic}${r.via ? " · via " + fmt.esc(r.via) : ""}</div>
        <div class="faint" style="font-size:12px;margin-top:6px">${r.steps.map(fmt.esc).join("<br>")}</div>
        <a href="${fmt.esc(r.link)}" target="_blank" rel="noopener" style="color:var(--cyan)">Apri in Google Maps</a>`;
  }

  function init() {
    document.querySelector('#tab-maps [data-tab-open="people"]').addEventListener("click", () => A.openTab("people"));
    $("mp-places").addEventListener("click", async (e) => {
      const b = e.target.closest("[data-del]"); if (!b) return;
      try { await A.api("DELETE", `/api/maps/places/${encodeURIComponent(b.dataset.del)}`); loadMaps(); } catch (err) { A.toast(err.message, true); }
    });
    $("mp-key").addEventListener("submit", async (e) => {
      e.preventDefault();
      const body = {};
      if ($("mp-apikey").value.trim()) body.JARVIS_MAPS_API_KEY = $("mp-apikey").value.trim();
      if (!Object.keys(body).length) return A.toast("Nessuna modifica");
      try { await A.api("PUT", "/api/config", body); $("mp-apikey").value = ""; A.toast("Salvato"); loadMaps(); } catch (err) { A.toast(err.message, true); }
    });
    $("mp-add").addEventListener("submit", async (e) => {
      e.preventDefault();
      try { await A.api("PUT", `/api/maps/places/${encodeURIComponent($("mp-name").value.trim())}`, { address: $("mp-addr").value.trim() }); $("mp-name").value = ""; $("mp-addr").value = ""; A.toast("Luogo salvato"); loadMaps(); }
      catch (err) { A.toast(err.message, true); }
    });
    $("mp-test").addEventListener("submit", async (e) => {
      e.preventDefault(); $("mp-result").textContent = "Calcolo…";
      try { $("mp-result").innerHTML = routeHtml(await A.api("POST", "/api/maps/test", { to: $("mp-to").value.trim() })); }
      catch (err) { $("mp-result").textContent = err.message; }
    });
  }

  A.tab("maps", { title: "Maps", init, load: loadMaps });
})();
