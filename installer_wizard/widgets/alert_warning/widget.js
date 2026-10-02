(() => {
  JarvisDesk.register("alert_warning", {
    render(el, d, ctx) {
      el.innerHTML = `<div style="background: rgba(245, 158, 11, 0.15); border-left: 4px solid #f59e0b; border-radius: 0 8px 8px 0; padding: 16px; display: flex; align-items: flex-start;">
        <span style="font-size: 1.5rem; margin-right: 12px; color: #fbbf24;">⚠️</span>
        <div>
          <h4 style="margin: 0 0 4px 0; color: #fcd34d; font-weight: bold;">${ctx.esc(d.title || "Attenzione")}</h4>
          <div style="color: #fde68a;">${d.content || ""}</div>
        </div>
      </div>`;
    }
  });
})();
