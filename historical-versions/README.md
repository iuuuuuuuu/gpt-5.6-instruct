# 历史提示词版本 / Historical prompt releases

本目录保存已退出生产部署菜单、但仍用于复现实验和趋势图的数据。项目根目录只将 `v41` 暴露为唯一默认生产版。

This directory keeps reproducibility artifacts that are no longer selectable
from the production deployment script.

| Release | Files retained here | Purpose |
|---|---|---|
| `v5` | Markdown + ZIP | Compact historical baseline |
| `v24` | ZIP | Intermediate iteration evidence |
| `v35` | ZIP | Previous issue-oriented release |

The repository root exposes `v41` as the sole default production release.
Historical source evidence and evaluation outputs remain under `reports/` and
`tests/` in local research workspaces. v24/v35 plaintext sources stay in local
`reports/prompt_candidates/`; their public history artifacts are ZIP-only.
