RELATIONS = {
    "coniuge": ("Coniuge", "coniuge"), "partner": ("Partner", "partner"), "fidanzato": ("Fidanzato/a", "fidanzato"),
    "ex_coniuge": ("Ex coniuge", "ex_coniuge"),
    "padre": ("Padre", "figlio"), "madre": ("Madre", "figlio"), "figlio": ("Figlio/a", "genitore"),
    "genitore": ("Genitore", "figlio"), "fratello": ("Fratello/Sorella", "fratello"),
    "nonno": ("Nonno/a", "nipote_nonno"), "nipote_nonno": ("Nipote (di nonno)", "nonno"),
    "zio": ("Zio/a", "nipote_zio"), "nipote_zio": ("Nipote (di zio)", "zio"), "cugino": ("Cugino/a", "cugino"),
    "suocero": ("Suocero/a", "genero_nuora"), "genero_nuora": ("Genero/Nuora", "suocero"),
    "cognato": ("Cognato/a", "cognato"), "padrino": ("Padrino/Madrina", "figlioccio"), "figlioccio": ("Figlioccio/a", "padrino"),
    "amico": ("Amico/a", "amico"), "collega": ("Collega", "collega"), "responsabile": ("Responsabile", "collaboratore"),
    "collaboratore": ("Collaboratore", "responsabile"), "vicino": ("Vicino di casa", "vicino"),
    "medico": ("Medico", "paziente"), "paziente": ("Paziente", "medico"), "altro": ("Altro", "altro"),
}

ROLES = {"owner": "Proprietario", "family": "Famiglia", "friend": "Amico", "guest": "Ospite", "staff": "Collaboratore",
         "service": "Servizi (medico, tecnico…)"}

SECTIONS = [
    {"id": "identity", "title": "Anagrafica", "icon": "👤", "fields": [
        {"key": "title", "label": "Titolo", "type": "select", "options": ["", "Sig.", "Sig.ra", "Dott.", "Dott.ssa", "Ing.", "Avv.", "Prof.", "Prof.ssa", "Arch.", "Geom."]},
        {"key": "first_name", "label": "Nome", "type": "text", "required": True},
        {"key": "middle_names", "label": "Secondo nome", "type": "text"},
        {"key": "last_name", "label": "Cognome", "type": "text"},
        {"key": "maiden_name", "label": "Cognome da nubile", "type": "text"},
        {"key": "nickname", "label": "Soprannome / come chiamarlo", "type": "text"},
        {"key": "gender", "label": "Genere", "type": "select", "options": ["", "Maschile", "Femminile", "Altro", "Preferisco non indicarlo"]},
        {"key": "pronouns", "label": "Pronomi", "type": "text", "placeholder": "es. lui, lei, loro"},
        {"key": "birthday", "label": "Data di nascita", "type": "date"},
        {"key": "birth_place", "label": "Luogo di nascita", "type": "text"},
        {"key": "name_day", "label": "Onomastico (gg-mm)", "type": "text", "placeholder": "calcolato dal nome se vuoto"},
        {"key": "nationality", "label": "Nazionalità", "type": "text"},
        {"key": "languages", "label": "Lingue parlate", "type": "tags"},
        {"key": "religion", "label": "Religione", "type": "text"},
        {"key": "marital_status", "label": "Stato civile", "type": "select", "options": ["", "Celibe/Nubile", "Fidanzato/a", "Convivente", "Sposato/a", "Unito/a civilmente", "Separato/a", "Divorziato/a", "Vedovo/a"]},
        {"key": "role", "label": "Ruolo per Jarvis", "type": "select", "options": list(ROLES), "labels": ROLES},
        {"key": "deceased", "label": "Deceduto/a", "type": "bool"},
        {"key": "death_date", "label": "Data di decesso", "type": "date"},
    ]},
    {"id": "contacts", "title": "Contatti", "icon": "📇", "fields": [
        {"key": "phones", "label": "Telefoni", "type": "list", "fields": [
            {"key": "label", "label": "Tipo", "type": "select", "options": ["Cellulare", "Casa", "Lavoro", "WhatsApp", "Altro"]},
            {"key": "number", "label": "Numero", "type": "tel"}]},
        {"key": "emails", "label": "Email", "type": "list", "fields": [
            {"key": "label", "label": "Tipo", "type": "select", "options": ["Personale", "Lavoro", "PEC", "Altro"]},
            {"key": "address", "label": "Indirizzo", "type": "email"}]},
        {"key": "addresses", "label": "Indirizzi", "type": "list", "fields": [
            {"key": "label", "label": "Tipo", "type": "select", "options": ["Casa", "Lavoro", "Scuola", "Università", "Palestra", "Casa vacanze", "Domicilio", "Altro"]},
            {"key": "street", "label": "Via e civico", "type": "text"}, {"key": "zip", "label": "CAP", "type": "text"},
            {"key": "city", "label": "Città", "type": "text"}, {"key": "province", "label": "Provincia", "type": "text"},
            {"key": "country", "label": "Nazione", "type": "text"}]},
        {"key": "socials", "label": "Social e messaggistica", "type": "list", "fields": [
            {"key": "network", "label": "Servizio", "type": "select", "options": ["Telegram", "Instagram", "Facebook", "LinkedIn", "X", "TikTok", "YouTube", "Altro"]},
            {"key": "handle", "label": "Utente / link", "type": "text"}]},
        {"key": "telegram_id", "label": "ID Telegram (per le notifiche)", "type": "text"},
        {"key": "website", "label": "Sito web", "type": "url"},
    ]},
    {"id": "family", "title": "Famiglia e relazioni", "icon": "👨‍👩‍👧", "fields": [
        {"key": "relations", "label": "Relazioni", "type": "list", "fields": [
            {"key": "type", "label": "Relazione", "type": "select", "options": list(RELATIONS), "labels": {k: v[0] for k, v in RELATIONS.items()}},
            {"key": "person", "label": "Persona dell'anagrafe", "type": "person"},
            {"key": "name", "label": "…oppure nome", "type": "text"},
            {"key": "since", "label": "Dal", "type": "date"},
            {"key": "notes", "label": "Note", "type": "text"}]},
        {"key": "pets", "label": "Animali domestici", "type": "list", "fields": [
            {"key": "name", "label": "Nome", "type": "text"}, {"key": "species", "label": "Specie / razza", "type": "text"},
            {"key": "birthday", "label": "Nascita", "type": "date"}, {"key": "vet", "label": "Veterinario", "type": "text"}]},
    ]},
    {"id": "work", "title": "Lavoro e studi", "icon": "💼", "fields": [
        {"key": "occupation", "label": "Professione attuale", "type": "text"},
        {"key": "jobs", "label": "Esperienze lavorative", "type": "list", "fields": [
            {"key": "company", "label": "Azienda / ente", "type": "text"}, {"key": "role", "label": "Ruolo", "type": "text"},
            {"key": "department", "label": "Reparto", "type": "text"}, {"key": "start", "label": "Inizio", "type": "date"},
            {"key": "end", "label": "Fine", "type": "date"}, {"key": "current", "label": "Attuale", "type": "bool"},
            {"key": "location", "label": "Sede", "type": "text"}, {"key": "schedule", "label": "Orari", "type": "text"}]},
        {"key": "education", "label": "Istruzione", "type": "list", "fields": [
            {"key": "institution", "label": "Istituto", "type": "text"}, {"key": "degree", "label": "Titolo", "type": "text"},
            {"key": "field", "label": "Indirizzo", "type": "text"}, {"key": "start", "label": "Inizio", "type": "date"},
            {"key": "end", "label": "Fine", "type": "date"}, {"key": "grade", "label": "Voto", "type": "text"}]},
        {"key": "skills", "label": "Competenze", "type": "tags"},
    ]},
    {"id": "mobility", "title": "Spostamenti", "icon": "🚗", "fields": [
        {"key": "commute_time", "label": "Esce per andare al lavoro alle", "type": "text", "placeholder": "es. 08:15 (vuoto = nessun avviso)"},
        {"key": "commute_days", "label": "Giorni del tragitto", "type": "select", "options": ["", "1-5", "1-6", "1-7", "6-7"],
         "labels": {"": "lunedì-venerdì", "1-5": "lunedì-venerdì", "1-6": "lunedì-sabato", "1-7": "tutti i giorni", "6-7": "solo weekend"}},
        {"key": "travel_mode", "label": "Mezzo preferito", "type": "select", "options": ["", "drive", "transit", "walk", "bike", "moto"],
         "labels": {"": "come impostato in Maps", "drive": "Auto", "transit": "Mezzi pubblici", "walk": "A piedi", "bike": "Bici", "moto": "Moto"}},
        {"key": "commute_before", "label": "Mostra il tragitto minuti prima", "type": "number", "placeholder": "45"},
    ]},
    {"id": "dates", "title": "Date importanti", "icon": "📅", "fields": [
        {"key": "events", "label": "Ricorrenze ed eventi", "type": "list", "fields": [
            {"key": "type", "label": "Tipo", "type": "select", "options": ["Anniversario di matrimonio", "Anniversario di fidanzamento", "Laurea", "Assunzione", "Trasloco", "Ricordo", "Appuntamento", "Altro"]},
            {"key": "title", "label": "Descrizione", "type": "text"}, {"key": "date", "label": "Data", "type": "date"},
            {"key": "yearly", "label": "Ogni anno", "type": "bool"}, {"key": "remind_days", "label": "Avvisa giorni prima", "type": "number"}]},
    ]},
    {"id": "health", "title": "Salute", "icon": "🩺", "private": True, "fields": [
        {"key": "blood_type", "label": "Gruppo sanguigno", "type": "select", "options": ["", "0+", "0-", "A+", "A-", "B+", "B-", "AB+", "AB-"]},
        {"key": "allergies", "label": "Allergie", "type": "tags"},
        {"key": "intolerances", "label": "Intolleranze", "type": "tags"},
        {"key": "diet", "label": "Alimentazione", "type": "select", "options": ["", "Onnivora", "Vegetariana", "Vegana", "Pescetariana", "Senza glutine", "Altro"]},
        {"key": "conditions", "label": "Condizioni di salute", "type": "textarea"},
        {"key": "medications", "label": "Farmaci e orari", "type": "list", "fields": [
            {"key": "name", "label": "Farmaco", "type": "text"}, {"key": "dose", "label": "Dose", "type": "text"},
            {"key": "times", "label": "Orari", "type": "text", "placeholder": "es. 08:00, 20:00"}]},
        {"key": "doctor", "label": "Medico di base", "type": "text"},
        {"key": "emergency", "label": "Contatti di emergenza", "type": "list", "fields": [
            {"key": "person", "label": "Persona", "type": "person"}, {"key": "name", "label": "…oppure nome", "type": "text"},
            {"key": "phone", "label": "Telefono", "type": "tel"}]},
        {"key": "height_cm", "label": "Altezza (cm)", "type": "number"},
        {"key": "notes_health", "label": "Note", "type": "textarea"},
    ]},
    {"id": "preferences", "title": "Gusti e preferenze", "icon": "⭐", "fields": [
        {"key": "food_likes", "label": "Cibi preferiti", "type": "tags"},
        {"key": "food_dislikes", "label": "Cibi non graditi", "type": "tags"},
        {"key": "drinks", "label": "Bevande preferite", "type": "tags"},
        {"key": "coffee", "label": "Come prende il caffè", "type": "text"},
        {"key": "music", "label": "Musica e artisti", "type": "tags"},
        {"key": "movies", "label": "Film, serie e generi", "type": "tags"},
        {"key": "books", "label": "Libri e autori", "type": "tags"},
        {"key": "sports", "label": "Sport e squadre", "type": "tags"},
        {"key": "hobbies", "label": "Hobby e passioni", "type": "tags"},
        {"key": "colors", "label": "Colori preferiti", "type": "tags"},
        {"key": "temperature", "label": "Temperatura di comfort (°C)", "type": "number"},
        {"key": "wake_time", "label": "Orario di sveglia abituale", "type": "text"},
        {"key": "sleep_time", "label": "Orario in cui va a dormire", "type": "text"},
        {"key": "gift_ideas", "label": "Idee regalo", "type": "tags"},
        {"key": "custom", "label": "Altre preferenze", "type": "list", "fields": [
            {"key": "key", "label": "Argomento", "type": "text"}, {"key": "value", "label": "Preferenza", "type": "text"}]},
    ]},
    {"id": "assets", "title": "Documenti e beni", "icon": "🗂", "private": True, "fields": [
        {"key": "documents", "label": "Documenti (con promemoria di scadenza)", "type": "list", "fields": [
            {"key": "type", "label": "Documento", "type": "select", "options": ["Carta d'identità", "Passaporto", "Patente", "Tessera sanitaria", "Permesso di soggiorno", "Altro"]},
            {"key": "number", "label": "Numero", "type": "text"}, {"key": "expiry", "label": "Scadenza", "type": "date"}]},
        {"key": "vehicles", "label": "Veicoli", "type": "list", "fields": [
            {"key": "model", "label": "Marca e modello", "type": "text"}, {"key": "plate", "label": "Targa", "type": "text"},
            {"key": "insurance", "label": "Scadenza assicurazione", "type": "date"}, {"key": "inspection", "label": "Scadenza revisione", "type": "date"},
            {"key": "tax", "label": "Scadenza bollo", "type": "date"}]},
    ]},
    {"id": "notes", "title": "Note e privacy", "icon": "📝", "fields": [
        {"key": "tags", "label": "Etichette", "type": "tags"},
        {"key": "notes", "label": "Note per Jarvis", "type": "textarea"},
        {"key": "consent", "label": "Usa questo profilo per personalizzare le risposte", "type": "bool"},
        {"key": "share_health", "label": "Jarvis può usare i dati sanitari (es. promemoria farmaci)", "type": "bool"},
    ]},
]

FIELD_INDEX = {f["key"]: (s["id"], f) for s in SECTIONS for f in s["fields"]}
