(() => {
  const ICON = { clear: "☀️", partly: "⛅", cloudy: "☁️", fog: "🌫️", drizzle: "🌦️", rain: "🌧️", snow: "❄️", storm: "⛈️" };
  JarvisDesk.register("weather", {
    render(el, d, ctx) {
      const c = d.current || {};
      const days = (d.days || []).slice(1, 5);
      el.innerHTML = `<div class="we-head"><span class="we-loc">${ctx.esc(d.location || "Meteo")}</span></div>
        <div class="we-now"><span class="we-ic">${ICON[c.icon] || "☁️"}</span><span class="we-t">${c.temp ?? "—"}°</span>
          <span class="we-d">${ctx.esc(c.desc || "")}<br><small>percepita ${c.feels ?? "—"}° · vento ${c.wind ?? "—"} km/h</small></span></div>
        <div class="we-days">${days.map((x) => `<div><b>${ctx.esc(x.label.slice(0, 3))}</b><span>${ICON[x.icon] || "☁️"}</span><i>${x.tmax}° <small>${x.tmin}°</small></i>${x.rain >= 40 ? `<em>☂ ${x.rain}%</em>` : ""}</div>`).join("")}</div>`;
    },
  });
})();
