import re

import httpx

from config import ollama_url, env_get
from features.study.constants import USER_AGENT, log


class StudySources:
    def _model(self) -> str:
        return self.settings.get("model") or env_get("JARVIS_LLM_MODEL", "qwen2.5:3b")

    def _embed_model(self) -> str:
        return env_get("JARVIS_EMBED_MODEL", "nomic-embed-text")

    async def llm_json(self, system: str, prompt: str, max_tokens: int = 600) -> dict:
        from features.brain.llm import BrainUnavailable, generate
        try:
            result = await generate(prompt, system=system, as_json=True, max_tokens=max_tokens, temperature=0.35,
                                    kind="deep", prefer=[self.settings.get("model")], timeout=900)
        except (BrainUnavailable, ValueError) as exc:
            log.info("Studio senza cervello disponibile: %s", exc)
            return {}
        return result if isinstance(result, dict) else {}

    async def embed(self, texts: list, query: bool = False) -> list:
        model = self._embed_model()
        if "nomic" in model:
            prefix = "search_query: " if query else "search_document: "
            texts = [prefix + t for t in texts]
        async with httpx.AsyncClient(timeout=httpx.Timeout(120, connect=5)) as client:
            r = await client.post(f"{ollama_url()}/api/embed", json={"model": model, "input": texts})
            if r.status_code == 404:
                out = []
                for t in texts:
                    rr = await client.post(f"{ollama_url()}/api/embeddings", json={"model": model, "prompt": t})
                    rr.raise_for_status()
                    out.append(rr.json()["embedding"])
                return out
            r.raise_for_status()
            return r.json()["embeddings"]

    async def _wiki(self, client: httpx.AsyncClient, query: str, lang: str, limit: int) -> dict | None:
        api = f"https://{lang}.wikipedia.org/w/api.php"
        r = await client.get(api, params={"action": "query", "list": "search", "srsearch": query,
                                          "srlimit": 1, "format": "json"})
        hits = r.json().get("query", {}).get("search", [])
        if not hits:
            return None
        title = hits[0]["title"]
        r = await client.get(api, params={"action": "query", "prop": "extracts", "explaintext": 1,
                                          "titles": title, "redirects": 1, "format": "json"})
        pages = r.json().get("query", {}).get("pages", {})
        text = next(iter(pages.values()), {}).get("extract", "")
        text = re.sub(r"\n==+ *(Note|Bibliografia|Voci correlate|Altri progetti|Collegamenti esterni|"
                      r"References|See also|External links|Further reading)[\s\S]*", "", text)
        text = re.sub(r"\n{2,}", "\n", text).strip()
        if len(text) < 300:
            return None
        return {"title": title, "url": f"https://{lang}.wikipedia.org/wiki/{title.replace(' ', '_')}",
                "text": text[:limit], "lang": lang}

    async def sources(self, topic: dict, lesson: dict, level: int) -> list:
        if not self.settings.get("web_sources"):
            return []
        query = f"{lesson['title']} {topic['name']}"
        found = []
        try:
            async with httpx.AsyncClient(timeout=15, headers={"User-Agent": USER_AGENT}) as client:
                langs = ("it", "en") if level >= 3 else ("it",)
                for lang in langs:
                    src = await self._wiki(client, query, lang, 3200 if level >= 3 else 4200)
                    if not src and lang == "it":
                        src = await self._wiki(client, lesson["title"], lang, 4200)
                    if src:
                        found.append(src)
                if not found:
                    src = await self._wiki(client, query, "en", 4200)
                    if src:
                        found.append(src)
        except (httpx.HTTPError, ValueError) as exc:
            log.info("Fonti non disponibili per «%s»: %s", lesson["title"], exc)
        return found
