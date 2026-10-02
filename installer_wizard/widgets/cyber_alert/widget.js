(() => {
  JarvisDesk.register("cyber_alert", {
    render(el, d, ctx) {
      el.innerHTML = `
        <div style="background: repeating-linear-gradient(45deg, #450a0a, #450a0a 10px, #2e0505 10px, #2e0505 20px); border: 2px solid #ef4444; border-radius: 8px; padding: 16px; height: 100%; box-sizing: border-box; position: relative;">
          <h4 style="margin: 0 0 12px 0; color: #f87171; font-size: 1rem; text-transform: uppercase; display: flex; justify-content: space-between;">
            <span>🛡️ VIOLAZIONE DI SICUREZZA</span>
            <span style="background: #ef4444; color: white; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; animation: pulse 1s infinite;">${ctx.esc(d.threat_level || 'ALERT')}</span>
          </h4>
          <div style="background: rgba(0,0,0,0.5); padding: 12px; border-radius: 6px; font-family: monospace; font-size: 0.85rem; color: #fca5a5;">
            <div><span style="color: #991b1b;">></span> IP SORGENTE: <span style="color: #fff;">${ctx.esc(d.source_ip || 'UNKNOWN')}</span></div>
            <div><span style="color: #991b1b;">></span> VETTORE D'ATTACCO: <span style="color: #fff;">${ctx.esc(d.attack_type || 'Tentativo di Intrusione')}</span></div>
            <div style="margin-top: 8px; border-top: 1px dashed #ef4444; padding-top: 8px; color: #10b981;">[✓] AZIONE: ${ctx.esc(d.action_taken || 'Registrato nei Log')}</div>
          </div>
        </div>
      `;
    }
  });
})();
