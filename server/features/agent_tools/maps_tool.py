import logging
from server.core.agent_registry.tool_registry import jarvis_tool

logger = logging.getLogger("jarvis.maps_tool")

@jarvis_tool("show_maps_route", "Mostra la mappa e il traffico per una destinazione. Esegui questo quando l'utente chiede indicazioni stradali, percorsi o informazioni sul traffico.")
async def show_maps_route(partenza: str, destinazione: str) -> str:
    """
    Mostra il widget di Google Maps / OSM.
    """
    try:
        from installer_wizard.features.maps.maps import answer
        testo_domanda = f"da {partenza} a {destinazione}"
        speech, payload = await answer(testo_domanda)
        return f"SUCCESSO. Ho generato l'itinerario. Il widget apparirà all'utente. Rispondi usando questo testo: '{speech}'"
    except Exception as e:
        logger.error(f"Errore nel calcolo del percorso Maps: {e}")
        return f"Errore nel caricamento delle mappe: {str(e)}"
