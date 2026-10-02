(() => {
  function copy(text, button) {
    const done = () => { button.textContent = "Copiato"; setTimeout(() => { button.textContent = "Copia"; }, 1500); };
    if (navigator.clipboard && window.isSecureContext) return navigator.clipboard.writeText(text).then(done).catch(() => fallback(text, done));
    fallback(text, done);
  }

  function fallback(text, done) {
    const area = document.createElement("textarea");
    area.value = text;
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.appendChild(area);
    area.select();
    try { document.execCommand("copy"); done(); } catch (err) { console.warn(err); }
    area.remove();
  }

  JarvisDesk.register("code_view", {
    render(el, d, ctx) {
      const lines = String(d.content || "").split("\n").length;
      el.innerHTML = `
        <div class="cv-head"><span class="cv-lang">${ctx.esc(d.language || "testo")}</span>
          <span class="cv-title">${ctx.esc(d.title || "")}</span><span class="cv-lines">${lines} righe</span>
          <button class="cv-copy" type="button">Copia</button></div>
        <pre class="cv-code"><code>${ctx.esc(d.content || "")}</code></pre>`;
      el.querySelector(".cv-copy").addEventListener("click", (e) => { e.stopPropagation(); copy(d.content || "", e.currentTarget); });
    },
  });
})();
