import re
import unicodedata

_UNITS = ["zero", "uno", "due", "tre", "quattro", "cinque", "sei", "sette", "otto", "nove"]
_TEENS = ["dieci", "undici", "dodici", "tredici", "quattordici", "quindici", "sedici", "diciassette", "diciotto",
          "diciannove"]
_TENS = {"venti": 20, "trenta": 30, "quaranta": 40, "cinquanta": 50, "sessanta": 60, "settanta": 70,
         "ottanta": 80, "novanta": 90}
NUMBER_WORDS: dict[str, int] = {w: 10 + i for i, w in enumerate(_TEENS)} | {"cento": 100}
for _w, _v in _TENS.items():
    NUMBER_WORDS[_w] = _v
    for _u in range(1, 10):
        _word = (_w[:-1] if _UNITS[_u] in ("uno", "otto") else _w) + _UNITS[_u]
        NUMBER_WORDS[_word] = _v + _u
for _u in (2, 3, 4, 5, 7, 8, 9):
    NUMBER_WORDS[_UNITS[_u]] = _u

STOPWORDS = set("""il lo la i gli le l un uno una un di del dello della dei degli delle d a al allo alla ai agli
alle in nel nello nella nei negli nelle su sul sullo sulla sui sugli sulle con col per tra fra e ed o che mi ti ci
si me te ce ne per favore perfavore jarvis puoi potresti vorrei voglio dammi fammi anche ora subito adesso please
grazie tutto tutte tutti tutta mio mia miei mie tuo tua suo sua nostro nostra quello quella quelli quelle questo
questa questi queste da dal dallo dalla dai dagli dalle""".split())


def norm(text: str) -> str:
    t = unicodedata.normalize("NFKD", str(text).lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"(\d),(\d)", r"\1.\2", t)
    t = re.sub(r"[^a-z0-9%°. ]+", " ", t)
    t = re.sub(r"(?<!\d)\.|\.(?!\d)", " ", t)
    words = [str(NUMBER_WORDS[w]) if w in NUMBER_WORDS else w for w in t.split()]
    return " ".join(words)


def stem(word: str) -> str:
    if len(word) > 3 and word[-1] in "aeiou":
        word = word[:-1]
        if word.endswith("h") and len(word) > 3:
            word = word[:-1]
    return word


def phrase_stems(text: str) -> tuple[str, ...]:
    return tuple(stem(w) for w in norm(text).split() if w not in STOPWORDS)


def find_phrase(tokens: list[str], phrase: tuple[str, ...]) -> int:
    if not phrase:
        return -1
    content = [(i, t) for i, t in enumerate(tokens) if t not in _STOP_STEMS]
    n = len(phrase)
    for k in range(len(content) - n + 1):
        if all(content[k + j][1] == phrase[j] for j in range(n)):
            return content[k][0]
    return -1


_STOP_STEMS = {stem(w) for w in STOPWORDS}
