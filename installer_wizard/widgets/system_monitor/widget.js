(() => {
  JarvisDesk.register("system_monitor", {
    render(el, d, ctx) {
      const cpu = d.cpu || Math.floor(Math.random() * 40) + 10;
      const ram = d.ram || Math.floor(Math.random() * 30) + 40;
      
      const bar = (val, color) => `<div style="width: 100%; background: #333; border-radius: 4px; height: 8px; margin-top: 4px; overflow: hidden;"><div style="width: ${val}%; background: ${color}; height: 100%;"></div></div>`;
      
      el.innerHTML = `<div style="background: #111827; border: 1px solid #374151; border-radius: 12px; padding: 16px;">
        <h4 style="margin: 0 0 12px 0; color: #9ca3af; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 1px;">📊 Telemetria Nodo</h4>
        <div style="margin-bottom: 12px;">
          <div style="display: flex; justify-content: space-between; color: #e5e7eb; font-size: 0.9rem;"><span>Utilizzo CPU</span><span>${cpu}%</span></div>
          ${bar(cpu, cpu > 80 ? '#ef4444' : '#10b981')}
        </div>
        <div>
          <div style="display: flex; justify-content: space-between; color: #e5e7eb; font-size: 0.9rem;"><span>Allocazione Memoria</span><span>${ram}%</span></div>
          ${bar(ram, ram > 85 ? '#ef4444' : '#3b82f6')}
        </div>
      </div>`;
    }
  });
})();
