(() => {
  const A = window.JarvisAdmin, { $, fmt } = A;
  let data = null;

  const blk = (t, rows) => `<div class="blk"><b>${t}</b>${rows}</div>`;
  const warn = (text) => `<div style="color:var(--amber)">${fmt.esc(text)}</div>`;

  function previewHtml(p) {
    let html = "";
    if (p.events) html += blk("Prossimi 7 giorni", p.events.length ? p.events.map((e) => `<div>${fmt.esc(e.day)} ${fmt.esc(e.when)} — ${fmt.esc(e.title)}</div>`).join("") : "<div>Nessun impegno</div>");
    if (p.events_error) html += blk("Calendar", warn(p.events_error));
    if (p.mail) html += blk(`Posta: ${p.mail.unread} non lette`, p.mail.items.map((m) => `<div>${fmt.esc(m.from)} — ${fmt.esc(m.subject)}</div>`).join(""));
    if (p.mail_error) html += blk("Gmail", warn(p.mail_error));
    if (p.tasks) html += blk("Cose da fare", p.tasks.length ? p.tasks.map((t) => `<div>☐ ${fmt.esc(t.title)}</div>`).join("") : "<div>Lista vuota</div>");
    if (p.tasks_error) html += blk("Tasks", warn(p.tasks_error));
    return html || "Nessun dato.";
  }

  function card(p) {
    const wanted = p.linked ? p.granted : data.default_services;
    const services = data.services.map((s) => `<label><input type="checkbox" value="${s.id}" ${wanted.includes(s.id) ? "checked" : ""}>
      ${s.icon} ${fmt.esc(s.name)}${s.workspace ? ' <span class="faint">(Workspace)</span>' : ""}${p.granted.includes(s.id) ? " ✓" : ""}</label>`).join("");
    return `<div class="gg-card ${p.linked ? "on" : ""}" data-slug="${fmt.esc(p.slug)}">
      <div><div class="gg-name">${fmt.esc(p.name)} ${p.role === "owner" ? '<span class="badge">proprietario</span>' : ""}</div>
        <div class="gg-sub">${p.linked ? `<span class="badge ok">collegato</span> ${fmt.esc(p.email)} · ${fmt.esc(p.status)}${p.unread != null ? ` · ${p.unread} email non lette` : ""}` : "Nessun account Google collegato"}</div></div>
      <div class="gg-services">${services}</div>
      <div class="actions">
        <button class="btn sm primary" data-act="link" ${data.has_credentials ? "" : "disabled"}>${p.linked ? "Ricollega" : "Collega il suo account"}</button>
        ${p.linked ? '<button class="btn sm" data-act="preview">Anteprima</button><button class="btn sm danger" data-act="unlink">Scollega</button>' : ""}
      </div>
      <div class="gg-preview" data-preview></div></div>`;
  }

  async function loadCredentials() {
    const cfg = await A.api("GET", "/api/config");
    const sec = cfg.editable.find((x) => x.key === "JARVIS_GOOGLE_CLIENT_SECRET");
    if (document.activeElement !== $("gg-id")) $("gg-id").value = data.client_id || "";
    $("gg-secret").placeholder = sec && sec.set ? sec.value : "non impostato";
  }

  async function load() {
    try { data = await A.api("GET", "/api/google"); } catch (e) { A.toast(e.message, true); return; }
    $("gg-app-badge").innerHTML = data.has_credentials ? '<span class="badge ok">app pronta</span>' : '<span class="badge warn">configura prima l\'app qui sotto</span>';
    $("gg-people").innerHTML = data.people.map(card).join("") || '<div class="muted-note">Nessuna persona: aggiungila prima dalla scheda Persone.</div>';
    $("gg-apis").textContent = data.services.map((s) => s.api).join(", ");
    await loadCredentials();
  }

  async function act(el, action) {
    const slug = el.dataset.slug;
    try {
      if (action === "link") {
        const services = [...el.querySelectorAll(".gg-services input:checked")].map((x) => x.value);
        const r = await A.api("POST", `/api/google/${encodeURIComponent(slug)}/auth-url`, { services });
        window.open(r.url, "_blank", "noopener");
        $("gg-finish").classList.add("show");
        A.toast("Accedi con l'account Google di questa persona, poi incolla qui l'indirizzo finale");
      } else if (action === "unlink") {
        if (!confirm("Scollegare questo account Google? Jarvis non potrà più leggerne agenda e posta.")) return;
        await A.api("DELETE", `/api/google/${encodeURIComponent(slug)}`); load();
      } else if (action === "preview") {
        const box = el.querySelector("[data-preview]"); box.textContent = "Carico…";
        box.innerHTML = previewHtml(await A.api("GET", `/api/google/${encodeURIComponent(slug)}/preview`));
      }
    } catch (e) { A.toast(e.message, true); }
  }

  function init() {
    $("gg-people").addEventListener("click", (e) => { const b = e.target.closest("[data-act]"); if (b) act(b.closest("[data-slug]"), b.dataset.act); });
    $("gg-creds").addEventListener("submit", async (e) => {
      e.preventDefault();
      const body = { JARVIS_GOOGLE_CLIENT_ID: $("gg-id").value.trim() };
      if ($("gg-secret").value.trim()) body.JARVIS_GOOGLE_CLIENT_SECRET = $("gg-secret").value.trim();
      try { await A.api("PUT", "/api/config", body); $("gg-secret").value = ""; A.toast("App Google salvata"); load(); } catch (err) { A.toast(err.message, true); }
    });
    $("gg-finish-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      try {
        const r = await A.api("POST", "/api/google/finish", { url: $("gg-url").value });
        $("gg-url").value = ""; $("gg-finish").classList.remove("show");
        A.toast(`Account collegato${r.email ? `: ${r.email}` : ""}`); load();
      } catch (err) { A.toast(err.message, true); }
    });
  }

  A.tab("google", { title: "Google", init, load });
})();
