import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


CLI_ROOT = Path(__file__).resolve().parents[1]


class WorkspaceLayoutTests(unittest.TestCase):
    def test_default_paths_match_domain_and_persistent_service_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "workspace"
            env = {
                key: value
                for key, value in os.environ.items()
                if not key.startswith("WS_")
            }
            env["WS_WORKSPACE_ROOT"] = str(root)
            env["PYTHONPATH"] = str(CLI_ROOT)
            code = """
import json
from ws_lib import paths

names = [
    "PROJECTS", "TASKS", "LITERATURE", "DOCUMENTS",
    "DOCUMENT_OBJECTS", "DOCUMENT_FILES", "RESOURCES", "RESOURCE_ITEMS", "LOGISTICS", "CAREER",
    "RELATIONS", "INDEX_DIR", "KNOWLEDGEBASE",
]
print(json.dumps({
    name: str(getattr(paths, name).relative_to(paths.WORKSPACE))
    for name in names
}))
"""
            result = subprocess.run(
                [sys.executable, "-c", code],
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(
                json.loads(result.stdout),
                {
                    "PROJECTS": "projects/items",
                    "TASKS": "tasks",
                    "LITERATURE": "literature",
                    "DOCUMENTS": "documents",
                    "DOCUMENT_OBJECTS": "documents/items",
                    "DOCUMENT_FILES": "documents/files",
                    "RESOURCES": "resources",
                    "RESOURCE_ITEMS": "resources/items",
                    "LOGISTICS": "logistics",
                    "CAREER": "profile",
                    "RELATIONS": "relations",
                    "INDEX_DIR": "index",
                    "KNOWLEDGEBASE": "wiki",
                },
            )


if __name__ == "__main__":
    unittest.main()
