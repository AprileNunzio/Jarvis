import os
import sqlite3
import tempfile
import threading
import unittest

from server.features.deep_memory.application.workspace import StructureWorkspace
from server.features.deep_memory.infrastructure.sqlite_structure import SqliteDerivedCache, SqliteStructureStore
from server.features.self_healing_coder.workspace_files import MAX_FILE_BYTES, WorkspaceError, WorkspaceFiles


def structure():
    db, lock = sqlite3.connect(":memory:", check_same_thread=False), threading.Lock()
    return StructureWorkspace("w", SqliteStructureStore(db, lock), SqliteDerivedCache(db, lock))


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = os.path.join(self.temp.name, "workspace")
        os.makedirs(self.root)
        self.structure = structure()
        self.files = WorkspaceFiles(self.root, lambda: self.structure)


class PathSafetyTest(Fixture):
    def test_normal_paths_resolve_inside_the_root(self):
        inside = self.files.resolve("site/index.php")
        self.assertTrue(inside.startswith(os.path.realpath(self.root) + os.sep))

    def test_rejections(self):
        sibling = os.path.basename(self.root) + "_evil/x.txt"
        bad = ["../outside.txt", "a/../../outside.txt", "/etc/passwd", "C:\\Windows\\x", "..", ".", "", "  ", "x\x00y",
               "../" + sibling, "../" + os.path.basename(self.root) + "_evil", None, 5]
        for path in bad:
            with self.subTest(path=path), self.assertRaises(WorkspaceError):
                self.files.resolve(path)

    def test_symlink_escape_is_blocked(self):
        outside = os.path.join(self.temp.name, "secret")
        os.makedirs(outside)
        try:
            os.symlink(outside, os.path.join(self.root, "link"), target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable")
        with self.assertRaises(WorkspaceError):
            self.files.write("link/stolen.txt", "x")
        self.assertEqual(os.listdir(outside), [])


class WritingTest(Fixture):
    def test_writes_files_and_creates_directories(self):
        message = self.files.write("proj/app/main.php", "<?php echo 1;")
        self.assertIn("scritto", message)
        with open(os.path.join(self.root, "proj", "app", "main.php"), encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "<?php echo 1;")
        self.assertIn("creata", self.files.make_directory("proj/assets"))
        self.assertTrue(os.path.isdir(os.path.join(self.root, "proj", "assets")))

    def test_oversized_or_non_text_content_is_refused(self):
        for content in ("x" * (MAX_FILE_BYTES + 1), b"bytes", None):
            with self.subTest(type=type(content)), self.assertRaises(WorkspaceError):
                self.files.write("big.txt", content)
        self.assertEqual(os.listdir(self.root), [])

    def test_unsupported_file_types_are_written_without_noise(self):
        self.assertEqual(self.files.write("style.css", "a{}"), "File style.css scritto con successo.")


class StructureTrackingTest(Fixture):
    def test_editing_a_dependency_reports_what_it_invalidates(self):
        self.files.write("lib/util.py", "def helper(x):\n    return x * 2\n")
        self.files.write("app.py", "from lib.util import helper\n\n\ndef main():\n    return helper(1)\n")
        message = self.files.write("lib/util.py", "def helper(x):\n    return x * 3\n")
        self.assertIn("invalida", message)
        self.assertIn("app.py::main", message)
        self.assertIn("app.py", message)

    def test_first_write_and_unrelated_edits_stay_quiet(self):
        self.assertEqual(self.files.write("a.py", "x = 1\n"), "File a.py scritto con successo.")
        self.assertEqual(self.files.write("b.py", "y = 2\n"), "File b.py scritto con successo.")
        self.assertEqual(self.files.write("a.py", "x = 1  # same\n"), "File a.py scritto con successo.")

    def test_python_syntax_errors_are_flagged_to_the_agent_but_the_file_is_kept(self):
        message = self.files.write("broken.py", "def f(:\n")
        self.assertIn("non è analizzabile", message)
        self.assertIn("line", message)
        self.assertTrue(os.path.exists(os.path.join(self.root, "broken.py")))

    def test_javascript_imports_feed_the_same_graph(self):
        self.files.write("src/Logo.jsx", "export default () => null;\n")
        self.files.write("src/App.jsx", "import Logo from './Logo';\nexport default () => Logo();\n")
        message = self.files.write("src/Logo.jsx", "export default () => 'logo';\n")
        self.assertIn("src/App.jsx", message)

    def test_many_dependents_are_summarised(self):
        self.files.write("core.py", "def base():\n    return 1\n")
        for i in range(12):
            self.files.write(f"user{i}.py", f"from core import base\n\n\ndef use{i}():\n    return base()\n")
        message = self.files.write("core.py", "def base():\n    return 2\n")
        self.assertIn("…", message)


if __name__ == "__main__":
    unittest.main()
