import logging
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from server.config.env import settings
from server.shared.errors.global_handler import register_global_error_handlers
from server.core.security_guard.zero_trust_interceptor import ZeroTrustMiddleware
from server.core.agent_registry.pool_manager import agent_pool
from server.features.home_assistant_bridge.ha_agent import HomeAssistantAgent
from server.features.vision_surveillance.surveillance_agent import VisionSurveillanceAgent
from server.features.self_healing_coder.coder_agent import SelfHealingCoderAgent
from server.features.sysops_automation.sysops_agent import SysOpsAutomationAgent
from server.cmd.api_routes import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("jarvis.main")



def create_application() -> FastAPI:
    app = FastAPI(
        title="Jarvis Autonomous Cognitive Orchestrator",
        version="2.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(ZeroTrustMiddleware)

    register_global_error_handlers(app)

    # Inizializza OpenTelemetry (Pilastro 2)
    try:
        from server.core.observability.telemetry import setup_telemetry
        setup_telemetry(app)
    except ImportError:
        logger.warning("Modulo Telemetry non trovato. Ignoro OpenTelemetry.")

    # Carica tutti i tool dinamici (Maps, 3D, ecc.) prima di avviare gli agenti
    try:
        import server.features.agent_tools.maps_tool
        import server.features.agent_tools.web_search_tool
        import server.features.agent_tools.music_tool
        _ = server.features.agent_tools.music_tool
        _ = server.features.agent_tools.web_search_tool
        _ = server.features.agent_tools.maps_tool
        logger.info("Tool dinamici caricati e pronti all'uso.")
    except ImportError as e:
        logger.warning("Nessun tool dinamico caricato: %s", str(e))

    agent_pool.register_agent(HomeAssistantAgent())
    agent_pool.register_agent(VisionSurveillanceAgent())
    agent_pool.register_agent(SelfHealingCoderAgent())
    agent_pool.register_agent(SysOpsAutomationAgent())
    logger.info("Core agents registered: %s", agent_pool.list_agents())

    app.include_router(router)

    @app.on_event("startup")
    async def on_startup() -> None:
        # Avvia background tasks
        from server.features.music_library.scanner import music_organizer
        import asyncio
        asyncio.create_task(music_organizer.scan_loop())
        
        # Inizializza Database (Pilastro 1)
        try:
            from server.core.db.database import engine, Base
            Base.metadata.create_all(bind=engine)
            logger.info("Database ORM Inizializzato (Tabelle sincronizzate).")
        except Exception as e:
            logger.error("Impossibile connettersi al database: %s", str(e))
        from server.core.cognitive_audit.embedding_engine import embedding_engine
        from server.core.context_graph.graph_client import graph_client

        model_ok = await embedding_engine.ensure_model_available()
        if not model_ok:
            logger.warning(
                "Embedding model not found! Run: ollama pull nomic-embed-text"
            )
            
        from server.core.orchestrator.interrupt_manager import project_manager
        await project_manager.load_and_resume_all()

        logger.info(
            "Jarvis v2.0.0 online — %d agents, %d graph nodes, %d graph edges",
            len(agent_pool.list_agents()),
            graph_client.node_count(),
            graph_client.edge_count(),
        )

    @app.get("/health")
    async def health_check():
        from server.core.context_graph.graph_client import graph_client
        return {
            "status": "HEALTHY",
            "version": "2.0.0",
            "orchestrator": "ONLINE",
            "active_agents": agent_pool.list_agents(),
            "knowledge_graph": {
                "nodes": graph_client.node_count(),
                "edges": graph_client.edge_count(),
            },
            "upgrades": [
                "llm_intent_classifier",
                "react_reasoning_loop",
                "task_planner",
                "persistent_knowledge_graph",
                "real_embeddings",
                "skill_synthesis",
                "self_critique",
                "tool_protocol",
            ],
        }

    return app


app = create_application()

if __name__ == "__main__":
    uvicorn.run(
        "server.cmd.main:app",
        host=settings.JARVIS_HOST,
        port=settings.JARVIS_PORT,
        reload=(settings.JARVIS_ENV == "development"),
    )
