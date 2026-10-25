"""Pair a map click's kind with the page it landed on -- the label the icon lacks.

The node's type is not in the panel (measured 2026-10-25: `NODE_PANEL` of `Sunk Gloom`
prints the encounter's name, `Clear Rewards` and `Enter`, no type word) and not in the
detector kind alone (370 boxes gave 30 glyph signatures).  What the journal does hold is
the click and the page the run arrived at afterwards, so a kind's meaning can be *learned*
instead of guessed: if every `gold_badge_node` click is followed by `BATTLE_HUD`, the kind
is a battle marker on this corpus, and a kind that splits across pages is not a type.
"""
import collections
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from maalimbus import run_metrics  # noqa: E402

PAGE_EVENTS = ("map_observed", "battle_observed", "loop_heartbeat")
STOP_EVENTS = ("mirror_loop_stopped", "mirror_loop_error", "window_no_progress", "window_stall")


def _rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _page(row):
    return row.get("scene") or row.get("page")


def landed_page(rows, index):
    """The next page named after `index`, or None when the run ended first."""
    for row in rows[index + 1:]:
        if row.get("event") in STOP_EVENTS:
            return None
        if row.get("event") in PAGE_EVENTS:
            page = _page(row)
            if page:
                return page
    return None


def pairs(rows):
    """(kind, landed page) for every settled map click that has a page after it."""
    found = []
    for index, row in enumerate(rows):
        if row.get("event") != "map_click_result":
            continue
        if row.get("outcome") not in ("accepted", "rejected"):
            continue
        found.append({"kind": row.get("kind"), "outcome": row.get("outcome"),
                      "landed": landed_page(rows, index), "point": row.get("point")})
    return found


def table(found):
    """kind -> landed page -> count, plus how many of a kind's clicks landed somewhere."""
    counts = collections.Counter()
    for row in found:
        counts[(row.get("kind") or "unrecorded", row.get("landed") or "no-page")] += 1
    return counts


def report(directories=None):
    directories = directories or sorted(p.parent for p in
                                       (ROOT / "evidence" / "runtime").glob("packaged-mirror-*/events.jsonl"))
    found = []
    for directory in directories:
        found.extend(pairs(_rows(directory / "events.jsonl")))
    return {"clicks": len(found), "pairs": found, "table": table(found)}


def main():
    data = report()
    if not data["clicks"]:
        print("nothing to read: no settled map click in this corpus")
        return 2
    print("map clicks with a page after them: %d" % data["clicks"])
    for (kind, landed), count in sorted(data["table"].items(), key=lambda kv: (-kv[1], kv[0])):
        print("%-22s -> %-16s %4d" % (kind, landed, count))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
