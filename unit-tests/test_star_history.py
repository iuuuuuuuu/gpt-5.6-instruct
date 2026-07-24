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


def load_project_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


render_star_history = load_project_module(
    "render_star_history",
    PROJECT_ROOT / ".github" / "scripts" / "render_star_history.py",
)
patch_upstream = load_project_module(
    "patch_star_history_upstream",
    PROJECT_ROOT / ".github" / "scripts" / "patch_star_history_upstream.py",
)


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


TOKEN_SOURCE = r"""export const initTokenFromEnv = async () => {
  const tokenList = envTokenString.split(/\r?\n/);
      await api.getRepoStargazersCount("star-history/star-history", token);
};
"""

API_SOURCE = """export async function getRepoStarRecords() {
        const patchRes = await getRepoStargazers(repo, token)
        const resArray = await Promise.all(
            requestPages.map((page) => {
                return getRepoStargazers(repo, token, page)
            })
        )
        return resArray
}
"""

CHART_SOURCE = """export const getRepoData = async () => {
            const [starRecords, logo] = await Promise.all([
                api.getRepoStarRecords(repo, token, maxRequestAmount),
                api.getRepoLogoUrl(repo, token),
            ])
            return { starRecords, logo }
}
"""


def write_upstream_fixture(root: Path) -> None:
    files = {
        patch_upstream.TOKEN_PATH: TOKEN_SOURCE,
        patch_upstream.API_PATH: API_SOURCE,
        patch_upstream.CHART_PATH: CHART_SOURCE,
    }
    for relative_path, content in files.items():
        destination = root / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")


class StarHistoryRendererTests(unittest.TestCase):
    # One degraded render covers the complete fallback pair and the Actions
    # annotation; the same warning helper must stay silent during local runs.
    def test_rate_limit_fallback_and_annotation_policy(self) -> None:
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

            self.assertEqual(
                (output_dir / "star-history-light.svg").read_bytes(),
                make_svg("light"),
            )
            self.assertEqual(
                (output_dir / "star-history-dark.svg").read_bytes(),
                make_svg("dark"),
            )
            self.assertIn("::warning title=Star History::", buffer.getvalue())

        local_buffer = io.StringIO()
        with patch.dict(os.environ, {}, clear=True), redirect_stdout(local_buffer):
            render_star_history.emit_github_warning("local check")
        self.assertEqual(local_buffer.getvalue(), "")


class StarHistoryUpstreamPatchTests(unittest.TestCase):
    # The production pipeline may use GitHub APIs and this project's Pages
    # cache, but a hosted Star History endpoint must never become its default.
    def test_pipeline_contains_no_hosted_star_history_domain(self) -> None:
        pipeline_files = (
            PROJECT_ROOT / ".github" / "scripts" / "patch_star_history_upstream.py",
            PROJECT_ROOT / ".github" / "scripts" / "render_star_history.py",
            PROJECT_ROOT / ".github" / "workflows" / "sync-star-history.yml",
        )
        for path in pipeline_files:
            with self.subTest(path=path):
                self.assertNotIn(
                    "star-history.com",
                    path.read_text(encoding="utf-8").lower(),
                )

    # The Actions adaptation must preserve sampled history, eliminate the API
    # burst, and remain a no-op when setup is repeated.
    def test_patch_serializes_all_github_api_reads(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            write_upstream_fixture(root)

            changed = patch_upstream.patch_upstream(root)

            self.assertEqual(
                changed,
                [
                    patch_upstream.TOKEN_PATH,
                    patch_upstream.API_PATH,
                    patch_upstream.CHART_PATH,
                ],
            )
            token_source = (root / patch_upstream.TOKEN_PATH).read_text(encoding="utf-8")
            api_source = (root / patch_upstream.API_PATH).read_text(encoding="utf-8")
            chart_source = (root / patch_upstream.CHART_PATH).read_text(encoding="utf-8")
            self.assertIn(".map((token) => token.trim())", token_source)
            self.assertIn(".filter(Boolean)", token_source)
            self.assertIn("STAR_HISTORY_TOKEN_TEST_REPO", token_source)
            self.assertIn("for (const page of requestPages)", api_source)
            self.assertIn("resArray.push(patchRes)", api_source)
            self.assertIn("setTimeout(resolve, 500)", api_source)
            self.assertNotIn("requestPages.map", api_source)
            self.assertNotIn("const [starRecords, logo] = await Promise.all", chart_source)
            self.assertEqual(patch_upstream.patch_upstream(root), [])

    # A changed upstream implementation must stop the job instead of silently
    # restoring concurrent requests or producing a partially patched renderer.
    def test_patch_rejects_unexpected_upstream_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            write_upstream_fixture(root)
            (root / patch_upstream.API_PATH).write_text(
                "export async function changedUpstream() {}\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(RuntimeError, "unexpected upstream"):
                patch_upstream.patch_upstream(root)


if __name__ == "__main__":
    unittest.main()
