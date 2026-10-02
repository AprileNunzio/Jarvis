(() => {
  JarvisDesk.register("active_tasks", {
    render(el, d, ctx) {
      const tasks = d.tasks || ["In attesa di istruzioni...", "Monitoraggio file di sistema in corso (Daemon)"];
      
      el.innerHTML = `<div style="background: #0f172a; border-left: 3px solid #14b8a6; border-radius: 0 12px 12px 0; padding: 16px;">
        <h4 style="margin: 0 0 12px 0; color: #5eead4; font-size: 0.85rem; text-transform: uppercase; display: flex; align-items: center;"><span style="margin-right: 8px;">🤖</span> Stato Agente</h4>
        <ul style="margin: 0; padding-left: 20px; color: #cbd5e1; font-size: 0.95rem; line-height: 1.6;">
          ${tasks.map(t => `<li style="margin-bottom: 4px;">${ctx.esc(t)}</li>`).join('')}
        </ul>
      </div>`;
    }
  });
})();
