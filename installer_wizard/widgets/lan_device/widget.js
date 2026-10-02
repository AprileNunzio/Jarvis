(() => {
  JarvisDesk.register("lan_device", {
    render(el, d, ctx) {
      el.innerHTML = `
        <div style="background: #0f172a; border: 1px solid #334155; border-top: 4px solid #10b981; border-radius: 8px; padding: 16px; height: 100%; box-sizing: border-box;">
          <h4 style="margin: 0 0 12px 0; color: #34d399; font-size: 0.9rem; text-transform: uppercase;">🖥️ Nodo di Rete Rilevato</h4>
          <div style="display: flex; flex-direction: column; gap: 6px; font-size: 0.85rem;">
            <div style="display: flex; justify-content: space-between;"><span style="color: #94a3b8;">Indirizzo IP</span><span style="color: #10b981; font-family: monospace;">${ctx.esc(d.ip || 'DHCP Pending')}</span></div>
            <div style="display: flex; justify-content: space-between;"><span style="color: #94a3b8;">Indirizzo MAC</span><span style="color: #94a3b8; font-family: monospace;">${ctx.esc(d.mac || 'N/A')}</span></div>
            <div style="display: flex; justify-content: space-between;"><span style="color: #94a3b8;">Nome Host</span><span style="color: #f8fafc;">${ctx.esc(d.hostname || 'Unknown')}</span></div>
            <div style="display: flex; justify-content: space-between;"><span style="color: #94a3b8;">Produttore</span><span style="color: #e2e8f0;">${ctx.esc(d.vendor || 'Generic')}</span></div>
          </div>
        </div>
      `;
    }
  });
})();
