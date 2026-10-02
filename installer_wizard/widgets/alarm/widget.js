(() => {
  const KIND = { smoke: ["🔥", "Fumo rilevato"], gas: ["⚠️", "Fuga di gas"], flood: ["💧", "Allagamento"],
                 intrusion: ["🚨", "Intrusione"], co: ["☠️", "Monossido di carbonio"], generic: ["⚠️", "Allarme"] };
  JarvisDesk.register("alarm", {
    render(el, d, ctx) {
      const [icon, title] = KIND[d.kind] || KIND.generic;
      el.innerHTML = `<div class="al-ring"></div><div class="al-icon">${icon}</div>
        <div class="al-title">${ctx.esc(d.title || title)}</div>
        ${d.room ? `<div class="al-room">${ctx.esc(d.room)}</div>` : ""}
        <div class="al-msg">${ctx.esc(d.message || "")}</div>
        <div class="al-time">${new Date((d.at || ctx.now()) * 1000).toLocaleTimeString("it-IT")}</div>`;
      el._rep = setInterval(() => d.speak && ctx.speak(d.speak), 45000);
    },
    destroy(el) { clearInterval(el._rep); },
  });
})();
