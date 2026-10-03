from typing import Any, List, Mapping

from features.presentation.infrastructure.wikimedia import MIN_WIDTH, Candidate

API = "https://api.openverse.org/v1/images/"
THUMB_PREFIX = "https://api.openverse.org/v1/images/"
PAGE_SIZE = 10
_LICENSES = {"cc0": "CC0", "pdm": "Public domain", "by": "CC BY", "by-sa": "CC BY-SA"}


def search_params(query: str) -> Mapping[str, str]:
    return {"q": query, "license": ",".join(_LICENSES), "page_size": str(PAGE_SIZE), "mature": "false",
            "category": "photograph,illustration"}


def candidates(payload: Mapping[str, Any]) -> List[Candidate]:
    out: List[Candidate] = []
    for item in payload.get("results") or []:
        code = str(item.get("license") or "").lower()
        thumb = str(item.get("thumbnail") or "")
        if code not in _LICENSES or not thumb.startswith(THUMB_PREFIX) or int(item.get("width") or 0) < MIN_WIDTH:
            continue
        version = str(item.get("license_version") or "").strip()
        label = _LICENSES[code] + (f" {version}" if version and code in ("by", "by-sa") else "")
        out.append(Candidate(thumb, str(item.get("foreign_landing_url") or ""), " ".join(str(item.get("creator") or "").split())[:80],
                             label, int(item.get("width") or 0), int(item.get("height") or 0), str(item.get("title") or "")[:80]))
    return out
