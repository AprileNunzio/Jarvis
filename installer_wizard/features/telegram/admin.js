(() => {
  const A = window.JarvisAdmin, { $, fmt } = A;
  let tgTimer = null;

  async function loadTelegram() {
    let t;
    try { t = await A.api("GET", "/api/telegram"); } catch (e) { A.toast(e.message, true); return; }
    $("tg-status").innerHTML = !t.configured ? '<span class="badge warn">non configurato</span> Inserisci il token del bot.'
      : t.status === "attivo" ? `<span class="badge ok">attivo</span> <a href="https://t.me/${fmt.esc(t.bot)}" target="_blank" style="color:var(--cyan)">@${fmt.esc(t.bot)}</a>`
      : `<span class="badge down">errore</span> ${fmt.esc(t.status)}`;
    $("tg-chats").innerHTML = t.chats.map((c) => `<tr data-chat="${fmt.esc(c.id)}">
      <td>${fmt.esc(c.name || "")}<div class="faint mono">${c.username ? "@" + fmt.esc(c.username) : fmt.esc(c.id)}</div></td>
      <td><select data-k="role" style="max-width:150px"><option value="owner" ${c.role === "owner" ? "selected" : ""}>Proprietario</option><option value="member" ${c.role !== "owner" ? "selected" : ""}>Membro</option></select></td>
      <td><input type="checkbox" data-k="notify" style="width:auto" ${c.notify !== false ? "checked" : ""}></td>
      <td><input type="checkbox" data-k="voice" style="width:auto" ${c.voice !== false ? "checked" : ""}></td>
      <td style="text-align:right"><button class="btn sm danger" data-tg-del="1">Rimuovi</button></td></tr>`).join("")
      || '<tr><td colspan="5" class="faint">Nessuna chat abbinata.</td></tr>';
    if (t.pair_code) showCode(t.pair_code, t.pair_expires_in);
  }

  function paired() {
    clearInterval(tgTimer); $("tg-code").textContent = "✓"; $("tg-code-note").textContent = "Abbinamento completato."; loadTelegram();
  }

  function showCode(code, seconds) {
    $("tg-code").textContent = code;
    clearInterval(tgTimer);
    let left = seconds;
    tgTimer = setInterval(() => {
      left--; $("tg-code-note").textContent = left > 0 ? `Invia questo codice al bot entro ${fmt.duration(left)}.` : "Codice scaduto: generane uno nuovo.";
      if (left <= 0) { clearInterval(tgTimer); $("tg-code").textContent = "——————"; }
      if (left % 5 === 0 && A.isOn("telegram")) A.api("GET", "/api/telegram").then((t) => { if (!t.pair_code && left > 0) paired(); });
    }, 1000);
  }

  function init() {
    $("tg-gen").addEventListener("click", async () => { try { const r = await A.api("POST", "/api/telegram/pair-code"); showCode(r.code, r.expires_in); } catch (e) { A.toast(e.message, true); } });
    $("tg-token-form").addEventListener("submit", async (e) => {
      e.preventDefault(); const v = $("tg-token").value.trim(); if (!v) return;
      try { await A.api("PUT", "/api/config", { JARVIS_TELEGRAM_TOKEN: v }); $("tg-token").value = ""; A.toast("Token salvato: connessione al bot…"); setTimeout(loadTelegram, 4000); }
      catch (err) { A.toast(err.message, true); }
    });
    $("tg-chats").addEventListener("change", async (e) => {
      const row = e.target.closest("tr"); const k = e.target.dataset.k; if (!row || !k) return;
      try { await A.api("PUT", `/api/telegram/chats/${row.dataset.chat}`, { [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value }); A.toast("Salvato"); }
      catch (err) { A.toast(err.message, true); }
    });
    $("tg-chats").addEventListener("click", async (e) => {
      if (!e.target.dataset.tgDel) return; const row = e.target.closest("tr");
      if (!confirm("Rimuovere questa chat? Non potrà più usare il bot.")) return;
      try { await A.api("DELETE", `/api/telegram/chats/${row.dataset.chat}`); loadTelegram(); } catch (err) { A.toast(err.message, true); }
    });
  }

  A.tab("telegram", { title: "Telegram", init, load: loadTelegram });
})();
