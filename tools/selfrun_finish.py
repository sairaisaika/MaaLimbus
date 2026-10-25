"""The bookkeeping every self-run needs, kept out of the framework wiring (D195).

Two things ended up missing from the in-process runner (D193): the stop row, because the
packaged agent writes it after the loop returns and a tool that replaces the agent has to
write it too, and `result.json`, because the loop can end the process (the stall watchdog
calls `os._exit`) and a summary written only in `finally` is then never written.

So the summary is written often -- after every row, cheap at this size -- and the stop row
is written by the tool in the same shape the agent uses, so `run_metrics.ending` reads both
paths the same way.
"""
import json
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'src')]
from maalimbus.documents import write_document  # noqa: E402

SNAPSHOT_EVERY = 1


def _line(data):
    """JSON that always writes: an unrepresentable field becomes its own text (D195).

    `json.dumps(..., default=str)` still raises on a cycle, and a summary is written while
    the loop's own objects are alive, so a key that cannot be represented is replaced by its
    `repr` instead of losing the whole document.
    """
    try:
        return json.dumps(data, indent=2, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        safe = {}
        for key, value in data.items():
            try:
                json.dumps(value, default=str)
            except (TypeError, ValueError):
                safe[key] = repr(value)[:400]
            else:
                safe[key] = value
        return json.dumps(safe, indent=2, ensure_ascii=False, default=str)


class Snapshotting:
    """A journal wrapper that keeps `result.json` current.

    It forwards `record` and `frame` to the real journal, and after `every` rows writes the
    result document.  Wrapping rather than subclassing keeps it usable with any journal.
    """

    def __init__(self, journal, directory, result, every=SNAPSHOT_EVERY):
        self.journal = journal
        self.directory = Path(directory)
        self.result = result
        self.every = max(1, int(every))
        self.count = 0

    def record(self, event, **fields):
        written = self.journal.record(event, **fields)
        self.count += 1
        if self.count % self.every == 0:
            self.snapshot()
        return written

    def frame(self, *args, **kwargs):
        return self.journal.frame(*args, **kwargs)

    def snapshot(self):
        write_document(self.directory / 'result.json', self.result)


def summary(journal, summary_result, result, directory):
    """Write the stop row and the final summary the way `agent/main.py` does.

    A loop that returned has ended; the row says which path ended it (`agent_loop`, the same
    label the packaged agent uses) and the numbers the run reached.  Returns the result.
    """
    summary_result = summary_result or {}
    result['passed'] = bool(summary_result.get('passed'))
    result['summary'] = summary_result
    journal.record('mirror_loop_stopped', reason=summary_result.get('reason'),
                   steps=summary_result.get('steps'), clicks_sent=summary_result.get('clicks_sent'),
                   passed=bool(summary_result.get('passed')), directory=str(directory),
                   stop_path='agent_loop')
    write_document(Path(directory) / 'result.json', result)
    return result


def tally(journal_rows, result):
    """Fill the summary fields from the rows already on disk (event count, stop, floors)."""
    stops = [row for row in journal_rows
             if row.get('event') in ('mirror_loop_stopped', 'mirror_loop_error')]
    result['events'] = len(journal_rows)
    result['stop'] = stops[-1].get('reason') if stops else None
    result['ending'] = stops[-1].get('event') if stops else None
    floors = [row.get('floor') for row in journal_rows
              if row.get('event') == 'map_observed' and row.get('floor')]
    result['floors'] = sorted({int(value) for value in floors if str(value).isdigit()})
    return result
