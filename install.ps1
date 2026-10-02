$Host.UI.RawUI.WindowTitle = "Jarvis Orchestrator Installer - NunzioTech"
Clear-Host

Write-Host @"
         ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗
         ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝
         ██║███████║██████╔╝██║   ██║██║███████╗
    ██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║
    ╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║
     ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝
       AUTONOMOUS COGNITIVE ORCHESTRATOR
================================================================
   ENGINEERED & POWERED BY NUNZIOTECH (C) 2026
================================================================
"@ -ForegroundColor Cyan

function Write-Step {
    param([string]$Text)
    Write-Host "[NunzioTech Step] " -ForegroundColor Cyan -NoNewline
    Write-Host $Text -ForegroundColor White
}

function Write-Success {
    param([string]$Text)
    Write-Host "[SUCCESS] " -ForegroundColor Green -NoNewline
    Write-Host $Text -ForegroundColor White
}

Write-Step "1/5 - Verifica runtime Python e Node.js..."
$pythonVersion = python --version 2>$null
if (-not $pythonVersion) {
    Write-Host "Python 3.11+ non trovato su PATH. Installare Python prima di procedere." -ForegroundColor Red
    exit 1
}
Write-Success "Ambiente runtime rilevato: $pythonVersion"

Write-Step "2/5 - Preparazione directory isolate di memoria..."
New-Item -ItemType Directory -Force -Path "data\db" | Out-Null
New-Item -ItemType Directory -Force -Path "data\certs" | Out-Null
Write-Success "Directory di storage preparate."

Write-Step "3/5 - Installazione dipendenze server Python..."
pip install -r server\requirements.txt --quiet
Write-Success "Dipendenze server installate."

Write-Step "4/5 - Configurazione client web console..."
Set-Location client_web
npm install --silent
Set-Location ..
Write-Success "Moduli interfaccia web pronti."

Write-Step "5/5 - Avvio del Server Jarvis Orchestrator..."
Write-Host "================================================================" -ForegroundColor Blue
Write-Host "   JARVIS PRONTO ALL'USO SULLA MACCHINA LOCALE                  " -ForegroundColor Green
Write-Host "   NunzioTech Autonomous System 2026                            " -ForegroundColor White
Write-Host "================================================================" -ForegroundColor Blue
python -m server.cmd.main
