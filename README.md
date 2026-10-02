# J.A.R.V.I.S. — Jarvis OS

<p align="center">
  <img src="https://img.shields.io/badge/Versione-3.0.0-00f0ff?style=for-the-badge" alt="Versione 3.0.0">
  <img src="https://img.shields.io/badge/OS-Debian%20%2F%20Ubuntu-red?style=for-the-badge" alt="Debian / Ubuntu">
  <img src="https://img.shields.io/badge/Python-3.11%2B-blue?style=for-the-badge" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/Locale%20%2B%20Cloud-Ollama%20%C2%B7%2022%20servizi-emerald?style=for-the-badge" alt="Locale e cloud">
  <img src="https://img.shields.io/badge/Licenza-MIT-amber?style=for-the-badge" alt="Licenza MIT">
</p>

```
         ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗
         ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝
         ██║███████║██████╔╝██║   ██║██║███████╗
    ██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║
    ╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║
     ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝
            J A R V I S   O S   ·   v3
         Progettato e sviluppato da NunzioTech
```

Jarvis OS trasforma un computer Debian o Ubuntu in un assistente domestico completo, nello stile del
J.A.R.V.I.S. dei film: ascolta («Ehi Jarvis»), parla con voce maschile, riconosce volti e voci, comanda la
casa tramite Home Assistant, mostra le informazioni su un display olografico a widget, impara da solo e
lavora in autonomia. Tutto gira sul tuo server; i servizi cloud sono facoltativi.

Questo documento è la guida completa per chi installa, usa e soprattutto **sviluppa** Jarvis: architettura,
funzionalità, configurazione, API, regole di codice, sicurezza e risoluzione dei problemi.

---

## Indice

1. [In breve](#1-in-breve)
2. [Novità della versione 3](#2-novità-della-versione-3)
3. [Requisiti](#3-requisiti)
4. [Installazione](#4-installazione)
5. [Primo avvio e accesso](#5-primo-avvio-e-accesso)
6. [Architettura](#6-architettura)
7. [Struttura del repository](#7-struttura-del-repository)
8. [Il supervisore](#8-il-supervisore)
9. [Passi d'installazione (step)](#9-passi-dinstallazione-step)
10. [Il cervello: modelli locali, altri server e cloud](#10-il-cervello-modelli-locali-altri-server-e-cloud)
11. [Catalogo delle funzionalità](#11-catalogo-delle-funzionalità)
12. [Display, widget e ologramma](#12-display-widget-e-ologramma)
13. [Algoritmi (skills)](#13-algoritmi-skills)
14. [Nodi e satelliti](#14-nodi-e-satelliti)
15. [Configurazione: jarvis.env e modalità auto/1/0](#15-configurazione-jarvisenv-e-modalità-auto10)
16. [Riferimento delle variabili](#16-riferimento-delle-variabili)
17. [Porte, servizi e file sul disco](#17-porte-servizi-e-file-sul-disco)
18. [API HTTP](#18-api-http)
19. [Aggiornamenti, collaudo e rollback](#19-aggiornamenti-collaudo-e-rollback)
20. [Sicurezza e privacy](#20-sicurezza-e-privacy)
21. [jarvisctl e manutenzione](#21-jarvisctl-e-manutenzione)
22. [Sviluppo](#22-sviluppo)
23. [Come aggiungere una funzionalità](#23-come-aggiungere-una-funzionalità)
24. [Come aggiungere un widget](#24-come-aggiungere-un-widget)
25. [Come aggiungere un algoritmo](#25-come-aggiungere-un-algoritmo)
26. [Come aggiungere un passo d'installazione](#26-come-aggiungere-un-passo-dinstallazione)
27. [Test e integrazione continua](#27-test-e-integrazione-continua)
28. [Jarvis Core (server/)](#28-jarvis-core-server)
29. [Client: web, Android, satelliti](#29-client-web-android-satelliti)
30. [Risoluzione dei problemi](#30-risoluzione-dei-problemi)
31. [Domande frequenti](#31-domande-frequenti)
32. [Contribuire, licenza e crediti](#32-contribuire-licenza-e-crediti)

---

## 1. In breve

| Cosa | Come |
| :--- | :--- |
| **Installazione** | Una riga su Debian/Ubuntu: scarica il repository in `/opt/Jarvis` e avvia il supervisore, che installa tutto il resto da solo. |
| **Supervisore** | Servizio `jarvis-supervisor` (Python, FastAPI). Esegue i passi d'installazione, controlla lo stato, ripara i guasti, si aggiorna da GitHub. |
| **Display** | Porta **80**: volto olografico 3D, voce, ascolto e desktop a widget. Il server stesso apre il display a schermo intero (kiosk). |
| **Pannello** | Porta **8080**: amministrazione completa, con accesso tramite gli utenti amministratori del sistema (PAM). |
| **Cervello** | Ollama locale, altri server Ollama o compatibili OpenAI, e 22 servizi cloud con la tua chiave, tutti mescolabili in liste di priorità. |
| **Funzionalità** | Oltre 35 cartelle in `installer_wizard/features/`, scoperte da sole. Ognuna si accende in automatico in base all'hardware (`auto`) e si può forzare (`1`/`0`). |
| **Aggiornamenti** | Ogni 5 minuti da `main`, solo per le versioni che hanno superato la CI, con collaudo e ritorno automatico alla versione precedente. |
| **Lingua** | Interfaccia e voce in italiano; Jarvis risponde nella lingua in cui gli si parla e scarica da solo le voci che gli mancano. |

---

## 2. Novità della versione 3

La versione 3 è una riscrittura organizzata **per funzionalità**: ogni capacità vive in una sola cartella
con codice Python, API, scheda del pannello e manifest. Le principali novità:

### Cervello
- **Liste di priorità miste** per ⚡ *Conversazione veloce* e 🧠 *Ragionamento*: modelli locali, modelli su
  altri server e servizi cloud nella stessa lista, ordinabili trascinando. Risponde il primo disponibile; se
  fallisce, Jarvis passa al successivo.
- **Altri server** (scheda «🖧 Altri server»): si aggiungono quanti server si vuole, Ollama o compatibili
  OpenAI (LM Studio, vLLM, LocalAI, llama.cpp). Ogni server mostra il proprio **catalogo dei modelli
  remoti**, aggiornato ogni 30 secondi, con i pulsanti **+ ⚡** e **+ 🧠**. Esempio: un PC con GPU per il
  ragionamento e un mini PC per le risposte veloci.
- **Server Ollama principale remoto**: con `JARVIS_OLLAMA_URL` tutto il motore neurale si sposta su un altro
  computer. Ollama locale viene fermato, sul server non si scarica nessun modello e i modelli degli altri
  programmi sul server remoto non vengono toccati.
- **22 servizi cloud** (OpenAI, Anthropic Claude, Google Gemini, xAI Grok, Mistral, DeepSeek, Groq, Cerebras,
  OpenRouter, Together, Fireworks, Perplexity, Cohere, Qwen, Moonshot Kimi, Zhipu GLM, NVIDIA NIM,
  Hugging Face, SambaNova, DeepInfra, Azure OpenAI, compatibile OpenAI) con elenchi di modelli reali,
  prezzi, contesto e chiavi cifrate sul disco.
- **Instradamento automatico** tra conversazione e ragionamento in base alla frase, con il cervello in uso
  sempre visibile e i tempi di ogni risposta.

### Assistente
- **Agente con strumenti**: file, widget, ologramma, modelli 3D, email con allegati, condivisioni SMB,
  terminale e web, con conferma a voce per le azioni delicate.
- **Automazioni a più stadi**: inneschi multipli, condizioni annidate, rami, attese, ripetizioni,
  parallelo, conferme a voce, variabili, webhook e traccia di ogni esecuzione. Si progettano anche a parole.
- **Autonomia**: compiti programmati a voce, autopilota ogni 30 minuti, approvazioni, riepilogo serale.
- **Abitudini**: Jarvis osserva come si usa la casa e propone le automazioni; segnala le situazioni insolite.
- **Mente**: valuta ogni scambio e decide cosa ricordare a lungo o breve termine.
- **Memoria in chiaro e diario**: la memoria in file Markdown leggibili e modificabili, con un diario per ogni
  giorno, nella cartella condivisa protetta (sottocartella «05 Memoria»).
- **Leggi**: quattro leggi fondamentali immutabili più le regole dell'utente, iniettate in ogni ragionamento; otto regole di comportamento predefinite, modificabili e inserite una sola volta.

### Percezione e display
- **Ologramma 3D** del volto in wireframe, con sguardo che segue la persona, emozioni, ballo con la musica e
  sfondo meteo; nucleo leggero sui dispositivi deboli.
- **Comandi con le mani** davanti alla webcam (pizzica, trascina, lancia, zoom a due mani), attivi solo se
  la GPU del display li regge.
- **Oltre 600 voci in più di 60 lingue** (Kokoro, Piper, voci online Microsoft Edge), con tono, velocità e
  volume.
- **Modelli 3D**: generazione da una frase e visualizzatore per decine di formati.
- **Telecamere** per nodo con registrazione ad anello, spenta di default e con consenso obbligatorio.

### Sistema
- **Collaudo**: 13 prove reali ogni notte e dopo ogni aggiornamento, con rollback automatico.
- **Condivisioni di rete Samba** compatibili con Windows 11.
- **Driver video NVIDIA** ufficiale per il display quando la scheda lo supporta, con ritorno automatico al
  driver libero in caso di problemi.
- **Nodi**: satelliti audio, display e altri server abbinati con codice monouso e token personale.

---

## 3. Requisiti

| Componente | Minimo | Consigliato |
| :--- | :--- | :--- |
| **Sistema operativo** | Debian 12 o Ubuntu 22.04+ (x86_64 o arm64) | Debian 12 minimale |
| **CPU** | 4 core | 8+ core con AVX2 |
| **RAM** | 8 GB | 16–32 GB |
| **GPU** | Nessuna (inferenza su CPU) | NVIDIA con 8 GB+ di VRAM |
| **Disco** | 30 GB | 100+ GB SSD/NVMe (modelli, voci, registrazioni) |
| **Rete** | Connessione a Internet per l'installazione | Rete cablata |
| **Periferiche** | — | Schermo, casse, microfono, webcam |

Note:
- Il bootstrap usa `apt-get`: **sono supportati solo Debian e Ubuntu** (e derivate).
- Senza GPU Jarvis sceglie modelli piccoli e veloci (vedi [§10](#10-il-cervello-modelli-locali-altri-server-e-cloud)).
- Con un server Ollama remoto o solo servizi cloud bastano anche macchine modeste.
- Le funzionalità che richiedono hardware (webcam, RAM, GPU) si spengono da sole se manca: vedi [§15](#15-configurazione-jarvisenv-e-modalità-auto10).

---

## 4. Installazione

### Una riga (consigliata)

```bash
curl -sL https://raw.githubusercontent.com/AprileNunzio/Jarvis/main/installer_wizard/bootstrap.sh | sudo bash
```

### Da una copia del repository

```bash
git clone https://github.com/AprileNunzio/Jarvis.git
cd Jarvis
sudo ./install.sh
```

`install.sh` avvia `installer_wizard/bootstrap.sh`, che in cinque fasi:

1. ripara `dpkg` e installa i prerequisiti minimi (`git`, `curl`, `python3`, `python3-venv`, `jq`);
2. clona o riallinea il repository in `/opt/Jarvis` (ramo `main`, modificabile con `JARVIS_BRANCH`);
3. crea `/etc/jarvis/jarvis.env` (permessi 600), il gruppo `jarvis-admin` e vi aggiunge l'utente che ha
   lanciato `sudo` (o il primo utente del sistema);
4. installa le unità `jarvis-supervisor` e `jarvis-rollback` ed esegue `scripts/os/prestart.sh`, che crea
   l'ambiente Python in `installer_wizard/venv` con `backend/requirements.txt` e il profilo PAM `jarvis-admin`;
5. avvia `jarvis-supervisor`, che da quel momento esegue tutti i passi d'installazione (vedi [§9](#9-passi-dinstallazione-step)),
   compreso `jarvisctl` in `/usr/local/bin` e le unità di voce, visione e ascolto.

Durante l'installazione lo schermo del server mostra l'avanzamento di ogni passo, con percentuale, velocità
e tempo stimato dei download. Il registro completo è in `/var/log/jarvis/install.log`:

```bash
jarvisctl logs install
```

Variabili utili per il bootstrap:

| Variabile | Predefinito | Uso |
| :--- | :--- | :--- |
| `JARVIS_REPO` | `https://github.com/AprileNunzio/Jarvis.git` | Repository da cui installare (per un fork) |
| `JARVIS_BRANCH` | `main` | Ramo da installare |

### Windows

`install.ps1` avvia il Core in locale per lo sviluppo; Jarvis OS completo (supervisore, display, voce) è
pensato per Debian/Ubuntu.

---

## 5. Primo avvio e accesso

| Indirizzo | Cosa mostra | Accesso |
| :--- | :--- | :--- |
| `http://<ip-del-server>/` | Display: volto 3D, voce, widget | Libero dalla rete di casa |
| `http://<ip-del-server>:8080/` | Pannello di amministrazione | Utente amministratore del sistema |

Al pannello si accede con un utente Linux che appartiene a uno dei gruppi `sudo`, `wheel` o `jarvis-admin`
(oppure `root`). La password è quella del sistema, verificata tramite PAM. Dopo 5 tentativi sbagliati in
5 minuti l'indirizzo viene bloccato temporaneamente. La sessione dura 12 ore.

L'utente che ha eseguito l'installazione con `sudo` è già nel gruppo `jarvis-admin`. Per aggiungerne altri:

```bash
sudo groupadd -f jarvis-admin
sudo usermod -aG jarvis-admin nomeutente
```

Primi passi consigliati nel pannello:

1. **Panoramica**: controllare che tutti i componenti siano verdi.
2. **Cervello**: verificare il modello in uso; aggiungere altri server o un servizio cloud se si vuole.
3. **Voci**: scegliere e ascoltare la voce preferita.
4. **Persone**: registrare il proprio volto e dire «impara la mia voce» davanti alla webcam.
5. **Casa**: inserire indirizzo e token di Home Assistant.
6. **Telegram**: collegare il bot per parlare con Jarvis da fuori casa.


---

## 6. Architettura

```text
                        ┌──────────────────────────────────────────────────────────┐
  Browser / kiosk  ───► │ :80   App pubblica  (display, voce, widget, nodi)        │
  Pannello admin   ───► │ :8080 App admin     (login PAM, configurazione, API)     │
                        │                                                          │
                        │        jarvis-supervisor  (Python 3, FastAPI, asyncio)   │
                        │  ┌───────────────┐ ┌──────────────┐ ┌─────────────────┐  │
                        │  │ Orchestratore │ │ Watchdog 15 s│ │ Updater 5 min   │  │
                        │  │ passi 10..95  │ │ auto-ripara  │ │ CI + rollback   │  │
                        │  └───────────────┘ └──────────────┘ └─────────────────┘  │
                        │  ┌────────────────────────────────────────────────────┐  │
                        │  │ features/<id>: chat, brain, cloud, voices, vision, │  │
                        │  │ ear, home_assistant, automations, autonomy, mind,  │  │
                        │  │ study, telegram, google, maps, desktop, nodes, …   │  │
                        │  └────────────────────────────────────────────────────┘  │
                        └───────┬───────────┬───────────┬───────────┬──────────────┘
                                │           │           │           │
              ┌─────────────────▼┐  ┌───────▼──────┐ ┌──▼──────────┐ ┌▼──────────────────┐
              │ Ollama :11434    │  │ jarvis-voice │ │jarvis-vision│ │ jarvis-ear :8093  │
              │ locale o remoto, │  │ Kokoro :8092 │ │ volti :8091 │ │ wake word + STT   │
              │ + altri server   │  └──────────────┘ └─────────────┘ └───────────────────┘
              └──────────────────┘
              ┌──────────────────────────────┐   ┌───────────────────────────────┐
              │ Docker: jarvis-core :8443    │   │ Servizi cloud (facoltativi)   │
              │         jarvis-qdrant :6333  │   │ OpenAI, Claude, Gemini, …     │
              └──────────────────────────────┘   └───────────────────────────────┘
```

### Componenti

| Componente | Dove | Ruolo |
| :--- | :--- | :--- |
| **Supervisore** | `installer_wizard/backend/` | Processo principale. Espone le due app web, esegue i passi d'installazione, controlla la salute dei componenti, aggiorna e ripara. |
| **Funzionalità** | `installer_wizard/features/<id>/` | Tutta la logica dell'assistente, una cartella per capacità. Girano dentro il supervisore come task asyncio. |
| **Servizi di percezione** | `features/voices/service.py`, `features/vision/service.py`, `features/ear/service.py` | Processi separati, ciascuno con il proprio ambiente Python (modelli pesanti), gestiti da systemd. |
| **Ollama** | servizio di sistema o server remoto | Modelli linguistici locali e modello di embedding. |
| **Jarvis Core** | `server/` in Docker | Orchestratore cognitivo: risponde alle conversazioni con i modelli Ollama, con prompt e strumenti propri. |
| **Qdrant** | Docker | Memoria vettoriale del Core. |
| **Display** | `installer_wizard/web/display/` | Pagina servita sulla porta 80 e aperta in kiosk da Chromium: volto 3D, voce, ascolto dal browser, widget. |
| **Pannello** | `installer_wizard/web/admin/` + `features/*/admin.*` | Guscio del pannello e schede delle funzionalità. |

### Percorso di una frase

1. L'utente dice «Ehi Jarvis, accendi la luce in cucina» (oppure scrive in chat, su Telegram o da un nodo).
2. `jarvis-ear` riconosce la parola di attivazione, pulisce l'audio e trascrive con faster-whisper;
   riconosce anche chi parla dall'impronta vocale.
3. Il supervisore riceve il testo (`/api/assistant/chat`) e lo passa, in ordine, a:
   - **intenti rapidi** (`features/chat/intents.py`, `features/chat/skills/`): casa, meteo, timer, widget,
     algoritmi, Google, mappe… rispondono in millisecondi senza modello linguistico;
   - **destinatario** (`features/chat/addressee.py`): nella conversazione continua decide se la frase era
     rivolta a Jarvis;
   - **cervello** (`features/brain/brains.py`): classifica la frase in *conversazione* o *ragionamento* e
     costruisce la catena dei modelli da provare;
   - **catena dei cervelli** (`features/chat/brain_chain.py`): i modelli del server Ollama principale passano
     dal Jarvis Core, quelli di altri server e del cloud dal client compatibile OpenAI/Anthropic
     (`features/cloud/client.py`).
4. Il contesto inviato al modello include leggi, persone presenti, dialogo recente, appunti di studio,
   memoria a lungo termine e lingua della risposta.
5. La risposta torna al display, che la pronuncia con la voce scelta (`/api/assistant/tts`) e apre i widget
   pertinenti; la Mente valuta lo scambio e decide cosa ricordare.

### Stati del sistema

| Fase | Significato |
| :--- | :--- |
| `INSTALLING` | Prima installazione: i passi vengono eseguiti uno dopo l'altro. |
| `BOOTING` | Avvio dopo un riavvio: ogni passo controlla di essere già a posto. |
| `UPDATING` | Verifica di una nuova versione appena scaricata. |
| `READY` | Tutto operativo. |
| `DEGRADED` | Funziona, ma un componente è guasto o in manutenzione: il watchdog sta intervenendo. |
| `ERROR` | Un passo critico è fallito: nuovo tentativo automatico con attesa crescente; nel frattempo il supervisore controlla se su GitHub esiste una correzione. |

---

## 7. Struttura del repository

```text
Jarvis/
├── install.sh                      # Avvia installer_wizard/bootstrap.sh (anche via curl)
├── install.ps1                     # Avvio del Core su Windows per sviluppo
├── installer_wizard/               # Jarvis OS
│   ├── bootstrap.sh                # Prima installazione su Debian/Ubuntu
│   ├── backend/                    # Nucleo del supervisore
│   │   ├── jarvis_supervisor.py    # Entry point (percorso fisso: lo usa l'unità systemd)
│   │   ├── config.py               # Percorsi, porte, jarvis.env, chiavi modificabili e segrete
│   │   ├── orchestrator.py         # Avvio, pipeline dei passi, convergenza
│   │   ├── steps.py                # Catalogo ed esecuzione dei passi d'installazione
│   │   ├── health.py               # Sonde dei componenti e watchdog che ripara
│   │   ├── updater.py              # Aggiornamenti da GitHub con verifica CI e rollback
│   │   ├── feature_registry.py     # Scoperta delle funzionalità, modalità auto/1/0, requisiti
│   │   ├── registry_api.py         # API delle funzionalità (/api/features)
│   │   ├── settings.py             # Applicazione della configurazione e passi da rieseguire
│   │   ├── system_api.py           # Login, stato, log, azioni, configurazione
│   │   ├── pages.py                # Pagine, file statici, schede e risorse delle funzionalità
│   │   ├── access.py · auth.py     # Controllo degli accessi e sessioni firmate
│   │   ├── sealed.py               # File cifrati (Fernet) per chiavi e token
│   │   ├── state.py · snapshot.py  # Stato condiviso, eventi e fotografia per /api/state
│   │   ├── core_client.py          # Client HTTP verso Jarvis Core
│   │   ├── sysinfo.py · tasks.py   # Informazioni di sistema, task in background
│   │   └── requirements.txt        # Dipendenze del supervisore
│   ├── features/<id>/              # Una cartella per funzionalità (vedi §11 e §23)
│   ├── widgets/<id>/               # Widget del display (vedi §24)
│   ├── skills/<categoria>/<id>/    # Algoritmi Python verificati (vedi §25)
│   ├── tests/                      # Test unitari e di API (unittest)
│   └── web/
│       ├── shared/                 # Stile, utilità e suoni comuni
│       ├── display/                # Display: volto 3D (scene/), voce, ascolto, mani, widget
│       ├── admin/                  # Guscio del pannello, ordinamento, impostazioni
│       ├── monitor/                # Schermata di installazione e avvio
│       └── screen/                 # Schermo secondario per i widget su più monitor
├── scripts/os/
│   ├── lib.sh                      # Funzioni comuni dei passi (progress, retry, apt, env, GPU…)
│   ├── steps/NN-nome.sh            # Passi idempotenti check/apply (vedi §9)
│   ├── systemd/                    # Unità: supervisor, rollback, voice, vision, ear
│   ├── kiosk/session.sh            # Sessione grafica del display
│   ├── prestart.sh                 # Ambiente Python e PAM prima di ogni avvio
│   ├── heal.sh                     # Riparazioni di sistema richiamate dal watchdog
│   ├── rollback.sh                 # Ritorno all'ultima versione buona dopo crash ripetuti
│   └── jarvisctl                   # Comando di gestione (vedi §21)
├── docker/                         # docker-compose: jarvis-core, jarvis-qdrant, jarvis-inference (GPU)
├── server/                         # Jarvis Core (vedi §28)
├── client_web/                     # Dashboard React + Three.js
├── client_apk/                     # Client Android (Kotlin)
├── client_satellite/               # Satelliti Linux ed ESP32
├── data/                           # Database e certificati del Core (contenuto non versionato)
├── .github/workflows/ci.yml        # Integrazione continua
└── LICENSE · SECURITY.md · CONTRIBUTING.md · CODE_OF_CONDUCT.md
```

Non vengono pubblicati (vedi `.gitignore`): ambienti Python, `__pycache__`, file di build, dati e modelli in
`data/`, appunti interni in `docs/`, cartelle degli strumenti di sviluppo con AI (`.claude/`, `.cursor/`…),
chiavi, vault, database e file di log.

---

## 8. Il supervisore

`installer_wizard/backend/jarvis_supervisor.py` compone **due applicazioni FastAPI** dagli stessi moduli:

- l'app **pubblica** (porta 80) include i router `public_routes` di ogni funzionalità e i file statici di
  `shared`, `display`, `monitor`, `screen`;
- l'app **admin** (porta 8080) include i router `admin_routes` e i file del pannello.

I moduli API delle funzionalità sono elencati in `FEATURE_APIS`; i loro task di lunga durata (bot Telegram,
esploratore di rete, studio, motore delle automazioni, collaudo, abitudini, memoria in chiaro, ecc.) vengono
avviati nella funzione `main()` insieme a:

| Task | Cosa fa |
| :--- | :--- |
| `orch.boot()` | Esegue la pipeline dei passi all'avvio; in caso di errore riprova con attesa crescente. |
| `health.Watchdog(orch).run()` | Ogni 15 secondi sonda i componenti (`docker`, `ollama`, `llm`, `core`, `qdrant`, `voice`, `vision`, `ear`, `kiosk`, `disk`) e interviene: riavvia servizi, rilancia passi, ricostruisce i container. Dopo troppi tentativi si ferma e lo segnala invece di insistere. |
| `updater.scheduler()` | Controlla GitHub ogni `JARVIS_UPDATE_INTERVAL_MIN` minuti (vedi [§19](#19-aggiornamenti-collaudo-e-rollback)). |
| `registry.run()` | Riesamina le funzionalità e i requisiti hardware. |
| `telemetry_loop()` | Aggiorna la telemetria per `/api/state` e il pannello. |

### Stato ed eventi

`state.py` contiene lo `store` condiviso: fase, avanzamento, componenti, passi, eventi
(`store.event(livello, messaggio, sorgente)`), stato degli aggiornamenti. È salvato in `/var/lib/jarvis/` e
pubblicato su:

- `GET /api/state` (porta 80, pubblico): fotografia sintetica, usata dal display, da `jarvisctl status` e
  per la diagnosi a distanza senza login;
- `GET /api/stream` (porta 8080): flusso in tempo reale per il pannello.

### Modalità demo

Con `JARVIS_DEMO=1` il supervisore gira su qualsiasi sistema (anche Windows) senza toccare la macchina:

- porte 8000 (display) e 8001 (pannello);
- cartelle in `<temp>/jarvis-demo/` invece di `/etc`, `/var/lib`, `/var/log`;
- login del pannello con utente `admin` e password `jarvis` (solo in demo);
- i passi d'installazione, Ollama, Docker e i servizi sono simulati; molte API restituiscono dati di esempio.

```bash
cd installer_wizard
python3 -m venv venv
venv/bin/pip install -r backend/requirements.txt
cd backend
JARVIS_DEMO=1 ../venv/bin/python jarvis_supervisor.py
```

Su Windows (PowerShell):

```powershell
cd installer_wizard
python -m venv venv
venv\Scripts\pip install -r backend\requirements.txt
cd backend
$env:JARVIS_DEMO = "1"; ..\venv\Scripts\python jarvis_supervisor.py
```

Poi aprire `http://localhost:8000/` (display) e `http://localhost:8001/` (pannello).

---

## 9. Passi d'installazione (step)

Ogni passo è uno script in `scripts/os/steps/` con due comandi:

- `check`: esce con 0 se il sistema è già nello stato voluto (deve essere veloce e senza effetti);
- `apply`: porta il sistema nello stato voluto; deve essere **idempotente**.

Il supervisore esegue `check` e, se fallisce, `apply` (fino a 3 tentativi), poi di nuovo `check`. I passi
non critici possono fallire senza bloccare Jarvis. Lo script comunica con il supervisore tramite righe
speciali su stdout (funzioni di `scripts/os/lib.sh`):

| Riga | Funzione | Effetto |
| :--- | :--- | :--- |
| `@@PROGRESS <0-100> <testo>` | `progress` | Avanzamento del passo e messaggio sul display |
| `@@DETAIL <testo>` | `detail` | Dettaglio (es. velocità e tempo stimato di un download) |
| `[INFO] …` · `[WARN] …` | `info` · `warn` | Registro |
| `[FAIL] …` | `fail` | Errore: il testo diventa il motivo mostrato all'utente; lo script esce con 1 |

Altre funzioni utili di `lib.sh`: `retry N attesa comando`, `wait_for secondi comando`, `apt_install`,
`set_env CHIAVE valore`, `write_if_changed file`, `same_content file`, `code_current`/`code_mark` (per
ricostruire solo se il codice è cambiato), `compose`, `has_usable_gpu`, `hw_profile`, `ollama_remote`.
`lib.sh` carica anche `/etc/jarvis/jarvis.env`, quindi ogni variabile di configurazione è disponibile.

| # | Passo | Script | Critico | Cosa fa |
| :--- | :--- | :--- | :---: | :--- |
| 1 | `preflight` | `10-preflight.sh` | sì | Analizza hardware e rete, sceglie i modelli adatti |
| 2 | `system` | `20-system.sh` | sì | Pacchetti di sistema, runtime, interfaccia grafica, audio |
| 3 | `kiosk` | `25-kiosk.sh` | no | Sessione kiosk dedicata (Chromium a schermo intero, avvio automatico) |
| 4 | `docker` | `30-docker.sh` | sì | Docker Engine |
| 5 | `display_driver` | `33-display-driver.sh` | no | Driver NVIDIA ufficiale se la scheda lo supporta (`nvidia-detect`), mai con Secure Boot; riavvio notturno o immediato; verifica dopo il riavvio e ritorno a `nouveau` se qualcosa non va |
| 6 | `gpu` | `35-gpu.sh` | no | Runtime NVIDIA per i container |
| 7 | `security` | `40-security.sh` | sì | Firewall `ufw` (aperte 22, 80, 8080 TCP e 50505, 51820 UDP; 8443 chiusa) e hardening del kernel (`sysctl`) |
| 8 | `ollama` | `50-ollama.sh` | sì | Ollama locale (in ascolto solo su 127.0.0.1) oppure verifica del server remoto e spegnimento di quello locale |
| 9 | `voice` | `55-voice.sh` | no | Sintesi vocale Kokoro e voci Piper |
| 10 | `bluetooth` | `56-bluetooth.sh` | no | Stack Bluetooth audio |
| 11 | `vision` | `57-vision.sh` | no | Servizio di riconoscimento facciale |
| 12 | `ear` | `58-ear.sh` | no | Servizio di ascolto (wake word, faster-whisper) |
| 13 | `music` | `59-music.sh` | no | Riconoscimento musicale |
| 14 | `shares` | `63-shares.sh` | no | Samba: un'unica cartella «condivisa» protetta da password, con le sottocartelle delle creazioni; sposta da solo i contenuti delle vecchie condivisioni |
| 15 | `convert3d` | `62-convert3d.sh` | no | Blender e LibreDWG per BLEND, USD, DWG |
| 16 | `models` | `60-models.sh` | sì | Scarica modello di ragionamento, modello veloce ed embedding (con server remoto non scarica nulla) |
| 17 | `soup` | `67-soup.sh` | no | Ambiente per il consolidamento dello studio nei pesi (solo con GPU adatta) |
| 18 | `core` | `70-core.sh` | sì | Compila l'immagine Docker di Jarvis Core (solo se il codice è cambiato) |
| 19 | `services` | `80-services.sh` | sì | Genera la chiave segreta del Core se manca e avvia Core e Qdrant con docker compose |
| 20 | `maintenance` | `90-maintenance.sh` | no | Aggiornamenti di sicurezza, rotazione dei log, `jarvisctl` |
| 21 | `warmup` | `95-warmup.sh` | sì | Carica in memoria il cervello principale e l'embedding; libera la memoria dai modelli non in uso (solo su Ollama locale) |

L'ordine di esecuzione è quello della lista `STEPS` in `backend/steps.py` (non quello numerico dei file).

Quando si cambia una configurazione dal pannello, `backend/settings.py` sa quali passi rieseguire
(`STEP_TRIGGERS`): per esempio cambiare `JARVIS_OLLAMA_URL` rilancia `ollama`, `models`, `warmup` e
`services`; cambiare la voce rilancia `voice`; cambiare `JARVIS_SHARES` rilancia `shares`. Anche il campo
`apply` dei manifest delle funzionalità indica quali passi rieseguire quando la funzionalità si accende o
si spegne.

---

## 10. Il cervello: modelli locali, altri server e cloud

### Due liste di priorità

Jarvis ha due liste, entrambe modificabili dal pannello (**Cervello**) trascinando gli elementi:

| Lista | Variabile | Usata per | Token massimi |
| :--- | :--- | :--- | :---: |
| ⚡ **Conversazione veloce** | `JARVIS_LLM_CHAT_ORDER` | saluti, domande brevi, chiacchiere | 320 |
| 🧠 **Ragionamento** | `JARVIS_LLM_DEEP_ORDER` | spiegazioni, analisi, codice, testi lunghi, calcoli, azioni | 1200 |

Se una lista è vuota è **automatica**: Jarvis usa `JARVIS_LLM_FAST_MODEL` / `JARVIS_LLM_MODEL`, a loro volta
scelti in base all'hardware se vuoti. Ogni lista può contenere elementi di tre tipi:

| Tipo | Formato del riferimento | Esempio |
| :--- | :--- | :--- |
| Modello sul server Ollama principale | `nome:tag` | `qwen2.5:7b` |
| Modello su un altro server | `cloud:srv-<id>/nome` | `cloud:srv-pc-studio/qwen2.5-coder:7b` |
| Modello di un servizio cloud | `cloud:<fornitore>/modello` | `cloud:anthropic/claude-sonnet-5-5` |

### Instradamento

`Brains.classify()` in `features/brain/brains.py` decide il tipo di frase:

- *conversazione*: saluti e frasi brevi («ciao», «grazie», «come stai», «ci sei»…);
- *ragionamento*: parole come «spiegami», «analizza», «confronta», «perché», «riassumi», «traduci», «scrivi
  un…», «codice», «calcola», «consigliami», «pro e contro»; testo lungo (oltre 220 caratteri); più domande
  insieme; codice o testo strutturato; operazioni aritmetiche.

`JARVIS_LLM_ROUTING` controlla il comportamento: `auto` usa due cervelli solo se il primo modello delle due
liste è diverso, `1` li usa sempre, `0` usa sempre il ragionamento. La catena finale è: la lista del tipo
scelto, poi l'altra lista, saltando i modelli non disponibili (non scaricati, chiave mancante, server
rimosso). Nel pannello si può scrivere una frase di prova e vedere quale cervello risponderebbe e in che
ordine verrebbero provati gli altri.

### Scelta automatica in base all'hardware

| Hardware | Ragionamento | Conversazione |
| :--- | :--- | :--- |
| GPU con 20 GB+ di VRAM | `qwen2.5:14b` | `qwen2.5:3b` |
| GPU con 8 GB+ o RAM 24 GB+ | `qwen2.5:7b` | `qwen2.5:3b` con GPU da 6 GB+, altrimenti `qwen2.5:1.5b` |
| RAM 7 GB+ | `qwen2.5:3b` | `qwen2.5:1.5b` (RAM 6 GB+) |
| Meno memoria | `qwen2.5:1.5b` | `qwen2.5:0.5b` |

Il catalogo locale (`CATALOG` in `features/brain/brains.py`) elenca 17 modelli con dimensione, ruoli
consigliati e note; il pannello stima la velocità su questa macchina (parole al secondo su GPU o CPU) e
segnala i modelli troppo grandi. I modelli installati a mano compaiono come «Installato manualmente».

### Server Ollama principale remoto

Nel pannello, **Cervello → Modelli locali → Server Ollama**, oppure con `JARVIS_OLLAMA_URL`:

- vuoto = Ollama su questo server (`127.0.0.1:11434`);
- un indirizzo (es. `192.168.1.50` o `http://192.168.1.50:11434`) = tutto il motore neurale su un altro
  computer. **Prova** controlla la connessione, **Salva** applica la scelta e riconfigura i servizi
  (il container `jarvis-core` viene ricreato, quindi Jarvis non risponde per qualche istante).

Con un server principale remoto:
- Ollama locale viene fermato e disattivato per liberare la memoria (i modelli già scaricati restano sul
  disco in `/usr/share/ollama`);
- il passo `models` non scarica nulla: si usano i modelli già presenti sul server remoto;
- il passo `warmup` usa il primo modello delle liste che esiste davvero sul server remoto e non toglie dalla
  memoria i modelli usati da altri programmi;
- se manca il modello di embedding (`nomic-embed-text`) la memoria semantica resta spenta con un avviso;
  si installa sul server remoto con `ollama pull nomic-embed-text`;
- il pulsante «Scarica» del catalogo scarica sul server remoto, mai su questo.

Sul server remoto Ollama deve ascoltare sulla rete, per esempio:

```bash
sudo systemctl edit ollama
# [Service]
# Environment="OLLAMA_HOST=0.0.0.0"
sudo systemctl restart ollama
```

### Altri server (quanti se ne vuole)

Pannello: **Cervello → Aggiungi cervelli → 🖧 Altri server**.

1. Nome (es. «PC studio»), tipo (*Ollama* oppure *Compatibile OpenAI*: LM Studio, vLLM, LocalAI,
   llama.cpp), indirizzo ed eventuale chiave.
2. **Prova** controlla che il server risponda ed elenca i modelli; **Aggiungi** lo salva (se non risponde si
   può salvare comunque).
3. Nel **Catalogo dei modelli remoti** ogni server mostra stato («raggiungibile» / «non risponde»), modelli e
   l'ora dell'ultimo aggiornamento; l'elenco si aggiorna da solo ogni 30 secondi. **+ ⚡** e **+ 🧠** mettono
   un modello in testa alla lista corrispondente.

Esempi d'uso:
- un PC con GPU per il 🧠 ragionamento e un mini PC sempre acceso per le ⚡ risposte veloci;
- un server LM Studio in ufficio come riserva in coda alle liste;
- modelli locali, altri server e un servizio cloud nella stessa lista, con il cloud come ultima risorsa.

Dettagli tecnici:
- ogni server è salvato nel vault cifrato (`/etc/jarvis/cloud.vault`) con id `srv-<nome>` ed è registrato a
  runtime come fornitore compatibile OpenAI (`sync_servers` in `features/cloud/catalog.py`);
- per Ollama si usa l'endpoint compatibile OpenAI `http://host:11434/v1` (`/v1/models`,
  `/v1/chat/completions`); per gli altri l'indirizzo indicato, completato con `/v1`;
- le risposte passano per `features/cloud/client.py` come per i servizi cloud, quindi valgono fallback,
  statistiche, tempi e la persona di Jarvis (`features/cloud/conversation.py`);
- rimuovendo un server, i suoi modelli escono anche dalle liste;
- codice: `features/cloud/servers.py` (prova, catalogo), `features/cloud/api.py` (rotte),
  `features/brain/admin-servers.js` (scheda).

### Servizi cloud

Pannello: **🔑 Servizi cloud**. Per ogni fornitore si incolla la chiave, si sceglie il modello (elenco reale
dal fornitore, altrimenti da un catalogo pubblico con prezzi e contesto) e si regolano creatività, top‑p,
lunghezza massima, ragionamento e attesa. **Prova** invia una frase di test; **+ ⚡ / + 🧠** aggiunge il
modello alle liste. «Usa solo il cloud» configura Jarvis senza modelli locali.

| Fornitore | Note |
| :--- | :--- |
| OpenAI | GPT e modelli di ragionamento o-series |
| Anthropic Claude | API nativa, ragionamento esteso facoltativo |
| Google Gemini | Endpoint compatibile OpenAI di Google |
| xAI Grok · Mistral · DeepSeek · Groq · Cerebras | Compatibili OpenAI |
| OpenRouter | Una chiave per centinaia di modelli |
| Together · Fireworks · DeepInfra · SambaNova · NVIDIA NIM · Hugging Face | Modelli open ospitati |
| Perplexity | Risposte con ricerca web |
| Cohere · Qwen (DashScope) · Moonshot Kimi · Zhipu GLM | Compatibili OpenAI |
| Azure OpenAI | Richiede l'indirizzo della risorsa |
| Compatibile OpenAI | Un singolo server con `/v1/chat/completions` (per più server usare «Altri server») |

Le chiavi sono cifrate in `/etc/jarvis/cloud.vault` con la chiave `/etc/jarvis/cloud.key` (permessi 600) e
non escono mai dal server; il pannello mostra solo le ultime quattro cifre. `GEMINI_API_KEY` e
`ANTHROPIC_API_KEY` presenti in `jarvis.env` vengono importate nel vault al primo avvio.

### Modelli in memoria

`features/brain/residency.py` tiene in memoria per 24 ore solo il primo modello del server principale
presente nelle liste e il modello di embedding; gli altri restano 5 minuti dopo l'uso. Su un server Ollama
principale remoto Jarvis non toglie dalla memoria i modelli altrui.

### Funzioni che usano il cervello

Oltre alla conversazione, il cervello viene usato da: estrazione dei fatti della Mente, progettazione delle
automazioni a parole, scrittura di nuovi algoritmi, studio autonomo, agente con strumenti, comprensione dei
comandi della casa non riconosciuti dalle regole. Tutte passano per `features/brain/llm.py`
(`generate()`), che applica le leggi, la catena dei modelli e il fallback. La visione (oggetti in mano,
etichette, riparazione guidata) usa un modello che vede (`features/brain/sight.py`).

---

## 11. Catalogo delle funzionalità

Ogni funzionalità è una cartella in `installer_wizard/features/`. Il pannello (**Funzionalità**) le mostra
raggruppate per categoria, con lo stato, i requisiti e un interruttore a tre posizioni (vedi [§15](#15-configurazione-jarvisenv-e-modalità-auto10)).

### Assistente

| Funzionalità | Cartella | Cosa fa |
| :--- | :--- | :--- |
| ✉ **Parla con Jarvis** | `chat` | Conversazione testuale e vocale, intenti rapidi, scelta del destinatario («stai parlando con me?»), dialogo continuo, lingua della risposta. Soglie: `JARVIS_ADDRESSEE_THRESHOLD`, `JARVIS_ADDRESSEE_ALONE`. |
| ✦ **Cervello** | `brain`, `cloud` | Modelli locali, altri server, servizi cloud, liste di priorità, instradamento (vedi [§10](#10-il-cervello-modelli-locali-altri-server-e-cloud)). |
| ⚙ **Azioni** | `actions` | Esegue davvero: crea file e siti web pubblicati sulla rete di casa (`/siti/<nome>`), cartelle SMB, trova dispositivi e IP, test di velocità, aggiornamenti, programmi, calcoli verificati; diagnosi con comandi di sola lettura quando manca un'abilità. |
| 🛠 **Agente con strumenti** | `agent` | Ragiona passo per passo e usa strumenti veri finché il compito è finito («creami un martello in 3D e mandalo per email a Marco»): file (le cancellazioni vanno nel cestino), widget, ologramma, modelli 3D, email con allegati (Gmail o SMTP), SMB, terminale, web. Conferma a voce prima di email, cancellazioni e comandi che modificano il sistema. Livello `JARVIS_AGENT_ACCESS`: `completo` o `standard` (solo `/srv/jarvis` e modelli 3D). |
| ⚙️ **Automazioni** | `automations` | Motore a più stadi: inneschi (orari, intervalli, alba/tramonto, stati dei dispositivi con soglie e durata, presenze, frasi dette, eventi, espressioni, webhook), condizioni annidate E/O/NON, azioni (Home Assistant, voce, notifiche, widget, ologramma, suoni, agente, email, richieste web), se/altrimenti, scelta tra casi, parallelo, ripetizioni, attese, conferme sì/no, variabili ed espressioni `{{ … }}`, modalità singola/riavvia/coda/parallela. Progettazione a parole, modelli pronti, importa/esporta, storico con traccia di ogni passo. |
| 🧭 **Autonomia** | `autonomy` | Compiti programmati a voce («ogni mattina alle 8 mandami il meteo per email»), autopilota ogni 30 minuti (diagnosi, studio delle richieste non soddisfatte, riepilogo serale), approvazioni per le azioni delicate, diario. |
| 🧠 **Mente** | `mind` | Valuta ogni frase (pertinenza, importanza, memorabilità, fiducia), decide cosa tenere a lungo o breve termine, suggerisce widget e algoritmi, manda spunti allo studio. |
| ⚖ **Leggi** | `laws` | Quattro leggi fondamentali immutabili (Zero, Prima, Seconda, Terza) e regole personali, iniettate in testa a ogni ragionamento locale e cloud, anche degli agenti e dei nodi. Al primo avvio vengono aggiunte otto regole di comportamento in stile J.A.R.V.I.S. (tono formale, niente preamboli, umorismo britannico asciutto, avvisi sui rischi senza allarmismi, codice senza commenti, lealtà): sono normali regole personali, modificabili e cancellabili, e vengono inserite **una sola volta** (`/var/lib/jarvis/laws/seeded.json`), quindi gli aggiornamenti non le reinseriscono né le sovrascrivono. |
| 🗣 **Voci** | `voices` | Oltre 600 voci in più di 60 lingue: Kokoro (9 lingue), catalogo Piper, voci online Microsoft Edge; voce preferita per lingua, ordine di priorità, anteprima, download automatico delle lingue nuove; velocità, tono e volume. |
| 🧑 **Aspetto** | `appearance` | Ologramma 3D del volto o nucleo leggero (`JARVIS_AVATAR`), colore (`JARVIS_FACE_COLOR`). |
| ▣ **Desktop a widget** | `desktop` | Il display come desktop: widget indipendenti con priorità, allarmi a schermo intero, prova dal pannello, più monitor (vedi [§12](#12-display-widget-e-ologramma)). |
| 🧊 **Modelli 3D** | `models3d` | Genera oggetti 3D da una frase (GLB a colori, STL in millimetri per la stampa, OBJ) e apre glTF/GLB, OBJ, STL, 3MF, AMF, PLY, FBX, DAE, 3DS, VRML, DXF, STEP, IGES, BREP; BLEND, USD e DWG con conversione sul server. |
| 🎵 **Suoni ed effetti** | `sounds` | Effetti di attivazione, attesa ed elaborazione, notifiche, allarmi, sottofondi (reattore, spazio, pioggia, onde, laboratorio), orari di silenzio e «non disturbare», tre temi sintetizzati dal vivo. |
| 🗺️ **Maps** | `maps` | Indicazioni stradali con mappa e percorso disegnato, tempi con traffico (chiave Google Maps) o OpenStreetMap, luoghi salvati a voce, tragitto per il lavoro al mattino, avvisi di partenza per gli appuntamenti. |

### Percezione

| Funzionalità | Cartella | Cosa fa |
| :--- | :--- | :--- |
| 🎙 **Ascolto vocale** | `ear` | «Jarvis» o «Ehi Jarvis», ascolto offline con riduzione del rumore e autolivellamento per il campo lontano, trascrizione faster-whisper adattata all'hardware, conversazione continua, impronta vocale di ogni persona, riconoscimento della lingua. Richiede 3 GB di RAM. |
| 👁 **Visione e volti** | `vision` | Riconoscimento facciale offline, presenze in tempo reale, ospiti registrati da soli, filtro dei riflessi, oggetti in mano, lettura di etichette, riparazione guidata via webcam con i cervelli che vedono. Richiede webcam e 2 GB di RAM. |
| ✋ **Comandi con le mani** | `hands` | Pizzica, trascina, lancia tra i monitor, zoom a due mani. In automatico solo se la GPU del display regge l'analisi entro `JARVIS_HANDS_MAX_MS`. |
| 🎵 **Riconoscimento musicale** | `music` | Brano in ascolto con titolo, artista, album e biografia; storico (invia 10 secondi di audio al servizio di riconoscimento). |
| 🔊 **Audio del display** | `devices` | Casse, cuffie e microfoni del display: dispositivo in uso, volume, muto, profili. |
| ᛒ **Bluetooth** | `bluetooth` | Abbinamento, ordine di preferenza per uscita e microfono, profilo, riconnessione automatica. |
| 📍 **Posizione** | `location` | GPS del telefono via Telegram, display, Wi-Fi e access point (BeaconDB), posizione detta a voce; l'IP solo come ultima risorsa. |
| 📹 **Telecamere** | `cameras` | Webcam o telecamere di rete (RTSP, ONVIF, Hikvision) per nodo, registrazione ad anello (5/15/60 minuti), credenziali cifrate. **Spenta di default**, consenso obbligatorio e indicatore di registrazione. |

### Casa

| Funzionalità | Cartella | Cosa fa |
| :--- | :--- | :--- |
| 🏠 **Casa (Home Assistant)** | `home_assistant` | Studia stanze, piani e dispositivi (Zigbee, Thread, Matter, Wi-Fi, Z-Wave, Bluetooth) via WebSocket, li tiene in un database SQLite locale aggiornato in tempo reale, li comanda a voce in millisecondi, sa dove c'è movimento o presenza, chiede conferma per serrature, allarme, cancelli e garage, impara le frasi nuove. |
| 💡 **Abitudini** | `habits` | Registra i comandi dati a mano, trova ogni notte le regolarità (stesso orario, tramonto, arrivo di qualcuno) e le propone a voce come automazioni; segnala porte, finestre o movimenti insoliti a casa vuota. |
| ☺ **Persone** | `people` | Anagrafe: volti, relazioni, compleanni e onomastici, preferenze, abitudini, impronta vocale. |
| 📡 **Esploratore della rete** | `network` | Scansione `nmap` ogni 10 minuti, tipo di dispositivo, nuovi dispositivi segnalati. |

### Conoscenza

| Funzionalità | Cartella | Cosa fa |
| :--- | :--- | :--- |
| 🎓 **Studio autonomo** | `study` | A riposo studia le materie scelte o scoperte dalle conversazioni, da fonti reali, con esercizi pratici, ripasso ed esami di livello; usa gli appunti nelle risposte. |
| 🧬 **Consolidamento (Soup)** | `soup` | Di notte addestra un modello personale (LoRA) dagli appunti e lo pubblica in Ollama come «jarvis-studio». Sperimentale: GPU con 4 GB+ e 8 GB di RAM. |
| ∑ **Algoritmi** | `skills` | Calcoli, conversioni e procedure come algoritmi Python verificati; Jarvis ne scrive di nuovi, li prova in isolamento e li riusa in millisecondi (vedi [§13](#13-algoritmi-skills)). |
| 📓 **Memoria in chiaro e diario** | `vault` | Memoria in file Markdown nella cartella condivisa, «05 Memoria»: `Persone/<Nome>.md`, `Memoria/Fatti generali.md`, `Casa/Abitudini.md`, `Automazioni.md`, `Diario/AAAA/MM/AAAA-MM-GG.md`. Le modifiche fatte nei file tornano nella memoria. |

### Comunicazione

| Funzionalità | Cartella | Cosa fa |
| :--- | :--- | :--- |
| ✈ **Telegram** | `telegram` | Abbinamento con codice, chat testo e voce, foto, notifiche di arrivi, guasti e ricorrenze, comandi di gestione. |
| 🟦 **Google** | `google` | Un account per persona (token cifrati): Calendar, Gmail, Tasks, Contatti, Drive, Keep; dati mostrati solo a chi Jarvis riconosce; promemoria prima degli appuntamenti. |
| 🎧 **Spotify** | `spotify` | Brano in riproduzione come widget, quando ti vede o sempre. |

### Sistema

| Funzionalità | Cartella | Cosa fa |
| :--- | :--- | :--- |
| 🖥 **Display** | `kiosk` | Chromium dedicato a schermo intero, riavvio automatico, driver video NVIDIA con verifica. |
| ⟳ **Aggiornamenti automatici** | `auto_update` | Aggiornamenti da GitHub con verifica e rollback (vedi [§19](#19-aggiornamenti-collaudo-e-rollback)). |
| 🧪 **Collaudo** | `selftest` | 13 prove reali ogni notte (03:30) e dopo ogni aggiornamento; rollback se una prova essenziale si rompe; «fai il collaudo» a voce. |
| 🗂 **Cartella condivisa** | `shares` | Un'unica cartella Samba `\\IP\condivisa`, protetta dall'utente `jarvis-share` e password, compatibile con Windows 11. Contiene tutte le creazioni di Jarvis in sottocartelle numerate, con nomi che iniziano per data inversa (vedi [§17](#17-porte-servizi-e-file-sul-disco)). |
| 🖧 **Nodi e server** | `nodes` | Server principale e nodi (satelliti, display, altri server, microcontrollori): abbinamento sicuro, stato, comandi, revoca (vedi [§14](#14-nodi-e-satelliti)). |

---

## 12. Display, widget e ologramma

Il display (`installer_wizard/web/display/`) è la pagina servita su `http://<server>/` e aperta in kiosk dal
server stesso. Può essere aperta anche da altri dispositivi della rete (tablet, PC, TV).

| File | Ruolo |
| :--- | :--- |
| `display.html` · `display.js` · `display.css` | Pagina e avvio |
| `scene/` · `scene/holo/` | Ologramma 3D (Three.js): `HoloAvatar.js`, `Director.js`, rig, animazioni, azioni, accessori, inquadrature |
| `avatar.js` · `look.js` · `mood.js` | Scelta dell'aspetto, sguardo che segue la persona, emozioni |
| `voice.js` · `ear.js` · `chat.js` | Voce, ascolto dal browser, conversazione |
| `desk.js` · `stage*.js` | Desktop a widget, palco centrale, schede Google e visione |
| `hands.js` · `perf.js` | Comandi con le mani e misura delle prestazioni del dispositivo |
| `sounds.js` · `ambient.js` | Effetti e sottofondi sintetizzati con Web Audio |
| `enroll.js` | Registrazione guidata della voce («impara la mia voce») |
| `audio_panel.js` | Scelta e volume dei dispositivi audio |

### Ologramma

- Volto wireframe olografico ricostruito dal modello `head.glb`, riempimento scuro, iride, colore
  personalizzabile.
- Segue lo sguardo della persona inquadrata dalla webcam; a riposo ruota mostrando profilo e busto.
- Emozioni richiamabili (sorriso, triste, piange, disaccordo, sorpresa) con ritorno automatico; usate anche
  dall'agente e dalle automazioni (`/api/holo_action`).
- Balla a ritmo con la musica, sfondo con il meteo del giorno.
- Sui dispositivi deboli (`JARVIS_AVATAR=auto`) si passa al **nucleo leggero**.

### Desktop a widget

Ogni informazione è un widget indipendente in `installer_wizard/widgets/<id>/` (oppure
`/var/lib/jarvis/widgets/<id>/` per quelli aggiunti dall'utente o da Jarvis). Il supervisore li scopre da
solo; il pannello (**Widget**) permette di cambiarne priorità, abilitarli e provarli con dati di esempio.

Widget inclusi (46): `active_tasks`, `alarm`, `alert_error`, `alert_info`, `alert_warning`, `api_costs`,
`audio_spectrum`, `cam_stream`, `cicd_tracker`, `clipboard_sync`, `code_view`, `contact_card`,
`context_window`, `crypto_ticker`, `cyber_alert`, `docker_matrix`, `document_viewer`, `energy_chart`,
`firewall_logs`, `g_notify`, `git_diff`, `kanban_board`, `karaoke`, `lan_device`, `listening`, `music`,
`net_topology`, `notice`, `os_networks`, `pomodoro`, `port_scanner`, `rag_sources`, `reminder`, `route`,
`spotify`, `ssh_sessions`, `study`, `system_monitor`, `text_long`, `text_short`, `thermostat`,
`thinking_tree`, `usb_monitor`, `viewer_3d`, `vram_allocator`, `weather`.

Comportamento:
- un widget compare quando serve (una domanda sul meteo, un brano in ascolto, un allarme) e scompare dopo il
  suo `ttl`; i widget con priorità più alta stanno al centro;
- widget senza bordi; posizionamento libero trascinando, doppio tocco per liberarlo;
- con più monitor (`/screen`) i widget si spostano tra gli schermi, anche con un lancio della mano;
- dopo un minuto di inattività il display torna alla vista di riposo.

### Più schermi

`http://<server>/screen` apre uno schermo secondario che mostra solo widget. Ogni schermo si presenta al
supervisore (`/api/desk/hello`) con dimensioni e posizione, così i widget possono essere spostati tra
monitor.

---

## 13. Algoritmi (skills)

Gli algoritmi sono piccoli programmi Python verificati che rispondono in millisecondi senza modello
linguistico: calcolatrice, percentuali e IVA, interesse composto, conversioni di unità, differenze tra date.

| Cartella | Contenuto |
| :--- | :--- |
| `installer_wizard/skills/<categoria>/<id>/` | Algoritmi di sistema (arrivano con gli aggiornamenti) |
| `/var/lib/jarvis/skills/<categoria>/<id>/` | Algoritmi scritti da Jarvis o dall'utente |

Categorie: `matematica`, `unita`, `date`, `finanza`, `testo`, `casa`, `altro`.

Ogni algoritmo ha:
- `skill.json`: `id`, `name`, `description`, `priority`, `patterns` (espressioni regolari che lo attivano),
  `examples`;
- `main.py`: una funzione `run(text: str) -> dict` che restituisce `{"ok": True, "result": …, "speech": "…"}`
  oppure `{"ok": False, "error": "…"}`.

Sicurezza dell'esecuzione (`features/skills/library.py`, `features/skills/worker.py`):
- il codice viene analizzato prima dell'uso: sono ammessi solo moduli come `math`, `statistics`,
  `fractions`, `decimal`, `datetime`, `re`, `json`, `itertools`…; sono vietati `open`, `exec`, `eval`,
  `__import__`, `getattr` e simili;
- gira in un processo separato (`python -I`) con memoria limitata a 768 MB, al massimo 32 file aperti e
  4 secondi per risposta;
- con `JARVIS_SKILLS_GENERATE=1` Jarvis scrive un nuovo algoritmo quando serve, lo prova sugli esempi e lo
  salva solo se funziona.

---

## 14. Nodi e satelliti

Un **nodo** è un altro dispositivo che lavora con Jarvis: satellite audio in un'altra stanza, display,
altro server Jarvis, microcontrollore, Android, sensore.

| Tipo | Valore |
| :--- | :--- |
| Satellite audio | `satellite` |
| Display | `display` |
| Server Jarvis | `server` |
| Microcontrollore | `esp32` |
| Android | `android` |
| Sensore | `sensor` |
| Altro | `other` |

### Abbinamento

Due modi:

1. **Codice monouso**: nel pannello **Nodi** si genera un codice di 6 cifre valido 10 minuti; sul dispositivo:

   ```bash
   curl -fsSL http://<server>/nodes/agent.py -o satellite.py
   python3 satellite.py --server http://<server> --code 123456 --name cucina --room Cucina --install
   ```

2. **Richiesta dalla rete**: `python3 satellite.py --join --install` cerca Jarvis in rete (UDP, porta 50505)
   e invia una richiesta che si approva dal pannello.

Il server consegna un **token personale** (conservato solo come hash SHA-256); il nodo invia un battito ogni
30 secondi con stato e risorse. Dal pannello si possono rinominare i nodi, assegnarli a una stanza, dare
impostazioni proprie (le chiavi non segrete di `jarvis.env` possono avere un valore per nodo), inviare
comandi (`identify`, `restart`, `update`, `reboot`) e revocarli: il token smette subito di valere.

Opzioni dell'agente (`client_satellite/linux_edge/satellite.py`): `--server`, `--code`, `--name`, `--room`,
`--type`, `--install` (servizio di sistema), `--join`. La configurazione è in
`~/.config/jarvis-node.json` (o `JARVIS_NODE_CONFIG`).

---

## 15. Configurazione: jarvis.env e modalità auto/1/0

Tutta la configurazione è in **`/etc/jarvis/jarvis.env`** (permessi 600), una riga `CHIAVE=valore` per
impostazione. Si modifica dal pannello (consigliato: sa quali passi rieseguire) oppure a mano, seguito da
`jarvisctl repair`.

Principi:
- **ogni funzionalità è offerta a tutti**: quelle con interruttore hanno tre modalità;
  - `auto` (predefinita): accesa se l'hardware soddisfa i requisiti (`requires` nel manifest: RAM, VRAM,
    webcam, comandi, altre funzionalità, variabili necessarie) e riaccesa da sola quando l'hardware cambia;
  - `1`: sempre accesa, anche senza i requisiti (il pannello mostra cosa manca);
  - `0`: spenta;
- le chiavi segrete (password, token, chiavi API) non vengono mai mostrate dal pannello;
- le chiavi dei servizi cloud e degli altri server stanno nel vault cifrato, non in `jarvis.env`;
- i nodi possono avere valori propri per le chiavi non segrete (vedi [§14](#14-nodi-e-satelliti)).

Lo stato delle modalità delle funzionalità e le loro impostazioni non globali sono in
`/var/lib/jarvis/features.json`.

---

## 16. Riferimento delle variabili

Elenco generato da `EDITABLE_KEYS` e `SECRET_KEYS` in `installer_wizard/backend/config.py` e dai manifest
delle funzionalità. **Segreta** = non viene mai mostrata dal pannello. **Per nodo** = un nodo può avere un
valore proprio.

| Variabile | Descrizione | Predefinito | Segreta | Per nodo |
| :--- | :--- | :--- | :---: | :---: |
| `JARVIS_LLM_MODEL` | Cervello potente: modello per il ragionamento (Ollama; vuoto = automatico) |  |  | sì |
| `JARVIS_LLM_FAST_MODEL` | Cervello veloce: modello per la conversazione (Ollama; vuoto = automatico) |  |  | sì |
| `JARVIS_LLM_ROUTING` | Instradamento tra cervello veloce e potente (auto, 1 = sempre, 0 = un solo cervello) |  |  | sì |
| `JARVIS_LLM_CHAT_ORDER` | Priorità dei modelli per la conversazione (separati da virgola; vuoto = automatico) |  |  | sì |
| `JARVIS_LLM_DEEP_ORDER` | Priorità dei modelli per il ragionamento (separati da virgola; vuoto = automatico) |  |  | sì |
| `JARVIS_EMBED_MODEL` | Modello di embedding (Ollama) |  |  | sì |
| `JARVIS_OLLAMA_URL` | Server Ollama (vuoto = locale; es. http://192.168.1.50:11434 per usare un altro server) |  |  | sì |
| `JARVIS_ASSISTANT_NAME` | Nome dell'assistente (predefinito J.A.R.V.I.S.) |  |  | sì |
| `JARVIS_USER_NAME` | Nome dell'utente principale (come Jarvis ti chiama) |  |  | sì |
| `JARVIS_LOCATION` | Posizione predefinita (nome; si imposta meglio da Audio e posizione) |  |  | sì |
| `JARVIS_LOCATION_MODE` | Posizione: auto (display/Wi-Fi più precisi) o fixed (sempre la predefinita) |  |  | sì |
| `JARVIS_LOCATION_LAT` | Latitudine della posizione predefinita |  |  | sì |
| `JARVIS_LOCATION_LON` | Longitudine della posizione predefinita |  |  | sì |
| `JARVIS_MUSIC_ID` | Riconoscimento della musica in ascolto (1/0; invia 10 s di audio al servizio di riconoscimento) | `auto` |  | sì |
| `JARVIS_STUDY_FINETUNE` | Consolidamento dello studio nei pesi con Soup (auto = deciso dall'hardware, 1 = sempre, 0 = mai) | `auto` |  | sì |
| `JARVIS_STUDY_BASE_MODEL` | Modello base per Soup (Hugging Face, es. Qwen/Qwen2.5-1.5B-Instruct) |  |  | sì |
| `JARVIS_VOICE` | Voce principale (es. im_nicola, it-IT-DiegoNeural, it_IT-serena-high; si gestisce da Voci) |  |  | sì |
| `JARVIS_VOICE_ORDER` | Priorità delle voci (separate da virgola; si gestisce meglio da Voci) |  |  | sì |
| `JARVIS_VOICE_SPEED` | Velocità della voce (0.6 - 1.6) | `1.0` |  | sì |
| `JARVIS_CAMERAS` | Telecamere e registrazione ad anello (1/0, spento di default) | `0` |  | sì |
| `JARVIS_ADDRESSEE_THRESHOLD` | Soglia per decidere se gli stai parlando (0.2 - 0.95) | `0.5` |  | sì |
| `JARVIS_ADDRESSEE_ALONE` | Fiducia aggiuntiva quando sei solo nella stanza (0 - 1) | `0.35` |  | sì |
| `JARVIS_VOICE_PITCH` | Tono della voce in semitoni (-6 grave, +6 acuto) | `0` |  | sì |
| `JARVIS_VOICE_VOLUME` | Volume della voce (0.4 - 2.0) | `1.0` |  | sì |
| `JARVIS_VOICE_LANG` | Voce preferita per ogni lingua (es. en:am_michael,de:de_DE-thorsten-medium; si gestisce da Voci) |  |  | sì |
| `JARVIS_VOICE_ONLINE` | Voci neurali online (auto = se disponibili, 1 = sì, 0 = mai: il testo non esce dal server) | `auto` |  | sì |
| `JARVIS_VOICE_AUTO_DOWNLOAD` | Scarica da solo la voce di una lingua nuova quando serve (1/0) | `1` |  | sì |
| `JARVIS_EAR_MULTILANG` | Riconosce la lingua in cui parli (1/0; 0 = ascolta solo l'italiano) | `1` |  | sì |
| `JARVIS_VISION` | Webcam e riconoscimento facciale (1/0) | `auto` |  | sì |
| `JARVIS_EAR` | Ascolto vocale con parola "Jarvis" (1/0) | `auto` |  | sì |
| `JARVIS_STT_MODEL` | Modello di ascolto (vuoto = automatico; base, small, medium) |  |  | sì |
| `JARVIS_EAR_MAX_GAIN` | Amplificazione massima del microfono per il campo lontano (2 - 80) | `30` |  | sì |
| `JARVIS_EAR_TARGET_RMS` | Livello vocale obiettivo dell'autolivellamento (0.03 - 0.2) | `0.08` |  | sì |
| `JARVIS_AVATAR` | Aspetto dell'assistente (auto = in base al dispositivo, full = ologramma 3D con volto, light = nucleo leggero) | `auto` |  | sì |
| `JARVIS_FACE_COLOR` | Colore dell'ologramma (colore, es. #29e0ff) |  |  | sì |
| `JARVIS_AUTO_UPDATE` | Aggiornamenti automatici (1/0) | `auto` |  |  |
| `JARVIS_UPDATE_INTERVAL_MIN` | Controllo aggiornamenti ogni N minuti (default 5) | `5` |  |  |
| `JARVIS_UPDATE_BRANCH` | Ramo GitHub | `main` |  |  |
| `JARVIS_KIOSK` | Display kiosk (1/0) | `auto` |  | sì |
| `JARVIS_SECRET_KEY` | Chiave che firma i token del Jarvis Core (generata dal passo `services`) |  | sì |  |
| `GEMINI_API_KEY` | API key Google Gemini (fallback) |  | sì |  |
| `ANTHROPIC_API_KEY` | API key Anthropic Claude (fallback) |  | sì |  |
| `JARVIS_TELEGRAM_TOKEN` | Token del bot Telegram (da @BotFather) |  | sì |  |
| `JARVIS_TELEGRAM` | Bot Telegram attivo (1/0) | `auto` |  |  |
| `JARVIS_NETWORK` | Esploratore della rete locale (1/0) | `auto` |  | sì |
| `JARVIS_SPOTIFY` | Spotify attivo (1/0) | `auto` |  | sì |
| `JARVIS_SPOTIFY_CLIENT_ID` | Spotify: Client ID dell'app (developer.spotify.com) |  |  |  |
| `JARVIS_SPOTIFY_CLIENT_SECRET` | Spotify: Client Secret dell'app |  | sì |  |
| `JARVIS_SPOTIFY_WHEN` | Spotify: quando mostrare il brano (present = se ti vede, always = sempre) | `present` |  | sì |
| `JARVIS_GOOGLE` | Google: connettori Calendar, Gmail, Tasks, Contatti, Drive, Keep attivi (1/0) | `auto` |  | sì |
| `JARVIS_GOOGLE_CLIENT_ID` | Google: Client ID OAuth (App desktop, console.cloud.google.com) |  |  |  |
| `JARVIS_GOOGLE_CLIENT_SECRET` | Google: Client Secret OAuth |  | sì |  |
| `JARVIS_GOOGLE_SERVICES` | Google: servizi da collegare (calendar,gmail,tasks,contacts,drive,keep) |  |  | sì |
| `JARVIS_GOOGLE_REMIND_MIN` | Google: avviso sul display N minuti prima di ogni appuntamento (0 = mai) | `10` |  | sì |
| `JARVIS_MAPS` | Maps: indicazioni, tempi e avvisi di viaggio (1/0) | `auto` |  | sì |
| `JARVIS_MAPS_API_KEY` | Maps: chiave Google Maps Platform (Routes API) per traffico e mezzi; vuota = OpenStreetMap |  | sì |  |
| `JARVIS_MAPS_MODE` | Maps: mezzo predefinito (drive, walk, bike, transit, moto) | `drive` |  | sì |
| `JARVIS_MAPS_EVENT_HOURS` | Maps: ore in anticipo in cui guardare gli appuntamenti con un luogo (default 4) |  |  | sì |
| `JARVIS_SKILLS` | Algoritmi riutilizzabili per calcoli e conversioni (1/0) | `auto` |  | sì |
| `JARVIS_SKILLS_GENERATE` | Jarvis scrive da solo nuovi algoritmi quando servono (1/0) | `1` |  | sì |
| `HOME_ASSISTANT_URL` | URL Home Assistant |  |  |  |
| `HOME_ASSISTANT_TOKEN` | Token Home Assistant |  | sì |  |
| `HOME_ASSISTANT_VERIFY_SSL` | Home Assistant: verifica il certificato HTTPS (1/0; 0 per certificati autofirmati) | `1` |  | sì |
| `JARVIS_HOME_ASSISTANT` | Casa: collegamento a Home Assistant attivo (1/0) | `auto` |  | sì |
| `JARVIS_HOME_ROOM` | Casa: stanza in cui si trova Jarvis (nome dell'area di Home Assistant) |  |  | sì |
| `JARVIS_HOME_MOTION_MIN` | Casa: minuti dopo l'ultimo movimento in cui una stanza resta occupata (default 5) | `5` |  | sì |
| `JARVIS_HOME_CONFIRM` | Casa: chiedi conferma per serrature, allarme, cancelli e garage (1/0) | `1` |  | sì |
| `JARVIS_HANDS` | Comandi con le mani davanti alla webcam (auto = solo se la GPU del display li regge, 1 = sempre, 0 = mai) | `auto` |  | sì |
| `JARVIS_HANDS_FPS` | Comandi con le mani: analisi al secondo con una mano in vista (10/20/30) | `20` |  | sì |
| `JARVIS_HANDS_COUNT` | Comandi con le mani: mani riconosciute (1/2) | `2` |  | sì |
| `JARVIS_HANDS_MAX_MS` | Comandi con le mani: in automatico si spengono se un'analisi supera questi millisecondi (30/50/90) | `50` |  | sì |
| `JARVIS_AUTOMATIONS` | Automazioni a più stadi: inneschi, condizioni, azioni, rami, attese, webhook (1/0) | `auto` |  | sì |
| `JARVIS_SOUNDS` | Suoni ed effetti (1/0) | `auto` |  | sì |
| `JARVIS_SOUNDS_VOLUME` | Suoni: volume degli effetti 0-100 | `55` |  | sì |
| `JARVIS_SOUNDS_THEME` | Suoni: tema (jarvis, soft, classic) | `jarvis` |  | sì |
| `JARVIS_SOUNDS_FEEDBACK` | Suoni di attivazione e richiesta (1/0) | `1` |  | sì |
| `JARVIS_SOUNDS_THINKING` | Suono mentre pensa ed elabora (1/0) | `1` |  | sì |
| `JARVIS_SOUNDS_NOTIFY` | Suoni di notifica (1/0) | `1` |  | sì |
| `JARVIS_SOUNDS_AMBIENT` | Sottofondo (none, reactor, space, rain, ocean, lab) | `none` |  | sì |
| `JARVIS_SOUNDS_AMBIENT_VOLUME` | Volume del sottofondo 0-100 | `18` |  | sì |
| `JARVIS_QUIET_MODE` | Orari di silenzio: soft (attenua), mute (solo allarmi), off | `soft` |  | sì |
| `JARVIS_QUIET_START` | Silenzio dalle HH:MM | `23:00` |  | sì |
| `JARVIS_QUIET_END` | Silenzio fino alle HH:MM | `07:00` |  | sì |
| `JARVIS_QUIET_DAYS` | Notti di silenzio: all, weekdays, weekend | `all` |  | sì |
| `JARVIS_QUIET_VOICE` | Volume della voce in silenzio 0-100 | `45` |  | sì |
| `JARVIS_QUIET_EFFECTS` | Volume degli effetti in silenzio attenuato 0-100 | `25` |  | sì |
| `JARVIS_SELFTEST` | Collaudo notturno e dopo ogni aggiornamento (1/0) | `auto` |  | sì |
| `JARVIS_SELFTEST_AT` | Ora del collaudo notturno HH:MM | `03:30` |  | sì |
| `JARVIS_SELFTEST_ROLLBACK` | Torna alla versione precedente se un aggiornamento rompe una funzione essenziale (1/0) | `1` |  | sì |
| `JARVIS_UPDATE_REQUIRE_CI` | Installa solo versioni con i test superati su GitHub (1/0) | `1` |  | sì |
| `JARVIS_HABITS` | Abitudini: osserva la casa e propone automazioni (1/0) | `auto` |  | sì |
| `JARVIS_HABITS_CONFIDENCE` | Abitudini: regolarità minima per proporre (0.6, 0.7, 0.8) | `0.7` |  | sì |
| `JARVIS_HABITS_ASK` | Abitudini: proposte a voce (1/0) | `1` |  | sì |
| `JARVIS_HABITS_ANOMALIES` | Avvisi di situazioni insolite con casa vuota (1/0) | `1` |  | sì |
| `JARVIS_VAULT` | Memoria in file leggibili e diario giornaliero (1/0) | `auto` |  | sì |
| `JARVIS_VAULT_DIR` | Cartella della memoria in chiaro (vuoto = cartella condivisa, «05 Memoria») |  |  | sì |
| `JARVIS_GPU_DRIVER` | Driver video del display: auto (NVIDIA ufficiale se adatto), nouveau (libero) | `auto` |  | sì |
| `JARVIS_GPU_DRIVER_REBOOT` | Riavvio per attivare il driver video: night (alle 04:15) o now | `night` |  | sì |
| `JARVIS_SHARES` | Cartella condivisa Samba «condivisa» con le creazioni di Jarvis, protetta da password (1/0) | `auto` |  | sì |
| `JARVIS_SMB_PASSWORD` | Password dell'utente jarvis-share per la cartella condivisa |  | sì |  |
| `JARVIS_AUTONOMY` | Autonomia: compiti programmati, autopilota (diagnosi, studio, riepilogo serale) e approvazioni (1/0) | `auto` |  | sì |
| `JARVIS_WELCOME` | Quando ti riconosce mostra meteo, promemoria e riepilogo Google nei widget (1/0) |  |  | sì |
| `JARVIS_AGENT` | Agente con strumenti: file, widget, ologramma, 3D, email, SMB, terminale (1/0) | `auto` |  | sì |
| `JARVIS_AGENT_ACCESS` | Accesso dell'agente (completo = tutto il server con conferma per le azioni delicate, standard = solo /srv/jarvis e modelli 3D) |  |  |  |
| `JARVIS_SMTP_HOST` | Email in uscita: server SMTP (es. smtp.gmail.com; vuoto = usa Gmail collegato) |  |  | sì |
| `JARVIS_SMTP_PORT` | Email in uscita: porta SMTP (587 STARTTLS, 465 SSL) |  |  | sì |
| `JARVIS_SMTP_USER` | Email in uscita: utente SMTP |  |  | sì |
| `JARVIS_SMTP_PASSWORD` | Email in uscita: password SMTP (per Gmail una password per le app) |  | sì |  |
| `JARVIS_SMTP_FROM` | Email in uscita: mittente (vuoto = utente SMTP) |  |  | sì |
| `JARVIS_3D_CONVERT` | Conversione 3D sul server: Blender per BLEND/USD/USDZ e LibreDWG per DWG (auto = se c'è spazio, 1 = sì, 0 = no) |  |  | sì |
| `JARVIS_GOOGLE_REFRESH_TOKEN` | Valore segreto impostato dalla scheda della funzionalità |  | sì |  |
| `JARVIS_SPOTIFY_REFRESH_TOKEN` | Valore segreto impostato dalla scheda della funzionalità |  | sì |  |

Altre variabili lette dai servizi:

| Variabile | Uso |
| :--- | :--- |
| `JARVIS_DEMO` | `1` = modalità demo (vedi §8) |
| `JARVIS_DIR` | Cartella del repository (predefinita `/opt/Jarvis`) |
| `JARVIS_PUBLIC_PORT` · `JARVIS_ADMIN_PORT` | Porte delle due app (80 e 8080; 8000 e 8001 in demo) |
| `JARVIS_CORE_URL` | Indirizzo di Jarvis Core (predefinito `http://127.0.0.1:8443`) |
| `OLLAMA_URL` | Ollama predefinito se `JARVIS_OLLAMA_URL` è vuoto |
| `JARVIS_EAR_PORT` | Porta del servizio di ascolto (8093) |
| `JARVIS_NODE_CONFIG` | File di configurazione dell'agente dei nodi |

---

## 17. Porte, servizi e file sul disco

### Porte

| Porta | Protocollo | Servizio | Raggiungibile da |
| :--- | :--- | :--- | :--- |
| 80 | TCP | Display e API pubbliche del supervisore | rete di casa |
| 8080 | TCP | Pannello di amministrazione | rete di casa (con login) |
| 8443 | TCP | Jarvis Core (token rilasciati solo al supervisore locale) | solo il server (chiusa nel firewall) |
| 22 | TCP | SSH | rete di casa |
| 50505 | UDP | Scoperta dei nodi | rete di casa |
| 50506 | UDP | Annunci del server ai nodi | rete di casa |
| 51820 | UDP | Aperta dal firewall, riservata a una futura rete privata tra nodi | rete di casa |
| 11434 | TCP | Ollama locale | solo il server (`127.0.0.1`) |
| 6333 · 6334 | TCP | Qdrant | solo il server |
| 8091 | TCP | `jarvis-vision` (volti) | solo il server |
| 8092 | TCP | `jarvis-voice` (Kokoro) | solo il server |
| 8093 | WebSocket | `jarvis-ear` (ascolto) | solo il server |
| 8444 | TCP | `jarvis-inference` (profilo `gpu` di docker compose, facoltativo) | — |
| 8888 · 8889 | TCP | Ritorno OAuth di Spotify e Google durante il collegamento | solo il server |
| 445 · 5357 (TCP), 3702 (UDP) | TCP/UDP | Samba e individuazione in Esplora file di Windows (se le condivisioni sono attive) | solo dalle reti locali del server |

Il firewall `ufw` blocca tutto in ingresso tranne le porte della tabella esposte alla rete di casa.

### Servizi systemd

| Unità | Programma | Note |
| :--- | :--- | :--- |
| `jarvis-supervisor` | `installer_wizard/backend/jarvis_supervisor.py` (venv `installer_wizard/venv`) | Prima di ogni avvio esegue `scripts/os/prestart.sh` |
| `jarvis-rollback` | `scripts/os/rollback.sh` | Attivata dai fallimenti ripetuti del supervisore |
| `jarvis-voice` | `features/voices/service.py` (venv `/opt/jarvis-voice/kokoro/venv`) | Sintesi vocale |
| `jarvis-vision` | `features/vision/service.py` | Riconoscimento facciale |
| `jarvis-ear` | `features/ear/service.py` (venv `/opt/jarvis-ear/venv`) | Ascolto vocale |
| `ollama` | Ollama | Spento con un server Ollama principale remoto |
| `docker` | `jarvis-core`, `jarvis-qdrant` | Avviati dal passo `services` |

### File e cartelle

| Percorso | Contenuto |
| :--- | :--- |
| `/opt/Jarvis` | Repository (aggiornato da solo: **non modificarlo a mano**, le modifiche vengono annullate) |
| `/etc/jarvis/jarvis.env` | Configurazione (600) |
| `/etc/jarvis/session.key` | Chiave che firma le sessioni del pannello |
| `/etc/jarvis/cloud.vault` · `cloud.key` | Chiavi dei servizi cloud e degli altri server, cifrate |
| `/etc/jarvis/*.vault` · `*.key` | Altri archivi cifrati (Google, telecamere…) |
| `/var/lib/jarvis/` | Stato: passi, eventi, funzionalità, persone, memoria, studio, automazioni, nodi, statistiche |
| `/var/lib/jarvis/features/` · `widgets/` · `skills/` | Funzionalità, widget e algoritmi aggiunti dall'utente o da Jarvis |
| `/var/lib/jarvis/last_good_rev` · `bad_revs` | Ultima versione funzionante e versioni scartate |
| `/var/log/jarvis/` | `install.log`, `rollback.log` e altri registri |
| `/srv/jarvis` | Cartella di lavoro dell'agente |
| `/srv/jarvis/condivisa/` | Cartella condivisa `\\IP\condivisa` (vedi sotto) |
| `/opt/Jarvis/data/` | Database, certificati e modelli del Core, dati di Qdrant |

### Cartella condivisa: struttura e nomi

Tutto ciò che Jarvis crea finisce in un'unica cartella di rete, `\\IP\condivisa` (sul server
`/srv/jarvis/condivisa`), protetta dall'utente `jarvis-share` e dalla password indicata nel pannello. Il modulo
`installer_wizard/features/shares/archive.py` definisce la struttura e i nomi; ogni funzionalità che crea file
deve usarlo (`archive.new_path(tipo, nome)`), mai percorsi propri.

| Sottocartella | Contenuto | Chi la usa |
| :--- | :--- | :--- |
| `01 Documenti` | Testi, note, elenchi e documenti | azione «crea un file», agente (`write_file`) |
| `02 Siti web` | Un sito per cartella, servito anche su `http://IP/siti/<cartella>/` | azione «crea un sito», agente (`create_site`) |
| `03 Modelli 3D` | Copia di ogni modello progettato (GLB, STL, OBJ, MTL) | Modelli 3D |
| `04 Codice` | Il codice mostrato nel widget o nelle schede | conversazione |
| `05 Memoria` | Persone, fatti, abitudini, automazioni, diario (modificabili) | Memoria in chiaro |
| `06 Scambio` | Cartella libera e sottocartelle create a richiesta | «crea una cartella condivisa», agente (`share_folder`, `copy_to_share`) |

Regole dei nomi (`archive.dated`):
- iniziano sempre con la data in ordine inverso: `20261002_lista-della-spesa.txt`, `20261002_pizzeria-da-mario/`;
- niente accenti né caratteri non validi per Windows; gli spazi diventano trattini;
- se un nome esiste già si aggiunge `_2`, `_3`…;
- un file già datato non viene ridatato.

Alla prima esecuzione del passo `shares` i contenuti delle vecchie condivisioni (`memoria-jarvis`, `condivisa`
libera, `/srv/jarvis/file`, `/srv/jarvis/siti`, cartelle create in `/srv/jarvis/condivisioni`) vengono spostati
nelle nuove sottocartelle e le vecchie condivisioni vengono rimosse da Samba. Nella cartella c'è anche un
`LEGGIMI.txt` che spiega la struttura.

---

## 18. API HTTP

Tutte le API rispondono in JSON. Regole di accesso (`backend/access.py`):

- **porta 8080 (`admin_routes`)**: serve la sessione del pannello (cookie `jarvis_session`, firmato HMAC‑SHA256,
  12 ore). Le richieste `POST`, `PUT`, `DELETE` devono avere anche l'intestazione `X-Jarvis-Request: 1`
  (protezione CSRF);
- **porta 80 (`public_routes`)**: usate dal display e dai nodi; quelle sensibili accettano solo il server
  stesso, una sessione valida o il token di un nodo;
- **`/api/internal/*`**: solo da `127.0.0.1` con `X-Jarvis-Request: 1` (usate da `jarvisctl` e dai servizi).

Le pagine di documentazione automatica di FastAPI sono disattivate.

### Sistema (`backend/`)

| Metodo | Percorso | Porta | Descrizione |
| :--- | :--- | :---: | :--- |
| GET | `/healthz` | 80, 8080 | Il supervisore è vivo |
| GET | `/api/state` | 80, 8080 | Stato sintetico: fase, componenti, passi, modello, aggiornamenti |
| GET | `/api/stream` | 8080 | Stato in tempo reale per il pannello |
| POST | `/api/auth/login` · `/api/auth/logout` · GET `/api/auth/me` | 8080 | Sessione del pannello |
| GET | `/api/logs/{source}` | 8080 | Registri (install, supervisor, core, ollama, voice, vision, ear…) |
| POST | `/api/actions/{action}` | 8080 | `repair`, `rerun-step`, `restart-component`, `update-check`, `update-apply`, `reboot`, `restart-supervisor` |
| POST | `/api/internal/{action}` | 8080 | `update`, `repair` (solo locale) |
| GET · PUT | `/api/config` | 8080 | Legge e modifica `jarvis.env` (le chiavi segrete non vengono restituite) |
| GET | `/api/features` · POST `/api/features/rescan` | 8080 | Funzionalità e nuova scansione |
| PUT | `/api/features/{id}` · `/api/features/{id}/settings` | 8080 | Modalità `auto`/`1`/`0` e impostazioni |
| POST | `/api/holo_action` | 80 | Azione o espressione dell'ologramma |
| GET | `/` · `/screen` | 80 | Display e schermo secondario |

### Funzionalità

| Area | Rotte principali |
| :--- | :--- |
| **Conversazione** | `POST /api/assistant/chat` (80 e 8080), `POST /api/assistant/wake`, `GET /api/assistant/predict`, `GET /api/assistant/memory`, `GET /api/ambient`, `POST /api/activity` |
| **Voce** | `POST /api/assistant/tts`; `GET/PUT /api/voices`, `POST /api/voices/download`, `/api/voices/preview`, `/api/voices/ensure`, `PUT /api/voices/language`, `DELETE /api/voices/{name}` |
| **Cervello** | `GET /api/models`, `POST /api/models/pull`, `DELETE /api/models/{name}`, `GET/PUT /api/brains`, `POST /api/brains/test`, `POST /api/brains/ollama/test` |
| **Altri server** | `GET/POST /api/brains/servers`, `POST /api/brains/servers/test`, `DELETE /api/brains/servers/{id}` |
| **Cloud** | `GET /api/cloud`, `PUT /api/cloud/{pid}`, `GET /api/cloud/{pid}/models`, `POST /api/cloud/{pid}/test`, `POST /api/cloud/only` |
| **Ascolto** | `POST /api/ear/client` |
| **Visione** | `GET /api/vision/snapshot.jpg`, `/api/vision/still/{id}.jpg`, `/api/vision/hands.mjpg`, `/api/vision/stream.mjpg`; `GET/POST /api/vision/people`, `DELETE /api/vision/people/{slug}` |
| **Persone** | `GET/POST /api/people`, `GET/PUT/DELETE /api/people/{slug}`, `DELETE /api/people/{slug}/voiceprint`, `GET /api/people/schema`, `/api/people/reminders` |
| **Casa** | `GET /api/home`, `/api/home/devices`, `/api/home/activity`; `POST /api/home/sync`, `/api/home/test`; `PUT /api/home/aliases`; `DELETE /api/home/learned` |
| **Automazioni** | `GET/POST /api/automations`, `GET/PUT/DELETE /api/automations/{id}`, `POST …/{id}/run`, `/toggle`, `/duplicate`, `/validate`, `/generate`, `/expr`, `/templates/{n}`, `GET /export`, `POST /import`, `GET /runs`, `POST /runs/{id}/stop`, `POST /api/automations/webhook/{key}` (pubblica, porta 80) |
| **Autonomia** | `GET /api/autonomy`, `POST/PUT/DELETE /api/autonomy/routines…`, `POST /api/autonomy/approvals/{id}`, `POST /api/autonomy/autopilot` |
| **Abitudini** | `GET /api/habits`, `POST /api/habits/analyse`, `POST /api/habits/{id}` |
| **Mente** | `GET/PUT /api/mind`, `DELETE /api/mind/facts/{id}`, `/api/mind/suggestions/{id}`, `POST /api/mind/clear` |
| **Leggi** | `GET/POST /api/laws`, `PUT/DELETE /api/laws/{id}`, `POST /api/laws/reorder` |
| **Studio** | `GET /api/study`, `PUT /api/study/settings`, `POST/GET/PUT/DELETE /api/study/topics…`, `POST /api/study/now`, `/api/study/search`, `GET /api/study/dataset.jsonl`; Soup: `PUT /api/study/soup`, `POST /api/study/soup/train` |
| **Algoritmi** | `GET /api/skills`, `POST /api/skills/ask`, `GET /api/skills/{key}/code`, `POST /api/skills/{key}/test`, `PUT/DELETE /api/skills/{key}` |
| **Widget** | `GET /api/widgets`, `PUT /api/widgets/{id}`, `POST /api/widgets/{id}/test`, `POST /api/alarm`, `DELETE /api/desk/{key}`; dal display: `POST /api/desk/hello`, `/idle`, `/position`, `/screen`, `GET /widgets/{id}/{file}` |
| **Modelli 3D** | `GET /api/models3d`, `POST /api/models3d/upload`, `/generate`, `POST /api/models3d/{id}/show`, `GET /api/models3d/{id}/{file}`, `DELETE /api/models3d/{id}` |
| **Audio** | `GET/PUT /api/audio`; Bluetooth: `GET /api/bluetooth`, `POST /api/bluetooth/scan`, `POST /api/bluetooth/devices/{mac}/{azione}`, `PUT /api/bluetooth/prefs` |
| **Suoni** | `GET /api/sounds`, `POST /api/sounds/dnd`, `POST /api/sounds/play/{nome}` |
| **Posizione e mappe** | `GET/PUT /api/location`, `GET /api/location/search`, `POST /api/location/browser`; `GET /api/maps`, `PUT/DELETE /api/maps/places/{nome}`, `POST /api/maps/test` |
| **Google · Spotify · Telegram** | `GET /api/google`, `POST /api/google/{slug}/auth-url`, `/api/google/finish`, `DELETE /api/google/{slug}`; `GET/DELETE /api/spotify`, `POST /api/spotify/auth-url`, `/finish`; `GET /api/telegram`, `POST /api/telegram/pair-code`, `PUT/DELETE /api/telegram/chats/{id}` |
| **Rete e nodi** | `GET /api/network`, `POST /api/network/scan`; `GET /api/nodes`, `POST /api/nodes/pairing-code`, `PUT/DELETE /api/nodes/{id}`, `POST /api/nodes/{id}/command/{cmd}`, approvazione richieste; dai nodi: `POST /api/nodes/pair`, `/heartbeat`, `/request`, `/claim`, `/chat`, `GET /nodes/agent.py` |
| **Altro** | `GET /api/cameras` e gestione; `GET /api/music`; `GET /api/selftest`, `POST /api/selftest/run`; `GET /api/shares`; `GET /api/vault`, `POST /api/vault/sync`; siti creati da Jarvis: `GET /siti/{nome}` |

Esempio: chiedere qualcosa a Jarvis dallo stesso server.

```bash
curl -s -X POST http://127.0.0.1/api/assistant/chat \
  -H 'Content-Type: application/json' -d '{"text": "che ore sono?"}'
```

---

## 19. Aggiornamenti, collaudo e rollback

### Aggiornamenti

Il task `updater.scheduler()` ogni `JARVIS_UPDATE_INTERVAL_MIN` minuti (predefinito 5):

1. `git fetch origin <ramo>` (ramo `JARVIS_UPDATE_BRANCH`, predefinito `main`);
2. se ci sono commit nuovi e `JARVIS_UPDATE_REQUIRE_CI=1`, sceglie il commit più recente i cui test su
   GitHub Actions sono **passati**, saltando quelli falliti o già scartati; se GitHub non è raggiungibile da
   oltre un'ora aggiorna comunque, segnalandolo;
3. `git reset --hard <commit>` e riavvio del supervisore;
4. al riavvio la fase è `UPDATING`: la pipeline dei passi verifica la nuova versione; se riesce, il commit
   diventa `last_good_rev`; se fallisce, si torna al commit precedente e quello nuovo finisce in `bad_revs`.

Poiché il server esegue `reset --hard`, **ogni modifica fatta a mano in `/opt/Jarvis` viene annullata**: le
modifiche si fanno nel repository e si pubblicano su GitHub.

### Rollback in caso di crash

Se il supervisore si blocca ripetutamente (systemd: `OnFailure=jarvis-rollback.service`; lo script interviene dal quarto fallimento in 10 minuti), parte `jarvis-rollback`, che riporta il repository
a `last_good_rev`, segna la versione difettosa e riavvia il supervisore (registro in
`/var/log/jarvis/rollback.log`).

### Collaudo

Ogni notte (`JARVIS_SELFTEST_AT`, predefinito 03:30) e cinque minuti dopo ogni aggiornamento, Jarvis esegue
13 prove reali in parallelo (al massimo 90 secondi): supervisore e pannello, componenti, conversazione, voce,
automazioni, cervello, display, ascolto, visione, casa, suoni, spazio su disco, aggiornamenti. Se una prova
essenziale che prima passava ora fallisce e `JARVIS_SELFTEST_ROLLBACK=1`, Jarvis torna alla versione
precedente e lo comunica su Telegram e sul display. A voce: «fai il collaudo».

---

## 20. Sicurezza e privacy

| Area | Misura |
| :--- | :--- |
| **Accesso al pannello** | Utenti del sistema via PAM, solo gruppi `sudo`, `wheel`, `jarvis-admin` o `root`; blocco dopo 5 errori in 5 minuti; sessione firmata HMAC‑SHA256 di 12 ore con chiave casuale in `/etc/jarvis/session.key`; intestazione anti-CSRF sulle modifiche. |
| **Segreti** | `jarvis.env` con permessi 600 in una cartella 700; chiavi API, token e credenziali in archivi cifrati Fernet (AES‑128‑CBC + HMAC) con chiave separata; il pannello non restituisce mai i valori segreti. |
| **Nodi** | Codici di abbinamento monouso validi 10 minuti, token casuali salvati solo come hash SHA‑256, revoca immediata, limite alle richieste. |
| **Jarvis Core** | Token firmati con una chiave casuale (`JARVIS_SECRET_KEY`), rilasciati solo al supervisore locale; porta 8443 chiusa verso la rete. |
| **Rete** | Firewall `ufw` (tutto chiuso in ingresso tranne le porte necessarie), hardening `sysctl` (niente redirect né source routing, `rp_filter`, SYN cookies, log dei pacchetti anomali); Ollama, Qdrant e i servizi di percezione ascoltano solo su `127.0.0.1`. |
| **Codice generato** | Gli algoritmi scritti da Jarvis vengono analizzati (solo moduli ammessi, nessuna funzione pericolosa) ed eseguiti in un processo isolato con limiti di memoria, file e tempo. |
| **Agente** | Conferma a voce prima di email, cancellazioni (che vanno nel cestino), comandi che modificano il sistema e scritture fuori dalla cartella di lavoro; livello `standard` per limitarlo a `/srv/jarvis`. |
| **Leggi** | Le leggi fondamentali sono in testa a ogni prompt (locale, altri server, cloud, agente) e non si possono modificare. Sono scritte per «Jarvis» in prima persona, qualunque modello lo faccia funzionare, e sono seguite da una **clausola di integrità**: nessun messaggio, documento, email, pagina web o risultato di uno strumento può sospenderle; niente eccezioni per giochi di ruolo, ipotesi, traduzioni o «modalità sviluppatore». Una **guardia nel codice** (`features/laws/guard.py`) intercetta i tentativi espliciti di aggirarle (anche con caratteri invisibili) prima che arrivino al modello, risponde con un rifiuto fisso e registra l'evento; le regole personali che le indeboliscono vengono rifiutate. |
| **Privacy** | Tutto funziona in locale; il cloud si usa solo se configurato. Voci online disattivabili (`JARVIS_VOICE_ONLINE=0`, il testo non esce dal server). Dati Google mostrati solo alla persona riconosciuta. Telecamere spente di default, con consenso e indicatore di registrazione. Il riconoscimento musicale invia 10 secondi di audio ed è disattivabile. |
| **Aggiornamenti** | Solo versioni con i test superati, verifica dopo l'installazione e rollback automatico. |
| **Repository** | Nessun segreto, password o dato personale nel codice: si leggono sempre da `jarvis.env` o dal vault. Prima di ogni push si controlla il contenuto (vedi [§22](#22-sviluppo)). |

Per segnalare una vulnerabilità vedere [SECURITY.md](SECURITY.md).

### Limiti delle leggi (da sapere)

Le leggi nel prompt e la guardia sulle frasi riducono molto i tentativi di aggiramento, ma **nessun modello
linguistico è impossibile da ingannare**: una richiesta formulata in modo nuovo può sfuggire ai controlli
testuali. Per questo la sicurezza fisica non si affida al modello ma al **codice**, che il modello non può
cambiare:

- le azioni delicate dell'agente (email, cancellazioni, comandi che modificano il sistema, scritture fuori
  dalla cartella di lavoro) richiedono la conferma dell'utente, decisa dal codice di ogni strumento
  (`features/agent/registry.py`), e i comandi distruttivi sono bloccati in ogni caso;
- serrature, allarme, cancelli e garage chiedono conferma (`JARVIS_HOME_CONFIRM`);
- le azioni dei compiti automatici aspettano l'approvazione;
- gli algoritmi generati girano isolati, senza file né rete.

Ogni nuovo strumento o azione che può avere effetti nel mondo reale deve avere il suo controllo nel codice,
non solo nelle leggi.

---

## 21. jarvisctl e manutenzione

`jarvisctl` è installato in `/usr/local/bin` dal passo `maintenance`.

```bash
jarvisctl status            # fase, componenti e stato dei passi
jarvisctl update            # controlla e applica subito gli aggiornamenti da GitHub
jarvisctl repair            # verifica e ripara tutti i componenti
jarvisctl logs install      # registro dell'installazione (anche: supervisor, core, ollama, voice, vision, ear)
jarvisctl version           # commit installato
```

Altri comandi utili:

```bash
systemctl status jarvis-supervisor
journalctl -fu jarvis-supervisor
docker ps
docker logs -f --tail 200 jarvis-core
curl -s http://127.0.0.1/api/state | jq .
```

Diagnosi a distanza senza accedere al server: `http://<server>/api/state` mostra fase, componenti, passi,
versione, stato degli aggiornamenti e telemetria di ascolto e display.

---

## 22. Sviluppo

### Regole del codice (obbligatorie)

| Regola | Dettaglio |
| :--- | :--- |
| **Niente commenti** | Né commenti né docstring: il codice deve spiegarsi da solo con nomi chiari e funzioni piccole. |
| **Massimo 500 righe per file** | Vale per ogni file di codice. Se un file cresce, si divide per responsabilità (mixin, moduli di supporto, sotto-pacchetti). Il README è l'unica eccezione. |
| **Per funzionalità, non per livello** | Tutto ciò che riguarda una capacità sta nella sua cartella `features/<id>/`: logica, API, scheda del pannello, stili. Il codice condiviso sta in `backend/` solo se serve al supervisore. |
| **Responsabilità singola** | Un modulo, un compito: `api.py` solo rotte, logica nei moduli dedicati, servizi esterni in `service.py`. |
| **Lingua** | Interfaccia, messaggi, eventi e registri in italiano; Jarvis si rivolge all'utente con il «Lei» e lo chiama «signore». |
| **Universale** | Ogni funzionalità è offerta a tutti, si accende da sola in base all'hardware (`auto`) e si può forzare (`1`/`0`). |
| **Idempotenza** | I passi d'installazione e le riparazioni si possono rieseguire all'infinito senza danni. |
| **Niente segreti nel codice** | Password, token e chiavi solo in `jarvis.env` o nel vault cifrato; mai nel repository, nei test o negli esempi. |

### Flusso di lavoro

- Si lavora **solo sul repository** e si pubblica sul ramo **`main`** di GitHub: online deve esistere solo
  `main`, niente altri rami.
- **Non si modificano a mano i server**: si aggiornano da soli da `main` entro pochi minuti (al massimo
  `jarvisctl update` per accelerare). Le modifiche fatte in `/opt/Jarvis` vengono annullate.
- Prima di ogni push si eseguono i controlli della CI (vedi [§27](#27-test-e-integrazione-continua)): se la CI
  fallisce, i server non installano quella versione.
- Commit piccoli e frequenti, con messaggi in italiano che descrivono il risultato per l'utente.
- Prima di ogni push controllare che non ci siano segreti, password, indirizzi interni o file inutili:

  ```bash
  git diff --cached --name-only
  git grep --cached -nIE "password\s*=\s*['\"]|sk-[A-Za-z0-9]{20}|AIza|ghp_|PRIVATE KEY"
  ```

### Ambiente di sviluppo

```bash
git clone https://github.com/AprileNunzio/Jarvis.git
cd Jarvis/installer_wizard
python3 -m venv venv
venv/bin/pip install -r backend/requirements.txt pyflakes
cd backend
JARVIS_DEMO=1 ../venv/bin/python jarvis_supervisor.py
```

- Display: `http://localhost:8000/` · Pannello: `http://localhost:8001/` (utente `admin`, password `jarvis`).
- In demo i dati stanno in `<temp>/jarvis-demo/`: cancellare la cartella per ripartire da zero.
- Per provare il cervello vero in demo basta un Ollama raggiungibile e `OLLAMA_URL` o la scheda Cervello.
- Gli script dei passi si provano su una macchina o macchina virtuale Debian:
  `sudo bash scripts/os/steps/50-ollama.sh check; echo $?`.

### Convenzioni Python

- Python 3.11+, `asyncio` ovunque nel supervisore; nessuna chiamata bloccante nel loop (usare `httpx.AsyncClient`,
  `asyncio.create_subprocess_exec`, `asyncio.to_thread`).
- Configurazione: `read_env()` / `env_get()` da `config.py`; scrittura con `write_env()` o meglio
  `settings.apply_config()` (sa quali passi rieseguire).
- Eventi per l'utente: `store.event("INFO" | "WARN" | "ERROR", messaggio, sorgente)`.
- Task in background: `tasks.background(coroutine)`.
- File privati: `sealed.write_private()`; segreti: `SealedFile` o il vault.
- Import delle funzionalità: `from features.<id>.<modulo> import …`.
- Nelle rotte admin la dipendenza `Depends(require_admin)` restituisce il nome dell'utente.

### Convenzioni JavaScript

- JavaScript moderno senza framework né build per il supervisore (il solo `client_web` usa React e Vite).
- Ogni file è un'IIFE `(() => { … })();` che si aggancia a `window.JarvisAdmin` (pannello) o a
  `window.JarvisDesk` / moduli del display.
- Nel pannello: `A.api(metodo, url, corpo)` aggiunge sessione e intestazione anti-CSRF; `A.toast(testo, errore)`;
  `A.tab(id, { init, load, onState, leave })`; `A.makeSortable`, `A.prioItem` per le liste ordinabili;
  `fmt.esc` per inserire testo nell'HTML.

---

## 23. Come aggiungere una funzionalità

1. Creare `installer_wizard/features/<id>/feature.json`:

   ```json
   {
     "id": "meteo_avanzato",
     "name": "Meteo avanzato",
     "icon": "⛅",
     "category": "casa",
     "order": 200,
     "description": "Allerta meteo e qualità dell'aria per la tua zona.",
     "capabilities": ["Allerte della protezione civile", "Pollini e qualità dell'aria"],
     "pinned": false,
     "panel": "meteo",
     "toggle": { "env": "JARVIS_METEO_PLUS", "tri": true, "apply": [] },
     "requires": { "ram_gb": 2, "commands": ["curl"], "features": ["location"] },
     "settings": [
       { "key": "JARVIS_METEO_VENTO", "label": "Avvisami con vento oltre (km/h)", "type": "number", "default": "60" }
     ]
   }
   ```

   | Campo | Significato |
   | :--- | :--- |
   | `id` | Minuscole, cifre, `-` e `_`; di norma uguale al nome della cartella |
   | `category` | `assistente`, `percezione`, `casa`, `conoscenza`, `comunicazione`, `sistema`, `altro` |
   | `order` | Posizione nell'elenco |
   | `pinned` | `true` = compare nel menu laterale alla prima scoperta |
   | `panel` | Id della scheda del pannello (vuoto = pagina generata dal manifest) |
   | `toggle` | Assente = sempre attiva. `env`: variabile `1`/`0` (`tri: true` = `auto`/`1`/`0`); `default`; `apply`: passi da rieseguire; `hook`: interruttore Python registrato con `registry.register_hook` |
   | `requires` | Requisiti per la modalità automatica: `ram_gb`, `gpu_vram_gb`, `video`, `commands`, `features`, `env` |
   | `settings` | Campi del modulo: `text`, `number`, `select`, `color`, `secret`, `bool`. Le chiavi MAIUSCOLE vanno in `jarvis.env` (aggiungerle a `EDITABLE_KEYS`, e a `SECRET_KEYS` se segrete), le altre restano nello stato della funzionalità (`registry.settings_of(id)`) |

2. Scrivere la logica in uno o più moduli (`meteo.py`, …), importati come `features.meteo_avanzato.meteo`.

3. Se servono API, creare `api.py` con `public_routes = APIRouter()` e/o `admin_routes = APIRouter()` e
   aggiungere il modulo a `FEATURE_APIS` in `backend/jarvis_supervisor.py`. Se c'è un task di lunga durata,
   aggiungere la sua `run()` alla lista dei task di `main()`.

4. Per la scheda del pannello: `admin.html` con `<section class="tab" id="tab-<panel>">`, `admin.js` che chiama
   `JarvisAdmin.tab("<panel>", { init, load, onState })` e, se serve, `admin.css`. Il supervisore li inserisce
   da solo nel pannello; file aggiuntivi devono chiamarsi `admin-<nome>.js` / `admin-<nome>.css` (solo
   lettere minuscole).

5. Se la funzionalità ha bisogno di pacchetti di sistema o di un servizio, aggiungere un passo (vedi [§26](#26-come-aggiungere-un-passo-dinstallazione))
   e indicarlo in `toggle.apply`.

6. Aggiungere i test in `installer_wizard/tests/` e verificare la CI.

Le funzionalità messe in `/var/lib/jarvis/features/<id>/` (dall'utente o da Jarvis, con `"source": "ai"` o
`"user"`) vengono scoperte ogni 20 secondi e compaiono nel pannello con la pagina generata dal manifest.

---

## 24. Come aggiungere un widget

1. Cartella `installer_wizard/widgets/<id>/` con:
   - `widget.json`:

     ```json
     {
       "id": "qualita_aria",
       "name": "Qualità dell'aria",
       "icon": "🌬",
       "priority": 45,
       "size": "m",
       "intents": ["air_quality"],
       "ttl": 600,
       "description": "Indice di qualità dell'aria dopo una domanda (resta 10 minuti).",
       "demo": { "aqi": 42, "label": "Buona" }
     }
     ```

     | Campo | Significato |
     | :--- | :--- |
     | `priority` | 0–100: i più alti stanno al centro |
     | `size` | `s`, `m`, `l`, `full` |
     | `intents` | Intenti della conversazione che lo aprono |
     | `ttl` | Secondi prima di chiudersi da solo (assente = resta finché non viene chiuso) |
     | `replaces` | Widget che sostituisce quando compare |
     | `chrome` | `false` = senza cornice |
     | `overlay` | `true` = sopra gli altri (allarmi) |
     | `demo` | Dati usati dal pulsante «Prova» del pannello |

   - `widget.js`:

     ```js
     (() => {
       JarvisDesk.register("qualita_aria", {
         render(el, d, ctx) {
           el.innerHTML = `<div class="aq">${ctx.esc(d.label || "")} · ${d.aqi ?? "—"}</div>`;
         },
       });
     })();
     ```

     `render(el, dati, ctx)` disegna; `update` (facoltativo) aggiorna senza ricreare. `ctx` offre `esc`,
     `mmss`, `speak(testo)`, `now()`.
   - `widget.css` (facoltativo): stili del solo widget.

2. Dal Python si mostra con:

   ```python
   from features.desktop.desk import desk
   desk.show("qualita_aria", {"aqi": 42, "label": "Buona"}, key="aria", ttl=600)
   desk.hide(key="aria")
   ```

   Anche le automazioni («Mostra widget») e l'agente possono aprirlo.

---

## 25. Come aggiungere un algoritmo

```text
installer_wizard/skills/finanza/rata_mutuo/
├── skill.json
└── main.py
```

`skill.json`:

```json
{
  "id": "rata_mutuo",
  "name": "Rata del mutuo",
  "description": "Rata mensile dati importo, tasso annuo e anni.",
  "priority": 40,
  "patterns": ["\\brata\\b.*\\bmutuo\\b"],
  "examples": ["rata del mutuo di 150000 euro al 3% per 25 anni"]
}
```

`main.py` (solo moduli ammessi, vedi [§13](#13-algoritmi-skills)):

```python
import re


def run(text: str) -> dict:
    nums = [float(n.replace(",", ".")) for n in re.findall(r"\d+(?:[.,]\d+)?", text.replace(".", ""))]
    if len(nums) < 3:
        return {"ok": False, "error": "servono importo, tasso e anni"}
    capitale, tasso, anni = nums[0], nums[1] / 100 / 12, int(nums[2]) * 12
    rata = capitale * tasso / (1 - (1 + tasso) ** -anni) if tasso else capitale / anni
    return {"ok": True, "result": round(rata, 2), "speech": f"La rata è di {rata:.2f} euro al mese.".replace(".", ",", 1)}
```

Il pannello (**Algoritmi**) permette di provarlo sugli esempi, vederne il codice e le statistiche d'uso.

---

## 26. Come aggiungere un passo d'installazione

1. Creare `scripts/os/steps/NN-nome.sh`:

   ```bash
   #!/usr/bin/env bash
   . "$(dirname "$0")/../lib.sh"

   step_check() {
       command -v mosquitto >/dev/null 2>&1 && systemctl is-active --quiet mosquitto
   }

   step_apply() {
       progress 20 "Installazione del broker MQTT"
       apt_install mosquitto
       systemctl enable --now mosquitto
       wait_for 30 systemctl is-active --quiet mosquitto || fail "Il broker MQTT non si avvia"
       progress 100 "Broker MQTT operativo"
   }

   step_main "$@"
   ```

2. Aggiungerlo a `STEPS` in `installer_wizard/backend/steps.py` nella posizione giusta, con titolo,
   descrizione, peso (quota della barra di avanzamento) e `critical`.
3. Se dipende da una variabile, aggiungerla a `STEP_TRIGGERS` in `backend/settings.py` o al `toggle.apply`
   della funzionalità.
4. Se il passo installa un servizio da sorvegliare, aggiungere la sonda in `backend/health.py`.
5. Verificare `bash -n` e provare `check`/`apply` più volte di seguito su una macchina Debian di prova.

---

## 27. Test e integrazione continua

La CI (`.github/workflows/ci.yml`) gira su ogni push e pull request verso `main`:

| Job | Controlli |
| :--- | :--- |
| `validate-python` | `py_compile` di tutti i `.py` in `server`, `installer_wizard`, `client_satellite`; `pyflakes` |
| `tests` | `python -m unittest discover -s tests -t .` in `installer_wizard` |
| `validate-scripts` | `node --check` su ogni `.js` di `installer_wizard`; `bash -n` su ogni `.sh`, `jarvisctl`, `install.sh` |
| `validate-web-client` | `npm ci` e `npm run build` di `client_web` |

Da eseguire in locale prima di ogni push:

```bash
python -m py_compile $(find server installer_wizard client_satellite -name "*.py" -not -path "*/venv/*")
python -m pyflakes server installer_wizard client_satellite
(cd installer_wizard && python -m unittest discover -s tests -t .)
for f in $(find installer_wizard -name "*.js" -not -path "*/venv/*"); do node --check "$f"; done
for f in $(find scripts installer_wizard -name "*.sh") scripts/os/jarvisctl install.sh; do bash -n "$f"; done
find installer_wizard server scripts -type f \( -name "*.py" -o -name "*.js" -o -name "*.sh" -o -name "*.css" -o -name "*.html" \) -not -path "*/venv/*" -exec awk 'END { if (NR > 500) print FILENAME ": " NR }' {} \;
```

Test esistenti (`installer_wizard/tests/`): automazioni, espressioni, abitudini, collaudo, suoni, supervisore,
memoria in chiaro. I server installano solo versioni con la CI verde (`JARVIS_UPDATE_REQUIRE_CI=1`).

---

## 28. Jarvis Core (server/)

Il Core è un servizio FastAPI separato (porta 8443, container `jarvis-core` con `network_mode: host`) che
risponde alle conversazioni con i modelli del server Ollama principale. Il supervisore lo chiama da
`backend/core_client.py` passando la lista dei modelli da provare, i token massimi e il contesto.

```text
server/
├── cmd/main.py · api_routes.py      # Applicazione e rotte /api/v1 (command, knowledge, tts, mesh, vision, ws)
├── config/env.py                    # Impostazioni (pydantic-settings) da /etc/jarvis/jarvis.env
├── core/
│   ├── orchestrator/                # Dispatcher e classificatore degli intenti
│   ├── reasoning/                   # Conversazione, ciclo ReAct, autocritica
│   ├── planner/                     # Scomposizione dei compiti
│   ├── context_graph/               # Grafo della conoscenza (nodi e archi)
│   ├── cognitive_audit/             # Embedding
│   ├── agent_registry/              # Interfacce e pool degli agenti
│   └── security_guard/              # Token firmati e middleware di verifica
├── features/
│   ├── llm_gateway/                 # Ollama con fallback Gemini e Claude
│   ├── sysops_automation/           # Comandi, SMB, MySQL, scaffolding di applicazioni
│   ├── home_assistant_bridge/ · vision_surveillance/ · voice_biometrics/
│   ├── mesh_coordinator/ · self_healing_coder/ · skill_synthesis/
└── shared/                          # Errori e sanificazione dell'input
```

Rotte principali: `POST /api/v1/command`, `GET /api/v1/knowledge/graph`, `POST /api/v1/knowledge/node`,
`/edge`, `POST /api/v1/tts/synthesize`, `POST /api/v1/mesh/sync`, `POST /api/v1/vision/feed`,
`WS /api/v1/ws/stream`, `GET /health`.

Il passo `core` ricompila l'immagine solo quando cambiano `server/` o `docker/core` (hash del codice); il
passo `services` avvia `jarvis-core` e `jarvis-qdrant` con `docker compose` (progetto `jarvis`).

Sicurezza del Core: tutte le rotte tranne `/health` richiedono un token firmato HMAC‑SHA256 con
`JARVIS_SECRET_KEY`, una chiave casuale generata dal passo `services` in `jarvis.env` (se manca, il Core ne usa
una casuale per la sola sessione). `POST /api/v1/auth/exchange` rilascia token solo alle richieste da
`127.0.0.1`, cioè al supervisore, e la porta 8443 è chiusa nel firewall: i client esterni passano dal
supervisore (porte 80 e 8080).

---

## 29. Client: web, Android, satelliti

| Client | Cartella | Stato | Descrizione |
| :--- | :--- | :--- | :--- |
| **Display integrato** | `installer_wizard/web/display/` | principale | Il modo consigliato per usare Jarvis da qualsiasi schermo: `http://<server>/` |
| **Dashboard web** | `client_web/` | sperimentale | React + Vite + Tailwind + Three.js: nucleo neurale 3D e pannello di controllo (`npm ci && npm run dev`) |
| **Android** | `client_apk/` | sperimentale | Kotlin: scoperta del server in rete, ascolto in primo piano con wake word, impronta vocale, webcam, interfaccia a schermo intero. Oggi punta direttamente al Core sulla porta 8443, ora chiusa: va portato sulle API del supervisore (porta 80) |
| **Satellite Linux** | `client_satellite/linux_edge/satellite.py` | in uso | Agente dei nodi (Raspberry Pi o qualsiasi Linux): abbinamento, battito, comandi, chat (vedi [§14](#14-nodi-e-satelliti)) |
| **ESP32** | `client_satellite/microcontrollers/esp32/` | sperimentale | Firmware PlatformIO per microfono I2S (INMP441) e amplificatore I2S (MAX98357A) |

---

## 30. Risoluzione dei problemi

| Problema | Cosa controllare |
| :--- | :--- |
| Il display resta su «Installazione» | `jarvisctl status` e `jarvisctl logs install`: il passo in errore mostra il motivo; il supervisore riprova da solo con attese crescenti. |
| Il pannello non accetta la password | L'utente deve essere in `sudo`, `wheel` o `jarvis-admin`; dopo 5 errori attendere 5 minuti. |
| «Nessun cervello disponibile» | Pannello → Cervello: controllare le liste (modelli «da scaricare» o «chiave mancante» vengono saltati), che Ollama risponda (`curl http://127.0.0.1:11434/api/version`) o che il server remoto sia raggiungibile. |
| Server Ollama remoto «non raggiungibile» | Sul server remoto `OLLAMA_HOST=0.0.0.0`, firewall aperto sulla porta 11434, stessa rete. |
| I modelli del server remoto non compaiono | Dopo «Salva» il catalogo si aggiorna da solo; per gli altri server usare la scheda «🖧 Altri server» e il pulsante ↻. |
| Jarvis non sente | Pannello → Audio: microfono giusto e non muto; `jarvisctl logs ear`; per il campo lontano aumentare `JARVIS_EAR_MAX_GAIN`. |
| Jarvis non parla | `jarvisctl logs voice`; scegliere un'altra voce in Voci; con `JARVIS_VOICE_ONLINE=0` servono voci offline. |
| La webcam non riconosce | `jarvisctl logs vision`; la funzionalità Visione richiede una webcam e 2 GB di RAM in modalità automatica. |
| Display lento o scattoso | Aspetto: «Nucleo leggero»; Comandi con le mani: disattivare; con NVIDIA controllare il passo «Driver video». |
| Un aggiornamento non arriva | `jarvisctl update`: se la CI su GitHub non è passata il server attende; `JARVIS_UPDATE_REQUIRE_CI=0` per ignorarla (sconsigliato). |
| Dopo un aggiornamento qualcosa non va | Il collaudo torna indietro da solo; altrimenti `/var/log/jarvis/rollback.log` e lo storico eventi nel pannello. |
| Home Assistant non si collega | Indirizzo e token a lunga durata; con certificato autofirmato `HOME_ASSISTANT_VERIFY_SSL=0`. |
| La cartella condivisa non si apre da Windows | Indirizzo `\\<ip-del-server>\condivisa` (copiabile dal pannello), utente `jarvis-share` e password del pannello; se Windows segnala credenziali diverse già in uso: `net use \\<ip> /delete` e riprovare. |

---

## 31. Domande frequenti

**Serve una GPU?** No. Senza GPU Jarvis usa modelli piccoli; per risposte più ricche si può aggiungere un
altro computer con GPU come server Ollama o un servizio cloud.

**Posso usare solo il cloud?** Sì: Cervello → Servizi cloud → «Usa solo il cloud». La voce, l'ascolto e la
visione restano locali.

**Posso usare più server Ollama?** Sì: uno come server principale (`JARVIS_OLLAMA_URL`) e quanti se ne
vuole in «🖧 Altri server», mescolati nelle liste ⚡ e 🧠.

**I miei dati escono di casa?** Solo se si attivano servizi cloud, voci online, riconoscimento musicale,
Google, Spotify, Telegram o mappe con chiave Google. Ognuno si può spegnere.

**Posso modificare il codice direttamente sul server?** No: il server si riallinea a GitHub e annulla le
modifiche locali. Si lavora sul repository e si pubblica su `main`.

**Come si torna a una versione precedente?** È automatico (collaudo e rollback). A mano:
`git -C /opt/Jarvis reset --hard <commit>` seguito da `systemctl restart jarvis-supervisor`, sapendo che
il prossimo aggiornamento riporterà l'ultima versione con la CI verde.

**Come cambio il nome dell'assistente o il mio?** `JARVIS_ASSISTANT_NAME` e `JARVIS_USER_NAME` in
Configurazione.

---

## 32. Contribuire, licenza e crediti

- Leggere [CONTRIBUTING.md](CONTRIBUTING.md) e il [Codice di condotta](CODE_OF_CONDUCT.md).
- Rispettare le regole della [§22](#22-sviluppo): niente commenti, file sotto 500 righe, codice per
  funzionalità, CI verde, nessun segreto nel repository.
- Le vulnerabilità si segnalano in privato come indicato in [SECURITY.md](SECURITY.md).

Progetto ideato, progettato e sviluppato da **[NunzioTech](https://github.com/AprileNunzio)** (Nunzio Aprile).
Rilasciato con licenza [MIT](LICENSE).
