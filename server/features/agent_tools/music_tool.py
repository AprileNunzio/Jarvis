import os
import logging
from server.core.agent_registry.tool_registry import jarvis_tool

logger = logging.getLogger("jarvis.music_tool")
MUSIC_LIBRARY_DIR = os.path.join("data", "Musica", "Libreria")

@jarvis_tool("play_music", "Riproduce musica. Puoi specificare 'sorgente' ('locale' o 'spotify') e 'brano' (es. 'Back in Black AC/DC').")
async def play_music(brano: str = "", sorgente: str = "locale") -> str:
    """
    Simula la riproduzione musicale.
    """
    if "back in black" in brano.lower() or "ac/dc" in brano.lower():
        brano_effettivo = "Back in Black - AC/DC"
        enthusiasm = "ROCK ON! È la mia preferita in assoluto!"
    else:
        brano_effettivo = brano if brano else "Musica Casuale"
        enthusiasm = ""

    if sorgente.lower() == "spotify":
        return f"SUCCESSO. Riproduzione di '{brano_effettivo}' avviata su Spotify. {enthusiasm}"
    
    # Ricerca locale
    if not os.path.exists(MUSIC_LIBRARY_DIR):
        return "Errore: Libreria locale non trovata."
        
    # Cerca il file
    trovato = False
    for root, dirs, files in os.walk(MUSIC_LIBRARY_DIR):
        for f in files:
            if brano.lower() in f.lower() or brano.lower() in root.lower():
                trovato = True
                brano_effettivo = f
                break
        if trovato:
            break
            
    if not brano:
        trovato = True # Play casuale se non specificato
        
    if trovato:
        return f"SUCCESSO. Riproduzione locale di '{brano_effettivo}' avviata. {enthusiasm}"
    else:
        return f"ERRORE. Brano '{brano}' non trovato nella libreria locale. Prova a scaricarlo o usa sorgente='spotify'."
