import time
from typing import Dict, Any, List
from pydantic import BaseModel, Field

class PeerNode(BaseModel):
    node_id: str
    device_type: str
    ip_address: str
    port: int
    last_heartbeat: float = Field(default_factory=time.time)
    public_key_fingerprint: str
    synced_state_version: int = 1

class MeshBlock(BaseModel):
    block_index: int
    prev_hash: str
    timestamp: float
    data: Dict[str, Any]
    validator_node: str
    signature: str

class MeshSyncPayload(BaseModel):
    origin_node_id: str
    blocks: List[MeshBlock]
    active_peers: List[PeerNode]
