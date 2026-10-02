# Funzionalità di Jarvis

Ogni funzionalità è una cartella con un file `feature.json`. Il supervisore scansiona in background
(ogni 20 secondi) queste due posizioni e la funzionalità compare da sola, come scheda, in
**Pannello → Funzionalità**:

| Cartella | Chi la crea |
|---|---|
| `installer_wizard/features/<id>/` | funzionalità di sistema, arrivano con gli aggiornamenti da GitHub |
| `/var/lib/jarvis/features/<id>/` | funzionalità aggiunte dall'utente o create da Jarvis stesso |

Una funzionalità non ha bisogno di modificare il pannello: la scheda, l'interruttore, le impostazioni e
la voce nel menu laterale (se l'utente la aggiunge ai preferiti) sono generati dal manifest.

## Contenuto della cartella

| File | Ruolo |
|---|---|
| `feature.json` | manifest (obbligatorio) |
| `*.py` | logica della funzionalità, importata come `features.<id>.<modulo>` |
| `api.py` | rotte HTTP: `public_routes` (porta 80) e `admin_routes` (porta 8080), registrate in `backend/jarvis_supervisor.py` |
| `service.py` | servizio esterno con una propria unità systemd (voce, visione, ascolto) |
| `admin.html` | una `<section class="tab" id="tab-<panel>">` inserita nel pannello |
| `admin.js` | registra la scheda con `JarvisAdmin.tab("<panel>", { init, load, onState, leave })` |
| `admin.css` | stili della sola scheda |

Il supervisore inserisce da solo `admin.html`, `admin.js` e `admin.css` di ogni cartella nella pagina
del pannello: aggiungere una scheda non richiede di modificare `web/admin`.

## Manifest

```json
{
  "id": "meteo_avanzato",
  "name": "Meteo avanzato",
  "icon": "⛅",
  "category": "casa",
  "order": 200,
  "source": "ai",
  "description": "Allerta meteo e qualità dell'aria per la tua zona.",
  "capabilities": ["Allerte della protezione civile", "Pollini e qualità dell'aria"],
  "pinned": false,
  "panel": "",
  "toggle": { "env": "JARVIS_METEO_PLUS", "apply": [] },
  "requires": { "ram_gb": 2, "gpu_vram_gb": 0, "video": false, "commands": ["curl"], "features": ["ear"] },
  "settings": [
    { "key": "soglia_vento", "label": "Avvisami con vento oltre (km/h)", "type": "number", "default": "60" },
    { "key": "zona", "label": "Zona di allerta", "type": "select", "options": ["Campania", "Lazio"] }
  ]
}
```

| Campo | Significato |
|---|---|
| `id` | minuscole, cifre, `-` e `_` (di norma uguale al nome della cartella) |
| `category` | `assistente`, `percezione`, `casa`, `conoscenza`, `comunicazione`, `sistema`, `altro` |
| `source` | solo per le cartelle utente: `ai` (creata da Jarvis) o `user` |
| `pinned` | se `true` compare già nel menu laterale alla prima scoperta |
| `panel` | scheda dedicata già presente nel pannello (es. `telegram`); vuoto = pagina generata |
| `toggle` | assente = sempre attiva. `env`: variabile `1`/`0` in `jarvis.env` (con `tri: true` vale `auto`/`1`/`0`), `apply`: step da riconvergere. `hook`: interruttore Python registrato dal modulo (`registry.register_hook`) |
| `requires` | requisiti per la modalità **automatica**: se mancano la funzionalità resta spenta, con il motivo |
| `settings` | campi del modulo generato: `text`, `number`, `select`, `color`, `secret`, `bool`. Le chiavi MAIUSCOLE vanno in `jarvis.env` (solo quelle ammesse per le funzionalità esterne), le altre restano nello stato della funzionalità (`registry.settings_of(id)`) |

## Modalità

Ogni funzionalità con interruttore ha tre modalità, scelte dalla scheda:

- **Automatica** (predefinita): Jarvis la accende se l'hardware soddisfa `requires`, e la riaccende da
  solo quando l'hardware cambia (es. si collega una webcam);
- **Sempre attiva**: accesa comunque, a rischio dell'utente (la scheda mostra cosa manca);
- **Disattivata**.
