(() => {
  const D = window.JarvisDisplay, { $, fmt } = D;
  const esc = fmt.esc;
  let snap = null, seen = -1, open = false, timer = null;

  const seconds = (ms) => `${(ms / 1000).toFixed(ms < 10000 ? 1 : 0)} s`;
  const modelLine = (model) => (model ? `${esc(model.model)} · ${esc(model.provider)}` : "");

  function focus() {
    if (!snap) return null;
    return snap.active[snap.active.length - 1] || snap.recent[0] || null;
  }

  function steps(entry) {
    return entry.steps.map((s) => `<div class="mind-step"><b>${s.t.toFixed(1)}</b><span>${esc(s.text)}</span></div>`).join("")
      + (entry.snippet ? `<div class="mind-snippet">${esc(entry.snippet)}</div>` : "");
  }

  function recent() {
    const rows = snap.recent.filter((e) => e !== focus()).slice(0, 5).map((e) =>
      `<div><span>${esc(e.label)} → ${e.model ? esc(e.model.model) : "agente"}</span><span class="ms">${e.state === "failed" ? "errore" : seconds(e.ms)}</span></div>`);
    return rows.length ? `<div class="mind-recent">${rows.join("")}</div>` : "";
  }

  function render() {
    const box = $("mind"), entry = focus();
    if (!entry) { box.classList.add("empty"); return; }
    const live = entry.state === "thinking";
    box.className = `mind ${live ? "live" : entry.state} ${open ? "open" : ""}`;
    const kind = live ? (entry.model ? "sta ragionando" : "in ascolto") : entry.state === "failed" ? "nessuna risposta" : "ha risposto";
    const last = entry.steps[entry.steps.length - 1];
    $("mind-who").innerHTML = `<small>${kind}</small>${esc(entry.label)}`;
    $("mind-time").textContent = live ? seconds(entry.elapsed_ms || 0) : seconds(entry.ms || 0);
    $("mind-model").innerHTML = modelLine(entry.model) || "&nbsp;";
    $("mind-line").textContent = live ? (last ? last.text : "") : (entry.snippet || (last ? last.text : ""));
    $("mind-more").innerHTML = steps(entry) + recent();
  }

  async function poll() {
    if (document.hidden) return;
    try {
      const r = await fetch("/api/brain/trace", { cache: "no-store" });
      if (!r.ok) return;
      const data = await r.json();
      const changed = data.seq !== seen;
      snap = data; seen = data.seq;
      if (changed || data.active.length) render();
    } catch (e) { return; }
  }

  function schedule() {
    clearTimeout(timer);
    timer = setTimeout(async () => { await poll(); schedule(); }, snap && snap.active.length ? 700 : 2500);
  }

  D.startMindStream = () => {
    $("mind").addEventListener("click", () => { open = !open; render(); });
    document.addEventListener("visibilitychange", () => { if (!document.hidden) poll(); });
    poll().then(schedule);
  };
})();
