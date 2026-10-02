import time

from state import store

ALIVE = 30
MAIN_CAP = 2
BIG = ("l", "full")


class Screens:
    def __init__(self) -> None:
        self.seen: dict[int, dict] = {}
        self.last: list[int] = []
        self.clients: dict[str, dict] = {}

    def perf(self, client: str, n: int, local: bool, w: int, h: int, text: str) -> None:
        now = time.time()
        self.clients[f"{client}#{n}"] = {"client": "questo server" if local else client, "screen": n,
                                         "size": f"{w}x{h}", "perf": text, "at": now}
        self.clients = {k: v for k, v in self.clients.items() if now - v["at"] < ALIVE * 4}
        store.displays = [{k: v for k, v in c.items() if k != "at"} for c in self.clients.values()]

    def hello(self, n: int, x: int, w: int, h: int, local: bool = False, ear: str = "") -> bool:
        known = set(s["n"] for s in self.active())
        previous = self.seen.get(n, {})
        if previous.get("local") and not local and time.time() - previous.get("at", 0) < ALIVE:
            return False
        self.seen[n] = {"n": n, "x": x, "w": w, "h": h, "local": local, "ear": ear, "at": time.time()}
        store.screens = self.active()
        return n not in known

    def active(self) -> list[dict]:
        now = time.time()
        live = [{k: v for k, v in s.items() if k != "at"} for s in self.seen.values() if now - s["at"] < ALIVE]
        return sorted(live, key=lambda s: (s["x"], s["n"]))

    def numbers(self) -> list[int]:
        return [s["n"] for s in self.active()] or [0]

    def changed(self) -> bool:
        return self.numbers() != self.last

    def assign(self, items: list[dict], wanted: dict) -> list[dict]:
        screens = self.last = self.numbers()
        main = 0 if 0 in screens else screens[0]
        others = [n for n in screens if n != main]
        load = {n: 0 for n in screens}
        store.screens = self.active()

        def lightest() -> int:
            return min(others, key=lambda n: (load[n], others.index(n)))

        for it in items:
            if it.get("takeover"):
                it["screen"] = -1
                continue
            if it.get("overlay"):
                it["screen"] = main
                continue
            pref = wanted.get(it["id"])
            if pref in load:
                it["screen"] = pref
            elif not others:
                it["screen"] = main
            elif it.get("size") in BIG or load[main] >= MAIN_CAP:
                it["screen"] = lightest()
            else:
                it["screen"] = main
            load[it["screen"]] += 1
        return items


screens = Screens()
