(() => {
  JarvisDesk.register("contact_card", {
    render(el, d, ctx) {
      el.innerHTML = `
        <div style="background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 16px; height: 100%; box-sizing: border-box; display: flex; align-items: center;">
          <div style="width: 50px; height: 50px; background: #3b82f6; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 1.5rem; margin-right: 16px; color: white;">
            ${d.name ? ctx.esc(d.name.charAt(0).toUpperCase()) : '👤'}
          </div>
          <div style="flex-grow: 1;">
            <div style="color: #f8fafc; font-weight: bold; font-size: 1.1rem;">${ctx.esc(d.name || 'Sconosciuto')}</div>
            <div style="color: #94a3b8; font-size: 0.85rem; margin-bottom: 6px;">${ctx.esc(d.company || '')}</div>
            <div style="background: rgba(255,255,255,0.05); padding: 6px 10px; border-radius: 6px; display: inline-block;">
              <div style="color: #38bdf8; font-weight: bold; font-family: monospace; font-size: 1rem;">${ctx.esc(d.phone || 'Nessun Numero')}</div>
              ${d.email ? `<div style="color: #64748b; font-size: 0.75rem; margin-top: 2px;">${ctx.esc(d.email)}</div>` : ''}
            </div>
          </div>
        </div>
      `;
    }
  });
})();
