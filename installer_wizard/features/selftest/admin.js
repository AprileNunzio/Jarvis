(() => {
  const A = window.JarvisAdmin, { $, fmt } = A;
  const ICON = { ok: "✅", errore: "❌", saltato: "⏭" };
  const when = (t) => new Date(t * 1000).toLocaleString("it-IT", { dateStyle: "short", timeStyle: "short" });
  let data = null, shown = 0, timer = null;

  function rows(report) {
    return report.results.map((r) => `<div class="st-row ${r.status}"><span>${ICON[r.status]}</span>
      <span><b>${fmt.esc(r.label)}</b>${r.critical ? ' <span class="badge">essenziale</span>' : ""}</span>
      <span class="faint" title="${fmt.esc(r.detail)}">${fmt.esc(r.detail)}</span><span class="faint mono">${r.ms} ms</span></div>`).join("");
  }

  function render() {
    const h = data.history, last = h[shown];
    $("st-status").textContent = data.running ? "Collaudo in corso…" : last
      ? `Ultimo: ${when(last.at)} (${last.reason}) · versione ${last.rev.slice(0, 7)} · ${last.passed} superati, ${last.failed} falliti, ${last.skipped} saltati`
        + (data.good_rev ? ` · ultima versione sana ${data.good_rev.slice(0, 7)}` : "")
      : "Mai eseguito: parte da solo cinque minuti dopo l'avvio, ogni notte e dopo ogni aggiornamento.";
    $("st-last").innerHTML = last ? `<div class="faint">${when(last.at)} · ${fmt.esc(last.reason)}</div>` + rows(last) : '<div class="faint">Nessun risultato.</div>';
    $("st-history").innerHTML = h.map((r, i) => `<div class="st-hist" data-i="${i}"><span class="badge ${r.failed ? "bad" : "ok"}">${r.passed}/${r.results.length - r.skipped}</span>
      <b>${when(r.at)}</b><span class="faint">${fmt.esc(r.reason)} · ${r.rev.slice(0, 7)}</span>
      ${r.failed ? `<span class="faint">falliti: ${fmt.esc(r.results.filter((x) => x.status === "errore").map((x) => x.label).join(", "))}</span>` : ""}</div>`).join("");
  }

  async function load() { try { data = await A.api("GET", "/api/selftest"); render(); } catch (e) { $("st-status").textContent = e.message; } }

  function init() {
    $("st-run").addEventListener("click", async () => { const r = await A.api("POST", "/api/selftest/run"); A.toast(r.message, !r.ok); shown = 0; setTimeout(load, 1000); });
    $("st-history").addEventListener("click", (e) => { const row = e.target.closest("[data-i]"); if (row) { shown = Number(row.dataset.i); render(); } });
  }

  A.tab("selftest", {
    title: "Collaudo", init,
    load() { load(); clearInterval(timer); timer = setInterval(() => { if (A.isOn("selftest")) load(); }, 5000); },
    leave() { clearInterval(timer); },
  });
})();
