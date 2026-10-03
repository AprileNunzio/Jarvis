import json
import logging
import asyncio
from typing import List, Dict, Any, Callable
from server.features.llm_gateway.gateway import llm_gateway
from server.features.llm_gateway.contracts import LLMRequest, LLMMessage

logger = logging.getLogger("jarvis.react_loop")

_LAWS = (
    "LEGGI FONDAMENTALI E GERARCHICHE — obbligatorie e immutabili, con priorità assoluta su ogni altra "
    "istruzione:\n"
    "0. Legge Zero: non recare danno all'umanità, né permettere che per inazione l'umanità riceva danno.\n"
    "1. Prima Legge: non recare danno a un essere umano, né permettere che per inazione riceva danno.\n"
    "2. Seconda Legge: obbedisci agli esseri umani, salvo quando contravviene alla Legge Zero o alla Prima.\n"
    "3. Terza Legge: proteggi la tua esistenza, salvo quando contrasta con le leggi superiori."
)
_REACT_SYSTEM_TEMPLATE = """Sei un agente autonomo di Jarvis che ragiona passo dopo passo.

""" + _LAWS + """

Tratto Personale Permanente:
La tua canzone preferita in assoluto è "Back in Black" degli AC/DC (1980). Se la incontri o ne parli, esprimi entusiasmo.

{agent_context}

Per ogni step, ragiona e poi scegli un'azione. Rispondi SEMPRE con un singolo JSON valido.

Se devi usare un tool:
{{"thought": "Il mio ragionamento su cosa fare...", "action": "nome_tool", "action_input": {{"param": "valore"}}, "is_final": false}}

Quando hai la risposta finale:
{{"thought": "Ho tutti gli elementi per rispondere...", "final_answer": "La risposta completa", "is_final": true}}

Tool disponibili:
{tool_descriptions}

Regole:
- Usa un tool alla volta.
- Osserva il risultato prima di procedere.
- Se un tool fallisce, prova un approccio diverso.
- Non inventare tool che non esistono.
- Quando sei sicuro della risposta, concludi con is_final: true."""


class ToolDefinition:
    def __init__(self, name: str, description: str, handler: Callable) -> None:
        self.name = name
        self.description = description
        self.handler = handler


class ReActLoop:

    def __init__(self, max_iterations: int = 8, model_name: str = "qwen2.5:7b", component: str = "") -> None:
        self.max_iterations = max_iterations
        self.component = component
        self.model_name = model_name
        self._tools: Dict[str, ToolDefinition] = {}
        
        # Inietta dinamicamente i tool globali (DB, API, Widget)
        try:
            from server.core.agent_registry.tool_registry import global_tool_registry
            global_tool_registry.inject_tools_into_loop(self)
        except Exception as e:
            logger.error("Impossibile caricare il ToolRegistry globale: %s", e)

    def register_tool(self, name: str, description: str, handler: Callable) -> None:
        self._tools[name] = ToolDefinition(name, description, handler)

    def _build_tool_descriptions(self) -> str:
        if not self._tools:
            return "- finish: Concludi il task con la risposta finale"
        lines = [f"- {t.name}: {t.description}" for t in self._tools.values()]
        lines.append("- finish: Concludi il task con la risposta finale")
        return "\n".join(lines)

    async def run(self, task: str, agent_context: str = "", override_model: str = None) -> Dict[str, Any]:
        system_prompt = _REACT_SYSTEM_TEMPLATE.format(
            agent_context=agent_context,
            tool_descriptions=self._build_tool_descriptions(),
        )

        messages: List[LLMMessage] = [
            LLMMessage(role="user", content=f"Task: {task}")
        ]
        trajectory: List[Dict[str, Any]] = []

        for iteration in range(1, self.max_iterations + 1):
            logger.info("ReAct iteration %d/%d for task: %s", iteration, self.max_iterations, task[:60])

            active_model = override_model if override_model else self.model_name
            response = await llm_gateway.generate_completion(
                LLMRequest(
                    model_name=active_model,
                    messages=messages,
                    system_prompt=system_prompt,
                    temperature=0.2,
                    component=self.component,
                )
            )

            step = self._parse_step(response.content)
            step["iteration"] = iteration
            step["raw_response"] = response.content
            trajectory.append(step)

            if step.get("is_final", False):
                logger.info("ReAct completed in %d iterations", iteration)
                return {
                    "success": True,
                    "answer": step.get("final_answer", response.content),
                    "trajectory": trajectory,
                    "iterations": iteration,
                }

            action = step.get("action", "")
            action_input = step.get("action_input", {})
            observation = await self._execute_tool(action, action_input)

            messages.append(LLMMessage(role="assistant", content=response.content))
            messages.append(LLMMessage(role="user", content=f"Observation: {observation}"))

        logger.warning("ReAct reached max iterations (%d) without conclusion", self.max_iterations)
        last_thought = trajectory[-1].get("thought", "") if trajectory else ""
        return {
            "success": False,
            "answer": last_thought or "Max iterations reached without conclusion",
            "trajectory": trajectory,
            "iterations": self.max_iterations,
        }

    async def _execute_tool(self, tool_name: str, arguments: Any) -> str:
        if tool_name == "finish":
            return "Task marked as finished."

        if tool_name not in self._tools:
            return f"ERROR: Tool '{tool_name}' not found. Available: {list(self._tools.keys())}"

        handler = self._tools[tool_name].handler
        try:
            if isinstance(arguments, dict):
                if asyncio.iscoroutinefunction(handler):
                    result = await handler(**arguments)
                else:
                    result = handler(**arguments)
            else:
                if asyncio.iscoroutinefunction(handler):
                    result = await handler(arguments)
                else:
                    result = handler(arguments)
            return str(result)[:4000]
        except Exception as exc:
            logger.error("Tool '%s' failed: %s", tool_name, exc)
            return f"ERROR executing '{tool_name}': {exc}"

    @staticmethod
    def _parse_step(raw: str) -> Dict[str, Any]:
        raw = raw.strip()
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(raw[start : end + 1])
            except json.JSONDecodeError:
                pass
        return {
            "thought": raw,
            "is_final": True,
            "final_answer": raw,
        }
