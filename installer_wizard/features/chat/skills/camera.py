import re

_OFF = re.compile(r"\b(chiudi|disattiva|spegni|nascondi|togli|ferma|basta|esci da(?:lla)?|torna indietro)\b", re.I)


def wants_camera_off(text: str) -> bool:
    return bool(_OFF.search(text))


def camera_skill(text: str) -> tuple[str, dict]:
    if wants_camera_off(text):
        return "Webcam chiusa, signore.", {"mode": "face", "camera": "off"}
    return ("Webcam attiva. Mi sposto in un angolo: può trascinarmi o pizzicarmi con la mano, "
            "e usare la barra in basso per specchio, zoom, scatto e disegno."), {"mode": "face", "camera": "on"}
