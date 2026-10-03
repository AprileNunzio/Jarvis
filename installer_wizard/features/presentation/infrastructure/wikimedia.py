import html
import re
from dataclasses import dataclass
from typing import Any, List, Mapping

API = "https://commons.wikimedia.org/w/api.php"
SEARCH_LIMIT = 12
MIN_WIDTH = 300
THUMB_WIDTH = 900
_MIMES = ("image/jpeg", "image/png", "image/webp", "image/svg+xml", "image/gif")
_FREE = re.compile(r"^(cc0|public domain|pd[- ]|pd$|cc[- ]by(?![- ]n)(?:[- ]sa)?\b)", re.I)
_RESTRICTED = re.compile(r"\b(nc|nd|non-?commercial|no-?derivs?)\b", re.I)
_TAGS = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class Candidate:
    thumb: str
    page: str
    author: str
    license: str
    width: int
    height: int
    title: str


def search_params(query: str) -> Mapping[str, str]:
    return {
        "action": "query", "format": "json", "generator": "search", "gsrsearch": f"{query} filetype:bitmap|drawing",
        "gsrnamespace": "6", "gsrlimit": str(SEARCH_LIMIT), "prop": "imageinfo",
        "iiprop": "url|size|mime|extmetadata", "iiurlwidth": str(THUMB_WIDTH),
    }


def _plain(value: Any, limit: int = 120) -> str:
    return " ".join(html.unescape(_TAGS.sub("", str(value or ""))).split())[:limit]


def is_free(license_name: str) -> bool:
    return bool(_FREE.match(license_name.strip())) and not _RESTRICTED.search(license_name)


def candidates(payload: Mapping[str, Any]) -> List[Candidate]:
    pages = sorted((payload.get("query") or {}).get("pages", {}).values(), key=lambda p: p.get("index", 0))
    out: List[Candidate] = []
    for page in pages:
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata") or {}
        license_name = _plain((meta.get("LicenseShortName") or {}).get("value"), 40)
        thumb = str(info.get("thumburl") or "")
        if info.get("mime") not in _MIMES or not thumb.startswith("https://upload.wikimedia.org/"):
            continue
        if not is_free(license_name) or int(info.get("width") or 0) < MIN_WIDTH:
            continue
        out.append(Candidate(thumb, str(info.get("descriptionshorturl") or info.get("descriptionurl") or ""),
                             _plain((meta.get("Artist") or {}).get("value"), 80), license_name,
                             int(info.get("thumbwidth") or info.get("width") or 0), int(info.get("thumbheight") or 0),
                             _plain(page.get("title", "")).removeprefix("File:")))
    return out
