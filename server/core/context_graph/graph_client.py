import os
import json
import time
import sqlite3
import logging
import threading
from typing import Dict, Any, Optional
from server.config.env import settings
from server.core.context_graph.node_schema import (
    KnowledgeNode,
    KnowledgeEdge,
    NodeType,
    RelationType,
    GraphSnapshot,
)
from server.shared.errors.domain_errors import EntityNotFoundException

logger = logging.getLogger("jarvis.graph_client")


class GraphClient:

    def __init__(self, db_path: str = "") -> None:
        if not db_path:
            db_path = os.path.join(settings.DATA_DIR, "db", "knowledge_graph.sqlite")
        self._db_path = db_path
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._create_tables()
        self._bootstrap_default_topology()

    def _create_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS nodes (
                id TEXT PRIMARY KEY,
                node_type TEXT NOT NULL,
                label TEXT NOT NULL,
                properties TEXT DEFAULT '{}',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS edges (
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                relation_type TEXT NOT NULL,
                weight REAL DEFAULT 1.0,
                properties TEXT DEFAULT '{}',
                PRIMARY KEY (source_id, target_id, relation_type),
                FOREIGN KEY (source_id) REFERENCES nodes(id),
                FOREIGN KEY (target_id) REFERENCES nodes(id)
            );
            CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id);
            CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id);
            CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(node_type);
        """)
        self._conn.commit()
        logger.info("Knowledge graph database initialized at %s", self._db_path)

    def _bootstrap_default_topology(self) -> None:
        now = time.time()
        row = self._conn.execute("SELECT id FROM nodes WHERE id = ?", ("jarvis_core",)).fetchone()
        if not row:
            self._conn.execute(
                "INSERT INTO nodes (id, node_type, label, properties, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                ("jarvis_core", NodeType.AGENT.value if hasattr(NodeType.AGENT, "value") else str(NodeType.AGENT),
                 "Jarvis Orchestrator",
                 json.dumps({"version": "2.0.0", "status": "ONLINE"}),
                 now, now),
            )
            self._conn.commit()

    def upsert_node(
        self,
        node_id: str,
        node_type: NodeType,
        label: str,
        properties: Dict[str, Any],
    ) -> KnowledgeNode:
        now = time.time()
        type_str = node_type.value if hasattr(node_type, "value") else str(node_type)
        props_json = json.dumps(properties, default=str)

        with self._lock:
            existing = self._conn.execute(
                "SELECT properties, created_at FROM nodes WHERE id = ?", (node_id,)
            ).fetchone()

            if existing:
                old_props = json.loads(existing[0])
                merged = {**old_props, **properties}
                merged_json = json.dumps(merged, default=str)
                self._conn.execute(
                    "UPDATE nodes SET node_type=?, label=?, properties=?, updated_at=? WHERE id=?",
                    (type_str, label, merged_json, now, node_id),
                )
                created_at = existing[1]
                final_props = merged
            else:
                self._conn.execute(
                    "INSERT INTO nodes (id, node_type, label, properties, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (node_id, type_str, label, props_json, now, now),
                )
                created_at = now
                final_props = properties

            self._conn.commit()

        return KnowledgeNode(
            id=node_id,
            node_type=node_type,
            label=label,
            properties=final_props,
            created_at=created_at,
            updated_at=now,
        )

    def get_node(self, node_id: str) -> KnowledgeNode:
        row = self._conn.execute(
            "SELECT id, node_type, label, properties, created_at, updated_at FROM nodes WHERE id = ?",
            (node_id,),
        ).fetchone()
        if not row:
            raise EntityNotFoundException("KnowledgeNode", node_id)
        return self._row_to_node(row)

    def link_nodes(
        self,
        source_id: str,
        target_id: str,
        relation_type: RelationType,
        weight: float = 1.0,
        properties: Optional[Dict[str, Any]] = None,
    ) -> KnowledgeEdge:
        src = self._conn.execute("SELECT id FROM nodes WHERE id = ?", (source_id,)).fetchone()
        tgt = self._conn.execute("SELECT id FROM nodes WHERE id = ?", (target_id,)).fetchone()
        if not src:
            raise EntityNotFoundException("KnowledgeNode", source_id)
        if not tgt:
            raise EntityNotFoundException("KnowledgeNode", target_id)

        rel_str = relation_type.value if hasattr(relation_type, "value") else str(relation_type)
        props_json = json.dumps(properties or {}, default=str)

        with self._lock:
            self._conn.execute(
                """INSERT INTO edges (source_id, target_id, relation_type, weight, properties)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(source_id, target_id, relation_type)
                   DO UPDATE SET weight=excluded.weight, properties=excluded.properties""",
                (source_id, target_id, rel_str, weight, props_json),
            )
            self._conn.commit()

        return KnowledgeEdge(
            source_id=source_id,
            target_id=target_id,
            relation_type=relation_type,
            weight=weight,
            properties=properties or {},
        )

    def export_snapshot(self) -> GraphSnapshot:
        node_rows = self._conn.execute(
            "SELECT id, node_type, label, properties, created_at, updated_at FROM nodes"
        ).fetchall()
        edge_rows = self._conn.execute(
            "SELECT source_id, target_id, relation_type, weight, properties FROM edges"
        ).fetchall()

        nodes = [self._row_to_node(r) for r in node_rows]
        edges = [self._row_to_edge(r) for r in edge_rows]
        return GraphSnapshot(nodes=nodes, edges=edges)

    def node_count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) FROM nodes").fetchone()
        return row[0] if row else 0

    def edge_count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) FROM edges").fetchone()
        return row[0] if row else 0

    @staticmethod
    def _row_to_node(row: tuple) -> KnowledgeNode:
        node_id, node_type_str, label, props_json, created_at, updated_at = row
        try:
            node_type = NodeType(node_type_str)
        except (ValueError, KeyError):
            node_type = NodeType.CONCEPT
        return KnowledgeNode(
            id=node_id,
            node_type=node_type,
            label=label,
            properties=json.loads(props_json),
            created_at=created_at,
            updated_at=updated_at,
        )

    @staticmethod
    def _row_to_edge(row: tuple) -> KnowledgeEdge:
        source_id, target_id, rel_type_str, weight, props_json = row
        try:
            relation_type = RelationType(rel_type_str)
        except (ValueError, KeyError):
            relation_type = RelationType.DEPENDS_ON
        return KnowledgeEdge(
            source_id=source_id,
            target_id=target_id,
            relation_type=relation_type,
            weight=weight,
            properties=json.loads(props_json),
        )

    def close(self) -> None:
        self._conn.close()


graph_client = GraphClient()
