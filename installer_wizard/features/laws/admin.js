(() => {
  const A = window.JarvisAdmin, { $, fmt } = A;

  const fixedRow = (l) => `<div class="lw-item lw-fixed">
    <div class="lw-n">${l.n}</div>
    <div><div class="nm">${fmt.esc(l.title)}</div><div class="nt">${fmt.esc(l.text)}</div></div>
    <span class="badge" title="Non modificabile">🔒</span></div>`;

  const customRow = (r) => `<div class="lw-item">
    <div class="lw-n">•</div>
    <div class="lw-edit" contenteditable="true" data-id="${fmt.esc(r.id)}">${fmt.esc(r.text)}</div>
    <button class="btn sm danger" data-del="${fmt.esc(r.id)}" title="Elimina">✕</button></div>`;

  async function load() {
    let d;
    try { d = await A.api("GET", "/api/laws"); } catch (e) { A.toast(e.message, true); return; }
    $("lw-fixed").innerHTML = d.fixed.map(fixedRow).join("");
    $("lw-custom").innerHTML = d.custom.length ? d.custom.map(customRow).join("")
      : '<div class="faint">Nessuna regola tua. Aggiungine una qui sotto.</div>';
  }

  function init() {
    $("lw-add").addEventListener("submit", async (e) => {
      e.preventDefault(); const text = $("lw-text").value.trim(); if (!text) return;
      try { await A.api("POST", "/api/laws", { text }); $("lw-text").value = ""; load(); }
      catch (err) { A.toast(err.message, true); }
    });
    $("lw-custom").addEventListener("click", async (e) => {
      const el = e.target.closest("[data-del]"); if (!el) return;
      if (!confirm("Eliminare questa regola?")) return;
      try { await A.api("DELETE", `/api/laws/${encodeURIComponent(el.dataset.del)}`); load(); }
      catch (err) { A.toast(err.message, true); }
    });
    $("lw-custom").addEventListener("blur", async (e) => {
      const el = e.target.closest(".lw-edit"); if (!el) return;
      const text = el.textContent.trim(); if (!text) { load(); return; }
      try { await A.api("PUT", `/api/laws/${encodeURIComponent(el.dataset.id)}`, { text }); A.toast("Regola aggiornata"); }
      catch (err) { A.toast(err.message, true); load(); }
    }, true);
  }

  A.tab("laws", { title: "Leggi", init, load });
})();
