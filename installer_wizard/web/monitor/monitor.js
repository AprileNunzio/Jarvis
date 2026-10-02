(() => {
  const { fmt, Reactor, connectState } = Jarvis;
  const $ = (id) => document.getElementById(id);
  const reactor = new Reactor($("reactor"));
  const STATUS_TEXT = { pending: "in attesa", checking: "verifica", running: "", retrying: "nuovo tentativo", done: "ok", failed: "errore", skipped: "saltato", background: "dopo l'avvio" };
  let state = null;

  setInterval(() => {
    $("clock").textContent = fmt.clock();
    if (state) $("elapsed").textContent = fmt.duration(Date.now() / 1000 - state.phase_since);
  }, 1000);

  const stepEls = {};
  let followTimer = null;
  function renderSteps(s) {
    const list = $("steps");
    let done = 0;
    s.catalog.forEach((c, i) => {
      let li = stepEls[c.id];
      if (!li) {
        li = document.createElement("li");
        li.innerHTML = '<span class="icon"></span><div><div class="t"></div><div class="d"></div></div><span class="s"></span>';
        li.querySelector(".t").textContent = c.title;
        li.querySelector(".d").textContent = c.description;
        stepEls[c.id] = li;
      }
      if (list.children[i] !== li) list.insertBefore(li, list.children[i] || null);
      const rec = s.steps[c.id] || { status: "pending" };
      if (rec.status === "done" || rec.status === "skipped" || rec.status === "background") done++;
      li.className = `${rec.status}${s.current_step === c.id ? " active" : ""}`;
      li.querySelector(".s").textContent = rec.status === "running" ? `${rec.progress || 0}%` : (STATUS_TEXT[rec.status] ?? "");
    });
    $("steps-count").textContent = `${done}/${s.catalog.length}`;
    $("steps-rail").style.width = `${(done * 100) / Math.max(1, s.catalog.length)}%`;
    clearTimeout(followTimer);
    followTimer = setTimeout(followActive, 60);
  }

  function followActive() {
    const list = $("steps");
    const items = [...list.children];
    const target = list.querySelector("li.active") || list.querySelector("li.failed, li.retrying, li.running, li.checking")
      || items.find((li) => li.classList.contains("pending")) || items[items.length - 1];
    if (target && list.scrollHeight > list.clientHeight) {
      const top = target.offsetTop - list.offsetTop - (list.clientHeight - target.offsetHeight) / 2;
      list.scrollTo({ top: Math.max(0, Math.min(top, list.scrollHeight - list.clientHeight)), behavior: "smooth" });
    }
    updateFades();
  }
  function updateFades() {
    const list = $("steps");
    list.classList.toggle("more-top", list.scrollTop > 4);
    list.classList.toggle("more-bottom", list.scrollTop + list.clientHeight < list.scrollHeight - 4);
  }
  $("steps").addEventListener("scroll", updateFades, { passive: true });
  window.addEventListener("resize", () => { clearTimeout(followTimer); followTimer = setTimeout(followActive, 150); });

  function renderSystem(sys) {
    if (!sys || !sys.mem_total) return;
    $("host").textContent = sys.hostname;
    $("ip").textContent = sys.ip;
    $("cpu").textContent = `${sys.cpu_percent.toFixed(0)}% · ${sys.cpu_count} core`;
    $("cpu-bar").style.width = `${sys.cpu_percent}%`;
    $("mem").textContent = `${fmt.bytes(sys.mem_used)} / ${fmt.bytes(sys.mem_total)}`;
    $("mem-bar").style.width = `${sys.mem_percent}%`;
    $("disk").textContent = `${fmt.bytes(sys.disk_used)} / ${fmt.bytes(sys.disk_total)}`;
    $("disk-bar").style.width = `${sys.disk_percent}%`;
    $("net").textContent = `${fmt.rate(sys.net_rx_rate)} / ${fmt.rate(sys.net_tx_rate)}`;
    $("temp").textContent = sys.temperature ? `${sys.temperature} °C` : "—";
    $("uptime").textContent = fmt.duration(sys.uptime);
  }

  function renderComponents(comps) {
    const keys = Object.keys(comps || {});
    if (!keys.length) return;
    $("comps").innerHTML = keys.map((k) => {
      const c = comps[k];
      return `<div><span class="dot ${c.status}"></span><span class="lbl">${fmt.esc(c.label)}</span><span class="det">${fmt.esc(c.detail)}</span></div>`;
    }).join("");
  }

  function renderLogs(logs) {
    $("console").innerHTML = logs.slice(-8).map((l) => {
      const cls = /^\[FAIL\]|errore|error/i.test(l.msg) ? "fail" : (/^\[WARN\]/.test(l.msg) ? "warn" : "");
      return `<div class="ln ${cls}"><span class="src">${fmt.esc(l.src)}</span>${fmt.esc(l.msg)}</div>`;
    }).join("");
  }

  function onState(s) {
    if ((s.phase === "READY" || s.phase === "DEGRADED") && state) {
      $("handoff").classList.add("show");
      setTimeout(() => location.reload(), 2200);
    } else if (s.phase === "READY" || s.phase === "DEGRADED") {
      location.reload();
      return;
    }
    state = s;
    document.body.className = `holo-grid ${s.phase}`;
    reactor.setPhase(s.phase);
    reactor.progress = s.progress;
    reactor.activity = s.phase === "ERROR" ? 0.15 : 0.55;
    $("pct").textContent = `${Math.floor(s.progress)}%`;
    $("phase").textContent = s.phase_label;
    $("msg").textContent = s.message || "";
    $("detail").textContent = s.detail || "";
    $("err").textContent = s.phase === "ERROR"
      ? `${s.last_error || "Errore"} — nuovo tentativo automatico tra ${fmt.duration(s.retry_in)}`
      : (s.last_error && s.phase !== "INSTALLING" ? "" : "");
    renderSteps(s);
    renderSystem(s.system);
    renderComponents(s.components);
    renderLogs(s.logs || []);
  }

  connectState("/api/stream", onState, (ok) => $("link").classList.toggle("show", !ok));
})();
