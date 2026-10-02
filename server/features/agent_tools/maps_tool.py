import logging
from server.core.agent_registry.tool_registry import jarvis_tool

logger = logging.getLogger("jarvis.maps_tool")

@jarvis_tool("show_maps_route", "Mostra mappa e traffico. 'destinazione' DEVE essere SOLO il nome del luogo o citta' (es. 'Roma'), SENZA punteggiatura o resti della frase. 'partenza' e' opzionale (es. 'Napoli').")
async def show_maps_route(destinazione: str, partenza: str = "") -> str:
    """
    Mostra il widget di Google Maps / OSM.
    """
    import re
    try:
        from installer_wizard.features.maps.maps import answer
        
        dest = re.sub(r"[\?\.\!].*$", "", destinazione).strip()
        part = re.sub(r"[\?\.\!].*$", "", partenza).strip() if partenza else ""
        
        testo_domanda = f"da {part} a {dest}" if part else f"per {dest}"
        speech, payload = await answer(testo_domanda)
        return f"SUCCESSO. Widget inviato. Dì ESATTAMENTE questo all'utente: '{speech}'"
    except Exception as e:
        logger.error(f"Errore nel calcolo del percorso Maps: {e}")
        return f"Errore nel caricamento delle mappe: {str(e)}"
