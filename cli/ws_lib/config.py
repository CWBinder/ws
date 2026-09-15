from __future__ import annotations

import os
import json
import re
import tempfile
from pathlib import Path

from ws_lib import yamlish


CONFIG_PATH = Path(
    os.environ.get("WS_CONFIG", "~/.config/ws/config.yaml")
).expanduser()


def load() -> dict:
    if not CONFIG_PATH.is_file():
        return {}
    return yamlish.load_mapping(CONFIG_PATH.read_text(encoding="utf-8"))


def get(path: str, default=None):
    value = load()
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return default
        value = value[part]
    return value


def save_workspace_root(root: Path) -> None:
    """Update only this setting, retaining other settings and comments."""
    old = CONFIG_PATH.read_text(encoding="utf-8") if CONFIG_PATH.exists() else ""
    if get("workspace_root") == str(root):
        return
    line = "workspace_root: " + json.dumps(str(root))
    if re.search(r"^workspace_root\s*:", old, re.M):
        new = re.sub(r"^workspace_root\s*:.*$", lambda _: line, old, flags=re.M)
    else:
        new = old.rstrip() + ("\n" if old.strip() else "# Local ws configuration; keep private.\n") + line + "\n"
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".ws-config-", dir=CONFIG_PATH.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(new)
        os.replace(name, CONFIG_PATH)
    finally:
        Path(name).unlink(missing_ok=True)
