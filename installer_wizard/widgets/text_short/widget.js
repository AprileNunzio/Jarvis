(() => {
  JarvisDesk.register("text_short", {
    render(el, d, ctx) {
      el.innerHTML = `<div style="padding: 1rem; font-size: 1.1rem; line-height: 1.5; color: #e2e8f0;">
        ${d.content || ""}
      </div>`;
    }
  });
})();
