(() => {
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const el = (tag, cls, html) => { const e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; };
  const uid = () => Math.random().toString(16).slice(2, 10);
  const DAYS = ["lun", "mar", "mer", "gio", "ven", "sab", "dom"];
  let CAT = null, onChange = () => {};

  const kinds = (group) => ({ triggers: CAT.triggers, conditions: CAT.conditions, actions: CAT.actions }[group]);

  function blank(group, type) {
    const spec = kinds(group)[type], item = { id: uid(), type };
    (spec.fields || []).forEach((f) => {
      if (f.default !== undefined) item[f.key] = Array.isArray(f.default) ? [...f.default] : f.default;
      if (["conditions", "actions"].includes(f.type)) item[f.key] = [];
      if (["branches", "options"].includes(f.type)) item[f.key] = [];
    });
    return item;
  }

  function changed(rerender) { onChange(rerender); }

  function input(f, obj) {
    const v = obj[f.key];
    const set = (val) => { if (val === "" || val === null || (Array.isArray(val) && !val.length)) delete obj[f.key]; else obj[f.key] = val; changed(false); };
    let node;
    switch (f.type) {
      case "textarea":
        node = el("textarea"); node.rows = 2; node.value = v ?? ""; node.oninput = () => set(node.value); break;
      case "number":
        node = el("input"); node.type = "text"; node.inputMode = "decimal"; node.value = v ?? ""; node.placeholder = f.placeholder || "";
        node.oninput = () => { const t = node.value.trim(); set(t === "" ? "" : (isNaN(Number(t)) ? t : Number(t))); }; break;
      case "time":
        node = el("input"); node.type = "time"; node.value = v ?? ""; node.oninput = () => set(node.value); break;
      case "bool":
        node = el("label", "am-check"); node.innerHTML = `<input type="checkbox"${(v ?? f.default) ? " checked" : ""}> sì`;
        node.firstChild.onchange = (e) => { obj[f.key] = e.target.checked; changed(false); }; break;
      case "days": case "multi": {
        const opts = f.type === "days" ? DAYS.map((d, i) => ({ value: i, label: d })) : f.options;
        const cur = new Set((v || []).map(String));
        node = el("div", "am-chips");
        opts.forEach((o) => {
          const c = el("label", "am-chip" + (cur.has(String(o.value)) ? " on" : ""), `<input type="checkbox"${cur.has(String(o.value)) ? " checked" : ""}>${esc(o.label)}`);
          c.firstChild.onchange = (e) => {
            const list = (obj[f.key] || []).filter((x) => String(x) !== String(o.value));
            if (e.target.checked) list.push(o.value);
            c.classList.toggle("on", e.target.checked); set(list);
          };
          node.appendChild(c);
        });
        break;
      }
      case "select": case "widget": case "sound": case "automation": {
        const opts = f.type === "widget" ? CAT.widgets.map((w) => ({ value: w, label: w }))
          : f.type === "sound" ? CAT.sounds.map((s) => ({ value: s, label: s }))
          : f.type === "automation" ? CAT.automations.map((a) => ({ value: a.id, label: a.name })) : f.options;
        node = el("select");
        node.innerHTML = `<option value="">—</option>` + opts.map((o) => `<option value="${esc(o.value)}"${String(o.value) === String(v ?? f.default ?? "") ? " selected" : ""}>${esc(o.label)}</option>`).join("");
        node.onchange = () => set(node.value); break;
      }
      case "entity": case "entities":
        node = el("input", "mono"); node.setAttribute("list", "am-entities"); node.value = Array.isArray(v) ? v.join(", ") : (v ?? "");
        node.placeholder = f.type === "entities" ? "light.soggiorno, light.cucina" : "light.soggiorno";
        node.oninput = () => set(node.value); break;
      case "json":
        node = el("textarea", "mono"); node.rows = 2; node.value = typeof v === "object" && v ? JSON.stringify(v) : (v ?? "");
        node.placeholder = '{"chiave": "valore"}'; node.oninput = () => set(node.value); break;
      case "list":
        node = el("textarea"); node.rows = 2; node.value = (v || []).join("\n");
        node.oninput = () => set(node.value.split("\n").map((x) => x.trim()).filter(Boolean)); break;
      default:
        node = el("input"); node.value = v ?? ""; node.placeholder = f.placeholder || ""; node.oninput = () => set(node.value);
    }
    return node;
  }

  function fieldRow(f, obj, group) {
    if (f.type === "conditions" || f.type === "actions") {
      const box = el("div", "am-nested");
      box.appendChild(el("div", "am-nested-title", esc(f.label)));
      obj[f.key] = obj[f.key] || [];
      box.appendChild(blockList(obj[f.key], f.type));
      return box;
    }
    if (f.type === "branches") {
      const box = el("div", "am-nested"); obj[f.key] = obj[f.key] || [];
      box.appendChild(el("div", "am-nested-title", esc(f.label)));
      obj[f.key].forEach((branch, i) => {
        const b = el("div", "am-branch");
        const head = el("div", "am-nested-title", `Ramo ${i + 1} <button class="btn sm" data-x>✕</button>`);
        head.querySelector("[data-x]").onclick = () => { obj[f.key].splice(i, 1); changed(true); };
        b.append(head, blockList(branch, "actions")); box.appendChild(b);
      });
      const add = el("button", "btn sm", "+ Ramo"); add.onclick = () => { obj[f.key].push([]); changed(true); };
      box.appendChild(add); return box;
    }
    if (f.type === "options") {
      const box = el("div", "am-nested"); obj[f.key] = obj[f.key] || [];
      box.appendChild(el("div", "am-nested-title", esc(f.label)));
      obj[f.key].forEach((opt, i) => {
        const b = el("div", "am-branch");
        const head = el("div", "am-nested-title", `Caso ${i + 1} <button class="btn sm" data-x>✕</button>`);
        head.querySelector("[data-x]").onclick = () => { obj[f.key].splice(i, 1); changed(true); };
        opt.conditions = opt.conditions || []; opt.actions = opt.actions || [];
        b.append(head, el("div", "faint", "Se"), blockList(opt.conditions, "conditions"), el("div", "faint", "Allora"), blockList(opt.actions, "actions"));
        box.appendChild(b);
      });
      const add = el("button", "btn sm", "+ Caso"); add.onclick = () => { obj[f.key].push({ conditions: [], actions: [] }); changed(true); };
      box.appendChild(add); return box;
    }
    const row = el("label", "am-field");
    row.appendChild(el("span", "", esc(f.label) + (f.required ? " *" : "")));
    row.appendChild(input(f, obj));
    return row;
  }

  function block(item, list, index, group) {
    const spec = kinds(group)[item.type] || { label: item.type, icon: "?", fields: [] };
    const card = el("div", "am-block" + (item.enabled === false ? " off" : "") + (item._closed ? " closed" : ""));
    const head = el("div", "am-block-head");
    const sel = el("select", "am-type");
    sel.innerHTML = Object.entries(kinds(group)).map(([k, s]) => `<option value="${k}"${k === item.type ? " selected" : ""}>${s.icon} ${esc(s.label)}</option>`).join("");
    sel.onchange = () => { list[index] = blank(group, sel.value); changed(true); };
    head.appendChild(el("span", "am-num", String(index + 1)));
    head.appendChild(sel);
    if (group === "triggers") head.appendChild(el("span", "faint mono am-id", `id ${esc(item.id)}`));
    const tools = el("span", "am-block-tools");
    const btn = (label, title, fn) => { const b = el("button", "btn sm", label); b.title = title; b.onclick = (e) => { e.preventDefault(); fn(); }; tools.appendChild(b); };
    if (group === "actions") {
      const c = el("label", "am-check faint", `<input type="checkbox"${item.continue_on_error ? " checked" : ""}> continua se fallisce`);
      c.firstChild.onchange = (e) => { item.continue_on_error = e.target.checked; changed(false); };
      tools.appendChild(c);
    }
    btn(item._closed ? "▸" : "▾", "Espandi o comprimi", () => { item._closed = !item._closed; changed(true); });
    btn("↑", "Sposta su", () => { if (index > 0) { [list[index - 1], list[index]] = [list[index], list[index - 1]]; changed(true); } });
    btn("↓", "Sposta giù", () => { if (index < list.length - 1) { [list[index + 1], list[index]] = [list[index], list[index + 1]]; changed(true); } });
    btn(item.enabled === false ? "Riattiva" : "Disattiva", "Escludi temporaneamente", () => { item.enabled = item.enabled === false; changed(true); });
    btn("⧉", "Duplica", () => { const copy = JSON.parse(JSON.stringify(item)); copy.id = uid(); list.splice(index + 1, 0, copy); changed(true); });
    btn("✕", "Elimina", () => { list.splice(index, 1); changed(true); });
    head.appendChild(tools);
    card.appendChild(head);
    if (!item._closed) {
      const body = el("div", "am-block-body");
      spec.fields.forEach((f) => body.appendChild(fieldRow(f, item, group)));
      if (!spec.fields.length) body.appendChild(el("div", "faint", "Nessuna impostazione."));
      card.appendChild(body);
    }
    return card;
  }

  function blockList(list, group) {
    const wrap = el("div", "am-blocks");
    list.forEach((item, i) => wrap.appendChild(block(item, list, i, group)));
    const add = el("div", "am-add");
    const sel = el("select");
    sel.innerHTML = `<option value="">+ Aggiungi ${group === "triggers" ? "innesco" : group === "conditions" ? "condizione" : "azione"}…</option>` +
      Object.entries(kinds(group)).map(([k, s]) => `<option value="${k}">${s.icon} ${esc(s.label)}</option>`).join("");
    sel.onchange = () => { if (sel.value) { list.push(blank(group, sel.value)); changed(true); } };
    add.appendChild(sel); wrap.appendChild(add);
    return wrap;
  }

  function general(a) {
    const box = el("div", "am-general");
    const fields = [
      { key: "name", label: "Nome", type: "text", required: true },
      { key: "description", label: "Descrizione", type: "textarea" },
      { key: "mode", label: "Se parte mentre è già in corso", type: "select", options: CAT.modes },
      { key: "max", label: "Massimo in coda o in parallelo", type: "number" },
      { key: "cooldown", label: "Pausa minima tra due esecuzioni (secondi)", type: "number" },
    ];
    fields.forEach((f) => box.appendChild(fieldRow(f, a)));
    const tags = el("label", "am-field", "<span>Etichette (separate da virgola)</span>");
    const ti = el("input"); ti.value = (a.tags || []).join(", ");
    ti.oninput = () => { a.tags = ti.value.split(",").map((x) => x.trim()).filter(Boolean); changed(false); };
    tags.appendChild(ti); box.appendChild(tags);
    const vars = el("label", "am-field", "<span>Variabili iniziali (JSON)</span>");
    const vi = el("textarea", "mono"); vi.rows = 2; vi.value = JSON.stringify(a.variables || {});
    vi.oninput = () => { try { a.variables = JSON.parse(vi.value || "{}"); vi.classList.remove("bad"); changed(false); } catch (e) { vi.classList.add("bad"); } };
    vars.appendChild(vi); box.appendChild(vars);
    const on = el("label", "am-check", `<input type="checkbox"${a.enabled !== false ? " checked" : ""}> Attiva`);
    on.firstChild.onchange = (e) => { a.enabled = e.target.checked; changed(false); };
    box.appendChild(on);
    return box;
  }

  function section(title, hint, list, group) {
    const s = el("div", "am-section");
    s.appendChild(el("div", "am-section-title", `${esc(title)} <span class="faint">${esc(hint)}</span>`));
    s.appendChild(blockList(list, group));
    return s;
  }

  function strip(x) {
    if (Array.isArray(x)) return x.map(strip);
    if (x && typeof x === "object") { const o = {}; Object.entries(x).forEach(([k, v]) => { if (!k.startsWith("_")) o[k] = strip(v); }); return o; }
    return x;
  }

  window.AutomationEditor = {
    render(container, a, catalog, cb) {
      CAT = catalog; onChange = cb || (() => {});
      a.triggers = a.triggers || []; a.conditions = a.conditions || []; a.actions = a.actions || [];
      container.innerHTML = "";
      container.append(general(a),
        section("Quando", "uno qualsiasi degli inneschi avvia l'automazione", a.triggers, "triggers"),
        section("Solo se", "tutte le condizioni devono essere vere (usa E/O/NON per combinarle)", a.conditions, "conditions"),
        section("Allora", "le azioni vengono eseguite in ordine, con rami, attese e ripetizioni", a.actions, "actions"));
    },
    clean: strip,
  };
})();
