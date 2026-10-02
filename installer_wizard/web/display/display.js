(() => {
  const D = window.JarvisDisplay, { $, fmt } = D;
  let homeSent = 0;

  function goHome() {
    D.setMode("face");
    if (Date.now() - homeSent < 5000) return;
    homeSent = Date.now();
    fetch("/api/desk/idle", { method: "POST" }).catch(() => {});
  }

  function tick() {
    const d = new Date();
    $("clock").textContent = d.toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit" });
    $("date").textContent = fmt.date(d);
    const h = d.getHours();
    const g = h < 6 ? "Buonanotte" : h < 13 ? "Buongiorno" : h < 18 ? "Buon pomeriggio" : "Buonasera";
    const who = D.presentNames.length ? D.presentNames.join(" e ") : D.userName;
    if ($("greet")) $("greet").textContent = `${g}${who ? ", " + who : ""}.`;
    const quiet = !D.busy && !D.isSpeaking() && Date.now() - D.lastInteraction;
    if (D.mode !== "face" && quiet > (D.mode === "brain" ? 90000 : 60000)) goHome();
    else if (D.mode === "face" && quiet > 60000 && (JarvisDesk.all || []).some((w) => w.intent)) goHome();
    if (quiet > 60000 && !rested) rest();
    else if (quiet && quiet < 60000) rested = false;
  }

  let rested = false;

  function rest() {
    rested = true;
    $("you").textContent = "";
    $("focus-say").textContent = "";
    $("stage-body").innerHTML = "";
    $("stage-title").textContent = "";
    $("stage-sub").textContent = "";
    if (!$("greet")) $("say").innerHTML = '<span class="greet" id="greet"></span>';
  }

  let presenceSig = "";

  function renderPresence(pr) {
    const people = (pr && pr.status === "ok" && pr.people) || [];
    const names = [...new Set(people.filter((p) => p.known).map((p) => p.name))];
    const near = new Set(people.filter((p) => p.known && p.near).map((p) => p.name));
    const strangers = people.filter((p) => !p.known).length;
    D.presentNames = names;
    D.Ear.presence(people.length === 1 && people[0].known ? people[0].slug : null);
    const look = people.find((p) => p.known && p.near) || people.find((p) => p.facing) || people[0];
    if (look && look.gaze && D.avatar && D.avatar.setGaze) D.avatar.setGaze(look.gaze.x, look.gaze.y);
    if (D.avatar && D.avatar.express) {
      const prev = D._nearSet || new Set();
      if ([...near].some((n) => !prev.has(n))) D.avatar.express("smile", 2.6);
      D._nearSet = new Set(near);
    }
    const sig = JSON.stringify([names, [...near], strangers]);
    if (sig === presenceSig) return;
    presenceSig = sig;
    const box = $("presence");
    if (!names.length && !strangers) { box.classList.remove("show"); return; }
    box.innerHTML = names.map((n) => `<span class="who ${near.has(n) ? "near" : ""}"><i></i>${fmt.esc(n)}</span>`).join("")
      + (strangers ? `<span class="who unknown"><i></i>${strangers === 1 ? "Ospite" : `${strangers} ospiti`}</span>` : "");
    box.classList.add("show");
  }

  function handleGreeting(g) {
    if (!g || !g.id) return;
    if (D.lastGreeting === null) { D.lastGreeting = g.id; return; }
    if (g.id === D.lastGreeting) return;
    D.lastGreeting = g.id;
    D.lastInteraction = Date.now();
    D.Mood.joy();
    if (g.names && g.names.length) {
      $("welcome-name").textContent = [...new Set(g.names)].join(" · ");
      $("welcome-sub").textContent = "Identità riconosciuta";
      $("welcome").classList.add("show");
      setTimeout(() => $("welcome").classList.remove("show"), 5000);
    }
    if (D.mode !== "brain") D.setMode("face");
    D.typeInto($("say"), g.text);
    if (!D.busy) D.speak(g.text);
  }

  function sendPosition() {
    if (!navigator.geolocation || !D.local) return;
    navigator.geolocation.getCurrentPosition(
      (p) => fetch("/api/location/browser", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ lat: p.coords.latitude, lon: p.coords.longitude, accuracy: p.coords.accuracy }) }).catch(() => {}),
      (err) => console.info("Posizione del display non disponibile:", err.message),
      { enableHighAccuracy: true, timeout: 30000, maximumAge: 10 * 60000 });
  }

  function onState(s) {
    renderPresence(s.presence);
    handleGreeting(s.greeting);
    D.onAudioRev(s.audio_rev);
    D.Ear.resetFrom(s.mic_reset);
    JarvisDesk.setScreens(s.screens);
    JarvisDesk.render(s.desk || []);
    if (D.Sounds) { D.Sounds.update(s.sounds); D.Sounds.desk(s.desk); }
    if (!["READY", "DEGRADED"].includes(s.phase)) { location.reload(); return; }
    if (s.asset_version && window.JARVIS_ASSET_V && s.asset_version !== window.JARVIS_ASSET_V) {
      D.staleSince = D.staleSince || Date.now();
      if ((!D.busy && !D.isSpeaking()) || Date.now() - D.staleSince > 120000) { location.reload(); return; }
    }
    const node = new URLSearchParams(location.search).get("node");
    const face = (node && s.node_faces && s.node_faces[node]) || s.face;
    if (face && window.JARVIS_FACE && JSON.stringify(face) !== JSON.stringify(window.JARVIS_FACE)) { location.reload(); return; }
    D.userName = s.user_name || "";
    $("banner").textContent = s.message;
    $("banner").classList.toggle("show", s.phase === "DEGRADED");
    if (D.avatar) D.avatar.setTint(s.phase === "DEGRADED" ? "#ffb547" : D.busy ? "#b36bff" : D.tint || "#29e0ff");
    $("chips").innerHTML = Object.values(s.components || {}).filter((c) => c.status && c.status !== "ok")
      .map((c) => `<span><i class="dot ${c.status}"></i>${fmt.esc(c.label)}</span>`).join("");

    if (s.holo_action && D.avatar) holoAction(s.holo_action);
  }

  function holoAction(a) {
    const av = D.avatar, call = (fn, ...args) => typeof av[fn] === "function" && av[fn](...args);
    if (a.express) call("express", a.express, a.seconds || 3);
    if (a.play) call("play", a.play);
    if (a.stop) call("stop", a.stop);
    if (a.shot) call("shot", a.shot, a.seconds || 12);
    if (a.dance !== undefined) call("dance", a.dance);
    if (a.sing !== undefined) call("sing", a.sing);
    if (a.accessory) call("toggleAccessory", a.accessory.name, a.accessory.state);
    if (a.tint && /^#[0-9a-f]{6}$/i.test(a.tint)) { D.tint = a.tint; call("setTint", a.tint); }
  }

  D.startLook();
  D.startAmbient();
  if (D.startSounds) D.startSounds();
  setInterval(tick, 1000); tick();
  ["pointerdown", "keydown", "wheel"].forEach((ev) => addEventListener(ev, () => (D.lastInteraction = Date.now()), { passive: true }));
  D.Ear.start();
  D.startHands();
  D.startAudioPanel();
  D.startVoiceToggle();
  D.startChat();
  setTimeout(sendPosition, 5000);
  setInterval(sendPosition, 30 * 60000);
  JarvisDesk.mount($("desk"), {
    speak: (text) => { if (!D.busy) { D.typeInto($("say"), text); D.speak(text); } },
    onStage: (zone) => { D.stageZone = zone; D.applyStage(); },
    screen: 0, x: +(new URLSearchParams(location.search).get("x") || 0),
  });
  Jarvis.connectState("/api/stream", (s) => (window.jarvisPerf ? window.jarvisPerf.measure("stato", () => onState(s)) : onState(s)), (ok) => $("link").classList.toggle("show", !ok));
  D.startBrain();
})();
