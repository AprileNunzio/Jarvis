(() => {
  const A = window.JarvisAdmin, { $ } = A;

  function bubble(text, who, meta) {
    const d = document.createElement("div"); d.className = `msg ${who}`; d.textContent = text;
    if (meta) { const m = document.createElement("div"); m.className = "meta"; m.textContent = meta; d.appendChild(m); }
    $("chat").appendChild(d); $("chat").scrollTop = $("chat").scrollHeight; return d;
  }

  function init() {
    $("chat-form").addEventListener("submit", async (e) => {
      e.preventDefault(); const text = $("chat-in").value.trim(); if (!text) return;
      $("chat-in").value = ""; bubble(text, "me"); const wait = bubble("…", "jv");
      try { const r = await A.api("POST", "/api/assistant/chat", { text }); wait.remove(); bubble(r.reply, "jv", `${r.agent || ""} · ${(r.elapsed_ms / 1000).toFixed(1)} s`); }
      catch (err) { wait.remove(); bubble(`⚠ ${err.message}`, "jv"); }
    });
  }

  A.tab("chat", { title: "Parla con Jarvis", init });
})();
