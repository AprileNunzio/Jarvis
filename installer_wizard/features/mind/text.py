import re
import unicodedata

WORD = re.compile(r"[a-zà-ÿ0-9]{3,}", re.I)
STOP = {
    "che", "chi", "con", "per", "una", "uno", "del", "della", "dello", "dei", "degli", "delle", "nel", "nella",
    "nei", "nelle", "sul", "sulla", "sui", "dal", "dalla", "dai", "gli", "le", "lo", "la", "il", "non", "come",
    "cosa", "sono", "sei", "era", "ero", "hai", "ho", "abbiamo", "avete", "hanno", "questo", "questa", "quello",
    "quella", "anche", "pero", "poi", "piu", "molto", "tanto", "tutto", "tutti", "mio", "mia", "miei", "mie",
    "tuo", "tua", "suo", "sua", "nostro", "nostra", "jarvis", "allora", "quindi", "quando", "dove", "perche",
    "quale", "quali", "qui", "qua", "oggi", "adesso", "ora", "sempre", "mai", "fare", "fai", "faccio", "essere",
    "stato", "stata", "dire", "dimmi", "sai", "puoi", "vorrei", "voglio", "the", "and", "you", "are", "what",
}


def plain(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text.lower()) if unicodedata.category(c) != "Mn")


def words(text: str) -> set:
    return {w[:6] for w in WORD.findall(plain(text)) if w not in STOP}


def overlap(a: str, b: str) -> float:
    wa, wb = words(a), words(b)
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / min(len(wa), len(wb))


def jaccard(a: str, b: str) -> float:
    wa, wb = words(a), words(b)
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)
