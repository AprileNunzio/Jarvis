(() => {
  JarvisDesk.register("alert_error", {
    render(el, d, ctx) {
      el.innerHTML = `
        <div style="background: rgba(239, 68, 68, 0.1); border: 1px solid #ef4444; border-radius: 8px; padding: 16px; display: flex; align-items: flex-start;">
          <span style="font-size: 1.5rem; margin-right: 12px;">🚨</span>
          <div>
            <h4 style="margin: 0 0 4px 0; color: #f87171; font-weight: bold;">${ctx.esc(d.title || "Errore")}</h4>
            <div style="color: #fca5a5;">${d.content || ""}</div>
          </div>
        </div>
      `;
    }
  });
})();
