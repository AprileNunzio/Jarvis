import os
import sqlite3
import tempfile
import threading
import unittest

from server.core.kernel.application.scheduler import DagScheduler
from server.core.kernel.application.validators import ValidatorCatalog
from server.core.kernel.domain.dag import ExecutionDag
from server.core.kernel.domain.node import NodeKind, NodeSpec, RetryPolicy
from server.core.kernel.domain.outcome import NodeResult
from server.core.kernel.infrastructure.failure_memory import DeepMemoryFailureAdapter
from server.features.deep_memory.application.embedders import HashingEmbedder
from server.features.deep_memory.application.failure_index import FailureIndex
from server.features.deep_memory.application.workspace import StructureWorkspace
from server.features.deep_memory.domain.episodes import cosine, pack, unpack
from server.features.deep_memory.domain.python_extractor import SourceError, extract_python
from server.features.deep_memory.domain.resolver import build_graph
from server.features.deep_memory.domain.script_extractor import extract_script, resolve_specifier, specifiers
from server.features.deep_memory.infrastructure.sqlite_episodes import SqliteEpisodeStore
from server.features.deep_memory.infrastructure.sqlite_structure import SqliteDerivedCache, SqliteStructureStore

UTIL = "def helper(x):\n    return x * 2\n\n\ndef unused():\n    return 0\n"
SERVICE = "from pkg.util import helper\n\nLIMIT = 10\n\n\ndef run(v):\n    return helper(v) + LIMIT\n\n\nclass Box:\n    def size(self):\n        return LIMIT\n"
APP = "import pkg.service as service\n\n\ndef main():\n    return service.run(1)\n"


def connection():
    db = sqlite3.connect(":memory:", check_same_thread=False)
    return db, threading.Lock()


def workspace(files=None):
    db, lock = connection()
    ws = StructureWorkspace("p", SqliteStructureStore(db, lock), SqliteDerivedCache(db, lock))
    for path, source in (files or {}).items():
        ws.update_file(path, source)
    return ws


PROJECT = {"pkg/util.py": UTIL, "pkg/service.py": SERVICE, "app.py": APP}


class PythonExtractionTest(unittest.TestCase):
    def test_extracts_modules_functions_classes_methods_and_variables(self):
        parse = extract_python("pkg/service.py", SERVICE)
        ids = {s.symbol_id: s.kind for s in parse.symbols}
        self.assertEqual(ids["pkg/service.py"], "module")
        self.assertEqual(ids["pkg/service.py::run"], "function")
        self.assertEqual(ids["pkg/service.py::Box"], "class")
        self.assertEqual(ids["pkg/service.py::Box.size"], "function")
        self.assertEqual(ids["pkg/service.py::LIMIT"], "variable")

    def test_fingerprint_ignores_formatting_and_comments_but_not_logic(self):
        base = extract_python("a.py", "def f(x):\n    return x + 1\n").symbols[1].fingerprint
        reformatted = extract_python("a.py", "def f( x ):\n    # note\n    return (x+1)\n").symbols[1].fingerprint
        changed = extract_python("a.py", "def f(x):\n    return x + 2\n").symbols[1].fingerprint
        self.assertEqual(base, reformatted)
        self.assertNotEqual(base, changed)

    def test_syntax_errors_are_reported(self):
        with self.assertRaisesRegex(SourceError, "line"):
            extract_python("bad.py", "def f(:\n")


class GraphResolutionTest(unittest.TestCase):
    def setUp(self):
        self.graph = build_graph(extract_python(p, s) for p, s in PROJECT.items())

    def test_resolves_imports_calls_and_module_attributes(self):
        edges = self.graph.edges
        self.assertIn(("pkg/service.py", "pkg/util.py::helper"), edges)
        self.assertIn(("pkg/service.py::run", "pkg/util.py::helper"), edges)
        self.assertIn(("pkg/service.py::run", "pkg/service.py::LIMIT"), edges)
        self.assertIn(("pkg/service.py::Box.size", "pkg/service.py::LIMIT"), edges)
        self.assertIn(("app.py::main", "pkg/service.py::run"), edges)

    def test_unrelated_symbols_have_no_edges(self):
        self.assertEqual(self.graph.dependencies_of("pkg/util.py::unused"), frozenset())
        self.assertNotIn("pkg/util.py::unused", self.graph.dependents_of(["pkg/util.py::helper"]))

    def test_dependents_are_transitive(self):
        dependents = self.graph.dependents_of(["pkg/util.py::helper"])
        self.assertTrue({"pkg/service.py::run", "app.py::main"} <= dependents)
        self.assertNotIn("pkg/service.py::Box.size", dependents)

    def test_relative_imports(self):
        graph = build_graph([
            extract_python("pkg/a.py", "def a():\n    return 1\n"),
            extract_python("pkg/b.py", "from .a import a\n\n\ndef b():\n    return a()\n"),
        ])
        self.assertIn(("pkg/b.py::b", "pkg/a.py::a"), graph.edges)


class ScriptGraphTest(unittest.TestCase):
    SOURCES = {
        "src/App.jsx": "import React from 'react';\nimport Header from './components/Header';\nimport { api } from '../lib/api.ts'\n",
        "src/components/Header.jsx": "import Logo from './Logo'; // comment\nexport default function Header(){}\n",
        "src/components/Logo.tsx": "export default () => null;\n",
        "lib/api.ts": "export const api = 1;\n",
    }

    def test_specifier_extraction_and_resolution(self):
        self.assertEqual(specifiers("import a from './a'; const b = require('../b'); import('./c'); export * from './d'"),
                         frozenset({"./a", "../b", "./c", "./d"}))
        files = list(self.SOURCES)
        self.assertEqual(resolve_specifier("src/App.jsx", "./components/Header", files), "src/components/Header.jsx")
        self.assertEqual(resolve_specifier("src/App.jsx", "../lib/api.ts", files), "lib/api.ts")
        self.assertIsNone(resolve_specifier("src/App.jsx", "react", files))

    def test_file_level_graph_and_invalidation(self):
        ws = workspace(self.SOURCES)
        self.assertIn(("src/App.jsx", "src/components/Header.jsx"), ws.graph.edges)
        result = ws.update_file("src/components/Logo.tsx", "export default () => 'logo';\n")
        self.assertEqual(result.invalidated, frozenset({"src/components/Logo.tsx", "src/components/Header.jsx", "src/App.jsx"}))

    def test_comments_and_whitespace_do_not_change_script_fingerprint(self):
        a = extract_script("x.js", "const a = 1; // hi\n").fingerprint
        b = extract_script("x.js", "const   a = 1;   /* other */\n").fingerprint
        self.assertEqual(a, b)


class InvalidationTest(unittest.TestCase):
    def test_modifying_a_function_invalidates_its_transitive_dependents_only(self):
        ws = workspace(PROJECT)
        for symbol in ("pkg/util.py::unused", "pkg/util.py::helper", "pkg/service.py::run", "app.py::main", "pkg/service.py::Box.size"):
            ws.remember(symbol, "summary", f"cached {symbol}")
        result = ws.update_file("pkg/util.py", UTIL.replace("x * 2", "x * 3"))
        self.assertEqual(result.changes.modified, frozenset({"pkg/util.py::helper"}))
        self.assertTrue({"pkg/util.py::helper", "pkg/service.py::run", "app.py::main"} <= result.invalidated)
        self.assertIsNone(ws.recall("pkg/util.py::helper", "summary"))
        self.assertIsNone(ws.recall("pkg/service.py::run", "summary"))
        self.assertIsNone(ws.recall("app.py::main", "summary"))
        self.assertEqual(ws.recall("pkg/util.py::unused", "summary"), "cached pkg/util.py::unused")
        self.assertEqual(ws.recall("pkg/service.py::Box.size", "summary"), "cached pkg/service.py::Box.size")
        self.assertEqual(result.dropped_cache_entries, 3)

    def test_cosmetic_change_invalidates_nothing(self):
        ws = workspace(PROJECT)
        ws.remember("app.py::main", "summary", "x")
        result = ws.update_file("pkg/util.py", UTIL.replace("x * 2", "x*2"))
        self.assertEqual(result.invalidated, frozenset())
        self.assertEqual(ws.recall("app.py::main", "summary"), "x")

    def test_removing_a_symbol_invalidates_users_of_the_old_definition(self):
        ws = workspace(PROJECT)
        ws.remember("pkg/service.py::run", "summary", "x")
        result = ws.update_file("pkg/util.py", "def other():\n    return 1\n")
        self.assertIn("pkg/util.py::helper", result.changes.removed)
        self.assertIn("pkg/service.py::run", result.invalidated)
        self.assertIsNone(ws.recall("pkg/service.py::run", "summary"))

    def test_adding_a_definition_invalidates_modules_that_now_resolve_to_it(self):
        ws = workspace({"app.py": "from lib import tool\n\n\ndef go():\n    return tool()\n", "lib.py": "x = 1\n"})
        ws.remember("app.py::go", "summary", "x")
        result = ws.update_file("lib.py", "x = 1\n\n\ndef tool():\n    return 2\n")
        self.assertIn("app.py::go", result.invalidated)

    def test_removing_a_file_invalidates_dependents(self):
        ws = workspace(PROJECT)
        ws.remember("pkg/service.py::run", "summary", "x")
        result = ws.remove_file("pkg/util.py")
        self.assertIn("pkg/service.py::run", result.invalidated)
        self.assertEqual(ws.remove_file("pkg/util.py").invalidated, frozenset())

    def test_invalid_source_leaves_state_untouched(self):
        ws = workspace(PROJECT)
        with self.assertRaises(SourceError):
            ws.update_file("pkg/util.py", "def broken(:\n")
        with self.assertRaises(SourceError):
            ws.update_file("notes.txt", "hello")
        self.assertIn("pkg/util.py::helper", ws.graph.symbols)

    def test_state_survives_restart_via_store(self):
        db, lock = connection()
        store, cache = SqliteStructureStore(db, lock), SqliteDerivedCache(db, lock)
        first = StructureWorkspace("p", store, cache)
        for path, source in PROJECT.items():
            first.update_file(path, source)
        first.remember("app.py::main", "summary", {"a": 1})
        second = StructureWorkspace("p", store, cache)
        self.assertEqual(second.graph.edges, first.graph.edges)
        self.assertEqual(second.recall("app.py::main", "summary"), {"a": 1})
        self.assertEqual(StructureWorkspace("other", store, cache).graph.symbols, {})

    def test_remember_unknown_symbol_fails(self):
        with self.assertRaises(KeyError):
            workspace(PROJECT).remember("ghost", "k", 1)


class VectorTest(unittest.IsolatedAsyncioTestCase):
    async def test_hashing_embedder_is_deterministic_normalised_and_similarity_aware(self):
        embedder = HashingEmbedder()
        a = await embedder.embed("compilare il progetto React con webpack")
        b = await embedder.embed("compilare il progetto React con webpack")
        c = await embedder.embed("compilare un progetto React usando webpack")
        d = await embedder.embed("preparare una torta al cioccolato")
        self.assertEqual(a, b)
        self.assertAlmostEqual(cosine(a, a), 1.0, places=5)
        self.assertGreater(cosine(a, c), cosine(a, d))
        self.assertEqual(await embedder.embed(""), [0.0] * 256)

    def test_pack_round_trip_and_cosine_edge_cases(self):
        self.assertEqual([round(x, 3) for x in unpack(pack([0.5, -1.25, 3]))], [0.5, -1.25, 3.0])
        self.assertEqual(cosine([1, 0], [1]), 0.0)
        self.assertEqual(cosine([], []), 0.0)
        self.assertEqual(cosine([0, 0], [1, 1]), 0.0)


class ScriptedSemantic:
    def __init__(self, table, fail=False):
        self.table, self.fail = table, fail

    async def embed(self, text):
        if self.fail:
            raise ConnectionError("ollama down")
        for key, vector in self.table.items():
            if key in text:
                return vector
        return [0.0, 0.0, 1.0]


class FailureIndexTest(unittest.IsolatedAsyncioTestCase):
    def index(self, semantic=None):
        db, lock = connection()
        return FailureIndex(SqliteEpisodeStore(db, lock), semantic=semantic, clock=lambda: 1000.0)

    async def test_lexical_recall_of_a_dead_end(self):
        index = self.index()
        await index.record("compilare il progetto React con webpack", "npm run build", "runtime_error", "Module not found: Can't resolve 'react-dom'")
        warnings = await index.warnings_for("compilare il progetto React con webpack")
        self.assertEqual(len(warnings), 1)
        self.assertIn("Vicolo cieco noto", warnings[0])
        self.assertIn("react-dom", warnings[0])
        self.assertEqual(await index.warnings_for("preparare una torta al cioccolato"), [])

    async def test_resolution_turns_a_warning_into_a_known_fix(self):
        index = self.index()
        episode = await index.record("compilare il progetto React", "npm run build", "runtime_error", "missing react-dom")
        self.assertTrue(index.resolve(episode.episode_id, "installare react-dom"))
        warnings = await index.warnings_for("compilare il progetto React")
        self.assertIn("Soluzione già trovata", warnings[0])
        self.assertIn("react-dom", warnings[0])
        self.assertFalse(index.resolve("missing", "x"))

    async def test_identical_unresolved_failures_are_deduplicated(self):
        index = self.index()
        first = await index.record("fai X", "approccio", "timeout", "troppo lento")
        second = await index.record("fai X", "approccio", "timeout", "troppo lento")
        self.assertEqual(first.episode_id, second.episode_id)
        third = await index.record("fai X", "approccio", "syntax_error", "troppo lento")
        self.assertNotEqual(first.episode_id, third.episode_id)

    async def test_semantic_similarity_beats_lexical_when_available(self):
        semantic = ScriptedSemantic({"build": [1.0, 0.0, 0.0], "compilazione": [0.99, 0.1, 0.0]})
        index = self.index(semantic)
        await index.record("build dell'app", "x", "runtime_error", "fail")
        self.assertEqual(len(await index.warnings_for("la compilazione dell'applicazione")), 1)

    async def test_falls_back_to_lexical_when_semantic_backend_is_down_and_across_dimensions(self):
        index = self.index(ScriptedSemantic({}, fail=True))
        await index.record("compilare il progetto React con webpack", "", "timeout", "lento")
        self.assertEqual(len(await index.warnings_for("compilare il progetto React con webpack")), 1)

        mixed = self.index(ScriptedSemantic({"alfa": [1.0, 0.0, 0.0]}))
        await mixed.record("alfa beta gamma delta", "", "timeout", "lento")
        mixed._semantic = None
        self.assertEqual(len(await mixed.warnings_for("alfa beta gamma delta")), 1)

    async def test_persistence_across_instances(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "m.sqlite")
            db = sqlite3.connect(path, check_same_thread=False)
            first = FailureIndex(SqliteEpisodeStore(db, threading.Lock()))
            await first.record("migrare il database", "drop e ricrea", "runtime_error", "perdita dati")
            db.close()
            db2 = sqlite3.connect(path, check_same_thread=False)
            second = FailureIndex(SqliteEpisodeStore(db2, threading.Lock()))
            self.assertEqual(len(await second.warnings_for("migrare il database")), 1)
            db2.close()


def node(retry=3, description="scrivere uno script per ordinare i file"):
    return NodeSpec("a", NodeKind.REASONING, description, retry=RetryPolicy(max_attempts=retry))


class SchedulerMemoryTest(unittest.IsolatedAsyncioTestCase):
    def memory(self):
        db, lock = connection()
        index = FailureIndex(SqliteEpisodeStore(db, lock))
        return index, DeepMemoryFailureAdapter(index)

    async def test_failures_are_recorded_then_resolved_when_a_later_attempt_succeeds(self):
        index, adapter = self.memory()

        class Actor:
            def __init__(self):
                self.calls = 0

            async def execute(self, spec, upstream, feedback):
                self.calls += 1
                status = "ERROR" if self.calls == 1 else "SUCCESS"
                return NodeResult("a", {"status": status}, "tentativo uno" if self.calls == 1 else "soluzione finale")

        outcome = await DagScheduler(Actor(), ValidatorCatalog(), memory=adapter).run(ExecutionDag.build([node()]))
        self.assertTrue(outcome.succeeded)
        warnings = await index.warnings_for("scrivere uno script per ordinare i file")
        self.assertEqual(len(warnings), 1)
        self.assertIn("Soluzione già trovata", warnings[0])
        self.assertIn("soluzione finale", warnings[0])

    async def test_known_dead_ends_are_given_to_the_actor_before_its_first_attempt(self):
        index, adapter = self.memory()
        await index.record("scrivere uno script per ordinare i file", "os.system('rm')", "runtime_error", "permesso negato")
        seen = []

        class Actor:
            async def execute(self, spec, upstream, feedback):
                seen.append(feedback)
                return NodeResult("a", {"status": "SUCCESS"}, "ok")

        await DagScheduler(Actor(), ValidatorCatalog(), memory=adapter).run(ExecutionDag.build([node()]))
        self.assertEqual(seen[0].kind, "memory_warning")
        self.assertIn("permesso negato", seen[0].message)

    async def test_memory_outage_never_blocks_execution(self):
        class Broken:
            async def warnings_for(self, spec):
                raise RuntimeError("db locked")

            async def record_failure(self, spec, approach, error):
                raise RuntimeError("db locked")

            def record_resolution(self, ids, summary):
                raise RuntimeError("db locked")

        class Flaky:
            def __init__(self):
                self.calls = 0

            async def execute(self, spec, upstream, feedback):
                self.calls += 1
                return NodeResult("a", {"status": "ERROR" if self.calls == 1 else "SUCCESS"}, "x")

        outcome = await DagScheduler(Flaky(), ValidatorCatalog(), memory=Broken()).run(ExecutionDag.build([node()]))
        self.assertTrue(outcome.succeeded)


if __name__ == "__main__":
    unittest.main()
