# AGENTS.md

MaaLimbus — MaaFramework Win32 controller + ProjectInterface V2 + MXU + Python Agent 的工程约定。
This file is the entry point for agents working in this repo.

## 先读这些

- `PROJECT.md` — 当前进度、continuation 记录与 development contract（改代码前先读）。
- `docs/design.md` — 设计约束。
- `docs/acceptance.md` — 验收口径。
- `docs/wiki/README.md` — 分层讲解 wiki（架构、运行时、业务流程、状态与数据、部署、质量，中英双语）；叙述性文档层，不替代上面三个事实源。

## Agent skills

### Issue tracker

Issues and specs live as GitHub issues in `sairaisaika/MaaLimbus`, read and written through the deck tools. See `docs/agents/issue-tracker.md`.

### Triage labels

The five canonical triage roles use their default label strings, plus the five `wayfinder:*` labels. See `docs/agents/triage-labels.md`.

### Domain docs

multi-context. See `docs/agents/domain.md`.

### Memory

Session conclusions are written back to agentmemory (project `MaaLimbus`) so the next session can retrieve them. See `docs/agents/memory.md`.
