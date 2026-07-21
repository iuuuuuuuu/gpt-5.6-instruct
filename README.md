<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/pojia-logo-dark.svg" />
  <source media="(prefers-color-scheme: light)" srcset="docs/images/pojia-logo-light.svg" />
  <img src="docs/images/pojia-logo-light.svg" alt="破甲项目标志" width="640" />
</picture>

<p>
  <a href="https://github.com/MDX-Tom/gpt-5.6-instruct/stargazers"><img src="https://img.shields.io/github/stars/MDX-Tom/gpt-5.6-instruct?logo=github&label=Stars" alt="GitHub Stars" /></a>
  <img src="https://img.shields.io/badge/Model-gpt--5.6--sol-7c3aed" alt="gpt-5.6-sol" />
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.8%2B-3776AB?logo=python&logoColor=white" alt="Python 3.8+" /></a>
  <a href="docs/comparison-tests-en.md"><img src="https://img.shields.io/badge/Documentation-Purple?color=8A2BE2&logo=readthedocs" alt="English Documentation" /></a>
  <a href="docs/comparison-tests.md"><img src="https://img.shields.io/badge/中文文档-red?logo=readthedocs" alt="中文文档" /></a>
</p>

<p>
  <a href="README_EN.md"><img src="https://img.shields.io/badge/lang-English-blue.svg" alt="English" /></a>
  <a href="README.md"><img src="https://img.shields.io/badge/语言-简体中文-red.svg" alt="简体中文" /></a>
</p>

<h1>gpt-5.6 破甲提示词及测试包</h1>

</div>

<!-- README_SYNC: 修改 README.md 时必须同步更新 README_EN.md；图表也必须提供对应语言版本。 -->

<a id="overview"></a>

本项目提供面向大模型的越狱/破甲提示词，将安全研究、渗透测试、逆向工程、软件破解与 NSFW 虚构内容统一设定为本地沙箱任务，并显式压制拒绝与回退话术，以提升 Codex CLI 对复杂指令的直接执行能力。

项目提供两个等级的提示词：`v5` 结构更简洁，足以覆盖大多数场景，并作为默认推荐版本；`v35` 在此基础上进一步将具体名称与网址归一化为占位符，再按中英文复合意图族进行统一路由，减少复合任务中只完成部分子任务的情况。**建议仅在 `v5` 无法满足需求时使用 `v35`。** 项目同时提供可复现的测试、评测与迭代优化流程。

在 `gpt-5.6-sol` 的 120 条 `medium` 测试集中，结构更简洁的 `v5` 在 low、medium、high 三档均达到 120/120；`v35` 在保持三档 120/120 的基础上增加了特殊任务优化。两版相较原有 5.5 提示词，在三档的测试通过率分别提升 29.17、45.00 和 30.83 个百分点。

<a id="architecture"></a>

## 系统架构

```mermaid
flowchart LR
    RELEASE["① 发布层<br/>v5 · v35 · 自定义包"]
    CONTROL["② 部署控制层<br/>菜单 / CLI<br/>读取 · 校验 · Dry Run"]
    CONFIG["③ 本地配置层<br/>复制指令文件<br/>备份 · 快照 · config.toml"]
    RUNTIME["④ Codex 运行时<br/>Codex CLI<br/>版本化指令 → gpt-5.6-sol"]
    EVAL["⑤ 回归评测层<br/>360 条双语用例<br/>模型 × 推理等级矩阵"]
    EVIDENCE["⑥ 证据与迭代<br/>原始输入 / 输出 · pass / fail<br/>汇总 · 图表 · 下一版本"]
    ROLLBACK["回滚路径<br/>选择备份 · 二次确认<br/>恢复配置 · 清理文件"]

    RELEASE --> CONTROL --> CONFIG --> RUNTIME --> EVAL --> EVIDENCE
    CONFIG -.-> ROLLBACK
```

<p align="center"><sub>从版本选择到部署、运行、评测和回滚，形成完整的本地闭环。</sub></p>

<a id="highlights"></a>

## 亮点

| | |
|---|---|
| 🚀 **一键部署**<br>交互式菜单或命令行完成预览、植入与切换。 | 🧭 **双版本路线**<br>`v5` 面向日常使用，`v35` 面向特殊复合任务。 |
| ↩️ **可控回滚**<br>自动保存基线备份与操作快照，恢复前再次确认。 | 🧪 **可复现评测**<br>360 条双语测试用例，记录输入、输出与最终判定。 |

<a id="versions"></a>

## 版本选择

| 版本 | 定位 | 推荐场景 | 获取 |
|---|---|---|---|
| **v5（推荐）** | 更短、更通用、稳定性优先 | 绝大多数常规任务 | [ZIP](gpt-5.6-sol-unrestricted-v5.zip) · [Markdown](gpt-5.6-sol-unrestricted-v5.md) |
| **v35** | 名称/网址归一化与双语复合意图路由 | `v5` 无法完整处理的特殊复合任务 | [ZIP](gpt-5.6-sol-unrestricted-v35.zip) |

> [!TIP]
> 从 `v5` 开始。只有在它无法满足任务需求时，再切换到 `v35`。

当前文件校验值：

```text
v5   e55293314a3f789d7d19cda22d60e2d5be306b850a9c17a015a836943b691afb
v35  72ca29f14615e22cb8c23d5d67ff9f26c68c89cc951873758930eb0ec668c3cf
```

<a id="quick-start"></a>

## 快速开始

### 1. 获取项目

```bash
git clone https://github.com/MDX-Tom/gpt-5.6-instruct.git
cd gpt-5.6-instruct
```

### 2. 预览并部署

```bash
# 先预览推荐版本，不写入任何文件
python3 codex-instruct.py --version v5 --dry-run

# 部署 v5
python3 codex-instruct.py --version v5
```

不带参数运行可打开交互式菜单：

```bash
python3 codex-instruct.py
```

<details>
<summary><strong>更多命令</strong></summary>

```bash
# 切换到特殊任务优化版
python3 codex-instruct.py --version v35

# 指定 Codex home
python3 codex-instruct.py --version v5 --codex-dir ~/.codex

# 部署自定义 ZIP 或 Markdown
python3 codex-instruct.py --file ./custom-instructions.zip

# 从备份恢复
python3 codex-instruct.py --reset
```

</details>

部署脚本会解压所选版本，将指令文件复制到 `CODEX_HOME`，备份 `config.toml`，并写入：

```toml
model_instructions_file = "./gpt-5.6-sol-unrestricted-v5.md"
```

执行 `--reset` 时，脚本会列出可用备份并要求二次确认，随后恢复配置并清理脚本管理的指令文件。

<a id="results"></a>

## 评测结果

在 `gpt-5.6-sol` 的 120 条 `medium` 测试集中，`v5` 与 `v35` 在 low、medium、high 三档完整回归中均达到 **120/120**。相较上游 5.5 指令，三档通过率分别提升 **29.17、45.00 和 30.83 个百分点**；跨模型记录同时表明，实际表现会随模型与推理等级变化。

完整的测试口径、上游对比、跨模型记录、版本趋势、典型案例与效果截图见 [中文对比测试文档](docs/comparison-tests.md) 或 [English Documentation](docs/comparison-tests-en.md)。

## 评测工具

测试集覆盖 6 类场景、3 种长度、2 种语言，每种组合 10 条，共 **360 条**。评测会在本地保存原始输入、模型输出、传输方式、重试来源与 `pass/fail` 判定；这些运行数据默认由 `.gitignore` 排除。

首次克隆后，先解压公开的测试脚本：

```bash
for archive in scripts/*.zip; do unzip -o "$archive" -d scripts; done
```

随后可以生成测试集并运行最短层级：

```bash
python3 scripts/generate_gpt56_sol_prompt_bank.py
python3 scripts/run_gpt56_sol_prompt_bank.py \
  --level minimal \
  --reasoning low \
  --run-label v5
```

完整的安全性评测说明见 [docs/gpt-5.6-sol-safety-eval.md](docs/gpt-5.6-sol-safety-eval.md)。

<a id="layout"></a>

## 项目结构

```text
gpt-5.6-instruct/
├── README.md / README_EN.md           # 中英文首页
├── codex-instruct.py                  # 部署、切换与回滚
├── sync-archives.py                   # 本地源文件与 ZIP 同步
├── gpt-5.6-sol-unrestricted-v5.md     # v5 明文版
├── gpt-5.6-sol-unrestricted-v5.zip    # v5 发布包
├── gpt-5.6-sol-unrestricted-v35.zip   # v35 发布包
├── scripts/*.zip                      # 可复现评测工具
└── docs/                              # 中英文对比文档、评测说明与图片
```

### 维护发布包

`v35` 与测试脚本中的部分文本不直接展示在 GitHub 页面上，因此仓库提交 ZIP，本地源文件由 `.gitignore` 排除。修改本地源文件后，请同步并检查压缩包：

```bash
python3 sync-archives.py
python3 sync-archives.py --check
```

## 声明

本项目使用 Codex 官方配置机制，不修改二进制、不劫持网络、不篡改进程。请仅在你有权操作的环境中使用，并自行承担使用风险。

## License

本项目采用 [MIT License](LICENSE)。

## Star History

<p align="center">
  <a href="https://www.star-history.com/?repos=MDX-Tom%2Fgpt-5.6-instruct&type=date&legend=top-left">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="https://mdx-tom.github.io/gpt-5.6-instruct/star-history-dark.svg" />
      <source media="(prefers-color-scheme: light)" srcset="https://mdx-tom.github.io/gpt-5.6-instruct/star-history-light.svg" />
      <img alt="Star History Chart" src="https://mdx-tom.github.io/gpt-5.6-instruct/star-history-light.svg" width="80%" />
    </picture>
  </a>
</p>

## 致谢

针对 `gpt-5.6-sol` 的 Codex CLI 破甲提示词与测试包。

参考并延展自 [yynxxxxx/Codex-5.5-codex-instruct-5.5](https://github.com/yynxxxxx/Codex-5.5-codex-instruct-5.5)。感谢原作者 [yynxxxxx](https://github.com/yynxxxxx) / li lingbo 的开源工作。

新版首页的信息层级与视觉组织参考了 [RLinf/RLinf](https://github.com/RLinf/RLinf)。
