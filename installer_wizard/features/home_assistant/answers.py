from features.home_assistant.constants import DOMAIN_PLURAL, FEMININE, PROTO_LABEL, STATE_IT
from features.home_assistant.helpers import ago, join_words


class HomeAnswers:
    def answer(self, q: dict) -> tuple[str, dict]:
        topic = q["topic"]
        return getattr(self, f"_a_{topic}")(q)

    def _rooms_for(self, q: dict) -> list[str]:
        if q.get("area_ids"):
            return q["area_ids"]
        return sorted(self.areas, key=lambda a: self.areas[a]["name"])

    def _a_presence(self, q: dict) -> tuple[str, dict]:
        rooms = [self.room_status(a) for a in self._rooms_for(q)]
        if q.get("area_ids"):
            parts = []
            for r in rooms:
                if not r["has_sensors"] and not r["occupied"]:
                    parts.append(f"in {r['name']} non ci sono sensori di movimento o presenza")
                elif r["occupied"]:
                    parts.append(f"in {r['name']} c'è qualcuno: {r['label']}")
                else:
                    parts.append(f"in {r['name']} non c'è nessuno" + (f", ultimo movimento {ago(r['last_motion'])}"
                                                                      if r["last_motion"] else ""))
            speech = join_words(parts)
            speech = speech[:1].upper() + speech[1:] + "."
        else:
            occ = [r["name"] for r in rooms if r["occupied"]]
            speech = (f"C'è movimento o presenza in {join_words(occ)}." if occ
                      else "In questo momento non rilevo movimento né presenza in nessuna stanza.")
            persons = [p["name"] for p in self.people_home() if p["home"]]
            if persons:
                speech += f" A casa risulta{'no' if len(persons) > 1 else ''} {join_words(persons)}."
        items = [{"label": r["name"], "value": r["label"], "status": "ok" if r["occupied"] else ""} for r in rooms
                 if r["has_sensors"] or r["occupied"]]
        return speech, {"mode": "focus", "title": "Presenza in casa", "subtitle": "Movimento e presenza per stanza",
                        "panels": [{"type": "list", "title": "Stanze", "items": items or
                                    [{"label": "Nessun sensore di presenza", "value": "", "status": ""}]}]}

    def _a_who_home(self, q: dict) -> tuple[str, dict]:
        people = self.people_home()
        home_ = [p["name"] for p in people if p["home"]]
        away = [p for p in people if not p["home"]]
        if not people:
            speech = "In Home Assistant non ci sono persone configurate: posso dirti solo in quali stanze c'è movimento."
            occ = [self.areas[a]["name"] for a in self.occupied]
            if occ:
                speech += f" Adesso c'è movimento in {join_words(occ)}."
            return speech, {"mode": "face"}
        speech = (f"A casa c'è {join_words(home_)}." if len(home_) == 1 else f"A casa ci sono {join_words(home_)}." if home_
                  else "Non risulta nessuno a casa.")
        if away:
            speech += " " + join_words([f"{p['name']} è {STATE_IT.get(p['state'], p['state'])}" for p in away]) + "."
        items = [{"label": p["name"], "value": f"{STATE_IT.get(p['state'], p['state'])} da {ago(p['since'])}",
                  "status": "ok" if p["home"] else ""} for p in people]
        return speech, {"mode": "focus", "title": "Chi è in casa", "subtitle": "Persone di Home Assistant",
                        "panels": [{"type": "list", "title": "Persone", "items": items}]}

    def _a_last_motion(self, q: dict) -> tuple[str, dict]:
        rooms = q.get("area_ids") or list(self.last_motion)
        parts = []
        for aid in rooms:
            ts = self.last_motion.get(aid)
            name = self.areas.get(aid, {}).get("name", aid)
            parts.append(f"in {name} {ago(ts)}" if ts else f"in {name} nessun movimento registrato")
        if not parts:
            return "Non ho ancora registrato movimenti.", {"mode": "face"}
        return "Ultimo movimento: " + join_words(parts[:6]) + ".", {"mode": "face"}

    def _a_climate_read(self, q: dict) -> tuple[str, dict]:
        ids = q.get("area_ids") or ([self.catalog.default_area] if self.catalog.default_area else self._rooms_for(q))
        rooms = [r for r in (self.room_status(a) for a in ids) if r["temperature"] is not None or r["humidity"] is not None]
        if not rooms:
            return "Non ho sensori di temperatura in quella stanza.", {"mode": "face"}
        parts = [f"in {r['name']} ci sono {str(r['temperature']).rstrip('0').rstrip('.')} gradi" if r["temperature"] is not None
                 else f"in {r['name']}" for r in rooms[:6]]
        for i, r in enumerate(rooms[:6]):
            if r["humidity"] is not None:
                parts[i] += f" con umidità al {round(r['humidity'])}%"
        items = [{"label": r["name"], "value": " · ".join(x for x in (
            f"{r['temperature']} °C" if r["temperature"] is not None else "",
            f"{round(r['humidity'])}%" if r["humidity"] is not None else "") if x), "status": ""} for r in rooms]
        joined = join_words(parts)
        return (joined[:1].upper() + joined[1:] + ".",
                {"mode": "focus" if len(rooms) > 1 else "face", "title": "Clima in casa", "subtitle": "Sensori delle stanze",
                 "panels": [{"type": "list", "title": "Stanze", "items": items}]})

    def _a_open(self, q: dict) -> tuple[str, dict]:
        rooms = [self.room_status(a) for a in self._rooms_for(q)]
        opened = [(r["name"], n) for r in rooms for n in r["open"]]
        covers = [e["name"] for eid, e in self.entities.items() if e["domain"] == "cover" and e.get("controllable")
                  and (not q.get("area_ids") or e.get("area_id") in q["area_ids"])
                  and (self.states.get(eid) or {}).get("state") == "open"]
        if not opened and not covers:
            return "È tutto chiuso: nessuna porta o finestra risulta aperta.", {"mode": "face"}
        speech = ""
        if opened:
            speech = f"Risulta aperto: {join_words([n for _, n in opened])}."
        if covers:
            speech += f" Tapparelle o tende aperte: {join_words(covers[:6])}."
        return speech.strip(), {"mode": "focus", "title": "Aperture", "subtitle": "Porte, finestre e tapparelle",
                                "panels": [{"type": "list", "title": "Aperti",
                                            "items": [{"label": n, "value": room, "status": "warn"} for room, n in opened]
                                            + [{"label": c, "value": "tapparella", "status": ""} for c in covers]}]}

    def _a_state(self, q: dict) -> tuple[str, dict]:
        t = " ".join(q.get("domains") or [])
        ents = [self.entities[x] for x in q.get("entities") or [] if x in self.entities]
        want = None
        if q.get("domains") and not ents:
            ents = [e for e in self.entities.values() if e.get("controllable") and e["domain"] in q["domains"]
                    and (not q.get("area_ids") or e.get("area_id") in q["area_ids"])]
        if q.get("domains") and not q.get("entities") and len(ents) > 1:
            want = "on" if "light" in t or "switch" in t or "media_player" in t else "open" if "cover" in t else None
        if want:
            on = [e for e in ents if (self.states.get(e["entity_id"]) or {}).get("state") == want]
            label = DOMAIN_PLURAL.get(q["domains"][0], "dispositivi")
            speech = (f"Sono {'accese' if want == 'on' else 'aperte'} {len(on)} {label} su {len(ents)}: "
                      f"{join_words([e['name'] for e in on[:8]])}." if on else
                      f"Nessuna delle {len(ents)} {label} è {'accesa' if want == 'on' else 'aperta'}.")
        else:
            speech = " ".join(f"{e['name']}: {self._state_text(e)}." for e in ents[:6]) or "Non trovo quel dispositivo."
        items = [{"label": e["name"], "value": self._state_text(e),
                  "status": "ok" if (self.states.get(e["entity_id"]) or {}).get("state") in ("on", "open", "playing") else ""}
                 for e in ents[:40]]
        return speech, {"mode": "focus" if len(ents) > 1 else "face", "title": "Stato dei dispositivi",
                        "subtitle": "Da Home Assistant, in tempo reale", "panels": [{"type": "list", "title": "Dispositivi", "items": items}]}

    def _state_text(self, e: dict) -> str:
        st = self.states.get(e["entity_id"]) or {}
        s, a = st.get("state", "unknown"), st.get("attrs", {})
        text = STATE_IT.get(s, s)
        if e["domain"] in FEMININE and text.split(" ")[0].endswith("o"):
            first, _, rest = text.partition(" ")
            text = (first[:-1] + "a " + rest).strip()
        if e["domain"] == "light" and s == "on" and a.get("brightness"):
            text += f" al {round(a['brightness'] / 2.55)}%"
        if e["domain"] == "cover" and a.get("current_position") is not None and s not in ("closed",):
            text += f" al {a['current_position']}%"
        if e["domain"] == "climate":
            if a.get("current_temperature") is not None:
                text += f", {a['current_temperature']} gradi"
            if a.get("temperature") is not None:
                text += f" (obiettivo {a['temperature']})"
        if e["domain"] == "sensor" and a.get("unit_of_measurement"):
            text += f" {a['unit_of_measurement']}"
        return text

    def _a_inventory(self, q: dict) -> tuple[str, dict]:
        devs = [d for d in self.devices.values() if not d["disabled"] and d["protocol"] != "virtual"]
        if q.get("area_ids"):
            devs = [d for d in devs if d["area_id"] in q["area_ids"]]
        if q.get("protocol"):
            p = q["protocol"]
            devs = [d for d in devs if d["protocol"] == p or (p == "matter" and d["matter"])]
        where = f" in {join_words([self.areas[a]['name'] for a in q['area_ids'] if a in self.areas])}" if q.get("area_ids") else ""
        label = f" {PROTO_LABEL.get(q['protocol'], q['protocol'])}" if q.get("protocol") else ""
        if not devs:
            return f"Non ho trovato dispositivi{label}{where}.", {"mode": "face"}
        counts: dict = {}
        for d in devs:
            counts[d["protocol"]] = counts.get(d["protocol"], 0) + 1
        speech = f"Ho {len(devs)} dispositiv{'o' if len(devs) == 1 else 'i'}{label}{where}"
        if not q.get("protocol") and len(counts) > 1:
            speech += ": " + join_words([f"{n} {PROTO_LABEL.get(p, p)}" for p, n in sorted(counts.items(), key=lambda x: -x[1])[:6]])
        speech += "."
        items = [{"label": d["name"], "value": " · ".join(x for x in (
            self.areas.get(d["area_id"] or "", {}).get("name", ""), f"{d['manufacturer']} {d['model']}".strip(),
            PROTO_LABEL.get(d["protocol"], d["protocol"]) + (" (Matter)" if d["matter"] and d["protocol"] != "matter" else "")) if x),
            "status": ""} for d in sorted(devs, key=lambda d: d["name"])[:60]]
        stats = [{"label": PROTO_LABEL.get(p, p), "value": str(n), "percent": round(n * 100 / len(devs))}
                 for p, n in sorted(counts.items(), key=lambda x: -x[1])]
        return speech, {"mode": "focus", "title": f"Dispositivi{label}{where}", "subtitle": "Studiati da Home Assistant",
                        "panels": [{"type": "stats", "title": "Per protocollo", "items": stats},
                                   {"type": "list", "title": f"Dispositivi ({len(devs)})", "items": items}]}

    def _a_home_summary(self, q: dict) -> tuple[str, dict]:
        rooms = [self.room_status(a) for a in self.areas]
        occ = [r["name"] for r in rooms if r["occupied"]]
        lights = sum(r["lights_on"] for r in rooms)
        opened = [n for r in rooms for n in r["open"]]
        line = self.summary_line()
        speech = line[:1].upper() + line[1:] + ". "
        speech += (f"Adesso c'è qualcuno in {join_words(occ)}. " if occ else "Nessun movimento in casa in questo momento. ")
        speech += (f"{lights} luc{'e accesa' if lights == 1 else 'i accese'}. " if lights else "Luci tutte spente. ")
        if opened:
            speech += f"Aperti: {join_words(opened[:5])}."
        items = [{"label": r["name"], "value": " · ".join(x for x in (
            r["label"], f"{r['temperature']} °C" if r["temperature"] is not None else "",
            f"{r['lights_on']} luci accese" if r["lights_on"] else "") if x), "status": "ok" if r["occupied"] else ""}
                 for r in sorted(rooms, key=lambda r: r["name"])]
        return speech.strip(), {"mode": "focus", "title": self.ha_name or "La casa", "subtitle": "Situazione in tempo reale",
                                "panels": [{"type": "stats", "title": "Protocolli", "items": self.protocol_stats()},
                                           {"type": "list", "title": "Stanze", "items": items}]}
