(() => {
  JarvisDesk.register("cicd_tracker", {
    render(el, d, ctx) {
      el.innerHTML = `
        <div style="background: #0f172a; border-left: 4px solid #3b82f6; border-radius: 8px; padding: 16px; height: 100%; box-sizing: border-box;">
          <h4 style="margin: 0 0 12px 0; color: #3b82f6; font-size: 0.9rem; text-transform: uppercase; display: flex; align-items: center;">
            <span style="margin-right: 8px; font-size: 1.2rem;">⚙️</span> CI/CD Pipeline
          </h4>
          <div style="color: #cbd5e1; font-size: 0.95rem;">
            ${d.content || "Inizializzazione modulo e caricamento dati in corso..."}<br>
            <small style="color: #64748b;">(Modulo Auto-Generato)</small>
          </div>
        </div>
      `;
    }
  });
})();
