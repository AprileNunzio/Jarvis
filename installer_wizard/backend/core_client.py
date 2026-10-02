import httpx

from config import CORE_URL, DEMO


class CoreClient:
    def __init__(self) -> None:
        self.token = ""

    async def _token(self, client: httpx.AsyncClient) -> str:
        if not self.token:
            r = await client.post(f"{CORE_URL}/api/v1/auth/exchange",
                                  json={"client_id": "jarvis-supervisor", "client_secret": "local",
                                        "device_type": "kiosk"})
            r.raise_for_status()
            self.token = r.json()["token"]
        return self.token

    async def request(self, method: str, path: str, **kwargs) -> httpx.Response:
        async with httpx.AsyncClient(timeout=kwargs.pop("timeout", 30)) as client:
            for _ in range(2):
                headers = {"Authorization": f"Bearer {await self._token(client)}"}
                r = await client.request(method, f"{CORE_URL}{path}", headers=headers, **kwargs)
                if r.status_code != 401:
                    return r
                self.token = ""
            return r

    async def remember(self, *items: tuple[str, dict]) -> None:
        if DEMO:
            return
        try:
            for kind, payload in items:
                await self.request("POST", f"/api/v1/knowledge/{kind}", timeout=10, json=payload)
        except httpx.HTTPError:
            pass


core = CoreClient()
