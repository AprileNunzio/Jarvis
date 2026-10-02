from enum import Enum
from typing import Dict, Any, List
from pydantic import BaseModel, Field

class NodeType(str, Enum):
    USER = "USER"
    DEVICE = "DEVICE"
    LOCATION = "LOCATION"
    AGENT = "AGENT"
    SKILL = "SKILL"
    CONCEPT = "CONCEPT"
    MEMORY = "MEMORY"

class RelationType(str, Enum):
    OWNS = "OWNS"
    LOCATED_IN = "LOCATED_IN"
    CAPABLE_OF = "CAPABLE_OF"
    DEPENDS_ON = "DEPENDS_ON"
    TRIGGERED_BY = "TRIGGERED_BY"
    CONNECTED_TO = "CONNECTED_TO"

class KnowledgeNode(BaseModel):
    id: str
    node_type: NodeType
    label: str
    properties: Dict[str, Any] = Field(default_factory=dict)
    created_at: float
    updated_at: float

class KnowledgeEdge(BaseModel):
    source_id: str
    target_id: str
    relation_type: RelationType
    weight: float = 1.0
    properties: Dict[str, Any] = Field(default_factory=dict)

class GraphSnapshot(BaseModel):
    nodes: List[KnowledgeNode]
    edges: List[KnowledgeEdge]
