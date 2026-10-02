(() => {
  JarvisDesk.register("code_view", {
    render(el, d, ctx) {
      const safeContent = ctx.esc(d.content || "");
      const lang = ctx.esc(d.language || "text");
      el.innerHTML = `
        <div style="background: #1e1e1e; border-radius: 8px; overflow: hidden; border: 1px solid #333;">
          <div style="background: #2d2d2d; padding: 4px 12px; font-size: 0.75rem; color: #888; font-family: monospace;">${lang}</div>
          <pre style="margin: 0; padding: 12px; color: #d4d4d4; font-family: monospace; overflow-x: auto;"><code>${safeContent}</code></pre>
        </div>
      `;
    }
  });
})();
