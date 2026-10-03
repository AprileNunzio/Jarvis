(() => {
  const A = window.JarvisAdmin, { fmt } = A;

  const all = () => (A.brain && A.brain.lists() ? A.brain.lists().roles : []);
  const refsOf = (roleId) => new Set((all().find((r) => r.id === roleId)?.entries || []).map((e) => e.name));
  const usedRefs = () => new Set(all().flatMap((r) => r.entries.map((e) => e.name)));
  const byId = (roleId) => all().find((r) => r.id === roleId);

  function addButtons(ref, extraAttrs = "", enabled = true) {
    return all().map((r) => `<button class="btn sm" ${extraAttrs} data-add="${r.id}" ${enabled && !refsOf(r.id).has(ref) ? "" : "disabled"} title="Aggiungi a ${fmt.esc(r.label)}">+ ${r.icon}</button>`).join("");
  }

  function addHint() {
    return all().map((r) => `+ ${r.icon}`).join(" ");
  }

  A.brainRoles = { all, byId, refsOf, usedRefs, addButtons, addHint };
})();
