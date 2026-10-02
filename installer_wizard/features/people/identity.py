from state import store

from features.people import people


def owner() -> dict | None:
    profiles = people.all_profiles(light=True)
    return next((p for p in profiles if p.get("role") == "owner"), profiles[0] if len(profiles) == 1 else None)


def present() -> list[dict]:
    slugs = list(dict.fromkeys(p["slug"] for p in store.presence.get("people", []) if p.get("known")))
    return [p for p in (people.load(s) for s in slugs) if p]


def strangers() -> int:
    return sum(1 for p in store.presence.get("people", []) if not p.get("known"))


def current(voice: str = "") -> dict | None:
    heard = people.load(voice) if voice else None
    if heard:
        return heard
    here = present()
    return here[0] if here else owner()


def alone(profile: dict) -> bool:
    return strangers() == 0 and all(p["slug"] == profile["slug"] for p in present())


def first_name(profile: dict) -> str:
    return profile.get("nickname") or profile.get("first_name") or (profile.get("name") or "").split(" ")[0]
