"""`ws setup --web`: the same steps as `ws setup`, asked in a browser.

A page on its own cannot write to disk, so this serves one from a small local
server for as long as setup runs. It listens on 127.0.0.1 only, on a free port,
and answers only requests that carry the token in the address it prints and
name that same host. It stops when the person finishes, or after half an hour
without a request.
"""

from __future__ import annotations

import json
import secrets
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from ws_lib import paths, setup


PAGE = paths.TEMPLATES / "setup.html"
IDLE_SECONDS = 30 * 60


def view(session: setup.Session) -> dict:
    """What the page shows next, as plain data."""
    known = setup.current_state()
    step = session.current(known)
    data: dict = {"test": known["test"], "about": setup._text("about"), "notice": setup.TEST_NOTICE}
    if step is None:
        data["done"] = {
            "owner": setup.owner_summary(),
            "text": setup._text("done"),
            "over": setup.TEST_OVER if known["test"] else "",
        }
        return data
    data["step"] = {
        "name": step.name,
        "title": step.title,
        "position": setup.position(step),
        "optional": step in setup.OPTIONAL,
        "explain": setup.explain(step, known),
        "ignored": known["test"] and step.name == "workspace",
        "questions": [
            {
                "key": question.key,
                "ask": question.ask,
                "many": question.many,
                "required": question.required,
                "default": setup.default_of(question, known),
                "long": question.key in {"description", "note"},
            }
            for question in step.questions
        ],
    }
    return data


def run(open_browser: bool = True) -> None:
    token = secrets.token_urlsafe(24)
    session = setup.Session()
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args) -> None:
            pass

        def _send(self, status: int, body: bytes, kind: str = "application/json") -> None:
            self.send_response(status)
            self.send_header("Content-Type", f"{kind}; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, value: dict, status: int = 200) -> None:
            self._send(status, json.dumps(value, ensure_ascii=False).encode("utf-8"))

        def _allowed(self, offered: str) -> bool:
            restart_idle()
            host_ok = self.headers.get("Host") == f"127.0.0.1:{server.server_port}"
            return host_ok and secrets.compare_digest(offered, token)

        def do_GET(self) -> None:
            url = urlparse(self.path)
            if url.path == "/" and self._allowed(parse_qs(url.query).get("t", [""])[0]):
                self._send(200, PAGE.read_bytes(), "text/html")
            elif url.path == "/state" and self._allowed(self.headers.get("X-Token", "")):
                with lock:
                    self._json(view(session))
            else:
                self._send(404, b"{}")

        def do_POST(self) -> None:
            if not self._allowed(self.headers.get("X-Token", "")):
                self._send(404, b"{}")
                return
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length) or b"{}")
            if self.path == "/finish":
                self._json({})
                threading.Thread(target=server.shutdown).start()
                return
            with lock:
                known = setup.current_state()
                step = session.current(known)
                # A second tab or a double click may answer a step already gone.
                if step is None or step.name != body.get("step"):
                    self._json(view(session))
                elif self.path == "/skip" and step in setup.OPTIONAL:
                    session.skip(step)
                    self._json(view(session))
                elif self.path == "/answer":
                    try:
                        session.submit(step, body.get("answers") or {}, known)
                    except setup.SetupError as problem:
                        self._json({**view(session), "error": str(problem), "answers": body.get("answers")})
                    else:
                        self._json(view(session))
                else:
                    self._send(404, b"{}")

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    idle: list[threading.Timer] = []

    def restart_idle() -> None:
        for timer in idle:
            timer.cancel()
        idle[:] = [threading.Timer(IDLE_SECONDS, server.shutdown)]
        idle[0].daemon = True
        idle[0].start()

    restart_idle()
    address = f"http://127.0.0.1:{server.server_port}/?t={token}"
    print(f"Setup is open at:\n\n  {address}\n\nIt stops when you finish there, or with Ctrl-C here.", flush=True)
    if open_browser:
        webbrowser.open(address)
    try:
        server.serve_forever()
    finally:
        for timer in idle:
            timer.cancel()
        server.server_close()
    print("Setup has stopped.")
