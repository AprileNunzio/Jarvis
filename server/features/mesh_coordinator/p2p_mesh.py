import hashlib
import json
import time
from typing import Any, Dict, List
from server.features.mesh_coordinator.mesh_models import PeerNode, MeshBlock, MeshSyncPayload

class P2PMeshCoordinator:
    def __init__(self, local_node_id: str = "jarvis_server_master") -> None:
        self._local_node_id = local_node_id
        self._peers: Dict[str, PeerNode] = {}
        self._ledger: List[MeshBlock] = []
        self._init_genesis_block()

    def _init_genesis_block(self) -> None:
        genesis = MeshBlock(
            block_index=0,
            prev_hash="0" * 64,
            timestamp=time.time(),
            data={"event": "GENESIS_JARVIS_MESH"},
            validator_node=self._local_node_id,
            signature="GENESIS_SIG"
        )
        self._ledger.append(genesis)

    def register_peer(self, peer: PeerNode) -> None:
        self._peers[peer.node_id] = peer

    def commit_state_event(self, event_data: Dict[str, Any]) -> MeshBlock:
        prev_block = self._ledger[-1]
        raw_payload = json.dumps(event_data, sort_keys=True)
        block_content = f"{prev_block.block_index + 1}{prev_block.signature}{raw_payload}"
        calculated_hash = hashlib.sha256(block_content.encode("utf-8")).hexdigest()

        new_block = MeshBlock(
            block_index=prev_block.block_index + 1,
            prev_hash=calculated_hash,
            timestamp=time.time(),
            data=event_data,
            validator_node=self._local_node_id,
            signature=f"sig_{calculated_hash[:16]}"
        )
        self._ledger.append(new_block)
        return new_block

    def get_sync_payload(self) -> MeshSyncPayload:
        return MeshSyncPayload(
            origin_node_id=self._local_node_id,
            blocks=self._ledger[-50:],
            active_peers=list(self._peers.values())
        )

p2p_mesh = P2PMeshCoordinator()
