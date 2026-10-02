from features.agent.registry import tool
from features.documents import jobs
from features.shares import archive


@tool("create_document", "crea documenti Office/LibreOffice professionali (Word, Excel, PowerPoint, ODT, ODS, ODP, PDF) "
      "con tema grafico, tabelle e grafici; con più documenti o la parola progetto crea una cartella di progetto con "
      "sottocartelle, documenti collegati tra loro e un indice",
      {"request": "descrizione completa: tipo, formato, contenuto, stile"})
async def create_document(request: str) -> str:
    entry = await jobs.run(str(request))
    files = ", ".join(str(archive.ROOT / f) for f in entry["files"])
    return f"creato «{entry['title']}» ({entry['summary']}): {files}"
