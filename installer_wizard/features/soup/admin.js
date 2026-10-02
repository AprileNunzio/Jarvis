(() => {
  const A = window.JarvisAdmin, { $, fmt } = A;
  let soup = null;

  A.renderSoup = (data) => {
    const s = soup = data, g = s.gpu || {};
    $("st-soup").innerHTML = `<table><tbody>
        <tr><td class="dim">GPU</td><td>${g.present ? `${fmt.esc(g.name)} · ${g.vram_mb} MB ${g.usable ? '<span class="badge ok">adatta</span>' : '<span class="badge warn">non adatta</span>'}` : `<span class="badge">assente</span> ${fmt.esc(g.reason || "")}`}</td></tr>
        <tr><td class="dim">Dataset</td><td>${s.examples} esempi (${s.new_examples} nuovi) · minimo ${s.min_examples} · <a href="/api/study/dataset.jsonl" style="color:var(--cyan)">scarica JSONL</a></td></tr>
        <tr><td class="dim">Ambiente Soup</td><td>${s.installed ? '<span class="badge ok">installato</span>' : '<span class="badge">non installato</span>'} ${s.phase ? `· ${fmt.esc(s.phase)}…` : ""}</td></tr>
        <tr><td class="dim">Modello addestrato</td><td>${s.model_ready ? `<span class="badge ok">${fmt.esc(s.ollama_model)}</span> (impostalo in Configurazione → Modello linguistico)` : "—"}</td></tr>
        ${(s.runs || []).slice().reverse().map((r) => `<tr><td class="dim mono">${new Date(r.started * 1000).toLocaleString("it-IT")}</td><td style="font-size:12px">${r.examples} esempi · ${fmt.esc(r.result || "in corso")}</td></tr>`).join("")}
      </tbody></table>
      <div class="form-grid" style="margin-top:12px">
        <div><label>Consolidamento notturno (02:00–06:00 o fascia di studio)</label><select id="soup-mode">
          <option value="auto" ${s.mode === "auto" ? "selected" : ""}>Automatico: decide Jarvis in base all'hardware (consigliato)</option>
          <option value="1" ${s.mode === "1" ? "selected" : ""}>Sempre attivo (a tuo rischio)</option>
          <option value="0" ${s.mode === "0" ? "selected" : ""}>Disattivato</option></select>
          <div class="faint" style="font-size:12px; margin-top:6px">${s.enabled ? '<span class="badge ok">attivo</span>' : '<span class="badge">non attivo</span>'} ${fmt.esc(s.decision || "")}</div></div>
        <div><label>Modello base (Hugging Face)</label><input id="soup-base" value="${fmt.esc(s.base_model)}"></div></div>
      <div class="actions" style="margin-top:12px"><button class="btn" id="soup-train" ${s.running || !s.enabled || !s.installed ? "disabled" : ""}>Addestra ora</button></div>
      <div class="muted-note">Lo studio finisce sempre nella memoria a lungo termine, usata nelle risposte. Soup trasferisce gli appunti anche nei pesi di un modello (LoRA, streaming dei layer) che diventa «${fmt.esc(s.ollama_model)}» in Ollama. In automatico si attiva con GPU NVIDIA ≥ 4 GB e RAM ≥ 8 GB.</div>`;
  };

  function init() {
    $("st-soup").addEventListener("change", async (e) => {
      const body = e.target.id === "soup-mode" ? { mode: e.target.value } : e.target.id === "soup-base" ? { base_model: e.target.value } : null;
      if (!body) return;
      if (body.mode === "1" && !(soup.gpu || {}).usable
          && !confirm("Questa macchina non ha una GPU adatta: l'addestramento userà la CPU, sarà molto lento e occuperà il sistema per ore. Attivarlo comunque?")) { A.renderSoup(soup); return; }
      try { A.renderSoup(await A.api("PUT", "/api/study/soup", body)); A.toast("Salvato"); } catch (err) { A.toast(err.message, true); }
    });
    $("st-soup").addEventListener("click", async (e) => {
      if (e.target.id !== "soup-train") return;
      if (!confirm("Avviare ora il consolidamento nei pesi? Può richiedere ore e occupa la GPU.")) return;
      try { await A.api("POST", "/api/study/soup/train"); A.toast("Addestramento avviato"); setTimeout(() => A.tabs.study.load(), 2000); } catch (err) { A.toast(err.message, true); }
    });
  }

  A.tab("soup", { init });
})();
