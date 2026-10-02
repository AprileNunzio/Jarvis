(() => {
  JarvisDesk.register("rag_sources", {
    render(el, d, ctx) {
      const sources = d.sources || [];
      const list = sources.map(s => `<div style="background: rgba(255,255,255,0.05); padding: 8px; margin-bottom: 6px; border-radius: 4px; display: flex; justify-content: space-between;"><span style="color: #e2e8f0;">📄 ${s.name}</span><span style="color: #a855f7;">${s.relevance}%</span></div>`).join('');
      el.innerHTML = `
        <div style="background: #0f172a; border-left: 4px solid #a855f7; border-radius: 8px; padding: 16px; height: 100%; box-sizing: border-box;">
          <h4 style="margin: 0 0 12px 0; color: #a855f7; font-size: 0.9rem; text-transform: uppercase;">📚 Fonti Documentali</h4>
          <div style="color: #94a3b8; font-size: 0.8rem; margin-bottom: 12px;">Query: "${d.query || 'Generica'}"</div>
          ${list}
        </div>
      `;
    }
  });
})();