SOUNDS = {
    "wake": ("Attivazione", "richieste"),
    "request": ("Richiesta ricevuta", "richieste"),
    "thinking": ("Sta pensando (ciclo)", "attesa"),
    "working": ("Sta elaborando (ciclo)", "attesa"),
    "done": ("Fatto", "richieste"),
    "error": ("Errore", "richieste"),
    "notify": ("Notifica", "notifiche"),
    "reminder": ("Promemoria", "notifiche"),
    "alert": ("Allarme", "allarmi"),
    "doorbell": ("Campanello", "allarmi"),
    "success": ("Successo", "effetti"),
    "scan": ("Scansione", "effetti"),
    "powerup": ("Accensione", "effetti"),
    "powerdown": ("Spegnimento", "effetti"),
    "whoosh": ("Passaggio", "effetti"),
    "click": ("Clic", "effetti"),
}
AMBIENTS = {"none": "Nessuno", "reactor": "Reattore", "space": "Spazio profondo", "rain": "Pioggia", "ocean": "Onde",
            "lab": "Laboratorio"}
URGENT = {"alert", "doorbell"}
CATEGORY = {k: v[1] for k, v in SOUNDS.items()}


def names() -> list[str]:
    return list(SOUNDS)


def listing() -> list[dict]:
    return [{"name": k, "label": v[0], "category": v[1], "urgent": k in URGENT} for k, v in SOUNDS.items()]


class _Sounds:
    @staticmethod
    def names() -> list[str]:
        return names()


sounds = _Sounds()
