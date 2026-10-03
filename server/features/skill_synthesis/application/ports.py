from typing import List, Optional, Protocol, Tuple

from server.features.skill_synthesis.domain.tool import DynamicTool


class ToolStore(Protocol):
    def all(self) -> List[DynamicTool]: ...

    def get(self, name: str) -> Optional[DynamicTool]: ...

    def save(self, tool: DynamicTool) -> None: ...

    def delete(self, name: str) -> bool: ...


class ApprovalPort(Protocol):
    async def approve(self, tool: DynamicTool) -> Tuple[bool, str]: ...
