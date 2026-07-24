#!/usr/bin/env python3
"""Persist Star History SVGs rendered by a local official backend instance."""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Optional

DEFAULT_BACKEND_URL = "http://127.0.0.1:8080"
DEFAULT_REPOSITORY = "mdx-tom/gpt-5.6-instruct"
THEMES = ("light", "dark")

# One retry lets the local backend rotate to the optional second token. More
# attempts do not help after every token enters its 15-minute cooldown, so fail
# over promptly to the last validated chart pair.
LOCAL_RENDER_ATTEMPTS = 2
# The fallback fetches the last-deployed pair from the Pages CDN, where retries
# usefully ride out short-lived network hiccups.
FALLBACK_RENDER_ATTEMPTS = 4


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Save light and dark SVGs produced by a local Star History backend."
    )
    parser.add_argument(
        "--backend-url",
        default=os.environ.get("STAR_HISTORY_BACKEND_URL", DEFAULT_BACKEND_URL),
        help="Local official backend origin (default: %(default)s)",
    )
    parser.add_argument(
        "--repository",
        default=os.environ.get("STAR_HISTORY_REPOSITORY", DEFAULT_REPOSITORY),
        help="GitHub repository in owner/name form (default: %(default)s)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".star-history-site"),
        help="Directory that receives the two SVG files (default: %(default)s)",
    )
    parser.add_argument(
        "--fallback-base-url",
        default=os.environ.get("STAR_HISTORY_FALLBACK_BASE_URL"),
        help=(
            "Base URL containing the last deployed star-history-light.svg and "
            "star-history-dark.svg files"
        ),
    )
    return parser.parse_args()


def validate_local_backend_url(value: str) -> str:
    parsed = urllib.parse.urlsplit(value.rstrip("/"))
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise ValueError("backend URL must point to a local HTTP server")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise ValueError("backend URL must be an origin without a path or query")
    return value.rstrip("/")


def validate_fallback_base_url(value: str) -> str:
    normalized = value.rstrip("/")
    parsed = urllib.parse.urlsplit(normalized)
    is_local_http = parsed.scheme == "http" and parsed.hostname in {
        "127.0.0.1",
        "localhost",
    }
    if parsed.scheme != "https" and not is_local_http:
        raise ValueError("fallback URL must use HTTPS or local HTTP")
    if not parsed.netloc or parsed.username or parsed.password:
        raise ValueError("fallback URL must contain a host without credentials")
    if parsed.query or parsed.fragment:
        raise ValueError("fallback URL must not contain a query or fragment")
    return normalized


def chart_url(backend_url: str, repository: str, theme: str) -> str:
    params = {
        "repos": repository.lower(),
        "type": "date",
        "legend": "top-left",
    }
    if theme == "dark":
        params["theme"] = "dark"
    return f"{backend_url}/svg?{urllib.parse.urlencode(params)}"


def fallback_chart_url(base_url: str, theme: str) -> str:
    return f"{base_url}/star-history-{theme}.svg"


def emit_github_warning(message: str) -> None:
    """Surface a degraded refresh as a run annotation, not just buried stderr.

    A green job that silently serves a stale chart hides the fact that the live
    Star History render keeps hitting GitHub rate limits; the annotation makes
    the degraded state visible so maintainers can rotate or add tokens.
    """
    if os.environ.get("GITHUB_ACTIONS") != "true":
        return
    single_line = message.replace("\r", " ").replace("\n", " ")
    print(f"::warning title=Star History::{single_line}")


def download_svg(url: str, attempts: int = 4) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "image/svg+xml",
            "User-Agent": "MDX-Tom/gpt-5.6-instruct local Star-History renderer",
        },
    )
    last_error: Optional[Exception] = None
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                content_type = response.headers.get("Content-Type", "").lower()
                body = response.read()
            if "svg" not in content_type:
                raise ValueError(
                    f"unexpected Content-Type: {content_type or '(missing)'}"
                )
            return body
        except urllib.error.HTTPError as exc:
            try:
                response_body = exc.read().decode("utf-8", errors="replace").strip()
            finally:
                exc.close()
            detail = f"HTTP {exc.code} {exc.reason}"
            if response_body:
                detail += f": {response_body}"
            last_error = RuntimeError(detail)
            if attempt == attempts:
                break
            time.sleep(attempt * 2)
        except (OSError, ValueError, urllib.error.URLError) as exc:
            last_error = exc
            if attempt == attempts:
                break
            time.sleep(attempt * 2)
    raise RuntimeError(f"local Star History backend request failed: {last_error}")


def validate_svg(content: bytes, repository: str, theme: str) -> None:
    if len(content) < 10_000:
        raise ValueError(f"SVG is unexpectedly small: {len(content)} bytes")
    root = ET.fromstring(content)
    if root.tag.rsplit("}", 1)[-1] != "svg":
        raise ValueError(f"document root is not SVG: {root.tag}")
    if root.attrib.get("width") != "800" or root.attrib.get("height") != "533.333":
        raise ValueError(
            "official laptop chart dimensions changed: "
            f"{root.attrib.get('width')}x{root.attrib.get('height')}"
        )

    text = content.decode("utf-8")
    required_fragments = (
        "Star History",
        "GitHub Stars",
        repository.lower(),
        "xkcdify",
        "font-family:xkcd",
    )
    missing = [fragment for fragment in required_fragments if fragment not in text]
    if missing:
        raise ValueError(f"SVG is missing official chart markers: {', '.join(missing)}")

    expected_background = "background:#0d1117" if theme == "dark" else "background:#fff"
    if expected_background not in text:
        raise ValueError(f"SVG does not contain the expected {theme} theme")


def atomic_write(destination: Path, content: bytes) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="wb",
        prefix=destination.name + ".",
        suffix=".tmp",
        dir=destination.parent,
        delete=False,
    ) as temporary:
        temporary.write(content)
        temporary_path = Path(temporary.name)
    temporary_path.replace(destination)
    destination.chmod(0o644)
    print(f"[rendered] {destination} ({len(content)} bytes)")


def fetch_chart_pair(
    *,
    repository: str,
    url_for_theme,
    attempts: int,
) -> Dict[str, bytes]:
    charts = {}
    for theme in THEMES:
        content = download_svg(url_for_theme(theme), attempts=attempts)
        validate_svg(content, repository, theme)
        charts[theme] = content
    return charts


def main() -> int:
    args = parse_args()
    try:
        backend_url = validate_local_backend_url(args.backend_url)
        repository = args.repository.strip().lower()
        if repository.count("/") != 1:
            raise ValueError("repository must use owner/name format")

        try:
            charts = fetch_chart_pair(
                repository=repository,
                url_for_theme=lambda theme: chart_url(
                    backend_url,
                    repository,
                    theme,
                ),
                attempts=LOCAL_RENDER_ATTEMPTS,
            )
        except (RuntimeError, OSError, ValueError, ET.ParseError) as local_error:
            if not args.fallback_base_url:
                raise
            fallback_base_url = validate_fallback_base_url(args.fallback_base_url)
            warning = (
                "Local Star History refresh failed; reusing the last deployed "
                f"chart pair: {local_error}"
            )
            print(f"[warning] {warning}", file=sys.stderr)
            emit_github_warning(warning)
            charts = fetch_chart_pair(
                repository=repository,
                url_for_theme=lambda theme: fallback_chart_url(
                    fallback_base_url,
                    theme,
                ),
                attempts=FALLBACK_RENDER_ATTEMPTS,
            )

        # Write only after both themes validate, preventing a mixed fresh/stale pair.
        for theme in THEMES:
            atomic_write(
                args.output_dir / f"star-history-{theme}.svg",
                charts[theme],
            )
    except (RuntimeError, OSError, ValueError, ET.ParseError) as exc:
        print(f"[error] Star History rendering failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
