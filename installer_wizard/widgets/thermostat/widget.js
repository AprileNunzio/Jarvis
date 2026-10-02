(() => {
  JarvisDesk.register("thermostat", {
    render(el, d, ctx) {
      el.innerHTML = `
        <div style="background: #0f172a; border-left: 4px solid #10b981; border-radius: 8px; padding: 16px; height: 100%; box-sizing: border-box; display: flex; align-items: center; justify-content: space-between;">
          <div>
            <h4 style="margin: 0 0 4px 0; color: #10b981; font-size: 0.9rem; text-transform: uppercase;">🌡️ Termostato</h4>
            <div style="color: #94a3b8; font-size: 0.85rem;">${d.status || 'Standby'}</div>
            <div style="color: #64748b; font-size: 0.75rem; margin-top: 4px;">Umidità: ${d.humidity || 0}%</div>
          </div>
          <div style="text-align: right;">
            <div style="font-size: 2.5rem; font-weight: bold; color: #f8fafc; line-height: 1;">${d.current || '--'}°</div>
            <div style="color: #10b981; font-size: 0.9rem;">Obiettivo: ${d.target || '--'}°</div>
          </div>
        </div>
      `;
    }
  });
})();