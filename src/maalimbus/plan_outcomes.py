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
    return {'intents': 0, 'landed': 0, 'same': 0, 'no_evidence': 0,
            'successors': {}, 'from_pages': {}}


def outcomes(words=None, directory=None):
    """``{word: {intents, landed, same, no_evidence, successors, from_pages, class}}``.

    ``words`` restricts the reading to the words asked about; every word the archive
    recorded is returned when it is None.
    """
    wanted = None if words is None else set(words)
    found = {}
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
            elif page != was:
                entry['landed'] += 1
                entry['successors'][page] = entry['successors'].get(page, 0) + 1
            else:
                entry['same'] += 1
    for entry in found.values():
        entry['class'] = classify(entry['landed'], entry['same'])
    return found


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
    """Print the classification, the owed words and the suspects."""
    from maalimbus import pages

    argv = list(argv or [])
    directory = None
    if '--directory' in argv:
        directory = argv[argv.index('--directory') + 1]
    found = outcomes(directory=directory)
    if not found:
        print('no retained run carries a plan word yet')
        return 0
    counts = {name: 0 for name in CLASSES}
    for entry in found.values():
        counts[entry['class']] += 1
    print('words the archive observed: %d' % len(found))
    for name in CLASSES:
        print('  %-14s %d' % (name, counts[name]))
    print('intents: %d  moved the page: %d  stayed: %d  no evidence: %d'
          % (sum(entry['intents'] for entry in found.values()),
             sum(entry['landed'] for entry in found.values()),
             sum(entry['same'] for entry in found.values()),
             sum(entry['no_evidence'] for entry in found.values())))
    declared = set(pages.PLANS_AWAITING_A_STATE_PROOF)
    state = needs_state_proof(found)
    owed, judged, suspect = {}, {}, {}
    for word, stayed in state.items():
        kind = proof_kind(word)
        if kind == 'pixel':
            judged[word] = (stayed, kind)
        elif kind == 'named':
            suspect[word] = stayed
        else:
            owed[word] = stayed
    print('never moved the page: %d  owed a state proof: %d  judged by the pixels: %d'
          '  named a successor the archive never saw: %d'
          % (len(state), len(owed), len(judged), len(suspect)))
    for word, stayed in owed.items():
        mark = 'declared' if word in declared else 'NOT DECLARED'
        print('  %-58s stayed %3d  %s' % (word, stayed, mark))
    for word, count in suspect.items():
        print('  %-58s stayed %3d  expected a named page it never reached' % (word, count))
    for word in sorted(declared - owed.keys()):
        print('  %-58s declared but the archive does not say so' % word)
    return 1 if owed.keys() - declared or declared - owed.keys() else 0
