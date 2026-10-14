# Engineering wiki contract

## Cheap routing

Aim for one small response to locate a feature. Prefer `agent-index.md` plus a
queryable manifest over a giant first-read chapter. Include user vocabulary,
observed errors, a stable feature ID, real paths/qualified symbols, local diagram,
narrow tests and evidence boundary. Derive line positions from current source.

Minimal `docs/wiki/routes.json` for the bundled helper:

```json
{
  "schema_version": 1,
  "project": "Example",
  "routes": [{
    "id": "startup",
    "title": "Start a saved job",
    "aliases": ["start failed", "startup", "job queue"],
    "sources": [{"path": "src/jobs.py", "symbol": "JobRunner.start"}],
    "docs": ["docs/wiki/runtime.md#startup"],
    "tests": ["tests/test_jobs.py"],
    "checks": ["python -m pytest -q tests/test_jobs.py"],
    "boundary": "Dispatch success is not job completion."
  }]
}
```

Non-Python locations may use an exact `needle`; require one match, not an arbitrary
first duplicate. Planned features may omit source locations but must say planned.
Do not cite future files as existing code. No secrets or private paths in manifests.

## Six views, selected by need

| View | Answers | Useful content | Frequent mistake |
| --- | --- | --- | --- |
| Architecture | Who owns which responsibility? | Components, interfaces, direction and side-effect boundaries | File list pretending to show interfaces |
| Activity/flow | Which business branch is next? | Decisions, alternatives, loops, exit outcomes | Changed screen treated as success |
| Sequence | In what order do components interact? | Participants, request/response, durable intent and recovery | No real interface between actors |
| Data model | Which facts persist and relate? | Logical entities, keys, cardinalities, references/copies | Proposed JSON called installed database schema |
| Deployment | What runs where? | Processes, libraries, models, devices, IPC and files | Source module confused with a service |
| State machine | Which legal transition is proven? | States, events, guards, recovery and terminal meaning | Navigation menu labelled a lifecycle machine |

Prefer compact Mermaid repository views where it fits. Split large views by feature;
each figure resolves an ambiguity rather than decorates prose. Explain its scope,
link actual symbols and visibly distinguish future components.

## Evidence and freshness

Planned, implemented, offline-tested, installed and live-verified are separate
claims. Diagram rendering proves syntax/readability, not runtime behavior. Unit
success is not installation or pipeline completion. Hashes bind evidence but do
not replace meaningful outcome criteria.

Put volatile progress in acceptance/continuation records and stable criteria in
plans. Record code revision and verification scope. Repair the smallest affected
route/section on drift. Regenerate moved symbols instead of editing hundreds of
line numbers by hand. Wiki routing needs no lock files or permission ceremony.

`--check` validates navigation structure and snapshot freshness, not semantic truth.
Forward-test a few realistic questions against source and acceptance: a symbol can
exist while the linked explanation is about the wrong layer, or a planned-status
sentence can remain stale after a new backend lands. Correct those local routes;
do not present structural validity as implementation or live acceptance.
