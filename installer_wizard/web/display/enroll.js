(() => {
  const D = window.JarvisDisplay, { fmt } = D;
  let session = null;

  function box() {
    let el = document.getElementById("enroll");
    if (!el) {
      el = document.createElement("div");
      el.id = "enroll";
      el.className = "enroll";
      document.body.appendChild(el);
      el.addEventListener("click", (e) => { if (e.target.closest("[data-stop]")) finish(true); });
    }
    return el;
  }

  function draw(note) {
    const s = session, total = s.sentences.length, pct = Math.round((s.index / total) * 100);
    box().innerHTML = `<div class="en-card"><div class="en-head">🎙 Impariamo la tua voce, ${fmt.esc(s.name)}</div>
      <div class="en-bar"><i style="width:${pct}%"></i></div>
      <div class="en-step">Frase ${Math.min(s.index + 1, total)} di ${total}</div>
      <div class="en-text">${fmt.esc(s.sentences[Math.min(s.index, total - 1)])}</div>
      <div class="en-note">${fmt.esc(note || "Leggi ad alta voce, con calma e con il tuo tono normale.")}</div>
      <button class="pill-btn" data-stop>Interrompi</button></div>`;
    box().classList.add("show");
  }

  function finish(stopped) {
    if (!session) return;
    D.Ear.send({ type: "enroll_stop" });
    const name = session.name;
    session = null;
    box().classList.remove("show");
    const text = stopped ? "Test interrotto: continuerò comunque a imparare la tua voce mentre parliamo."
      : `Perfetto, ${name}: da adesso ti riconosco anche dalla voce.`;
    D.typeInto(document.getElementById("say"), text);
    D.speak(text);
  }

  D.Enroll = {
    start(ui) {
      if (!D.local) return;
      session = { slug: ui.slug, name: ui.name, sentences: ui.sentences || [], index: 0 };
      draw();
      setTimeout(() => session && D.Ear.send({ type: "enroll_start", slug: session.slug }), 3500);
    },
    progress(ev) {
      if (!session) return;
      if (!ev.ok) { draw("Non ho sentito bene: ripeti la frase un po' più vicino al microfono."); return; }
      if (ev.count === undefined || session.started === undefined) { session.started = ev.count || 0; return; }
      session.index += 1;
      if (session.index >= session.sentences.length) finish(false);
      else draw();
    },
    unavailable() {
      session = null;
      box().classList.remove("show");
      const text = "Su questo sistema l'impronta vocale non è disponibile: continuerò a riconoscerti dal volto.";
      D.typeInto(document.getElementById("say"), text);
      D.speak(text);
    },
    get active() { return !!session; },
  };
})();
