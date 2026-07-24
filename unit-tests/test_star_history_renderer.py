from __future__ import annotations

import importlib.util
import io
import os
import tempfile
import threading
import unittest
from contextlib import contextmanager, redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "render_star_history",
    PROJECT_ROOT / ".github" / "scripts" / "render_star_history.py",
)
assert SPEC and SPEC.loader
render_star_history = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(render_star_history)


def make_svg(theme: str) -> bytes:
    background = "#0d1117" if theme == "dark" else "#fff"
    padding = "x" * 10_000
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="800" height="533.333">'
        f"<style>svg{{background:{background};font-family:xkcd}}</style>"
        "<desc>Star History GitHub Stars mdx-tom/gpt-5.6-instruct xkcdify"
        f"{padding}</desc></svg>"
    ).encode("utf-8")


@contextmanager
def serve(handler):
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


class FailingBackendHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.send_response(503)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"rate limited")

    def log_message(self, format: str, *args) -> None:
        pass


class DeployedChartHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        theme = "dark" if self.path.endswith("star-history-dark.svg") else "light"
        content = make_svg(theme)
        self.send_response(200)
        self.send_header("Content-Type", "image/svg+xml")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format: str, *args) -> None:
        pass


class StarHistoryRendererTests(unittest.TestCase):
    # A rate-limited local refresh must reuse the complete last-deployed pair,
    # allowing README-only changes to reach Pages without mixing chart vintages.
    def test_rate_limit_reuses_last_deployed_chart_pair(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory)
            with serve(FailingBackendHandler) as backend_url, serve(
                DeployedChartHandler
            ) as fallback_url:
                argv = [
                    "render_star_history.py",
                    "--backend-url",
                    backend_url,
                    "--fallback-base-url",
                    fallback_url,
                    "--output-dir",
                    str(output_dir),
                ]
                with patch("sys.argv", argv), patch.object(
                    render_star_history.time,
                    "sleep",
                    return_value=None,
                ):
                    self.assertEqual(render_star_history.main(), 0)

            self.assertEqual(
                (output_dir / "star-history-light.svg").read_bytes(),
                make_svg("light"),
            )
            self.assertEqual(
                (output_dir / "star-history-dark.svg").read_bytes(),
                make_svg("dark"),
            )

    # A degraded refresh under Actions must surface a run annotation so a green
    # job never silently keeps serving a stale chart.
    def test_rate_limit_emits_github_warning_annotation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory)
            with serve(FailingBackendHandler) as backend_url, serve(
                DeployedChartHandler
            ) as fallback_url:
                argv = [
                    "render_star_history.py",
                    "--backend-url",
                    backend_url,
                    "--fallback-base-url",
                    fallback_url,
                    "--output-dir",
                    str(output_dir),
                ]
                buffer = io.StringIO()
                with patch("sys.argv", argv), patch.object(
                    render_star_history.time,
                    "sleep",
                    return_value=None,
                ), patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}), redirect_stdout(
                    buffer
                ):
                    self.assertEqual(render_star_history.main(), 0)

            self.assertIn("::warning title=Star History::", buffer.getvalue())

    # Outside Actions the annotation is suppressed to keep local output clean.
    def test_rate_limit_skips_annotation_outside_actions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory)
            with serve(FailingBackendHandler) as backend_url, serve(
                DeployedChartHandler
            ) as fallback_url:
                argv = [
                    "render_star_history.py",
                    "--backend-url",
                    backend_url,
                    "--fallback-base-url",
                    fallback_url,
                    "--output-dir",
                    str(output_dir),
                ]
                buffer = io.StringIO()
                environment = dict(os.environ)
                environment.pop("GITHUB_ACTIONS", None)
                with patch("sys.argv", argv), patch.object(
                    render_star_history.time,
                    "sleep",
                    return_value=None,
                ), patch.dict(os.environ, environment, clear=True), redirect_stdout(
                    buffer
                ):
                    self.assertEqual(render_star_history.main(), 0)

            self.assertNotIn("::warning", buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
