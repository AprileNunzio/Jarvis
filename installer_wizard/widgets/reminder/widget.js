(() => {
  JarvisDesk.register("reminder", {
    render(el, d, ctx) {
      el.innerHTML = `<div style="background: linear-gradient(90deg, rgba(139,92,246,0.15) 0%, rgba(99,102,241,0.15) 100%); border: 1px solid rgba(139,92,246,0.3); border-radius: 12px; padding: 16px; display: flex; justify-content: space-between; align-items: center;">
        <div style="display: flex; align-items: center;">
          <span style="font-size: 1.8rem; margin-right: 16px; color: #a78bfa;">⏰</span>
          <div style="color: #ddd6fe; font-size: 1.1rem; font-weight: 500;">${d.content || "Nuovo promemoria"}</div>
        </div>
        <div style="color: #8b5cf6; font-size: 0.9rem; font-family: monospace; background: rgba(0,0,0,0.3); padding: 4px 8px; border-radius: 4px;">ATTESA</div>
      </div>`;
    }
  });
})();
