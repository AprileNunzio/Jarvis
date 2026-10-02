(() => {
  const A = window.JarvisAdmin, { $, fmt } = A;

  const copyButton = (text) => `<button class="btn sm" data-copy="${fmt.esc(text)}">Copia</button>`;

  async function load() {
    let d;
    try { d = await A.api("GET", "/api/shares"); } catch (e) { $("sh-status").textContent = e.message; return; }
    $("sh-status").textContent = d.active === "active" || d.active === "demo" ? "Samba attivo" : `Samba non attivo (${d.active}): l'installazione lo configura da sola`;
    $("sh-access").innerHTML = `<table><tbody>
      <tr><td class="dim">Indirizzo da Windows</td><td class="mono">${fmt.esc(d.unc)} ${copyButton(d.unc)}</td></tr>
      <tr><td class="dim">Da Mac / Linux</td><td class="mono">smb://${fmt.esc(d.ip)}/condivisa</td></tr>
      <tr><td class="dim">Utente</td><td class="mono">${fmt.esc(d.user)} ${copyButton(d.user)}</td></tr>
      <tr><td class="dim">Password</td><td class="mono"><span id="sh-pass">••••••••</span> <button class="btn sm" id="sh-show">Mostra</button> <button class="btn sm" id="sh-copy">Copia</button></td></tr></tbody></table>`;
    $("sh-show").onclick = () => { $("sh-pass").textContent = d.password || "(non ancora generata)"; };
    $("sh-copy").onclick = async () => { try { await navigator.clipboard.writeText(d.password); A.toast("Password copiata"); } catch (e) { A.toast("Copia non riuscita", true); } };
    $("sh-list").innerHTML = (d.folders || []).map((f) => `<div class="row" style="justify-content:space-between; padding:8px 0; border-bottom:1px solid var(--line); gap:12px">
      <div style="min-width:0"><b>${fmt.esc(f.name)}</b> <span class="badge">${f.count} element${f.count === 1 ? "o" : "i"}</span>
        <div class="faint">${fmt.esc(f.description)}</div>
        ${f.latest.length ? `<div class="faint mono" style="font-size:11px">ultimi: ${f.latest.map(fmt.esc).join(" · ")}</div>` : ""}</div>
      ${copyButton(`${d.unc}\\${f.name}`)}</div>`).join("") || '<div class="faint">La struttura viene creata dall\'installazione.</div>';
  }

  function init() {
    document.getElementById("tab-shares").addEventListener("click", async (e) => {
      const b = e.target.closest("[data-copy]");
      if (!b) return;
      try { await navigator.clipboard.writeText(b.dataset.copy); A.toast(`Copiato: ${b.dataset.copy}`); } catch (err) { A.toast(b.dataset.copy); }
    });
  }

  A.tab("shares", { title: "Condivisioni", init, load });
})();
