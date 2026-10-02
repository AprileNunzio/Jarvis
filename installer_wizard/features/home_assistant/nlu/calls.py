from features.home_assistant.nlu.vocabulary import SENSITIVE_COVERS

ON_OFF = {"light", "switch", "fan", "input_boolean", "media_player", "climate", "humidifier", "siren", "automation",
          "remote", "water_heater"}


def build_call(action: str, e: dict, p: dict) -> tuple[str, dict] | None:
    d, caps = e["domain"], e.get("caps", set())
    attrs = e.get("attrs", {})
    pct, temp, num = p.get("percent"), p.get("temperature"), p.get("number")

    if d == "light":
        data = {}
        if action in ("up", "down"):
            return "turn_on", {"brightness_step_pct": 20 if action == "up" else -20}
        if action in ("on", "set") or (action is None and (pct or p.get("rgb") or p.get("kelvin"))):
            if pct is None and num is not None and num <= 100 and action == "set":
                pct = num
            if pct is not None and "brightness" in caps:
                data["brightness_pct"] = max(1, round(pct))
            if p.get("rgb") and "color" in caps:
                data["rgb_color"] = list(p["rgb"])
            elif p.get("kelvin") and "color_temp" in caps:
                data["color_temp_kelvin"] = p["kelvin"]
            return "turn_on", data
        if action == "off":
            return "turn_off", {}
        if action == "toggle":
            return "toggle", {}
        return None

    if d == "cover":
        if action in ("open", "up", "on"):
            return ("set_cover_position", {"position": round(pct)}) if pct is not None and "position" in caps \
                else ("open_cover", {})
        if action in ("close", "down", "off"):
            return "close_cover", {}
        if action == "stop":
            return "stop_cover", {}
        if action == "set" and "position" in caps and (pct is not None or num is not None):
            return "set_cover_position", {"position": round(pct if pct is not None else min(100, num))}
        if action == "toggle":
            return "toggle", {}
        return None

    if d == "climate":
        target = temp if temp is not None else (num if num is not None and 5 <= num <= 35 else None)
        if action in ("up", "down"):
            cur = attrs.get("temperature")
            if cur is None:
                return None
            step = attrs.get("target_temp_step") or 0.5
            return "set_temperature", {"temperature": round(cur + (step * 2 if action == "up" else -step * 2), 1)}
        if target is not None and action in ("set", "on", None):
            data = {"temperature": target}
            if p.get("hvac") and p["hvac"] in (attrs.get("hvac_modes") or []):
                data["hvac_mode"] = p["hvac"]
            return "set_temperature", data
        if p.get("hvac") and action in ("set", "on") and p["hvac"] in (attrs.get("hvac_modes") or [p["hvac"]]):
            return "set_hvac_mode", {"hvac_mode": p["hvac"]}
        if action == "on":
            return "turn_on", {}
        if action == "off":
            return "turn_off", {}
        return None

    if d == "fan":
        if pct is not None and action in ("set", "on", None) and "speed" in caps:
            return "set_percentage", {"percentage": round(pct)}
        if action in ("up", "down") and "speed" in caps:
            return ("increase_speed" if action == "up" else "decrease_speed"), {}
    if d == "media_player":
        if action in ("up", "down"):
            return ("volume_up" if action == "up" else "volume_down"), {}
        if (pct is not None or (num is not None and num <= 100)) and action in ("set", None) and "volume" in caps:
            return "volume_set", {"volume_level": round((pct if pct is not None else num) / 100, 2)}
        return {"play": ("media_play", {}), "pause": ("media_pause", {}), "stop": ("media_stop", {}),
                "next": ("media_next_track", {}), "previous": ("media_previous_track", {}),
                "mute": ("volume_mute", {"is_volume_muted": True}), "on": ("turn_on", {}),
                "off": ("turn_off", {}), "toggle": ("toggle", {})}.get(action)
    if d == "lock":
        return {"lock": ("lock", {}), "close": ("lock", {}), "unlock": ("unlock", {}),
                "open": ("open", {}) if "open" in caps else ("unlock", {})}.get(action)
    if d == "vacuum":
        return {"on": ("start", {}), "clean": ("start", {}), "play": ("start", {}), "pause": ("pause", {}),
                "stop": ("stop", {}), "off": ("return_to_base", {}), "dock": ("return_to_base", {})}.get(action)
    if d == "lawn_mower":
        return {"on": ("start_mowing", {}), "pause": ("pause", {}), "off": ("dock", {}), "dock": ("dock", {}),
                "stop": ("pause", {})}.get(action)
    if d in ("scene",):
        return ("turn_on", {}) if action in ("on", "set", None) else None
    if d == "script":
        return ("turn_on", {}) if action in ("on", "set", None) else ("turn_off", {}) if action in ("off", "stop") else None
    if d in ("button", "input_button"):
        return ("press", {}) if action in ("press", "on", None) else None
    if d == "valve":
        if action in ("open", "on"):
            return "open_valve", {}
        if action in ("close", "off"):
            return "close_valve", {}
        return None
    if d == "alarm_control_panel":
        if action == "disarm" or (action == "off"):
            return "alarm_disarm", {}
        if action in ("arm", "on"):
            return "alarm_arm_away", {}
        return None
    if d in ("number", "input_number") and (pct is not None or num is not None or temp is not None):
        return "set_value", {"value": next(v for v in (num, temp, pct) if v is not None)}
    if d in ON_OFF:
        if action in ("on", "open", "play"):
            return "turn_on", {}
        if action in ("off", "close", "stop"):
            return "turn_off", {}
        if action == "toggle":
            return "toggle", {}
    return None


def is_sensitive(domain: str, service: str, e: dict) -> bool:
    if domain == "lock" and service in ("unlock", "open"):
        return True
    if domain == "alarm_control_panel" and service == "alarm_disarm":
        return True
    if domain == "cover" and e.get("device_class") in SENSITIVE_COVERS and service in ("open_cover", "set_cover_position"):
        return True
    return domain == "valve" and service == "open_valve"
