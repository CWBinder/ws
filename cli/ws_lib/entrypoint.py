"""Select an init target before importing modules with resolved workspace paths."""
import argparse
import os
import sys


def main():
    if sys.version_info < (3, 10):
        raise SystemExit("ws requires Python 3.10 or newer")
    words = sys.argv[1:]
    if words[:1] == ["--receipt"]:
        words = words[1:]
    if words[:1] == ["init"]:
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument("--root")
        options, _ = parser.parse_known_args(words[1:])
        if options.root:
            os.environ["WS_WORKSPACE_ROOT"] = options.root
    from ws_lib.cli import main as run
    run()
