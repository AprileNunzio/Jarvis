from abc import ABC, abstractmethod
from typing import Dict, Any, List
from pydantic import BaseModel, Field

class AgentTaskRequest(BaseModel):
    task_id: str
    user_id: str
    intent: str
    raw_query: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = 1.0

class AgentTaskResponse(BaseModel):
    task_id: str
    agent_id: str
    status: str
    result_data: Dict[str, Any] = Field(default_factory=dict)
    speech_output: str
    execution_time_ms: float

class BaseAgent(ABC):
    @property
    @abstractmethod
    def agent_id(self) -> str:
        pass

    @property
    @abstractmethod
    def capabilities(self) -> List[str]:
        pass

    @abstractmethod
    async def can_handle(self, request: AgentTaskRequest) -> float:
        pass

    @abstractmethod
    async def execute(self, request: AgentTaskRequest) -> AgentTaskResponse:
        pass
