(() => {
  const ICON = { docx: "📝", odt: "📝", xlsx: "📊", ods: "📊", pptx: "📽", odp: "📽", pdf: "📕" };
  const ext = (name) => (String(name).split(".").pop() || "").toLowerCase();
  const base = (path) => String(path).split("/").pop();

  function office(el, d, ctx) {
    const files = (d.files || []).map((f, i) => `<a class="dv-file" href="/api/documents/${encodeURIComponent(d.id)}/file/${i}" target="_blank" rel="noopener">
        <span class="dv-ic">${ICON[ext(f)] || "📄"}</span><span class="dv-name">${ctx.esc(base(f))}</span><span class="dv-ext">${ctx.esc(ext(f))}</span></a>`).join("");
    const errors = (d.errors || []).length ? `<div class="dv-err">Non riusciti: ${d.errors.map(ctx.esc).join("; ")}</div>` : "";
    const preview = d.preview ? `<iframe class="dv-frame" src="/api/documents/${encodeURIComponent(d.id)}/preview.pdf#view=FitH&toolbar=0"></iframe>` : "";
    el.innerHTML = `<div class="dv-wrap">
      <div class="dv-head"><div><div class="dv-title">${ctx.esc(d.title || "Documento")}</div>
        <div class="dv-sub">${ctx.esc(d.kind === "progetto" ? "Progetto" : "Documento")} · ${ctx.esc(d.summary || "")}</div></div></div>
      <div class="dv-body ${preview ? "with-preview" : ""}"><div class="dv-files">${files}${errors}
        <div class="dv-where">Cartella condivisa › 01 Documenti${d.project ? ` › ${ctx.esc(base(d.project))}` : ""}</div></div>${preview}</div></div>`;
  }

  JarvisDesk.register("document_viewer", {
    render(el, d, ctx) {
      if (d.type === "office") return office(el, d, ctx);
      const url = d.url ? String(d.url) : "";
      const content = url ? `<iframe class="dv-frame" src="${ctx.esc(url)}"></iframe>`
        : `<div class="dv-empty">Anteprima non disponibile per questo formato (${ctx.esc(d.type || "file")}).</div>`;
      el.innerHTML = `<div class="dv-wrap"><div class="dv-head"><div class="dv-title">${ctx.esc(d.title || "Visualizzatore")}</div>
        <span class="dv-ext">${ctx.esc(d.type || "file")}</span></div><div class="dv-body with-preview">${content}</div></div>`;
    },
  });
})();
