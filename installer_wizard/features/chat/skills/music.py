def music_skill() -> tuple[str, dict]:
    from features.music.music import speech_for, watcher
    np_ = watcher.current()
    if not np_:
        return speech_for(np_), {"mode": "face"}
    kv = {k: v for k, v in (("Artista", np_.get("artist")), ("Album", np_.get("album")), ("Anno", np_.get("year")),
                            ("Genere", np_.get("genre")), ("Etichetta", np_.get("label"))) if v}
    panels = [{"type": "image", "title": np_["title"], "src": np_["cover"]}] if np_.get("cover") else []
    panels.append({"type": "kv", "title": "Dettagli", "data": kv})
    if (np_.get("bio") or {}).get("text"):
        panels.append({"type": "text", "title": np_.get("artist") or "Artista", "body": np_["bio"]["text"]})
    return speech_for(np_), {"mode": "focus", "title": f"♪ {np_['title']}", "subtitle": np_.get("artist") or "",
                             "panels": panels}
