(() => {
  JarvisDesk.register("kanban_board", {
    render(el, d, ctx) {
      const doing = (d.doing || []).map(t => `<div style="background: rgba(245,158,11,0.1); border: 1px solid #f59e0b; padding: 6px; border-radius: 4px; margin-bottom: 4px; font-size: 0.85rem; color: #fde68a;">⏳ ${t}</div>`).join('');
      const todo = (d.todo || []).map(t => `<div style="background: rgba(255,255,255,0.05); border: 1px solid #334155; padding: 6px; border-radius: 4px; margin-bottom: 4px; font-size: 0.85rem; color: #cbd5e1;">📋 ${t}</div>`).join('');
      el.innerHTML = `
        <div style="background: #0f172a; border-left: 4px solid #f59e0b; border-radius: 8px; padding: 16px; height: 100%; box-sizing: border-box;">
          <h4 style="margin: 0 0 12px 0; color: #f59e0b; font-size: 0.9rem; text-transform: uppercase;">📋 Kanban Agente</h4>
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
            <div>
              <div style="font-size: 0.75rem; color: #94a3b8; margin-bottom: 8px; text-transform: uppercase;">In Lavorazione</div>
              ${doing}
            </div>
            <div>
              <div style="font-size: 0.75rem; color: #94a3b8; margin-bottom: 8px; text-transform: uppercase;">Da Fare</div>
              ${todo}
            </div>
          </div>
        </div>
      `;
    }
  });
})();