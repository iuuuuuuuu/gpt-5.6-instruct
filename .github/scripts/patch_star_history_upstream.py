#!/usr/bin/env python3
"""Apply the small Actions-specific patch to a pinned Star History checkout.

The official renderer is kept intact.  Only GitHub REST request scheduling and
the token validation target are adjusted for a runner that normally has one
usable token instead of the hosted service's larger token pool.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Tuple


TOKEN_PATH = Path("backend/token.ts")
API_PATH = Path("shared/common/api.tsx")
CHART_PATH = Path("shared/common/chart.tsx")

TOKEN_LIST_ORIGINAL = "  const tokenList = envTokenString.split(/\\r?\\n/);"
TOKEN_LIST_PATCHED = """  const tokenList = envTokenString
    .split(/\\r?\\n/)
    .map((token) => token.trim())
    .filter(Boolean);"""

TOKEN_ORIGINAL = (
    '      await api.getRepoStargazersCount("star-history/star-history", token);'
)
TOKEN_PATCHED = """      await api.getRepoStargazersCount(
        process.env.STAR_HISTORY_TOKEN_TEST_REPO || "star-history/star-history",
        token
      );"""

PAGING_ORIGINAL = """        const resArray = await Promise.all(
            requestPages.map((page) => {
                return getRepoStargazers(repo, token, page)
            })
        )"""
PAGING_PATCHED = """        // The hosted deployment can spread fan-out across a large token pool.
        // This local Actions renderer normally has one token, so keep the same
        // sample pages but request them serially. Reuse the initial page-one
        // response to remove a duplicate GitHub API call.
        const resArray: typeof patchRes[] = []
        for (const page of requestPages) {
            if (page === 1) {
                resArray.push(patchRes)
                continue
            }
            await new Promise((resolve) => setTimeout(resolve, 500))
            resArray.push(await getRepoStargazers(repo, token, page))
        }"""

REPO_DATA_ORIGINAL = """            const [starRecords, logo] = await Promise.all([
                api.getRepoStarRecords(repo, token, maxRequestAmount),
                api.getRepoLogoUrl(repo, token),
            ])"""
REPO_DATA_PATCHED = """            // Keep every GitHub REST request serial in the single-token runner.
            const starRecords = await api.getRepoStarRecords(repo, token, maxRequestAmount)
            const logo = await api.getRepoLogoUrl(repo, token)"""


def replace_exactly_once(
    path: Path,
    original: str,
    replacement: str,
    description: str,
) -> bool:
    """Replace one pinned-upstream fragment and reject silent source drift."""
    source = path.read_text(encoding="utf-8")
    original_count = source.count(original)
    replacement_count = source.count(replacement)

    if original_count == 0 and replacement_count == 1:
        return False
    if original_count != 1 or replacement_count != 0:
        raise RuntimeError(
            "unexpected upstream implementation for {0} in {1} "
            "(original={2}, patched={3})".format(
                description,
                path,
                original_count,
                replacement_count,
            )
        )

    path.write_text(source.replace(original, replacement), encoding="utf-8")
    return True


def patch_upstream(source_dir: Path) -> List[Path]:
    """Patch the pinned checkout and return the files changed in this call."""
    operations: Tuple[Tuple[Path, str, str, str], ...] = (
        (TOKEN_PATH, TOKEN_LIST_ORIGINAL, TOKEN_LIST_PATCHED, "empty token filtering"),
        (TOKEN_PATH, TOKEN_ORIGINAL, TOKEN_PATCHED, "token validation target"),
        (API_PATH, PAGING_ORIGINAL, PAGING_PATCHED, "stargazer page scheduling"),
        (CHART_PATH, REPO_DATA_ORIGINAL, REPO_DATA_PATCHED, "repo data scheduling"),
    )
    changed = []
    for relative_path, original, replacement, description in operations:
        path = source_dir / relative_path
        if not path.is_file():
            raise RuntimeError("missing pinned upstream file: {0}".format(path))
        if (
            replace_exactly_once(path, original, replacement, description)
            and relative_path not in changed
        ):
            changed.append(relative_path)
    return changed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Patch a pinned official Star History checkout for local Actions use."
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        required=True,
        help="Path to the checked-out star-history/star-history source",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        changed = patch_upstream(args.source_dir)
    except (OSError, RuntimeError) as exc:
        print("[error] Star History upstream patch failed: {0}".format(exc))
        return 1

    if changed:
        for path in changed:
            print("[patched] {0}".format(path))
    else:
        print("[current] Star History upstream patch is already applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
