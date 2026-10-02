from typing import List, Optional
from pydantic import BaseModel, Field

class LLMMessage(BaseModel):
    role: str
    content: str

class LLMRequest(BaseModel):
    model_name: str
    messages: List[LLMMessage]
    temperature: float = 0.2
    max_tokens: int = 2048
    stream: bool = False
    system_prompt: Optional[str] = None
    models: List[str] = Field(default_factory=list)
    pinned: str = ""

class LLMResponse(BaseModel):
    content: str
    model_used: str
    tokens_consumed: int
    duration_ms: float
