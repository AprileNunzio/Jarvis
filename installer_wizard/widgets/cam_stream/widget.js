(() => {
  JarvisDesk.register("cam_stream", {
    render(el, d, ctx) {
      el.innerHTML = `
        <div style="background: #0f172a; border-left: 4px solid #ef4444; border-radius: 8px; padding: 16px; height: 100%; box-sizing: border-box; position: relative;">
          <h4 style="margin: 0 0 12px 0; color: #ef4444; font-size: 0.9rem; text-transform: uppercase;">📷 Videocamera di Sicurezza</h4>
          <div style="width: 100%; height: 80px; background: #000; border-radius: 4px; display: flex; align-items: center; justify-content: center; border: 1px solid #333; position: relative; overflow: hidden;">
            <div style="color: #444; font-size: 0.8rem; font-family: monospace;">[ FEED RTSP OFFLINE (SIMULAZIONE) ]</div>
            ${d.motion_detected ? '<div style="position: absolute; top: 4px; right: 4px; background: #ef4444; color: white; font-size: 0.6rem; padding: 2px 6px; border-radius: 12px; font-weight: bold; animation: pulse 2s infinite;">MOVIMENTO RILEVATO</div>' : ''}
          </div>
          <div style="color: #94a3b8; font-size: 0.75rem; margin-top: 8px; text-align: right;">Sorgente: ${d.camera || 'Sconosciuta'}</div>
        </div>
      `;
    }
  });
})();