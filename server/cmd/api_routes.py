import base64
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from server.core.orchestrator.dispatcher import orchestrator_dispatcher
from server.core.context_graph.graph_client import graph_client
from server.core.security_guard.token_provider import token_provider
from server.features.voice_biometrics.tts_engine import tts_engine
from server.features.voice_biometrics.audio_contracts import TTSRequest
from server.features.mesh_coordinator.p2p_mesh import p2p_mesh
from server.features.mesh_coordinator.mesh_models import PeerNode

router = APIRouter(prefix="/api/v1")

class AuthExchangeRequest(BaseModel):
    client_id: str
    client_secret: str
    device_type: str

class UserCommandPayload(BaseModel):
    query: str
    device_id: str = "web_console"
    voice_pcm_base64: str = ""
    context: Dict[str, Any] = {}


class KnowledgeNodePayload(BaseModel):
    id: str
    node_type: str
    label: str
    properties: Dict[str, Any] = {}

LOOPBACK = {"127.0.0.1", "::1", "localhost"}

@router.post("/auth/exchange")
async def exchange_token(payload: AuthExchangeRequest, request: Request) -> Dict[str, Any]:
    if not request.client or request.client.host not in LOOPBACK:
        raise HTTPException(status_code=403, detail="Token rilasciati solo al supervisore locale")
    token = token_provider.issue_token(
        subject=payload.client_id,
        claims={"device_type": payload.device_type, "role": "OPERATOR"}
    )
    return {"status": "success", "token": token}

@router.post("/command")
async def handle_user_command(payload: UserCommandPayload) -> Dict[str, Any]:
    speaker_id = "user_primary"
    biometric_score = 0.95

    if payload.voice_pcm_base64:
        raw_pcm = base64.b64decode(payload.voice_pcm_base64)
        if len(raw_pcm) > 0:
            pass

    response = await orchestrator_dispatcher.dispatch_user_command(
        raw_query=payload.query,
        speaker_id=speaker_id,
        device_id=payload.device_id,
        biometric_score=biometric_score,
        context_override=payload.context or None,
    )

    p2p_mesh.commit_state_event({
        "event_type": "USER_COMMAND_EXECUTED",
        "task_id": response.task_id,
        "agent": response.agent_id,
        "status": response.status
    })

    return {
        "status": "success",
        "task_id": response.task_id,
        "agent_id": response.agent_id,
        "speech_output": response.speech_output,
        "execution_time_ms": response.execution_time_ms,
        "result_data": response.result_data
    }

@router.get("/knowledge/graph")
async def get_knowledge_graph_snapshot() -> Dict[str, Any]:
    snapshot = graph_client.export_snapshot()
    return {"status": "success", "graph": snapshot.model_dump()}

@router.post("/knowledge/node")
async def upsert_knowledge_node(payload: KnowledgeNodePayload) -> Dict[str, Any]:
    from server.core.context_graph.node_schema import NodeType
    try:
        node_type = NodeType(payload.node_type)
    except ValueError:
        return {"status": "error", "message": f"Tipo di nodo non valido: {payload.node_type}"}
    graph_client.upsert_node(node_id=payload.id, node_type=node_type, label=payload.label,
                             properties=payload.properties)
    return {"status": "success", "id": payload.id}


class KnowledgeEdgePayload(BaseModel):
    source_id: str
    target_id: str
    relation_type: str = "CONNECTED_TO"
    weight: float = 1.0


@router.post("/knowledge/edge")
async def link_knowledge_nodes(payload: KnowledgeEdgePayload) -> Dict[str, Any]:
    from server.core.context_graph.node_schema import RelationType
    try:
        relation = RelationType(payload.relation_type)
    except ValueError:
        return {"status": "error", "message": f"Tipo di relazione non valido: {payload.relation_type}"}
    try:
        graph_client.link_nodes(payload.source_id, payload.target_id, relation, payload.weight)
    except Exception as exc:
        return {"status": "error", "message": str(exc)}
    return {"status": "success"}


@router.post("/tts/synthesize")
async def synthesize_speech(payload: TTSRequest) -> Response:
    wav_bytes = tts_engine.synthesize_speech_wav(payload)
    return Response(content=wav_bytes, media_type="audio/wav")

@router.post("/mesh/sync")
async def sync_mesh_network(peer: PeerNode) -> Dict[str, Any]:
    p2p_mesh.register_peer(peer)
    sync_data = p2p_mesh.get_sync_payload()
    return {"status": "success", "sync": sync_data.model_dump()}

class CameraFeedPayload(BaseModel):
    device_id: str
    frame_base64: str
    timestamp: float

@router.post("/vision/feed")
async def receive_camera_feed(payload: CameraFeedPayload) -> Dict[str, Any]:
    return {
        "status": "success",
        "device_id": payload.device_id,
        "processed": True
    }

@router.websocket("/ws/stream")
async def websocket_stream_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            query = data.get("query", "")
            if query:
                res = await orchestrator_dispatcher.dispatch_user_command(
                    raw_query=query,
                    speaker_id="stream_user",
                    device_id=data.get("device_id", "stream_device"),
                    biometric_score=0.9
                )
                await websocket.send_json({
                    "event": "COMMAND_RESULT",
                    "speech_output": res.speech_output,
                    "agent_id": res.agent_id
                })
    except WebSocketDisconnect:
        pass
