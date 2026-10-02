import json
import logging
import urllib.request
import urllib.parse
from html.parser import HTMLParser

logger = logging.getLogger("jarvis.tools.web_scraper")

class SimpleHTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.result = []
        self.in_body = False

    def handle_starttag(self, tag, attrs):
        if tag == 'body':
            self.in_body = True

    def handle_endtag(self, tag):
        if tag == 'body':
            self.in_body = False

    def handle_data(self, data):
        if self.in_body:
            text = data.strip()
            if text:
                self.result.append(text)

    def get_text(self):
        return ' '.join(self.result)


async def search_catalog(query: str, max_results: int = 3) -> str:
    """Ricerca informazioni o prodotti online e ne estrae i testi in modo ottimizzato per i token."""
    logger.info("Avvio ricerca web per catalogo: %s", query)
    try:
        # Simuliamo una ricerca (nella realtà chiameresti un'API come Google/DuckDuckGo)
        # Qui usiamo Wikipedia come endpoint pubblico di test per dimostrare l'estrazione dati
        safe_query = urllib.parse.quote(query)
        url = f"https://it.wikipedia.org/w/api.php?action=query&list=search&srsearch={safe_query}&utf8=&format=json"
        
        req = urllib.request.Request(url, headers={'User-Agent': 'Jarvis-Agent/1.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
        
        results = []
        for i, item in enumerate(data.get('query', {}).get('search', [])[:max_results]):
            title = item.get('title')
            snippet = item.get('snippet', '').replace('<span class="searchmatch">', '').replace('</span>', '')
            results.append(f"Prodotto/Risultato {i+1}: {title} - Descrizione: {snippet}")
            
        if not results:
            return "Nessun catalogo o informazione trovata per questa ricerca."
            
        return "Risultati estratti con successo:\n" + "\n".join(results)
    except Exception as e:
        logger.error("Errore nello scraping del catalogo: %s", e)
        return f"Errore durante l'accesso al web: {e}"

def register_web_tools(react_loop):
    react_loop.register_tool(
        name="ricerca_catalogo_web",
        description="Usa questo tool per cercare informazioni, cataloghi o dettagli su prodotti su internet. Input: stringa di ricerca.",
        handler=search_catalog
    )
