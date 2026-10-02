# JARVIS: Autonomous Cognitive Orchestrator

<p align="center">
  <img src="https://img.shields.io/badge/Architecture-Clean%20Architecture-00f0ff?style=for-the-badge" alt="Clean Architecture">
  <img src="https://img.shields.io/badge/Security-Zero--Trust%20OWASP-emerald?style=for-the-badge" alt="Zero Trust">
  <img src="https://img.shields.io/badge/Engine-Multi--Agent%20Mesh-blue?style=for-the-badge" alt="Multi-Agent">
  <img src="https://img.shields.io/badge/OS-Debian%2012%20Minimal-red?style=for-the-badge" alt="Debian 12">
  <img src="https://img.shields.io/badge/License-MIT-amber?style=for-the-badge" alt="MIT License">
  <img src="https://img.shields.io/badge/Powered%20By-NunzioTech-0051ff?style=for-the-badge" alt="NunzioTech">
</p>

```
         ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗
         ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝
         ██║███████║██████╔╝██║   ██║██║███████╗
    ██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║
    ╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║
     ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝
       AUTONOMOUS COGNITIVE ORCHESTRATOR
       Designed & Engineered by NunzioTech
```

---

## Panoramica del Progetto

**Jarvis** non è un semplice assistente o un agente isolato. È un **Orchestratore Cognitivo Autonomo Multi-Agente** e distribuito, concepito per gestire l'intera infrastruttura domestica, server, sicurezza e sviluppo software.

Il sistema apprende autonomamente generando una **rete neurale di nodi di memoria e sinapsi dinamiche (Knowledge Graph)**. Comunica con voce maschile profonda, assertiva e professionale, riconosce l'identità biometrica di chi impartisce i comandi vocali, e coordina in tempo reale agenti specializzati locali o cloud (Ollama, OpenAI, Anthropic, Gemini).

---

## One-Liner Graphic Auto-Installer (by NunzioTech)

Abbiamo introdotto il nuovissimo **Graphic Installer Wizard**! Un'interfaccia utente ultra-moderna in stile macOS/Windows che guida l'utente, gestisce l'installazione dei container in background e mostra in tempo reale le percentuali e la velocità di download dei modelli AI.

Installazione completa e configurazione automatica universale (supporto per **Debian, Ubuntu, RHEL, CentOS, Fedora, Arch e Raspbian**):

```bash
curl -sL https://raw.githubusercontent.com/AprileNunzio/Jarvis/main/installer_wizard/bootstrap.sh | sudo bash
```

> **Nota:** Il server entrerà immediatamente in modalità "Smart Display" (Kiosk Mode a schermo intero) mostrando l'avanzamento. Al termine, configurerà l'avvio automatico per accendersi sempre direttamente nell'interfaccia di Jarvis.

### Installazione da una copia del repository
```bash
git clone https://github.com/AprileNunzio/Jarvis.git
cd Jarvis
sudo ./install.sh
```
*`install.sh` avvia `installer_wizard/bootstrap.sh`: il servizio `jarvis-supervisor` esegue gli step idempotenti di `scripts/os/steps`, si ripara da solo e si aggiorna da GitHub con verifica e rollback. Il registro dell'installazione è in `/var/log/jarvis`.*

Per ambienti **Windows / PowerShell**:
```powershell
.\install.ps1
```

---

## Caratteristiche Principali

### 1. Orchestrazione Intelligente & Knowledge Graph Dinamico
* Non un chatbot: analizza il contesto e instrada l'istruzione all'agente più performante.
* Costruisce nodi cognitivi (`USER`, `DEVICE`, `AGENT`, `CONCEPT`, `MEMORY`) salvati su database a grafi e database vettoriale (Qdrant).

### 2. SysOps & Automazione DevOps
* **Esecuzione Comandi**: Supporto nativo per comandi **Debian (bash)**, **Windows (PowerShell/pwsh)** e shell remote su **SSH**.
* **Cartelle Condivise SMB (Samba)**: Creazione automatica di condivisioni di rete con permessi granulari (`smb.conf`).
* **Provisioning MySQL / MariaDB**: Creazione istantanea di database, tabelle, utenti dedicati e grant di sicurezza.
* **Scaffolding Applicativo**: Generazione autonoma di file, script di servizio `systemd`, e microservizi completi (es. FastAPI).

### 3. Auto-Programmazione & Self-Healing Loop
* Jarvis sintetizza autonomamente codice per risolvere compiti complessi o autocorreggersi.
* Il codice viene testato all'interno di una **sandbox isolata a livello di kernel** con controlli preventivi anti-breakout. Se i test passano con successo, il codice viene integrato a caldo tramite Git.

### 4. Biometria Vocale & Sintesi Maschile d'Elite
* Rilevamento continuo offline della wake-word *"Jarvis"*.
* **Speaker ID Biometrics**: Estrazione vettoriale dell'impronta vocale con confronto coseno per autorizzare comandi critici.
* Voce maschile autorevole, professionale e fluida generata a bordo macchina.

### 5. Domotica & Videosorveglianza
* **Home Assistant**: Controllo bidirezionale via WebSocket & REST API.
* **Frigate NVR**: Analisi stream RTSP, tracciamento perimetrale, persone e oggetti con trigger MQTT in tempo reale.

### 6. Client APK Edge (Smartphone & Tablet) - Zero-Config, Always-Listening & Webcam
* **Ricerca Automatica del Server (Zero-Config)**: All'avvio l'APK scansiona la rete locale tramite UDP broadcast e sonde HTTP, individuando autonomamente l'IP e la porta del server Jarvis.
* **Rendering Grafico Nativo a Schermo Intero**: Una volta localizzato il server, l'APK proietta immediatamente la grafica di Jarvis (Sfera 3D Three.js e Pannello di Controllo) con accelerazione hardware.
* **Sempre in Ascolto (Foreground Service)**: Servizio di background permanente con micro-buffer audio locale a 16 kHz: rileva la wake-word *"Jarvis"* e riconosce biometricamente l'oratore prima di trasmettere il comando.
* **Webcam & Visione Integrata**: Se autorizzata dall'utente, l'applicazione acquisisce il flusso video della webcam (frontale o posteriore) trasmettendolo in tempo reale all'agente di sicurezza e videosorveglianza di Jarvis.
* **Architettura P2P Mesh**: Più dispositivi nella LAN comunicano tra loro come nodi paritari distribuiti, garantendo sincronizzazione di stato e ridondanza operativa.

### 7. Interfaccia Web 3D Responsive (Dual-View)
* **Vista 1 (Visione Core 3D)**: Ologramma e particelle Three.js/WebGL reattive all'audio e alle frequenze della voce di Jarvis.
* **Vista 2 (Pannello di Controllo)**: Monitoraggio in tempo reale degli agenti, selezione del modello neurale, ispezione del database a nodi e log di self-healing.

---

## Architettura del Repository (per funzionalità)

Ogni funzionalità vive in una sola cartella con tutto ciò che le serve: manifest, codice Python,
rotte API e scheda del pannello. Il supervisore scopre da solo le cartelle nuove.

```text
Jarvis/
├── install.sh                          # Avvio dell'installazione (bootstrap del supervisore)
├── install.ps1                         # Avvio locale del Core su Windows
├── installer_wizard/                   # Jarvis OS: supervisore, funzionalità e interfacce
│   ├── bootstrap.sh                    # Prima installazione su Debian/Ubuntu
│   ├── backend/                        # Nucleo del supervisore (porte 80 e 8080)
│   │   ├── jarvis_supervisor.py        # Entry point: compone le app e avvia i servizi
│   │   ├── orchestrator.py             # Pipeline degli step, convergenza e riparazione
│   │   ├── updater.py                  # Aggiornamenti da GitHub con verifica e rollback
│   │   ├── feature_registry.py         # Scoperta delle funzionalità e modalità auto/1/0
│   │   ├── pages.py                    # Pagine, risorse statiche e schede delle funzionalità
│   │   ├── system_api.py               # Accesso, stato, log, azioni e configurazione
│   │   └── config.py · state.py · steps.py · health.py · access.py · …
│   ├── features/<id>/                  # Una cartella per funzionalità
│   │   ├── feature.json                # Manifest (nome, requisiti, impostazioni)
│   │   ├── *.py                        # Logica della funzionalità
│   │   ├── api.py                      # Rotte HTTP della funzionalità
│   │   └── admin.html · admin.js · admin.css   # Scheda del pannello
│   ├── widgets/<id>/                   # Widget del display (widget.json + widget.js)
│   ├── skills/<categoria>/<id>/        # Algoritmi riutilizzabili eseguiti in isolamento
│   └── web/
│       ├── shared/                     # Stile e utilità comuni
│       ├── display/                    # Display con volto 3D, voce, ascolto e widget
│       ├── admin/                      # Guscio del pannello di amministrazione
│       └── monitor/                    # Schermata di avvio e installazione
├── scripts/os/                         # Step idempotenti, unità systemd, kiosk, jarvisctl
├── docker/                             # Jarvis Core, Qdrant e inferenza GPU opzionale
├── server/                             # Jarvis Core (orchestratore cognitivo, porta 8443)
│   ├── cmd/                            # Entry point e rotte REST/WebSocket
│   ├── core/                           # Dispatcher, grafo della conoscenza, ragionamento, sicurezza
│   ├── features/                       # Agenti: casa, visione, SysOps, coder, gateway LLM, mesh
│   └── shared/                         # Errori e sanificazione dell'input
├── client_web/                         # Dashboard web 3D (React + Tailwind + Three.js)
├── client_apk/                         # Client Android Edge (Kotlin)
└── client_satellite/                   # Satelliti Linux ed ESP32
```

---

## Specifiche Server Raccomandate

| Componente | Requisito Minimo | Raccomandato (Full Edge AI) |
| :--- | :--- | :--- |
| **Sistema Operativo** | Debian 12 Minimal (x86_64 / arm64) | Debian 12 Minimal |
| **CPU** | 4 Core x86_64 / Cortex-A76 | 8+ Core moderni con supporto AVX2 / AVX-512 |
| **RAM** | 8 GB DDR4 | 16 - 32 GB DDR4/DDR5 |
| **GPU (Opzionale)** | Nessuna (CPU inference) | NVIDIA RTX (8GB+ VRAM) con driver CUDA |
| **Storage** | 30 GB SSD | 100+ GB NVMe per modelli LLM e registrazioni NVR |

---

## Avvio Rapido con Docker Compose

```bash
cd docker
docker compose up -d --build
```

Accesso ai servizi:
* **Web UI Dashboard**: `http://localhost:8443`
* **API Documentation**: `http://localhost:8443/docs`
* **Vector Store Qdrant**: `http://localhost:6333/dashboard`

---

## Sicurezza Zero-Trust & Conformità

1. **Nessun commento nel codice**: Il codice sorgente rispetta la massima purezza espressiva tramite tipizzazione statica e architettura pulita.
2. **Modularità rigorosa**: Nessun file nel repository supera il limite di 500 righe.
3. **Crittografia**: Tutti i token sono firmati crittograficamente e i dati sensibili sono protetti con cifratura autenticata AES-256-GCM.
4. **Sanitizzazione Totale**: Ispezione preliminare di tutti i comandi per prevenire command injection e violazioni della sandbox.

---

## Licenza & Crediti

Progetto ideato, architettato e sviluppato da **[NunzioTech](https://github.com/AprileNunzio)** (Nunzio Aprile).  
Rilasciato sotto licenza [MIT](LICENSE).

---

## 🚀 Prossime Implementazioni (Roadmap 2.0)
Stiamo lavorando per trasformare Jarvis da "assistente locale" a un vero **Autonomous Cognitive Orchestrator** implementando le seguenti tecnologie:

*   🧠 **Architettura a Doppio Cervello (System 1 + System 2):** Integrazione nativa del modello **Contrastive-LM (CLM-v0.1-8B)** per il routing istantaneo e la classificazione delle azioni, lasciando il ragionamento profondo ai modelli generativi (LLaMA/Mistral).
*   🗜️ **Context Compaction Lossless:** Ispirandoci a tecnologie come *fast-jev-compaction*, Jarvis sarà dotato di un sistema di pulizia della memoria a ritenzione esatta (verbatim). Invece di riassumere i log perdendo dati preziosi, l'IA deciderà in modo binario (sì/no) quali chiamate agli strumenti eliminare e quali conservare inalterate, risparmiando un'enormità di token e mantenendo il contesto perfetto.
### 🛠️ Moduli & Capabilities in Sviluppo
*   **Comunicazione:** Integrazione SMTP + Email (lettura/scrittura) e Canale Sensoriale Bot Telegram.
*   **Cognizione:** Memoria a Lungo Termine tramite Graph Database e Qdrant, + Skill Synthesis per l'auto-apprendimento.
*   **Interazione Esterna:** Ricerca Web autonoma (anti-allucinazione) e Analisi Documenti (PDF/Excel/Word via RAG).
*   **Logica & Calcolo:** Elaborazione Dati e Calcoli Matematici esatti (tramite esecuzione Python in Sandbox isolata).
*   **Produttività:** Generazione di Contenuti avanzata e Automazioni Complesse multi-step.
*   **Intrattenimento:** Gestione Musicale professionale con indexing SQLite locale, lettura tag ID3 e supporto NAS/SMB per lo streaming MP3.
