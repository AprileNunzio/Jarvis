(() => {
  JarvisDesk.register("text_long", {
    render(el, d, ctx) {
      el.innerHTML = `<div style="padding: 1.5rem; max-height: 400px; overflow-y: auto; background: rgba(30,41,59,0.8); border: 1px solid #334155; border-radius: 12px; font-size: 1.1rem; line-height: 1.6; color: #f8fafc;">
        ${d.content || "<i>Caricamento testo esteso...</i>"}
      </div>`;
    }
  });
})();
