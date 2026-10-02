(() => {
  JarvisDesk.register("alert_info", {
    render(el, d, ctx) {
      el.innerHTML = `<div style="background: rgba(59, 130, 246, 0.15); border-left: 4px solid #3b82f6; border-radius: 0 8px 8px 0; padding: 16px; display: flex; align-items: flex-start;">
        <span style="font-size: 1.5rem; margin-right: 12px; color: #60a5fa;">ℹ️</span>
        <div>
          <h4 style="margin: 0 0 4px 0; color: #93c5fd; font-weight: bold;">${ctx.esc(d.title || "Informazione")}</h4>
          <div style="color: #bfdbfe;">${d.content || ""}</div>
        </div>
      </div>`;
    }
  });
})();
