(() => {
  JarvisDesk.register("document_viewer", {
    render(el, d, ctx) {
      const isWeb = d.type === 'web';
      
      const content = isWeb && d.url 
        ? `<iframe src="${d.url}" style="width:100%; height:75vh; min-height:600px; border:none; border-radius:4px; background:#fff;"></iframe>`
        : `<div style="padding: 40px; text-align: center; border: 2px dashed #475569; border-radius: 8px; color: #94a3b8;">
             <span style="font-size: 3rem; display: block; margin-bottom: 12px;">📑</span>
             Preview non disponibile per il formato nativo locale (${d.type || 'Sconosciuto'}). Apre l'applicazione predefinita di sistema.
           </div>`;

      el.innerHTML = `
        <div style="background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 12px; height: 100%; width: 100%; box-sizing: border-box; display: flex; flex-direction: column;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
            <div style="color: #e2e8f0; font-weight: bold; font-size: 1.2rem;">${ctx.esc(d.title || "Visualizzatore")}</div>
            <div style="background: #475569; color: #f8fafc; font-size: 0.8rem; padding: 4px 8px; border-radius: 4px; text-transform: uppercase;">${ctx.esc(d.type || "FILE")}</div>
          </div>
          <div style="flex-grow: 1;">${content}</div>
        </div>
      `;
    }
  });
})();
