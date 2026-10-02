(() => {
  const A = window.JarvisAdmin, { $, fmt } = A;
  const LOC_SRC = { phone: "GPS del telefono (Telegram)", browser: "posizione precisa del display", wifi: "reti Wi-Fi vicine", lan: "access point di casa",
                   default: "posizione predefinita", ip: "indirizzo IP (approssimata)", none: "sconosciuta" };
  const acc = (m) => m == null ? "" : m >= 1000 ? `±${(m / 1000).toFixed(m >= 10000 ? 0 : 1)} km` : `±${Math.round(m)} m`;

  function renderCurrent(c) {
    $("loc-current").innerHTML = c.lat != null ? `📍 <b>${fmt.esc(c.name)}</b> <span class="faint mono">${c.lat.toFixed(4)}, ${c.lon.toFixed(4)}</span><div class="faint" style="font-size:12px">Fonte: ${LOC_SRC[c.source] || c.source}${c.accuracy ? ` · precisione ±${c.accuracy >= 1000 ? (c.accuracy / 1000).toFixed(1) + " km" : Math.round(c.accuracy) + " m"}` : ""}
      · <a href="https://www.openstreetmap.org/?mlat=${c.lat}&mlon=${c.lon}#map=15/${c.lat}/${c.lon}" target="_blank" rel="noopener" style="color:var(--cyan)">mappa</a></div>` : "Posizione sconosciuta";
  }

  function renderLocation(d) {
    const c = d.current || {}, s = d.settings || {};
    renderCurrent(c);
    $("loc-mode").value = s.mode || "auto";
    $("loc-default").innerHTML = s.default ? `${fmt.esc(s.default.name)}${s.default.lat != null ? ` <span class="mono faint">${(+s.default.lat).toFixed(4)}, ${(+s.default.lon).toFixed(4)}</span>` : ""} <button class="btn sm danger" id="loc-clear">Rimuovi</button>` : "Nessuna: scegline una qui sotto (consigliato come riserva).";
    const src = d.sources || {}, ip = src.ip || {};
    $("loc-sources").innerHTML = ["phone", "browser", "wifi", "lan", "ip"].map((k) => {
      const v = src[k];
      const val = !v ? '<span class="faint">non disponibile</span>' : v.lat == null ? '<span class="faint">nessun risultato</span>'
        : `${fmt.esc(v.name || "—")} <span class="faint">${acc(v.accuracy)} · ${new Date(v.at * 1000).toLocaleString("it-IT")}</span>`;
      return `<tr><td class="dim">${LOC_SRC[k]}</td><td>${val}${c.source === k ? ' <span class="badge ok">in uso</span>' : ""}</td></tr>`;
    }).join("");
    $("loc-warn").innerHTML = c.source === "ip" ? `<div class="muted-note" style="color:var(--amber); margin:0 0 12px">⚠ Posizione approssimata dall'indirizzo IP.
        ${ip.disagree ? `I servizi non sono d'accordo: ${ip.cities.map((x) => `<button class="btn sm" data-locpick="${fmt.esc(x.city)}">📍 ${fmt.esc(x.city)} (${x.providers.length})</button>`).join(" ")} — tocca la città giusta.` : "Conferma la città qui sotto per renderla precisa."}</div>` : "";
  }

  async function loadLocation() { try { renderLocation(await A.api("GET", "/api/location")); } catch (e) { $("loc-current").textContent = e.message; } }

  const setPlace = (x) => A.api("PUT", "/api/location", { name: x.name, lat: x.lat, lon: x.lon }).then(renderLocation);

  function init() {
    $("loc-warn").addEventListener("click", async (e) => {
      const b = e.target.closest("[data-locpick]"); if (!b) return;
      try { const r = await A.api("GET", `/api/location/search?q=${encodeURIComponent(b.dataset.locpick)}`); const x = r.results[0];
        if (!x) throw new Error("Città non trovata");
        await setPlace(x); A.toast(`Posizione impostata: ${x.name}`); }
      catch (err) { A.toast(err.message, true); }
    });
    $("loc-mode").addEventListener("change", async (e) => { try { renderLocation(await A.api("PUT", "/api/location", { mode: e.target.value })); A.toast("Salvato"); } catch (err) { A.toast(err.message, true); } });
    $("loc-search").addEventListener("submit", async (e) => {
      e.preventDefault(); const q = $("loc-q").value.trim(); if (!q) return;
      try {
        const r = await A.api("GET", `/api/location/search?q=${encodeURIComponent(q)}`);
        $("loc-results").innerHTML = r.results.map((x, i) => `<button class="btn" data-loc="${i}">📍 ${fmt.esc(x.name)} <span class="faint">${fmt.esc(x.detail || "")}</span></button>`).join("") || '<div class="faint">Nessun risultato.</div>';
        $("loc-results").dataset.items = JSON.stringify(r.results);
      } catch (err) { A.toast(err.message, true); }
    });
    $("loc-results").addEventListener("click", async (e) => {
      const b = e.target.closest("[data-loc]"); if (!b) return;
      const x = JSON.parse($("loc-results").dataset.items)[+b.dataset.loc];
      try { await setPlace(x); $("loc-results").innerHTML = ""; $("loc-q").value = ""; A.toast(`Posizione predefinita: ${x.name}`); }
      catch (err) { A.toast(err.message, true); }
    });
    $("loc-default").addEventListener("click", async (e) => {
      if (e.target.id !== "loc-clear") return;
      try { renderLocation(await A.api("PUT", "/api/location", { name: "", lat: "", lon: "" })); } catch (err) { A.toast(err.message, true); }
    });
  }

  A.tab("location", { title: "Posizione", init, load: loadLocation });
})();
