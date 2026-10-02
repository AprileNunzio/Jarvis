(() => {
  JarvisDesk.register("usb_monitor", {
    render(el, d, ctx) {
      el.innerHTML = `
        <div style="background: #0f172a; border: 1px solid #334155; border-top: 4px solid #3b82f6; border-radius: 8px; padding: 16px; height: 100%; box-sizing: border-box;">
          <h4 style="margin: 0 0 12px 0; color: #60a5fa; font-size: 0.9rem; text-transform: uppercase;">🔌 Nuovo Dispositivo USB</h4>
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 0.85rem;">
            <div style="color: #94a3b8;">Mount Point: <br><span style="color: #f8fafc; font-weight: bold;">${ctx.esc(d.mount || 'N/A')}</span></div>
            <div style="color: #94a3b8;">Capacità: <br><span style="color: #f8fafc; font-weight: bold;">${ctx.esc(d.size || 'N/A')}</span></div>
            <div style="color: #94a3b8; grid-column: span 2;">Produttore: <br><span style="color: #e2e8f0;">${ctx.esc(d.vendor || 'Unknown')} - ${ctx.esc(d.product || 'Generic Device')}</span></div>
            <div style="color: #475569; grid-column: span 2; font-family: monospace; font-size: 0.7rem; margin-top: 4px;">S/N: ${ctx.esc(d.serial || 'N/A')}</div>
          </div>
        </div>
      `;
    }
  });
})();
