(() => {
  const A = window.JarvisAdmin, { fmt } = A;
  const order = (list) => [...list.querySelectorAll(".prio-item[draggable=true]")].map((el) => el.dataset.id);

  A.makeSortable = (list, onChange) => {
    let dragged = null;
    list.addEventListener("dragstart", (e) => { dragged = e.target.closest(".prio-item[draggable=true]"); if (!dragged) return; dragged.classList.add("dragging"); e.dataTransfer.effectAllowed = "move"; });
    list.addEventListener("dragend", () => { if (!dragged) return; dragged.classList.remove("dragging"); dragged = null; list.classList.remove("drop"); onChange(order(list)); });
    list.addEventListener("dragover", (e) => {
      if (!dragged) return; e.preventDefault(); list.classList.add("drop");
      const after = [...list.querySelectorAll(".prio-item[draggable=true]:not(.dragging)")].find((el) => e.clientY < el.getBoundingClientRect().top + el.offsetHeight / 2);
      if (after) list.insertBefore(dragged, after); else { const safety = list.querySelector(".prio-item.safety"); list.insertBefore(dragged, safety); }
    });
    list.addEventListener("dragleave", (e) => { if (!list.contains(e.relatedTarget)) list.classList.remove("drop"); });
    list.addEventListener("click", (e) => {
      const b = e.target.closest("[data-mv]"); if (!b) return;
      const item = b.closest(".prio-item"), items = order(list), i = items.indexOf(item.dataset.id);
      if (b.dataset.mv === "x") items.splice(i, 1);
      else { const j = i + (b.dataset.mv === "up" ? -1 : 1); if (j < 0 || j >= items.length) return; [items[i], items[j]] = [items[j], items[i]]; }
      onChange(items);
    });
  };

  A.prioItem = (id, i, title, sub, missing, safety) => `<div class="prio-item ${missing ? "miss" : ""} ${safety ? "safety" : ""}" data-id="${fmt.esc(id)}" ${safety ? "" : 'draggable="true"'}>
      <span class="grip">${safety ? "🔒" : "⠿"}</span><span class="rank">${i + 1}</span>
      <div style="min-width:0"><div class="nm">${fmt.esc(title)}</div><div class="sub">${sub}</div></div>
      <div class="ops">${safety ? "" : `<button data-mv="up" title="Sposta su">▲</button><button data-mv="down" title="Sposta giù">▼</button><button data-mv="x" title="Togli dalla lista">✕</button>`}</div></div>`;
})();
