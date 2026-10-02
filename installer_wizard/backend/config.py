import json
import os
import re
import tempfile
from contextvars import ContextVar
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
APP_DIR = BACKEND_DIR.parent
WEB_DIR = APP_DIR / "web"
FEATURES_DIR = APP_DIR / "features"
WIDGETS_DIR = APP_DIR / "widgets"
SKILLS_DIR = APP_DIR / "skills"

DEMO = os.environ.get("JARVIS_DEMO") == "1"

JARVIS_DIR = Path(os.environ.get("JARVIS_DIR", BACKEND_DIR.parents[1] if DEMO else "/opt/Jarvis"))
_ROOT = Path(tempfile.gettempdir()) / "jarvis-demo" if DEMO else Path("/")
ETC_DIR = _ROOT / "etc/jarvis"
STATE_DIR = _ROOT / "var/lib/jarvis"
LOG_DIR = _ROOT / "var/log/jarvis"
ENV_FILE = ETC_DIR / "jarvis.env"
STEPS_DIR = JARVIS_DIR / "scripts/os/steps"
HEAL_SCRIPT = JARVIS_DIR / "scripts/os/heal.sh"

PUBLIC_PORT = int(os.environ.get("JARVIS_PUBLIC_PORT", 8000 if DEMO else 80))
ADMIN_PORT = int(os.environ.get("JARVIS_ADMIN_PORT", 8001 if DEMO else 8080))
CORE_URL = os.environ.get("JARVIS_CORE_URL", "http://127.0.0.1:8443")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")

VERSION = "3.0.0"

for _d in (ETC_DIR, STATE_DIR, LOG_DIR):
    _d.mkdir(parents=True, exist_ok=True)

EDITABLE_KEYS = {
    "JARVIS_LLM_MODEL": "Cervello potente: modello per il ragionamento (Ollama; vuoto = automatico)",
    "JARVIS_LLM_FAST_MODEL": "Cervello veloce: modello per la conversazione (Ollama; vuoto = automatico)",
    "JARVIS_LLM_ROUTING": "Instradamento tra cervello veloce e potente (auto, 1 = sempre, 0 = un solo cervello)",
    "JARVIS_LLM_CHAT_ORDER": "Priorità dei modelli per la conversazione (separati da virgola; vuoto = automatico)",
    "JARVIS_LLM_DEEP_ORDER": "Priorità dei modelli per il ragionamento (separati da virgola; vuoto = automatico)",
    "JARVIS_EMBED_MODEL": "Modello di embedding (Ollama)",
    "JARVIS_OLLAMA_URL": "Server Ollama (vuoto = locale; es. http://192.168.1.50:11434 per usare un altro server)",
    "JARVIS_ASSISTANT_NAME": "Nome dell'assistente (predefinito J.A.R.V.I.S.)",
    "JARVIS_USER_NAME": "Nome dell'utente principale (come Jarvis ti chiama)",
    "JARVIS_LOCATION": "Posizione predefinita (nome; si imposta meglio da Audio e posizione)",
    "JARVIS_LOCATION_MODE": "Posizione: auto (display/Wi-Fi più precisi) o fixed (sempre la predefinita)",
    "JARVIS_LOCATION_LAT": "Latitudine della posizione predefinita",
    "JARVIS_LOCATION_LON": "Longitudine della posizione predefinita",
    "JARVIS_MUSIC_ID": "Riconoscimento della musica in ascolto (1/0; invia 10 s di audio al servizio di riconoscimento)",
    "JARVIS_STUDY_FINETUNE": "Consolidamento dello studio nei pesi con Soup (auto = deciso dall'hardware, 1 = sempre, 0 = mai)",
    "JARVIS_STUDY_BASE_MODEL": "Modello base per Soup (Hugging Face, es. Qwen/Qwen2.5-1.5B-Instruct)",
    "JARVIS_VOICE": "Voce principale (es. im_nicola, it-IT-DiegoNeural, it_IT-serena-high; si gestisce da Voci)",
    "JARVIS_VOICE_ORDER": "Priorità delle voci (separate da virgola; si gestisce meglio da Voci)",
    "JARVIS_VOICE_SPEED": "Velocità della voce (0.6 - 1.6)",
    "JARVIS_CAMERAS": "Telecamere e registrazione ad anello (1/0, spento di default)",
    "JARVIS_ADDRESSEE_THRESHOLD": "Soglia per decidere se gli stai parlando (0.2 - 0.95)",
    "JARVIS_ADDRESSEE_ALONE": "Fiducia aggiuntiva quando sei solo nella stanza (0 - 1)",
    "JARVIS_VOICE_PITCH": "Tono della voce in semitoni (-6 grave, +6 acuto)",
    "JARVIS_VOICE_VOLUME": "Volume della voce (0.4 - 2.0)",
    "JARVIS_VOICE_LANG": "Voce preferita per ogni lingua (es. en:am_michael,de:de_DE-thorsten-medium; si gestisce da Voci)",
    "JARVIS_VOICE_ONLINE": "Voci neurali online (auto = se disponibili, 1 = sì, 0 = mai: il testo non esce dal server)",
    "JARVIS_VOICE_AUTO_DOWNLOAD": "Scarica da solo la voce di una lingua nuova quando serve (1/0)",
    "JARVIS_EAR_MULTILANG": "Riconosce la lingua in cui parli (1/0; 0 = ascolta solo l'italiano)",
    "JARVIS_VISION": "Webcam e riconoscimento facciale (1/0)",
    "JARVIS_EAR": "Ascolto vocale con parola \"Jarvis\" (1/0)",
    "JARVIS_STT_MODEL": "Modello di ascolto (vuoto = automatico; base, small, medium)",
    "JARVIS_EAR_MAX_GAIN": "Amplificazione massima del microfono per il campo lontano (2 - 80)",
    "JARVIS_EAR_TARGET_RMS": "Livello vocale obiettivo dell'autolivellamento (0.03 - 0.2)",
    "JARVIS_AVATAR": "Aspetto dell'assistente (auto = in base al dispositivo, full = ologramma 3D con volto, light = nucleo leggero)",
    "JARVIS_FACE_COLOR": "Colore dell'ologramma (colore, es. #29e0ff)",
    "JARVIS_AUTO_UPDATE": "Aggiornamenti automatici (1/0)",
    "JARVIS_UPDATE_INTERVAL_MIN": "Controllo aggiornamenti ogni N minuti (default 5)",
    "JARVIS_UPDATE_BRANCH": "Ramo GitHub",
    "JARVIS_KIOSK": "Display kiosk (1/0)",
    "GEMINI_API_KEY": "API key Google Gemini (fallback)",
    "ANTHROPIC_API_KEY": "API key Anthropic Claude (fallback)",
    "JARVIS_TELEGRAM_TOKEN": "Token del bot Telegram (da @BotFather)",
    "JARVIS_TELEGRAM": "Bot Telegram attivo (1/0)",
    "JARVIS_NETWORK": "Esploratore della rete locale (1/0)",
    "JARVIS_SPOTIFY": "Spotify attivo (1/0)",
    "JARVIS_SPOTIFY_CLIENT_ID": "Spotify: Client ID dell'app (developer.spotify.com)",
    "JARVIS_SPOTIFY_CLIENT_SECRET": "Spotify: Client Secret dell'app",
    "JARVIS_SPOTIFY_WHEN": "Spotify: quando mostrare il brano (present = se ti vede, always = sempre)",
    "JARVIS_GOOGLE": "Google: connettori Calendar, Gmail, Tasks, Contatti, Drive, Keep attivi (1/0)",
    "JARVIS_GOOGLE_CLIENT_ID": "Google: Client ID OAuth (App desktop, console.cloud.google.com)",
    "JARVIS_GOOGLE_CLIENT_SECRET": "Google: Client Secret OAuth",
    "JARVIS_GOOGLE_SERVICES": "Google: servizi da collegare (calendar,gmail,tasks,contacts,drive,keep)",
    "JARVIS_GOOGLE_REMIND_MIN": "Google: avviso sul display N minuti prima di ogni appuntamento (0 = mai)",
    "JARVIS_MAPS": "Maps: indicazioni, tempi e avvisi di viaggio (1/0)",
    "JARVIS_MAPS_API_KEY": "Maps: chiave Google Maps Platform (Routes API) per traffico e mezzi; vuota = OpenStreetMap",
    "JARVIS_MAPS_MODE": "Maps: mezzo predefinito (drive, walk, bike, transit, moto)",
    "JARVIS_MAPS_EVENT_HOURS": "Maps: ore in anticipo in cui guardare gli appuntamenti con un luogo (default 4)",
    "JARVIS_SKILLS": "Algoritmi riutilizzabili per calcoli e conversioni (1/0)",
    "JARVIS_SKILLS_GENERATE": "Jarvis scrive da solo nuovi algoritmi quando servono (1/0)",
    "HOME_ASSISTANT_URL": "URL Home Assistant",
    "HOME_ASSISTANT_TOKEN": "Token Home Assistant",
    "HOME_ASSISTANT_VERIFY_SSL": "Home Assistant: verifica il certificato HTTPS (1/0; 0 per certificati autofirmati)",
    "JARVIS_HOME_ASSISTANT": "Casa: collegamento a Home Assistant attivo (1/0)",
    "JARVIS_HOME_ROOM": "Casa: stanza in cui si trova Jarvis (nome dell'area di Home Assistant)",
    "JARVIS_HOME_MOTION_MIN": "Casa: minuti dopo l'ultimo movimento in cui una stanza resta occupata (default 5)",
    "JARVIS_HOME_CONFIRM": "Casa: chiedi conferma per serrature, allarme, cancelli e garage (1/0)",
    "JARVIS_HANDS": "Comandi con le mani davanti alla webcam (auto = solo se la GPU del display li regge, 1 = sempre, 0 = mai)",
    "JARVIS_HANDS_FPS": "Comandi con le mani: analisi al secondo con una mano in vista (10/20/30)",
    "JARVIS_HANDS_COUNT": "Comandi con le mani: mani riconosciute (1/2)",
    "JARVIS_HANDS_MAX_MS": "Comandi con le mani: in automatico si spengono se un'analisi supera questi millisecondi (30/50/90)",
    "JARVIS_AUTOMATIONS": "Automazioni a più stadi: inneschi, condizioni, azioni, rami, attese, webhook (1/0)",
    "JARVIS_SOUNDS": "Suoni ed effetti (1/0)",
    "JARVIS_SOUNDS_VOLUME": "Suoni: volume degli effetti 0-100",
    "JARVIS_SOUNDS_THEME": "Suoni: tema (jarvis, soft, classic)",
    "JARVIS_SOUNDS_FEEDBACK": "Suoni di attivazione e richiesta (1/0)",
    "JARVIS_SOUNDS_THINKING": "Suono mentre pensa ed elabora (1/0)",
    "JARVIS_SOUNDS_NOTIFY": "Suoni di notifica (1/0)",
    "JARVIS_SOUNDS_AMBIENT": "Sottofondo (none, reactor, space, rain, ocean, lab)",
    "JARVIS_SOUNDS_AMBIENT_VOLUME": "Volume del sottofondo 0-100",
    "JARVIS_QUIET_MODE": "Orari di silenzio: soft (attenua), mute (solo allarmi), off",
    "JARVIS_QUIET_START": "Silenzio dalle HH:MM",
    "JARVIS_QUIET_END": "Silenzio fino alle HH:MM",
    "JARVIS_QUIET_DAYS": "Notti di silenzio: all, weekdays, weekend",
    "JARVIS_QUIET_VOICE": "Volume della voce in silenzio 0-100",
    "JARVIS_QUIET_EFFECTS": "Volume degli effetti in silenzio attenuato 0-100",
    "JARVIS_SELFTEST": "Collaudo notturno e dopo ogni aggiornamento (1/0)",
    "JARVIS_SELFTEST_AT": "Ora del collaudo notturno HH:MM",
    "JARVIS_SELFTEST_ROLLBACK": "Torna alla versione precedente se un aggiornamento rompe una funzione essenziale (1/0)",
    "JARVIS_UPDATE_REQUIRE_CI": "Installa solo versioni con i test superati su GitHub (1/0)",
    "JARVIS_HABITS": "Abitudini: osserva la casa e propone automazioni (1/0)",
    "JARVIS_HABITS_CONFIDENCE": "Abitudini: regolarità minima per proporre (0.6, 0.7, 0.8)",
    "JARVIS_HABITS_ASK": "Abitudini: proposte a voce (1/0)",
    "JARVIS_HABITS_ANOMALIES": "Avvisi di situazioni insolite con casa vuota (1/0)",
    "JARVIS_VAULT": "Memoria in file leggibili e diario giornaliero (1/0)",
    "JARVIS_VAULT_DIR": "Cartella della memoria in chiaro (vuoto = condivisione memoria-jarvis)",
    "JARVIS_GPU_DRIVER": "Driver video del display: auto (NVIDIA ufficiale se adatto), nouveau (libero)",
    "JARVIS_GPU_DRIVER_REBOOT": "Riavvio per attivare il driver video: night (alle 04:15) o now",
    "JARVIS_SHARES": "Condivisioni di rete Samba: «condivisa» e «memoria-jarvis» (1/0)",
    "JARVIS_SMB_PASSWORD": "Password dell'utente jarvis-share per le condivisioni",
    "JARVIS_AUTONOMY": "Autonomia: compiti programmati, autopilota (diagnosi, studio, riepilogo serale) e approvazioni (1/0)",
    "JARVIS_WELCOME": "Quando ti riconosce mostra meteo, promemoria e riepilogo Google nei widget (1/0)",
    "JARVIS_AGENT": "Agente con strumenti: file, widget, ologramma, 3D, email, SMB, terminale (1/0)",
    "JARVIS_AGENT_ACCESS": "Accesso dell'agente (completo = tutto il server con conferma per le azioni delicate, standard = solo /srv/jarvis e modelli 3D)",
    "JARVIS_SMTP_HOST": "Email in uscita: server SMTP (es. smtp.gmail.com; vuoto = usa Gmail collegato)",
    "JARVIS_SMTP_PORT": "Email in uscita: porta SMTP (587 STARTTLS, 465 SSL)",
    "JARVIS_SMTP_USER": "Email in uscita: utente SMTP",
    "JARVIS_SMTP_PASSWORD": "Email in uscita: password SMTP (per Gmail una password per le app)",
    "JARVIS_SMTP_FROM": "Email in uscita: mittente (vuoto = utente SMTP)",
    "JARVIS_3D_CONVERT": "Conversione 3D sul server: Blender per BLEND/USD/USDZ e LibreDWG per DWG (auto = se c'è spazio, 1 = sì, 0 = no)",
}
SECRET_KEYS = {"JARVIS_SMB_PASSWORD", "GEMINI_API_KEY", "ANTHROPIC_API_KEY", "HOME_ASSISTANT_TOKEN", "JARVIS_TELEGRAM_TOKEN", "JARVIS_SMTP_PASSWORD",
               "JARVIS_SPOTIFY_CLIENT_SECRET", "JARVIS_SPOTIFY_REFRESH_TOKEN",
               "JARVIS_GOOGLE_CLIENT_SECRET", "JARVIS_GOOGLE_REFRESH_TOKEN", "JARVIS_MAPS_API_KEY"}
_KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")


NODE = ContextVar("jarvis_node", default="")
NODE_FIXED = {"JARVIS_AUTO_UPDATE", "JARVIS_UPDATE_INTERVAL_MIN", "JARVIS_UPDATE_BRANCH", "JARVIS_GOOGLE_CLIENT_ID",
              "JARVIS_SPOTIFY_CLIENT_ID", "HOME_ASSISTANT_URL", "JARVIS_TELEGRAM", "JARVIS_AGENT_ACCESS"}
_nodes_cache = {"mtime": -1.0, "data": {}}


def node_keys() -> list[str]:
    return [k for k in EDITABLE_KEYS if k not in SECRET_KEYS and k not in NODE_FIXED]


def node_overrides(node_id: str) -> dict:
    path = STATE_DIR / "nodes.json"
    try:
        mtime = path.stat().st_mtime
        if mtime != _nodes_cache["mtime"]:
            _nodes_cache.update(mtime=mtime, data=json.loads(path.read_text(encoding="utf-8")).get("nodes", {}))
    except (OSError, ValueError):
        return {}
    allowed = set(node_keys())
    return {k: v for k, v in (_nodes_cache["data"].get(node_id, {}).get("settings") or {}).items() if k in allowed}


def read_env() -> dict:
    env = read_global_env()
    node = NODE.get()
    if node:
        env.update(node_overrides(node))
    return env


def read_global_env() -> dict:
    env = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip().strip('"')
    return env


_ollama_cache: dict = {}


def ollama_url() -> str:
    import time
    node = NODE.get()
    at, url = _ollama_cache.get(node, (0.0, OLLAMA_URL))
    if time.time() - at > 5:
        custom = read_env().get("JARVIS_OLLAMA_URL", "").strip().rstrip("/")
        if custom and not custom.startswith(("http://", "https://")):
            custom = f"http://{custom}"
        if custom and not re.search(r":\d+$", custom.split("//", 1)[1]):
            custom += ":11434"
        url = custom or OLLAMA_URL
        _ollama_cache[node] = (time.time(), url)
    return url


def ollama_remote() -> bool:
    host = ollama_url().split("//", 1)[-1].split(":", 1)[0]
    return host not in ("127.0.0.1", "localhost", "::1", "")


def write_env(updates: dict) -> None:
    for key, value in updates.items():
        if not _KEY_RE.match(key) or "\n" in str(value):
            raise ValueError(f"Chiave o valore non valido: {key}")
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
    pending = dict(updates)
    out = []
    for line in lines:
        key = line.split("=", 1)[0].strip() if "=" in line and not line.lstrip().startswith("#") else None
        if key in pending:
            value = pending.pop(key)
            if value != "":
                out.append(f"{key}={value}")
        else:
            out.append(line)
    out.extend(f"{k}={v}" for k, v in pending.items() if v != "")
    tmp = ENV_FILE.with_suffix(".tmp")
    tmp.write_text("\n".join(out) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, ENV_FILE)


def env_get(key: str, default: str = "") -> str:
    return read_env().get(key, default)
