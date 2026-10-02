import logging
from duckduckgo_search import DDGS
from server.core.agent_registry.tool_registry import jarvis_tool

logger = logging.getLogger("jarvis.web_search_tool")

@jarvis_tool(
    "web_search", 
    "Cerca informazioni su internet in tempo reale tramite DuckDuckGo. Usa per trovare prezzi, orari, recensioni o notizie aggiornate (es. per pianificare viaggi o rispondere a domande di attualità)."
)
async def web_search(query: str, max_results: int = 5) -> str:
    """
    Esegue una ricerca web live usando DuckDuckGo Search e ritorna un riassunto dei risultati.
    """
    logger.info(f"Eseguendo ricerca web live per: '{query}'")
    try:
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append(f"Titolo: {r.get('title', '')}\nLink: {r.get('href', '')}\nSnippet: {r.get('body', '')}")
        
        if not results:
            return f"Nessun risultato trovato per la ricerca '{query}'."
            
        return "Risultati Web in Tempo Reale:\n\n" + "\n---\n".join(results)
    except Exception as e:
        logger.error(f"Errore nella ricerca web: {e}")
        return f"Impossibile completare la ricerca web: {str(e)}"
