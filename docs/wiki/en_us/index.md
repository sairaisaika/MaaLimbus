# 0 Index

[简体中文](../zh_cn/index.md) · [Wiki entry](../README.md)

This wiki is the narrative documentation layer of MaaLimbus. The sources of truth remain `PROJECT.md`, `docs/design.md` and `docs/acceptance.md` — the wiki navigates and explains them, it does not replace them (the same three files `AGENTS.md:5-11` lists as required reading).

## Site navigation

| Page | English title | 中文标题 | What this page answers |
| --- | --- | --- | --- |
| 0 | Index (this page) | 索引 | Site map, reading order, and what this round delivered |
| 1 | [Overview and Glossary](1-overview.md) | [概览与术语](../zh_cn/1-overview.md) | What this is, what each of the six main tasks does, how far completion actually goes, how to read the terms, dependency and license boundaries |
| 2 | [Architecture](2-architecture.md) | [架构](../zh_cn/2-architecture.md) | How the modules are layered, the module map, the key design decisions |
| 3 | [Runtime](3-runtime.md) | [运行时](../zh_cn/3-runtime.md) | What happens from startup to shutdown in one run, the runner loop and the controller/recognition sequence |
| 4 | [Business Flows](4-business-flows.md) | [业务流程](../zh_cn/4-business-flows.md) | How each of the six main tasks plays out end to end, where it stops, and what evidence it leaves |
| 5 | [State and Data](5-state-and-data.md) | [状态与数据](../zh_cn/5-state-and-data.md) | Private user state, the run ledger, the data model of transactions and receipts |
| 6 | [Deployment and Operations](6-deployment.md) | [部署与运维](../zh_cn/6-deployment.md) | Packaging, installation, updates, logs and evidence archiving |
| 7 | [Quality and Acceptance](7-quality.md) | [质量与验收](../zh_cn/7-quality.md) | Tests and the acceptance standard: what actually counts as passing |
| 8 | [Agent Rules Layer](8-agent-rules.md) | [Agent 规则层](../zh_cn/8-agent-rules.md) | What you follow while working in this repository: tickets and specs, triage labels, domain vocabulary, sedimenting conclusions |

Every chapter's main page shares the same name and structure in both languages (`en_us/<page>` mirrors `zh_cn/<page>`). Some chapters may add sub-pages; a sub-page is linked only from its own chapter's main page, so it is not listed here.

Chapter 8 is a meta chapter: it covers what you follow while working in this repository rather than product behaviour, so it sits outside the reading paths above — open it when you need to file a ticket, apply a label, check vocabulary, or sediment a conclusion.

## The state of chapter 4

Number 4 covers "Business Flows / 业务流程" and is **delivered**: `4-business-flows.md` walks each of the six main tasks end to end, with the three kinds of termination and the evidence each leaves. It presupposes chapter 3 (runtime), and leads straight into chapter 5 for where the state lands.

## Suggested reading orders

### Path for a new reader
**1 → 2 → 3 → 4 → 5**: learn the goal chain and the six main tasks, then how the modules are layered, then how one run proceeds, then each task's end-to-end chain, then which files the state lands in.

### Path for a maintainer
**0 → 2 → 5 → 7**: take the module map, then read the state and data model, then use chapter 7's acceptance standard to decide whether a change counts as passing. Chapter 4 (Business Flows) sits between chapters 3 and 5.

### Path for a developer (someone changing code)
**0 → 2 → 3 → 5 → 7 → 2.2**: start at this page (0) to pick a lane; then read chapter 2 for the module map and the key decisions; then chapter 3 for the sequence of one run from startup to shutdown; then chapter 5 for the state and data model; and finally use chapter 7's acceptance standard to decide whether a change counts as passing. When you actually touch a module, go back to the module map in 2.2. **If you are going to change code, this is the path; chapter 6 is not relevant to it** — chapter 6 covers the portable package, installation and updates, which is the end-user path. (For documentation work, chapter 4 (business flows) and chapter 1 (the glossary) are available for reference at any point.)

**Environment**: Windows + Python 3.11+. The version requirement lives in `pyproject.toml:9` (`requires-python = ">=3.11"`); the interpreter measured on this machine is 3.13.1. The MaaFramework native-library version is pinned to `maafw==5.12.2` by `pyproject.toml:10`.

**Install dependencies and run the tests** (the original commands are at `README.md:34-41`, and the English version states the same at `README_en.md:34-41`):

```powershell
git clone https://github.com/sairaisaika/MaaLimbus.git
cd MaaLimbus
python -m pip install -e '.[dev]'
python -m pytest -q
```

pytest's path configuration is in `pyproject.toml:20-22` (`pythonpath = ["src"]`, `testpaths = ["tests"]`): **because `pythonpath` is set, you do not have to set `PYTHONPATH` by hand, and you can run the tests from the repository root without installing the package first**. The `dev` extra holds only `pytest>=8` and `pyinstaller>=6` (`pyproject.toml:13-14`); the training-related dependencies live in the separate `learning` extra (`pyproject.toml:15`) and are not needed for day-to-day development.

**When you change the wiki, run one extra guard**: `python tools/check_wiki.py` and `python -m pytest tests/test_wiki.py -q` must both pass (usage and failure behaviour are in `docs/wiki/README.md:74-80`). The guard is read-only and exits non-zero with a list of problems.

**Further reading**: the wiki pages cite only part of the topics under `docs/`; the remaining topics are grouped by theme in the [docs/ topic map](../README.md#docs-专题地图--docs-topic-map) section.

### Path for an end user (someone who just wants it running)
**6 → 1.1 → 7**: install and run the package via Deployment and Operations; then read the completion table in 1.1 to see which capabilities have verifiable evidence; then read chapter 7 to absorb this repository's standard — "the process started, the task returned success, the offline tests passed" is not a Mirror Dungeon clear (`README.md:31-32`). This lane uses only the packaged program and never touches a Python environment; **if you are going to change code, use the developer path above**.

## Reading conventions

- Every technical claim is bound to a verifiable anchor: `relative/path:line`, a test name, or an `evidence/runtime/...` path.
- Anything unverifiable is explicitly marked "not accepted / to be verified"; plans are never presented as facts.
- Chinese is the main text; terms keep their English names with a Chinese gloss at first use. `en_us/` is a section-by-section mirror, not a summary.
- Diagrams are Mermaid fences only; no image files and no extra build step.
