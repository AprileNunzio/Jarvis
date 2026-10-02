(() => {
  const A = window.JarvisAdmin, { $, fmt } = A;
  let auTimer = null;

  const options = (list, cur) => list.length
    ? list.map((d) => `<option value="${fmt.esc(d.name)}" ${d.name === cur ? "selected" : ""}>${fmt.esc(d.label)}</option>`).join("")
    : '<option value="">Nessun dispositivo rilevato</option>';

  const row = (kind, icon, label, x, list) => `<div style="margin-bottom:18px"><div class="row" style="justify-content:space-between"><span>${icon} ${label} <b class="mono">${x.volume}%</b></span>
        <label class="switch"><input type="checkbox" data-au="${kind}.muted" ${x.muted ? "checked" : ""}> muto</label></div>
        <input type="range" min="0" max="150" value="${x.volume}" data-au="${kind}.volume" style="padding:0; margin:8px 0">
        <select data-au="${kind}.device">${options(list, x.device)}</select><div class="faint" style="font-size:11px; margin-top:4px">${list.length} disponibili</div></div>`;

  async function loadDevices() {
    let a;
    try { a = await A.api("GET", "/api/audio"); } catch (e) { $("au-body").textContent = e.message; return; }
    if (!a.available) { $("au-body").innerHTML = `<span class="badge warn">non disponibile</span> ${fmt.esc(a.error || "sessione audio del display non attiva")}`; return; }
    if ($("au-body").contains(document.activeElement)) return;
    $("au-body").innerHTML = row("output", "🔊", "Uscita", a.output, a.outputs) + row("input", "🎙", "Microfono", a.input, a.inputs);
  }

  function init() {
    $("au-body").addEventListener("input", (e) => {
      const [kind, key] = (e.target.dataset.au || "").split("."); if (!key || key === "device") return;
      const value = key === "muted" ? e.target.checked : +e.target.value;
      clearTimeout(auTimer);
      auTimer = setTimeout(async () => { try { await A.api("PUT", "/api/audio", { [kind]: { [key]: value } }); e.target.blur(); loadDevices(); } catch (err) { A.toast(err.message, true); } }, 200);
    });
    $("au-body").addEventListener("change", async (e) => {
      const [kind, key] = (e.target.dataset.au || "").split("."); if (key !== "device") return;
      try { await A.api("PUT", "/api/audio", { [kind]: { device: e.target.value } }); e.target.blur(); A.toast("Dispositivo attivato"); loadDevices(); } catch (err) { A.toast(err.message, true); }
    });
  }

  function onState(s) {
    if (s.audio_rev === window.__audioRev) return;
    window.__audioRev = s.audio_rev;
    if (A.isOn("audio")) loadDevices();
  }

  A.tab("audio", { title: "Audio del display", init, load: loadDevices, onState });
})();
