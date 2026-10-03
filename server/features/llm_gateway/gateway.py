import time
import httpx
import logging
import os
from server.config.env import settings
from server.core.orchestrator.brain_routing import brain_order_for, keep_alive_for
from server.features.llm_gateway.supervisor_bridge import BridgeError, CallTrace, bridge, is_remote_ref
from server.features.llm_gateway.contracts import SYNTHETIC_MODEL, LLMRequest, LLMResponse

logger = logging.getLogger("jarvis.llm_gateway")


class LLMGateway:
    def __init__(self) -> None:
        self._ollama_url = settings.OLLAMA_BASE_URL
        self._gemini_api_key = os.getenv("GEMINI_API_KEY", "")
        self._claude_api_key = os.getenv("ANTHROPIC_API_KEY", "")
        self._provider_chain = ["ollama", "gemini", "claude"]

    async def generate_completion(self, request: LLMRequest) -> LLMResponse:
        start_time = time.time()
        last_error = ""

        for provider in self._provider_chain:
            try:
                logger.info(f"LLMGateway attempting inference via {provider}...")
                if provider == "ollama":
                    return await self._call_ollama(request, start_time)
                elif provider == "gemini" and self._gemini_api_key:
                    return await self._call_gemini(request, start_time)
                elif provider == "claude" and self._claude_api_key:
                    return await self._call_claude(request, start_time)
            except Exception as e:
                logger.warning(f"Inference via {provider} failed: {e}")
                last_error = str(e)
                continue

        logger.error("All providers in chain failed. Using deterministic fallback.")
        return self._fallback_synthetic_response(request, start_time, last_error)

    async def _call_ollama(self, request: LLMRequest, start_time: float) -> LLMResponse:
        chain = [m for m in request.models if m] or brain_order_for(request.component) or [settings.JARVIS_LLM_MODEL or request.model_name]
        messages = [{"role": m.role, "content": m.content} for m in request.messages]
        if request.system_prompt:
            messages.insert(0, {"role": "system", "content": request.system_prompt})
        trace = CallTrace(bridge, request.component, "richiesta del Core", chain) if request.component else None
        errors = []
        for model in chain:
            if trace:
                await trace.attempt(model)
            started = time.time()
            try:
                content, tokens = await self._complete_one(model, messages, request, chain)
            except (httpx.HTTPError, BridgeError, ValueError) as exc:
                logger.warning("Modello %s non disponibile: %s", model, exc)
                errors.append(f"{model}: {exc}")
                if trace:
                    await trace.failed(model, str(exc) or type(exc).__name__)
                continue
            if not content.strip():
                errors.append(f"{model}: risposta vuota")
                if trace:
                    await trace.failed(model, "risposta vuota")
                continue
            if trace:
                await trace.done(model, (time.time() - started) * 1000, content)
            return LLMResponse(
                content=content,
                model_used=model if is_remote_ref(model) else f"ollama/{model}",
                tokens_consumed=tokens,
                duration_ms=(time.time() - start_time) * 1000,
            )
        if trace:
            await trace.abort("; ".join(errors)[:160] or "nessun modello")
        raise RuntimeError("; ".join(errors) or "nessun modello Ollama disponibile")

    async def _complete_one(self, model: str, messages: list, request: LLMRequest, chain: list) -> tuple:
        if is_remote_ref(model):
            reply = await bridge.complete(model, [m for m in messages if m["role"] != "system"],
                                          request.system_prompt, request.max_tokens, request.temperature)
            return reply.get("text", ""), int(reply.get("tokens") or 0)
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "keep_alive": keep_alive_for(model, "24h" if model == (request.pinned or chain[0]) else "5m"),
            "options": {"temperature": request.temperature, "num_predict": request.max_tokens},
        }
        async with httpx.AsyncClient(timeout=180.0) as client:
            res = await client.post(f"{self._ollama_url}/api/chat", json=payload)
            res.raise_for_status()
            data = res.json()
        return data.get("message", {}).get("content", ""), data.get("eval_count", 0)

    async def _call_gemini(self, request: LLMRequest, start_time: float) -> LLMResponse:
        contents = []
        if request.system_prompt:
            contents.append({
                "role": "user",
                "parts": [{"text": f"System Context: {request.system_prompt}\n\n"}]
            })
            contents.append({
                "role": "model",
                "parts": [{"text": "Understood. I will follow the system context."}]
            })
            
        for m in request.messages:
            role = "model" if m.role == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": m.content}]})

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": request.temperature,
                "maxOutputTokens": request.max_tokens,
            }
        }
        
        gemini_model = "gemini-1.5-pro-latest"

        async with httpx.AsyncClient(timeout=60.0) as client:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{gemini_model}:generateContent?key={self._gemini_api_key}"
            res = await client.post(url, json=payload)
            res.raise_for_status()
            data = res.json()
            content = data["candidates"][0]["content"]["parts"][0]["text"]
            elapsed = (time.time() - start_time) * 1000
            return LLMResponse(
                content=content,
                model_used=gemini_model,
                tokens_consumed=0,
                duration_ms=elapsed
            )

    async def _call_claude(self, request: LLMRequest, start_time: float) -> LLMResponse:
        messages = []
        for m in request.messages:
            role = "assistant" if m.role == "assistant" else "user"
            messages.append({"role": role, "content": m.content})

        payload = {
            "model": "claude-3-opus-20240229",
            "messages": messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }
        if request.system_prompt:
            payload["system"] = request.system_prompt

        headers = {
            "x-api-key": self._claude_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            res = await client.post("https://api.anthropic.com/v1/messages", json=payload, headers=headers)
            res.raise_for_status()
            data = res.json()
            content = data["content"][0]["text"]
            tokens = data.get("usage", {}).get("output_tokens", 0)
            elapsed = (time.time() - start_time) * 1000
            return LLMResponse(
                content=content,
                model_used="claude-3",
                tokens_consumed=tokens,
                duration_ms=elapsed
            )

    def _fallback_synthetic_response(self, request: LLMRequest, start_time: float, error: str) -> LLMResponse:
        elapsed = (time.time() - start_time) * 1000
        user_query = request.messages[-1].content if request.messages else ""
        return LLMResponse(
            content=f"Jarvis Core acknowledges the request: '{user_query}'. Operating in deterministic autonomous mode. (Last error: {error})",
            model_used=SYNTHETIC_MODEL,
            tokens_consumed=25,
            duration_ms=elapsed
        )


llm_gateway = LLMGateway()
