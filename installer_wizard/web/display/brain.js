(() => {
  const D = window.JarvisDisplay, { $, fmt } = D;
  let knownIds = null;

  function renderLegend() {
    const { scene } = D;
    const counts = scene.brain.counts();
    const total = Object.values(counts).reduce((a, b) => a + b, 0);
    $("legend").innerHTML = `<div class="panel-title">Regioni cerebrali</div>` + Object.entries(D.regions()).map(([k, r]) =>
      `<div class="r"><i style="background:${r.color}; box-shadow:0 0 8px ${r.color}"></i><div>${r.name}<small>${r.role}</small></div><b>${counts[k] || 0}</b></div>`).join("")
      + `<div class="tot">${total} neuroni · ${(scene.brain.edges || []).length} sinapsi<br>Trascina per ruotare · rotella per lo zoom · tocca un neurone</div>`;
  }

  D.refreshBrain = async (announce) => {
    try {
      const graph = await fetch("/api/assistant/memory").then((r) => (r.ok ? r.json() : null));
      if (!graph) return;
      const nodes = graph.nodes || [];
      const fresh = knownIds ? nodes.filter((n) => !knownIds.has(n.id)) : [];
      knownIds = new Set(nodes.map((n) => n.id));
      if (D.scene) { D.scene.brain.setGraph(graph, true); renderLegend(); }
      if (announce && fresh.length) {
        const t = $("toast-mem");
        t.textContent = `✦ ${fresh.length === 1 ? "Nuovo neurone" : `${fresh.length} nuovi neuroni`}: ${fresh[0].label}`;
        t.classList.add("show"); setTimeout(() => t.classList.remove("show"), 3500);
      }
    } catch (e) { console.warn(e); }
  };

  D.showNode = (node) => {
    D.lastInteraction = Date.now();
    if (!node) { $("inspector").classList.remove("show"); return; }
    D.selectedId = node.id;
    const regions = D.regions(), r = regions[node.node_type] || regions.CONCEPT;
    const links = D.scene.brain.neighbours(node.id);
    const created = node.created_at ? new Date(node.created_at * 1000).toLocaleString("it-IT") : "—";
    $("inspector").innerHTML = `<div class="type" style="color:${r.color}">${r.name} · ${fmt.esc(node.node_type)}</div>
      <h3>${fmt.esc(node.label)}</h3><div class="faint mono" style="font-size:11px">${fmt.esc(node.id)} · creato ${created}</div>
      <div class="panel-title" style="margin-top:16px">Proprietà</div><pre>${fmt.esc(JSON.stringify(node.properties || {}, null, 2))}</pre>
      <div class="panel-title" style="margin-top:16px">Sinapsi (${links.length})</div>
      ${links.map((l) => `<button class="link" data-id="${fmt.esc(l.other.id)}"><span style="color:${(regions[l.other.node_type] || r).color}">●</span> ${fmt.esc(l.other.label)} <span class="faint">— ${fmt.esc(l.edge.relation_type)}</span></button>`).join("") || '<div class="faint">Nessuna connessione</div>'}`;
    $("inspector").classList.add("show");
  };

  D.hoverNode = (node, e) => {
    const tip = $("tip");
    if (!node) { tip.style.display = "none"; return; }
    tip.textContent = node.label; tip.style.display = "block";
    tip.style.left = `${e.clientX + 14}px`; tip.style.top = `${e.clientY + 10}px`;
  };

  D.startBrain = () => {
    $("inspector").addEventListener("click", (e) => {
      const b = e.target.closest(".link"); if (!b) return;
      const entry = D.scene.brain.nodes.get(b.dataset.id); if (!entry) return;
      D.scene.brain.select(entry.node.id); D.scene.focusOn(entry.pos); D.showNode(entry.node);
    });
    $("btn-brain").addEventListener("click", () => D.setMode(D.mode === "brain" ? "face" : "brain"));
    $("back-face").addEventListener("click", () => D.setMode("face"));
    D.refreshBrain(false);
    setInterval(() => D.refreshBrain(true), 15000);
  };
})();
