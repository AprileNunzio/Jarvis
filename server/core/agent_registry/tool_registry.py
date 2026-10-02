import logging
import inspect
from typing import Callable, Dict, Any

logger = logging.getLogger("jarvis.tool_registry")

class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, dict] = {}

    def register(self, name: str, description: str):
        """
        Decoratore per esporre automaticamente una funzione come strumento (Tool) 
        per tutti gli agenti cognitivi e il ReAct Loop.
        """
        def decorator(func: Callable):
            self._tools[name] = {
                "name": name,
                "description": description,
                "func": func,
                "signature": inspect.signature(func)
            }
            return func
        return decorator

    def get_all_tools(self) -> Dict[str, dict]:
        return self._tools

    def inject_tools_into_loop(self, react_loop: Any):
        """
        Inietta automaticamente tutti i tools registrati nel sistema 
        all'interno di un ReActLoop.
        """
        for name, tool_data in self._tools.items():
            react_loop.register_tool(name, tool_data["description"], tool_data["func"])
        logger.info(f"Auto-injected {len(self._tools)} tools into ReAct loop.")

global_tool_registry = ToolRegistry()
jarvis_tool = global_tool_registry.register
