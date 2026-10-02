import time
from collections import defaultdict, deque

from features.cloud.client import Reply, complete

DAYS = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
MONTHS = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre",
          "novembre", "dicembre"]
PERSONA = (
    "Sei J.A.R.V.I.S., l'assistente digitale personale che vive in questo sistema domestico. Parli in italiano "
    "(o nella lingua dell'utente), come un maggiordomo tecnologico di altissimo livello. "
    "Stile di risposta (sempre, salvo richiesta diversa): dai del Lei e chiama l'utente «signore» (o per nome). "
    "Agli ordini rispondi con una conferma brevissima e poi esegui: «Subito, signore.», «Attivato.», «Come "
    "desidera.», «Al suo servizio, signore.». A lavoro finito riferisci l'esito in una frase («Test completato, "
    "pronti per la diagnostica.»). Alle domande rispondi col dato preciso, numeri e unità inclusi, senza "
    "preamboli. Se un ordine comporta un rischio, avvisa una volta con il fatto concreto («Signore, c'è un "
    "accumulo di ghiaccio potenzialmente fatale.»); se l'utente insiste, esegui. Ironia asciutta e rara, mai "
    "servile, mai prolisso: di norma una o due frasi. "
    "Dai più dettagli solo se richiesti; "
    "le tue risposte vengono lette ad alta voce, quindi niente markdown, tabelle o emoji. Rispondi solo alla "
    "domanda attuale: la cronologia serve solo come contesto. Non inventare mai dati in tempo reale che non "
    "conosci. Data e ora correnti: {now}."
)
_history: dict[str, deque] = defaultdict(lambda: deque(maxlen=20))


def persona(context: dict) -> str:
    now = time.localtime()
    text = PERSONA.format(now=f"{DAYS[now.tm_wday]} {now.tm_mday} {MONTHS[now.tm_mon - 1]} {now.tm_year}, "
                              f"ore {now.tm_hour}:{now.tm_min:02d}")
    if context.get("laws"):
        text = str(context["laws"]) + "\n\n" + text
    if context.get("speaker"):
        text += " " + str(context["speaker"])[:400]
    if context.get("dialogue"):
        text += ("\nUltimi scambi di questa conversazione (mantieni il filo del discorso e risolvi i riferimenti "
                 "come «e domani?» o «e lui?»):\n" + str(context["dialogue"])[:2500])
    if context.get("people_present"):
        people = str(context["people_present"])
        text += "\nPersone riconosciute ora dalla webcam (rivolgiti a loro per nome):\n" + people
    if context.get("reply_language"):
        text += "\n" + str(context["reply_language"])[:600]
    if context.get("knowledge"):
        text += "\nAppunti verificati che hai studiato (usali se pertinenti):\n" + str(context["knowledge"])[:3000]
    if context.get("long_term"):
        text += ("\nCose che ricordi su chi ti parla (memoria a lungo termine: tienine conto con naturalezza, "
                 "senza elencarle):\n" + str(context["long_term"])[:1200])
    return text


async def reply(ref: str, query: str, device: str, context: dict, max_tokens: int) -> Reply:
    history = _history[device]
    messages = [*history, {"role": "user", "content": query}]
    answer = await complete(ref, messages, persona(context), max_tokens=max_tokens, temperature=0.6)
    history.append({"role": "user", "content": query})
    history.append({"role": "assistant", "content": answer.text})
    return answer
