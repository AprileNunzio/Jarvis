(() => {
  const D = window.JarvisDisplay;
  const MUSIC = new Set(["music", "spotify", "karaoke"]);
  let floor = 0.02, peak = 0.1;

  const idle = () => !D.busy && !D.isSpeaking() && D.mode === "face" && !(D.Enroll && D.Enroll.active);
  const musicOn = () => (window.JarvisDesk && JarvisDesk.all || []).some((w) => MUSIC.has(w.id));
  const night = () => { const h = new Date().getHours(); return h >= 23 || h < 6; };

  function level(v) {
    const avatar = D.avatar;
    if (!avatar || !avatar.setGroove) return;
    floor = floor * 0.995 + v * 0.005;
    peak = Math.max(v, peak * 0.985);
    if (!musicOn() || !idle()) return;
    const beat = Math.max(0, (v - floor) / Math.max(0.02, peak - floor));
    avatar.setGroove(0.35 + beat * 0.65);
  }

  function tick() {
    const avatar = D.avatar;
    if (!avatar || !avatar.setCalm) return;
    avatar.setCalm(night() && idle() && !musicOn() && Date.now() - D.lastInteraction > 120000);
    document.body.classList.toggle("dancing", musicOn() && idle());
  }

  function joy() { if (D.avatar && D.avatar.burst) D.avatar.burst(); }

  D.Mood = { level, joy };
  setInterval(tick, 1000);
})();
