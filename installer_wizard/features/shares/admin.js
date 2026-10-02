(() => {
  const A = window.JarvisAdmin, { $, fmt } = A;

  async function load() {
    let d;
    try { d = await A.api("GET", "/api/shares"); } catch (e) { $("sh-status").textContent = e.message; return; }
    $("sh-status").textContent = d.active === "active" || d.active === "demo" ? "Samba attivo" : `Samba non attivo (${d.active}): l'installazione lo configura da sola`;
    $("sh-access").innerHTML = `<table><tbody>
      <tr><td class="dim">Indirizzo da Windows</td><td class="mono">${fmt.esc(d.windows)}</td></tr>
      <tr><td class="dim">Utente</td><td class="mono">${fmt.esc(d.user)}</td></tr>
      <tr><td class="dim">Password</td><td class="mono"><span id="sh-pass">••••••••</span> <button class="btn sm" id="sh-show">Mostra</button> <button class="btn sm" id="sh-copy">Copia</button></td></tr></tbody></table>`;
    $("sh-show").onclick = () => { $("sh-pass").textContent = d.password || "(non ancora generata)"; };
    $("sh-copy").onclick = async () => { try { await navigator.clipboard.writeText(d.password); A.toast("Password copiata"); } catch (e) { A.toast("Copia non riuscita", true); } };
    $("sh-list").innerHTML = d.shares.map((s) => `<div class="row" style="justify-content:space-between; padding:6px 0; border-bottom:1px solid var(--line)">
      <div><b>${fmt.esc(s.name)}</b> <span class="badge ${s.guest ? "" : "ok"}">${s.guest ? "libera in rete" : "con password"}</span><div class="faint mono">${fmt.esc(s.path)}</div></div>
      <span class="mono">${fmt.esc(d.windows)}\${fmt.esc(s.name)}</span></div>`).join("") || '<div class="faint">Nessuna cartella condivisa ancora.</div>';
  }

  A.tab("shares", { title: "Condivisioni", init() {}, load });
})();
