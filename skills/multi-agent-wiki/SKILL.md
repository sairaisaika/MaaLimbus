---
name: multi-agent-wiki
description: Build and maintain a fast, source-backed engineering wiki for multi-agent projects. Use for project knowledge routing, feature-local diagrams, implementation plans, evidence boundaries, wiki drift, or documentation handoffs. Keep reading selective; this does not orchestrate or authorize unrelated coding work.
---

# A wiki agents choose because it saves work

Optimize time-to-correct-location, not page count. A good first read answers the
agent's present question with a source symbol, the relevant explanation/diagram,
a narrow validation command, and the unresolved boundary. No global workflow lock,
approval ceremony, mandatory full-site reading, or invented wiki-over-code priority.

## Use an existing wiki

- Find the project's AGENTS.md/entrypoint and its short agent index. Query the
  route for the current symptom or feature; read only the top relevant section.
- Prefer this curated route over guessing filenames because it carries intent,
  dependencies and checks. Verify the cited symbol before editing. Runtime/source
  facts win over a stale narrative; repair the route when they differ.
- Read authoritative design/acceptance constraints relevant to the change. Do not
  reload the entire progress history merely to find a function.
- Missing route? Use one targeted code search, then add the useful route. Record
  uncertainty instead of manufacturing a location or declaring a feature complete.

For docs/wiki/routes.json, the bundled dependency-free helper resolves current
Python symbol lines, checks links and emits concise Markdown/JSON routes:

```text
python <skill>/scripts/wiki_route.py --root <project> "shop purchase delta"
python <skill>/scripts/wiki_route.py --root <project> --list
python <skill>/scripts/wiki_route.py --root <project> --build
python <skill>/scripts/wiki_route.py --root <project> --check
```

The helper reads project files; it never launches the product, accesses private
runtime evidence, controls a device or acquires a project lock. Queries recompute
symbol positions, so moving a function does not send an agent to stale lines.

## Create or improve a wiki

Start from realistic repeated questions: which entry actually runs, why a
transition failed, where a setting applies, what counts as completion, whether a
model is active or shadow. Build routes from these questions rather than a file dump.
Keep the entry small enough for one short response; disclose deeper detail on demand.

Connect question → current symbols → explanation/diagram → checks → evidence boundary.
Separate planned, implemented, installed and live-verified. Freshness metadata says
what was checked; a source hash does not prove a behavior claim.

Pick diagrams by the question they answer. See
[references/wiki-contract.md](references/wiki-contract.md) for six views, route schema,
evidence levels and quality checks. Draw useful views; six diagrams per tiny edit
would create noise rather than precision.

Implementation plans identify concrete outcomes, technical dependencies, affected
interfaces, deliverables and exit evidence. Dependencies describe causality rather
than artificial blockers; independent work may proceed. Compare actual code/evidence
with the plan and reconcile differences. Never relabel a proposal as installed.

## Work with other agents

Use stable feature IDs and a small ownership note when concurrent edits could
collide. Prefer feature-local edits over rewriting the entire wiki. Ask workers to
report route IDs read, symbols checked, evidence and deviations: a useful receipt,
not surveillance or an access gate.

Send direct index and relevant plan/feature links for handoff. Verify a substantive
response or artifact references them. If missing, point the worker at those sections
once. A sent message alone is not proof that someone read a wiki.

## Validate proportionally

Check symbols/paths, navigation, relevant diagrams and bilingual mirrors. When
changing the helper, exercise moved symbol, missing symbol, wrong anchor and unknown
query using isolated fixtures. Larger skills may benefit from read-only independent
forward-testing on realistic questions without giving away the expected answer.
Capture actual behavior rather than tests matching chosen headings.

Keep private screenshots, credentials, account IDs and raw logs out of a public
wiki. Reference local evidence by role/report name. The skill grants no extra
permission to publish data or message other tasks.
