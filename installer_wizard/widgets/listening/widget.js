(() => {
  const LABEL = { idle: "Di' «Jarvis»", listening: "Ti ascolto…", transcribing: "Sto capendo…", off: "Microfono non attivo" };
  JarvisDesk.register("listening", {
    render(el) {
      el.innerHTML = `<div class="ls-box idle"><span class="ls-ic">🎙</span><span class="ls-bars">${"<i></i>".repeat(10)}</span><span class="ls-t">${LABEL.idle}</span></div>`;
      const box = el.firstChild, bars = [...box.querySelectorAll(".ls-bars i")], text = box.querySelector(".ls-t");
      const onState = (e) => {
        const s = e.detail.state;
        box.className = `ls-box ${s}`;
        text.textContent = s === "off" ? (e.detail.text || LABEL.off).replace(/^Microfono non disponibile: /, "Microfono: ") : LABEL[s] || s;
      };
      const onLevel = (e) => {
        const v = e.detail;
        bars.forEach((b, i) => { b.style.height = `${3 + Math.max(0, v * 30 - Math.abs(i - 4.5) * 2 + Math.random() * 3)}px`; });
      };
      window.addEventListener("jarvis-ear", onState);
      window.addEventListener("jarvis-ear-level", onLevel);
      el._off = () => { window.removeEventListener("jarvis-ear", onState); window.removeEventListener("jarvis-ear-level", onLevel); };
      if (window.jarvisEar) onState({ detail: { state: window.jarvisEar.state } });
    },
    update() {},
    destroy(el) { if (el._off) el._off(); },
  });
})();
