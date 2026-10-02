import re

from features.home_assistant.nlu.text import phrase_stems, stem

DOMAIN_WORDS = {
    "light": ["luce", "luci", "lampada", "lampadina", "lampadario", "faretto", "faretti", "led", "striscia led",
              "abat jour", "piantana", "applique", "plafoniera", "illuminazione", "light"],
    "cover": ["tapparella", "serranda", "persiana", "tenda", "veneziana", "scuri", "avvolgibile", "saracinesca",
              "tende da sole", "tendone", "basculante", "garage", "cancello", "portone", "cover", "blind"],
    "climate": ["condizionatore", "climatizzatore", "clima", "aria condizionata", "termostato", "riscaldamento",
                "termosifone", "caldaia", "pompa di calore", "split", "climate"],
    "fan": ["ventilatore", "ventola", "pale", "fan"],
    "switch": ["presa", "interruttore", "spina", "rele", "switch", "ciabatta"],
    "media_player": ["tv", "televisione", "televisore", "stereo", "musica", "cassa", "casse", "altoparlante",
                     "speaker", "chromecast", "sonos", "radio", "soundbar", "home theater"],
    "lock": ["serratura", "porta blindata", "lucchetto", "lock"],
    "vacuum": ["aspirapolvere", "robot", "roomba", "robottino", "folletto", "lavapavimenti"],
    "scene": ["scena", "scenario", "atmosfera", "ambiente"],
    "script": ["script", "routine", "procedura"],
    "alarm_control_panel": ["allarme", "antifurto", "sistema di sicurezza"],
    "humidifier": ["umidificatore", "deumidificatore"],
    "water_heater": ["boiler", "scaldabagno", "scaldacqua"],
    "valve": ["valvola", "rubinetto"],
    "siren": ["sirena"],
    "lawn_mower": ["tosaerba", "robot tagliaerba", "rasaerba"],
    "button": ["pulsante", "bottone"],
}
DOMAIN_PHRASES = {d: [phrase_stems(w) for w in words] for d, words in DOMAIN_WORDS.items()}
DOMAIN_TOKEN_STEMS = {s for phrases in DOMAIN_PHRASES.values() for p in phrases for s in p}
PLURAL_WORDS = {"luci", "lampade", "lampadine", "faretti", "tapparelle", "serrande", "persiane", "tende", "prese",
                "interruttori", "casse", "tutte", "tutti", "tutto", "ovunque"}
SENSITIVE_COVERS = {"garage", "gate", "door"}

AREA_SYNONYMS = [
    ["soggiorno", "salotto", "sala", "salone", "living", "living room", "lounge"],
    ["camera da letto", "camera matrimoniale", "matrimoniale", "stanza da letto", "bedroom", "master bedroom"],
    ["cameretta", "camera dei bambini", "camera bimbi", "kids room", "nursery"],
    ["bagno", "toilette", "wc", "bathroom"],
    ["cucina", "angolo cottura", "kitchen"],
    ["studio", "ufficio", "office", "study"],
    ["ingresso", "entrata", "atrio", "entrance", "hall"],
    ["corridoio", "disimpegno", "hallway"],
    ["balcone", "terrazzo", "terrazza", "veranda", "balcony", "terrace"],
    ["giardino", "cortile", "esterno", "garden", "backyard", "yard"],
    ["garage", "box", "autorimessa"],
    ["lavanderia", "laundry"],
    ["cantina", "taverna", "basement"],
    ["sala da pranzo", "sala pranzo", "dining room"],
    ["camera degli ospiti", "camera ospiti", "stanza degli ospiti", "guest room"],
]
FLOOR_WORDS = {"piano terra": 0, "pianterreno": 0, "piano terreno": 0, "primo piano": 1, "piano di sopra": 1,
               "di sopra": 1, "piano superiore": 1, "secondo piano": 2, "seminterrato": -1, "piano di sotto": -1,
               "di sotto": -1, "piano interrato": -1}
WHOLE_HOME = re.compile(r"\b(tutta la casa|in tutta casa|ovunque|dappertutto|tutte le stanze|in ogni stanza|"
                        r"in casa|della casa|di casa)\b")

COLORS = {"rosso": (255, 0, 0), "verde": (0, 255, 0), "blu": (0, 0, 255), "azzurro": (0, 150, 255),
          "celeste": (110, 200, 255), "giallo": (255, 215, 0), "arancione": (255, 110, 0), "arancio": (255, 110, 0),
          "viola": (140, 0, 255), "lilla": (200, 150, 255), "rosa": (255, 105, 180), "fucsia": (255, 0, 200),
          "magenta": (255, 0, 255), "turchese": (0, 220, 200), "ciano": (0, 255, 255), "oro": (255, 190, 60),
          "dorato": (255, 190, 60), "ambra": (255, 160, 0), "indaco": (75, 0, 130)}
COLOR_STEMS = {stem(k): (k, v) for k, v in COLORS.items()}
KELVIN = [("bianco caldo", 2700), ("luce calda", 2700), ("bianco naturale", 4000), ("luce naturale", 4000),
          ("bianco neutro", 4000), ("bianco freddo", 6200), ("luce fredda", 6200), ("bianco", 4000)]
HVAC = [(r"\b(riscalda\w*|caldo|scaldare|heat)\b", "heat"), (r"\b(raffresca\w*|raffredda\w*|freddo|cool)\b", "cool"),
        (r"\b(deumidific\w*|dry)\b", "dry"), (r"\b(automatic\w*|auto)\b", "heat_cool"),
        (r"\b(ventilazione|solo ventola|fan only)\b", "fan_only")]

ACTIONS = [
    ("disarm", r"\b(disinserisci|disattiva (l )?allarme|disarma|disinserire)\b"),
    ("arm", r"\b(inserisci|arma|attiva (l )?allarme|inserire)\b"),
    ("unlock", r"\b(sblocca|sbloccare|apri (la )?serratura)\b"),
    ("lock", r"\b(blocca|bloccare|chiudi a chiave)\b"),
    ("dock", r"\b(torna alla base|rimanda alla base|alla base|in carica)\b"),
    ("clean", r"\b(pulisci|pulire|aspira|passa (l )?aspirapolvere)\b"),
    ("pause", r"\b(pausa|metti in pausa)\b"),
    ("play", r"\b(riproduci|riprendi|play|fai ripartire)\b"),
    ("next", r"\b(prossim[ao]|successiv[ao]|salta)\b"),
    ("previous", r"\b(precedente|torna indietro)\b"),
    ("mute", r"\b(muto|silenzia|togli (l )?audio)\b"),
    ("stop", r"\b(stop|fermati|ferma)\b"),
    ("toggle", r"\b(inverti|commuta)\b"),
    ("press", r"\b(premi|schiaccia|pigia)\b"),
    ("up", r"\b(aumenta|aumentare|incrementa|alza|alzare|solleva|tira su|piu (forte|luce|alt[oa]|caldo|luminos[ao]))\b"),
    ("down", r"\b(diminuisci|diminuire|riduci|ridurre|abbassa|abbassare|cala|tira giu|meno (forte|luce)|"
             r"piu (bass[oa]|fresco|debole|soffus[ao]))\b"),
    ("open", r"\b(apri|aprire|aprite|spalanca)\b"),
    ("close", r"\b(chiudi|chiudere|chiudete)\b"),
    ("off", r"\b(spegni|spegnere|spegnete|spegnimi|disattiva|disattivare|stacca|off)\b"),
    ("on", r"\b(accendi|accendere|accendete|accendimi|attiva|attivare|avvia|avviare|fai partire|"
           r"metti in funzione|illumina|esegui|lancia|on)\b"),
    ("set", r"\b(imposta|impostare|metti|mettere|porta|portare|regola|regolare|setta|settare|fissa|cambia|colora)\b"),
]
ACTION_RES = [(a, re.compile(p)) for a, p in ACTIONS]

QUERY_RE = re.compile(r"(\?|\b(e|sono|risulta|risultano) (acces|spent|apert|chius|attiv)\w*|\bquali\b|\bquanti\b|"
                      r"\bquante\b|\bc e\b|\bci sono\b|\bchi\b|\bdove\b|\bquando\b|\bstato\b|\bcom e\b|\bcome e\b|"
                      r"\bdimmi\b|\bsai\b|\belenca\b|\bmostrami\b|\bfammi vedere\b|\bche temperatura\b|\bquanti gradi\b)")
PROTOCOLS = [(r"\bzigbee\b", "zigbee"), (r"\bthread\b", "thread"), (r"\bmatter\b", "matter"),
             (r"\b(wi ?fi|wireless)\b", "wifi"), (r"\bbluetooth\b", "bluetooth"), (r"\bz ?wave\b", "zwave"),
             (r"\b(ethernet|via cavo|cablat\w+)\b", "ethernet"), (r"\bmqtt\b", "mqtt")]
