"""What the retained archive says happened after each plan word was sent.

D49 declared twenty-eight plan words as having no way for their input to be judged.
That number was an artifact of the instrument: :func:`maalimbus.plan_reasons.unproven`
counted only *named* successors, and `plan_reasons._elements` drops every symbol, so
``expect=(ANY,)`` -- the dismissal proof, "the page must change" -- read as zero.  All
twenty-eight carried it.  Measured 2026-10-23 after the fix: of the 80 acting plans, 45
carry a named successor, 43 carry a dismissal, 21 are named by a runner hook, and **none
is unjudgeable**.

That correction leaves a different and quieter gap, and this module answers it from the
evidence the repository already has instead of from a guess: every packaged run in
``evidence/runtime/packaged-mirror-*`` records the plan word it sent (``window_intent``)
and the pages it read afterwards, so for each word the archive can say whether the input
moved the screen and where to.  The answer is not uniform:

A successor set is *names*, and the plan may name the page it acts from: a shelf
refresh stays in the shop, a team-list scroll stays on the team page.  Judging a landing
by "the page changed" alone reads those as failures (D56's two "suspects", D57), so the
verdict here compares the observed page with what the plan itself said would be right.

* ten words always changed the page (3+ observations, none staying),
* five changed it sometimes,
* seven **never** changed it -- ``team_card_joins_the_next_unpicked_identity`` sent 109
  times and stayed on the same page 107 of them, because filling a team slot is a state
  change, not a page change.

For the last group a page proof is not weak, it is *wrong*: those clicks must be judged
by the state they change (a slot's name, a counter, a lit control), which is a proof the
loop does not have yet, and :data:`maalimbus.pages.PLANS_AWAITING_A_STATE_PROOF` declares
them until it does.  The classification is derived, never restated: the gate fails if a
declared word is not classified that way by the archive it cites.

Reading the archive is read-only and sends no input; a run that has no archive at all
reports nothing rather than an empty success.
"""
from __future__ import annotations

import glob
import json
import pathlib


HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
ARCHIVES = 'evidence/runtime/packaged-mirror-*'

# Every word lands in exactly one class, and the classes partition the words that were
# observed at all; `unseen` is the word that was never sent in a retained run.
CLASSES = ('unanimous', 'few', 'mixed', 'never_changed', 'unseen')

# Three observations is the floor for calling a result a pattern rather than a sample:
# one or two landings prove the input *can* land, not that it always does.
UNANIMOUS_FLOOR = 3

# The pages a frame can name.  `semantic_frame_proposal` is not one of them: it carries
# no page, and treating it as an answer was a one-line bug that made every observation
# look like a missing one.
PAGE_EVENTS = ('map_observed', 'battle_observed')
STOP_EVENTS = ('mirror_loop_stopped', 'mirror_loop_error', 'window_no_progress', 'window_stall')

# A page that could not be read is not a successor.  Naming UNKNOWN in a plan's `expect`
# would hide a perception failure behind a legitimate landing, so the relation reports
# those landings apart and they never count as "the plan forgot a page" (D58).
UNREADABLE = ('UNKNOWN',)


def _archives(directory=None):
    """The ``events.jsonl`` files of the retained runs, oldest name first."""
    if directory is not None:
        found = [pathlib.Path(directory)]
        if found[0].is_dir():
            return sorted(found[0].glob('*/events.jsonl'))
        return found if found[0].exists() else []
    return sorted(pathlib.Path(path) for path in glob.glob(str(ROOT / ARCHIVES / 'events.jsonl')))


def _rows(path):
    """Every record of one run, skipping a line that is not JSON."""
    rows = []
    for line in pathlib.Path(path).read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    return rows


def after_page(rows, index):
    """The first page named after record ``index``, or None when the run ended first.

    A ``loop_heartbeat`` names the page it woke on and a ``window_intent`` names the page
    it acted from, so either answers "where is the loop now"; a stop event answers
    "nowhere", and a proposal answers nothing at all.
    """
    for row in rows[index + 1:]:
        event = row.get('event')
        if event in PAGE_EVENTS and row.get('scene'):
            return row['scene']
        if event in ('loop_heartbeat', 'window_intent') and row.get('page'):
            return row['page']
        if event in STOP_EVENTS:
            return None
    return None


def classify(landed, stayed):
    """The label for one word's observed outcomes."""
    if landed == 0 and stayed == 0:
        return 'unseen'
    if landed == 0:
        return 'never_changed'
    if stayed == 0:
        return 'unanimous' if landed >= UNANIMOUS_FLOOR else 'few'
    return 'mixed'


def _entry():
    return {'intents': 0, 'landed': 0, 'declared_same': 0, 'same': 0, 'unexpected': 0,
            'no_evidence': 0, 'successors': {}, 'from_pages': {}}


def outcomes(words=None, directory=None):
    """``{word: {intents, landed, declared_same, same, unexpected, ...}}``.

    ``words`` restricts the reading to the words asked about; every word the archive
    recorded is returned when it is None.
    """
    wanted = None if words is None else set(words)
    found = {}
    declared = _declared()
    for path in _archives(directory):
        rows = _rows(path)
        for index, row in enumerate(rows):
            if row.get('event') != 'window_intent':
                continue
            word = row.get('reason')
            if not isinstance(word, str):
                continue
            if wanted is not None and word not in wanted:
                continue
            entry = found.setdefault(word, _entry())
            entry['intents'] += 1
            was = row.get('page')
            if isinstance(was, str):
                entry['from_pages'][was] = entry['from_pages'].get(was, 0) + 1
            page = after_page(rows, index)
            if page is None:
                entry['no_evidence'] += 1
                continue
            names = declared.get(word, set())
            if page != was:
                if names and page not in names:
                    entry['unexpected'] += 1
                else:
                    entry['landed'] += 1
                entry['successors'][page] = entry['successors'].get(page, 0) + 1
            elif names and was in names:
                # The plan named the page it acted from as a legitimate successor -- a
                # shelf refresh stays in the shop, a team-list scroll stays on the team
                # page.  Judging that as "did not move" was D56's error, not a defect.
                entry['declared_same'] += 1
            else:
                entry['same'] += 1
    for entry in found.values():
        entry['class'] = classify(entry['landed'] + entry['declared_same'], entry['same'])
    return found


def _declared():
    """``{word: successor names}`` for every acting plan, read once.

    ``plan_reasons.acting_plans`` parses two source files.  Asking it per intent made a
    read of the whole archive take minutes (D57: the tool was killed at 120 s), so the
    vocabulary is read once and looked up per row.
    """
    from maalimbus import plan_reasons

    return {word: set((facts or {}).get('expect_names') or ())
            for word, facts in plan_reasons.acting_plans().items()}


def unnamed_landings(found=None, declared=None, floor=None):
    """Landings the archive saw on a page the plan never named, worth acting on.

    A landing is *evidence about the plan*, not about the click: `expect` says which
    pages do not disprove this input, so a page the archive reaches every single time is
    one the plan is missing, and its absence shows up as ``unexpected_successor`` and a
    recovery ladder (D58: 55 of 55 resume clicks).  A landing at an unreadable page is
    reported separately by :func:`unreadable_landings`, because that is a perception
    question and naming the page would hide it.
    """
    found = outcomes(directory=None) if found is None else found
    declared = _declared() if declared is None else declared
    floor = UNANIMOUS_FLOOR if floor is None else int(floor)
    rows = []
    for word, entry in sorted(found.items()):
        names = declared.get(word, set())
        if not names:
            # The plan proves this input by a dismissal or a hook, so it never named a
            # page and has nothing to forget: reporting these would repeat D56's mistake
            # of judging a plan by a criterion it did not use (found by the first draft
            # of this function, which offered 17 "missing successors" to plans that
            # already carried expect=(ANY,)).
            continue
        for page, count in sorted(entry['successors'].items()):
            if page in names or page in UNREADABLE or count < floor:
                continue
            rows.append({'word': word, 'page': page, 'count': count,
                         'intents': entry['intents']})
    return sorted(rows, key=lambda row: (-row['count'], row['word'], row['page']))


def unreadable_landings(found=None, floor=None):
    """Landings at a page that could not be read: a perception question, not a successor."""
    found = outcomes() if found is None else found
    floor = UNANIMOUS_FLOOR if floor is None else int(floor)
    rows = []
    for word, entry in sorted(found.items()):
        for page in UNREADABLE:
            count = entry['successors'].get(page, 0)
            if count >= floor:
                rows.append({'word': word, 'page': page, 'count': count,
                             'intents': entry['intents']})
    return sorted(rows, key=lambda row: (-row['count'], row['word']))


def needs_state_proof(found=None, directory=None):
    """Every word the archive says never moved the page, with its stay count.

    Word-level, because the observation is word-level: whether the plan that carried
    the word stated a named successor does not change what the screen did.
    """
    found = outcomes(directory=directory) if found is None else found
    return {word: entry['same'] for word, entry in sorted(found.items())
            if entry['class'] == 'never_changed'}


def _facts(word):
    from maalimbus import plan_reasons

    return plan_reasons.acting_plans().get(word) or {}


def _other_proof(word):
    """``'named'``, ``'hook'``, ``'dismissal'`` or None -- what else judges this word."""
    facts = _facts(word)
    if facts.get('expects'):
        return 'named'
    if facts.get('hooked'):
        return 'hook'
    if facts.get('dismissal'):
        return 'dismissal'
    return None


def proof_kind(word):
    """What can judge this word's input, and whether the page label is even one of them.

    ``'pixel'`` is the strongest of the weak ones: an ``advance`` plan accepts a changed
    frame, so its page staying identical is the *designed* outcome and the archive's
    page-level verdict says nothing about it.  Reading only the page would have declared
    ``team_card_joins_the_next_unpicked_identity`` (107 stays in 109 sends) a defect,
    when it advances and is judged by pixels -- the mistake this function exists to stop.
    """
    facts = _facts(word)
    if facts.get('advance'):
        return 'pixel'
    return _other_proof(word)


def main(argv=None):
    """Print the classification, and the words the static index cannot name."""
    from maalimbus import pages, plan_reasons

    argv = list(argv or [])
    directory = None
    if '--directory' in argv:
        directory = argv[argv.index('--directory') + 1]
    found = outcomes(directory=directory)
    if not found:
        print('no retained run carries a plan word yet')
        return 0
    plans = plan_reasons.acting_plans()
    counts = {name: 0 for name in CLASSES}
    for entry in found.values():
        counts[entry['class']] += 1
    print('words the archive observed: %d' % len(found))
    for name in CLASSES:
        print('  %-14s %d' % (name, counts[name]))
    print('intents: %d  said where it went: %d  named the page it acted from: %d'
          '  moved where it did not say: %d  stayed: %d  no evidence: %d'
          % (sum(entry['intents'] for entry in found.values()),
             sum(entry['landed'] for entry in found.values()),
             sum(entry['declared_same'] for entry in found.values()),
             sum(entry['unexpected'] for entry in found.values()),
             sum(entry['same'] for entry in found.values()),
             sum(entry['no_evidence'] for entry in found.values())))
    kept = sum(entry['landed'] + entry['declared_same']
               for entry in found.values())
    sent = sum(entry['landed'] + entry['declared_same'] + entry['unexpected']
               + entry['same'] for entry in found.values())
    print('inputs whose outcome the archive can name: %d of %d (%.0f%%)'
          % (kept, sent, 100.0 * kept / sent if sent else 0.0))
    declared = dict(pages.PLANS_THE_INDEX_CANNOT_NAME)
    unnamed = {word: entry['intents'] for word, entry in found.items() if word not in plans}
    print('words the index cannot name: %d  declared: %d'
          % (len(unnamed), len(declared)))
    for word, count in sorted(unnamed.items()):
        mark = 'declared' if word in declared else 'NOT DECLARED'
        print('  %-58s sent %3d  %s' % (word, count, mark))
    for word in sorted(set(declared) - set(unnamed)):
        print('  %-58s declared but the archive never shows it' % word)
    stale = sorted(set(unnamed) - set(declared))

    # A landing on a page the plan never named is evidence about the plan (D58).  The
    # ones worth acting on are declared in pages.SUCCESSORS_THE_ARCHIVE_SAW until the
    # plan learns the page; a landing at UNKNOWN is a reading question and is reported
    # apart so it can never be "fixed" by naming the unreadable page.
    seen = pages.SUCCESSORS_THE_ARCHIVE_SAW
    forgotten = unnamed_landings(found)
    print('landings on a page no plan names: %d  (floor %d)'
          % (len(forgotten), UNANIMOUS_FLOOR))
    undeclared, agreed = [], 0
    for row in forgotten:
        known = seen.get(row['word'], {}).get(row['page'])
        if known is None:
            undeclared.append(row)
        elif known != row['count']:
            undeclared.append(row)
            print('  %-52s -> %-18s count changed: declared %d, archive %d'
                  % (row['word'][:52], row['page'], known, row['count']))
            continue
        else:
            agreed += 1
        print('  %-52s -> %-18s %3d of %3d  %s'
              % (row['word'][:52], row['page'], row['count'], row['intents'],
                 'declared' if known is not None else 'NOT DECLARED'))
    gone = sorted((word, page) for word, pages_seen in seen.items()
                  for page in pages_seen
                  if page not in (found.get(word) or {'successors': {}})['successors'])
    for word, page in gone:
        print('  %-52s -> %-18s declared but the archive no longer shows it'
              % (word[:52], page))
    unreadable = unreadable_landings(found)
    print('landings on a page that could not be read: %d' % len(unreadable))
    for row in unreadable:
        print('  %-52s -> %-18s %3d of %3d  (a reading, not a successor)'
              % (row['word'][:52], row['page'], row['count'], row['intents']))
    print('declared landings that still agree with the archive: %d of %d'
          % (agreed, sum(len(pages_seen) for pages_seen in seen.values())))
    failed = bool(stale or set(declared) - set(unnamed) or undeclared or gone)
    return 1 if failed else 0
