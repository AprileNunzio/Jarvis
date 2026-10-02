(() => {
  JarvisDesk.register("os_networks", {
    render(el, d, ctx) {
      const devs = d.devices || [];
      const list = devs.map(net => `
        <div style="background: rgba(255,255,255,0.05); border: 1px solid ${net.connected ? '#10b981' : '#334155'}; padding: 12px; margin-bottom: 8px; border-radius: 6px; display: flex; justify-content: space-between; align-items: center;">
          <div style="display: flex; align-items: center;">
            <span style="font-size: 1.2rem; margin-right: 12px;">${net.secure ? '🔒' : '🔓'}</span>
            <div>
              <div style="color: #f8fafc; font-weight: bold; font-size: 0.95rem;">${ctx.esc(net.name)}</div>
              <div style="color: #94a3b8; font-size: 0.75rem;">Segnale: ${net.signal}%</div>
            </div>
          </div>
          <button style="background: ${net.connected ? '#047857' : '#3b82f6'}; border: none; color: white; padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 0.8rem;">
            ${net.connected ? 'Connesso' : 'Connetti'}
          </button>
        </div>
      `).join('');

      el.innerHTML = `
        <div style="background: #0f172a; border-left: 4px solid #3b82f6; border-radius: 8px; padding: 16px; height: 100%; box-sizing: border-box; overflow-y: auto;">
          <h4 style="margin: 0 0 16px 0; color: #3b82f6; font-size: 0.9rem; text-transform: uppercase;">📡 Gestore Reti & Bluetooth</h4>
          ${list || '<div style="color: #64748b; font-style: italic;">Nessun dispositivo rilevato nel raggio.</div>'}
        </div>
      `;
    }
  });
})();
