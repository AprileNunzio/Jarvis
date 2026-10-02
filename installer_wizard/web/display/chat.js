(() => {
  const D = window.JarvisDisplay, { $ } = D;

  function thinking(on) {
    const { avatar } = D;
    if (!avatar) return;
    avatar.setTint(on ? "#b36bff" : D.tint || "#29e0ff");
    if (avatar.face) avatar.face.thinking = on;
  }

  D.greetWake = async () => {
    if (D.busy) return;
    D.busy = true; D.lastInteraction = Date.now();
    try {
      const d = await fetch("/api/assistant/wake", { method: "POST" }).then((r) => r.json());
      if (D.mode !== "face") D.setMode("face");
      D.Mood.joy();
      $("you").textContent = "";
      D.typeInto($("say"), d.reply);
      D.lastVoice = true;
      D.speak(d.reply);
    } catch (err) {
      D.Ear.followup(8);
    } finally {
      D.busy = false; D.lastInteraction = Date.now();
    }
  };

  function enrollUi(d) {
    if (!d.ui || d.ui.mode !== "enroll") return false;
    D.setMode("face");
    D.typeInto($("say"), d.reply);
    D.lastVoice = false;
    D.speak(d.reply);
    D.Enroll.start(d.ui);
    return true;
  }

  function show(text, d) {
    $("you").textContent = `« ${text} »`;
    if (enrollUi(d)) return;
    const ui = d.ui || { mode: "face" };
    if (ui.mode === "focus") { D.renderStage(ui); D.typeInto($("focus-say"), d.reply); }
    D.setPresence(ui.presence || "normal");
    D.setMode(ui.mode);
    D.typeInto($("say"), d.reply);
    D.speak(d.reply, d.lang);
    if (ui.mode === "face" || ui.mode === "focus") setTimeout(() => D.refreshBrain(true), 1500);
  }

  async function predict(text) {
    const pred = await fetch(`/api/assistant/predict?q=${encodeURIComponent(text)}`).then((r) => r.json()).catch(() => null);
    if (pred && pred.skeleton && pred.skeleton.mode === "focus") { D.renderSkeleton(pred.skeleton); D.setMode("focus"); }
    else if (pred && pred.intent === "brain") D.setMode("brain");
  }

  D.ask = async (text, lang, heard = {}) => {
    D.busy = true; D.lastInteraction = Date.now();
    thinking(true);
    if (!heard.followup) {
      $("you").textContent = `« ${text} »`;
      $("say").textContent = "…";
    }
    try {
      if (!heard.followup) await predict(text);
      const r = await fetch("/api/assistant/chat", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, lang, ...heard }) });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || "Errore");
      if (d.ignored) { D.lastVoice = false; D.Ear.followup(12); return; }
      show(text, d);
    } catch (err) {
      D.setMode("face");
      $("say").textContent = `⚠ ${err.message}`;
      if (D.avatar && D.avatar.express) D.avatar.express("sad", 2.6);
    } finally {
      D.busy = false; D.lastInteraction = Date.now();
      thinking(false);
    }
  };

  D.startChat = () => {
    $("in").addEventListener("input", () => D.pingActivity(false));
    $("in").addEventListener("keydown", (e) => {
      if (e.key !== "Enter") return;
      const text = $("in").value.trim(); if (!text || D.busy) return;
      $("in").value = ""; D.ask(text);
    });
    if (!D.local) {
      fetch(`${location.protocol}//${location.hostname}:8080/api/auth/me`, { credentials: "include" }).then((r) => {
        if (!r.ok) $("note").textContent = "Accesso remoto in sola visione — per parlare con Jarvis accedi al pannello :8080";
      }).catch(() => {});
    }
  };
})();
