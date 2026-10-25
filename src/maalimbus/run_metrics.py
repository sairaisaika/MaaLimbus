"""Turn one run's event journal into the numbers phase 6 asks for.

The point is a *comparable* baseline: the same definitions applied to every stored
run, so a change can be argued with numbers instead of impressions.  Nothing here
touches the device; it reads `evidence/runtime/*/events.jsonl` only.

Definitions (deliberately narrow, because a wide one invites self-congratulation):
- `steps`             distinct `map_observed` frames -- the run advanced a page.
- `no_progress_stops` a `mirror_loop_stopped` whose reason is not a requested end.
- `recovery_rate`     `window_recovery` events / stops that arrived while a page was
                      being refused; `None` when nothing was ever refused.
- `verdicts`          `map_click_result` by outcome; an accepted one must name a
                      movement reason, otherwise it is recorded as `accepted_other`.
"""
ACCEPTED_MOVEMENT = ('the_party_moved_after_the_click',)
# `the_click_opened_the_next_page` is deliberately NOT a movement: every accepted click of
# that kind in `evidence/runtime/packaged-mirror-20261023-05xxxx` has target centre
# (1844,60) -- the top-right progress gear.  Counting it as advancement treated opening a
# panel as walking, which inflated `recovery_advanced` to 6/17 when the party never moved.


def recovery_effect(rows, *, window=3):
    """Did a recovery recover, or only happen?

    `recovery_rate` counts events against refusals, which cannot tell a recovery that
    moved the run on from one that was written to the journal and then repeated.  This
    asks the narrower question: within the next `window` observed frames, did the
    engine get to *do* something again (a new intent or a new verdict)?  "Recovered but
    refused again" still counts as recovered: the ladder did its job and the next step
    is a different problem.
    """
    seen = 0
    effective = 0
    frames_left = None
    for row in rows:
        event = row.get('event')
        if event == 'window_recovery':
            seen += 1
            frames_left = window
            continue
        if frames_left is None:
            continue
        if event == 'map_observed':
            frames_left -= 1
            if frames_left < 0:
                frames_left = None
            continue
        if event in ('map_click_result', 'window_intent'):
            effective += 1
            frames_left = None
    return {'recoveries': seen, 'effective': effective,
            'rate': (effective / seen) if seen else None}


def recovery_advanced(rows, *, window=5):
    """Did a recovery move the run *forward*, not merely change the screen?

    A first version counted any page change as progress and measured 17/17 -- but the
    recovery it was measuring opens and closes the pause panel, which changes pages and
    advances the dungeon by nothing.  So progress is now only one of two things a panel
    round-trip cannot fake: a verdict that names a party movement, or a floor the run
    had not reached before.
    """
    seen = 0
    advanced = 0
    frames_left = None
    reached = set()
    for row in rows:
        if row.get('event') == 'map_observed' and row.get('floor'):
            reached.add(row['floor'])
        if row.get('event') == 'window_recovery':
            seen += 1
            frames_left = window
            before = set(reached)
            continue
        if frames_left is None:
            continue
        if row.get('event') == 'map_observed' and row.get('floor'):
            frames_left -= 1
            if frames_left < 0:
                frames_left = None
            continue
        moved = (row.get('event') == 'map_click_result'
                 and row.get('reason') in ACCEPTED_MOVEMENT)
        if moved or reached != before:
            advanced += 1
            frames_left = None
    return {'recoveries': seen, 'advanced': advanced,
            'rate': (advanced / seen) if seen else None}


# `budget` is the fifth way a run ends: the caller's own wall clock stopped it.  It is
# not a death -- the 2026-10-24 00:19 run was walking floor 2 into floor 3 when the
# harness killed it 15 s after its 420 s budget -- and until D78 the census counted
# it under `process_died`, which is what `no_progress_stop_rate` is computed from.
ENDING_KINDS = ('stop', 'error', 'died', 'budget', 'no_events')
HARNESS_FILE = 'harness.json'


def ending(rows, directory=None):
    """Which of the five ways this run ended; the five are exhaustive by construction.

    `tools/audit_runs.py` used to classify a run as "stopped" or "died" and nothing else,
    so the ten retained runs that ended on `mirror_loop_error` alone appeared in neither
    column (81 + 51 = 132 of 142 on 2026-10-23).  A census whose buckets do not partition
    the corpus is not a denominator, it is a sample that looks like one.

    `path` names the writer, and defaults to `unrecorded` for an ending written before
    the path existed -- which is a dated fact about the archive, not a silent default.
    """
    if not rows:
        return {'kind': 'no_events', 'path': None, 'reason': None}
    # A read that blocks inside a native call cannot be interrupted from Python, so the
    # harness may give up long before the loop finds out (live run
    # `packaged-mirror-20261024-010918`: the wrap-up killed the process at 05:20:02 and
    # the progress watch only wrote its stop at 05:23:20).  Both records are true; the
    # journal's own ending is the one that says what the *run* did, and `harness.json`
    # only explains a run that wrote no ending of its own (D82).
    for row in rows:
        if row.get('event') == 'mirror_loop_stopped':
            return {'kind': 'stop', 'path': str(row.get('stop_path') or 'unrecorded'),
                    'reason': row.get('reason')}
    for row in rows:
        if row.get('event') == 'mirror_loop_error':
            return {'kind': 'error', 'path': str(row.get('stop_path') or 'unrecorded'),
                    'reason': row.get('reason') or row.get('error_type')
                    or 'an_error_was_recorded_without_a_reason'}
    killed = _harness_kill(directory)
    if killed is not None:
        return killed
    return {'kind': 'died', 'path': 'process_died', 'reason': None}


def _harness_kill(directory):
    """The caller's own record of killing this run, when it left one.

    A run killed from outside cannot write its ending, so the process that killed it has
    to: `tools/selfrun_mirror.py` drops `harness.json` beside the journal when its own
    wall clock fired.  Without that file the same rows stay `died`, because a process
    that vanished is not evidence of a budget.
    """
    if directory is None:
        return None
    import json
    import pathlib
    path = pathlib.Path(directory) / HARNESS_FILE
    if not path.exists():
        return None
    try:
        record = json.loads(path.read_text(encoding='utf-8'))
    except ValueError:
        return None
    if not isinstance(record, dict) or not record.get('killed_by_budget'):
        return None
    return {'kind': 'budget', 'path': 'harness_budget',
            'reason': str(record.get('stop') or 'the_budget_ended_the_run')}


def unknown_stop_paths(rows):
    """Paths in this record that no writer is allowed to name, or none."""
    from maalimbus.pages import STOP_PATHS
    seen = {str(row.get('stop_path')) for row in rows
            if row.get('event') in STOP_EVENTS and row.get('stop_path')}
    return sorted(seen - set(STOP_PATHS))


def summarise(rows, directory=None):
    """One dict of counts for one run.  Pure: same rows in, same dict out."""
    events = [row.get('event') for row in rows]
    stops = [row for row in rows if row.get('event') == 'mirror_loop_stopped']
    verdicts = {}
    for row in rows:
        if row.get('event') != 'map_click_result':
            continue
        outcome = row.get('outcome')
        why = row.get('reason')
        if outcome == 'accepted' and why not in ACCEPTED_MOVEMENT:
            outcome = 'accepted_other'
        verdicts[outcome] = verdicts.get(outcome, 0) + 1
    refusals = sum(1 for row in rows if row.get('event') in
                   ('window_recovery', 'map_candidates_empty', 'window_map_retry',
                    'window_page_retry'))
    recoveries = events.count('window_recovery')
    return {
        'events': len(rows),
        'frames': events.count('map_observed'),
        'pages': len({row.get('page') for row in rows if row.get('page')}),
        'verdicts': verdicts,
        'refusals': refusals,
        'recoveries': recoveries,
        'recovery_effect': recovery_effect(rows),
        'recovery_advanced': recovery_advanced(rows),
        'recovery_rate': (recoveries / refusals) if refusals else None,
        'stops': len(stops),
        'stop_reasons': sorted({str(row.get('reason')) for row in stops}),
        'no_progress_stops': sum(
            1 for row in stops
            if str(row.get('reason')) not in ('loop_deadline_exceeded',)),
        # A run whose process died mid-flight writes no stop event, so counting stops
        # alone silently drops it from every rate.  Measured on
        # `evidence/runtime/packaged-mirror-20261023-094914`: 183 events, floor 1,
        # `exit 3221226505`, `stop: null` -- a crash that no rate could see.
        # An error event is a recorded end too: counting only `mirror_loop_stopped`
        # made 10 runs look like silent deaths (33 vs 23 on the same corpus) because
        # they ended on `mirror_loop_error`.
        'ended_without_a_stop': bool(rows) and not stopped_in_events(rows),
        'ending': ending(rows, directory),
        'floors': sorted({row.get('floor') for row in rows
                          if row.get('event') == 'map_observed' and row.get('floor')}),
        'floor_pace': floor_pace(rows),
    }

STOP_EVENTS = ('mirror_loop_stopped', 'mirror_loop_error')


# The player's own requirement (2026-10-24): one floor per ten minutes, so a complete
# five-floor exploration fits in fifty.  Everything the loop does that is not a floor is
# measurable against this number, and a run that cannot be given this much time is not
# evidence about throughput at all.
TARGET_SECONDS_PER_FLOOR = 600.0
# Below this a floor change is a label that repeated, not a floor that was walked.
MIN_FLOOR_SECONDS = 30.0


def _floor_of(value):
    """The floor number as the journal writes it.

    It is a **string** on every retained run (`'2'`, `'3'`), which a type check for
    numbers silently drops: measured 2026-10-24, five runs walked two floors and every
    one of them reported no pace.
    """
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def floor_pace(rows):
    """Seconds the run spent per floor it actually gained, or None.

    Measured from the **first floor seen to the last**, not from the run's start: the
    entry walk before the first floor is a different cost, and charging it to a floor
    makes a slow entry look like a slow floor.  A run that gained no floor has no pace.
    """
    seen = []
    for row in rows:
        if row.get('event') != 'map_observed':
            continue
        floor = _floor_of(row.get('floor'))
        if floor is None:
            continue
        at = _stamp(row)
        if at is not None:
            seen.append((at, floor))
    if len({floor for _, floor in seen}) < 2:
        return None
    seen.sort()
    # A floor label that moves within seconds is not a cleared floor: measured on the
    # retained archive (2026-10-24), the five runs that showed two floors moved between
    # them in 5-19 s, which is one floor read twice, not two floors walked.  A floor that
    # takes less than MIN_FLOOR_SECONDS is dropped from the sample rather than averaged
    # into it, and the caller is told how many were dropped.
    if (seen[-1][0] - seen[0][0]).total_seconds() < MIN_FLOOR_SECONDS:
        return None
    gained = seen[-1][1] - seen[0][1]
    seconds = (seen[-1][0] - seen[0][0]).total_seconds()
    if gained <= 0 or seconds <= 0:
        return None
    return {'seconds': round(seconds, 1), 'floors': gained,
            'per_floor': round(seconds / gained, 1),
            'from_floor': seen[0][1], 'to_floor': seen[-1][1]}



FLOOR_TIME_GROUPS = (
    ('battle', ('BATTLE_HUD', 'BATTLE_PLANNING', 'BATTLE_RESULT', 'BATTLE_DEFEAT',
                'BATTLE_TIP', 'DEFEAT', 'REVIVE_PICK', 'HEAL_SINNERS')),
    ('shop', ('SHOP', 'SHOP_PURCHASE')),
    ('gift', ('GIFT_PICK', 'GIFT_GET', 'GIFT_SEARCH')),
    ('map', ('MAP', 'NODE_PANEL', 'DUNGEON_PROGRESS', 'DUNGEON_TEAM', 'RESUME_DIALOG',
             'PRE_BATTLE_TEAM', 'DEPLOYMENT', 'LOADING', 'UNKNOWN', 'REWARD_CARD',
             'THEME_PACKS', 'INITIAL_GIFTS', 'STAR_GRACES', 'EXPIRED_SESSION')),
)


def floor_time_group(page):
    """Which part of a floor a page belongs to (D122).

    The dwell of a floor says how long it was on screen; this says what was happening
    while it was.  The groups are coarse on purpose: the question an operator asks is
    "how much of the ten minutes is fighting, walking or shopping", and a finer split
    would be an opinion about where a boundary is.
    """
    name = str(page or '')
    for group, pages in FLOOR_TIME_GROUPS:
        if name in pages:
            return group
    return 'other'


def floor_time(rows):
    """Seconds spent inside each named floor, split by what the loop was doing (D122).

    A gap is attributed to the page the journal named while it ran -- the last
    `loop_heartbeat`/`map_observed`/`battle_observed` scene -- and only inside a floor the
    reader could name.  The nested `events` map is what turns "70% on the map page" into a
    next question: which events cost that time.
    """
    stamps = [(row, _stamp(row)) for row in rows]
    stamps = [(row, when) for row, when in stamps if when is not None]
    stamps.sort(key=lambda pair: pair[1])
    page, floor = None, None
    floors = {}
    for index, (row, when) in enumerate(stamps):
        if row.get('event') in ('loop_heartbeat', 'map_observed', 'battle_observed'):
            page = row.get('page') or row.get('scene') or page
            if row.get('floor') is not None:
                floor = _floor_of(row.get('floor'))
        if index + 1 >= len(stamps):
            continue
        following = stamps[index + 1][1]
        seconds = (following - when).total_seconds()
        if seconds < 0 or seconds > MAX_GAP_SECONDS:
            continue
        if floor is None:
            continue
        entry = floors.setdefault(floor, {'seconds': 0.0, 'groups': {}, 'events': {}})
        group = floor_time_group(page)
        entry['seconds'] = round(entry['seconds'] + seconds, 1)
        bucket = entry['groups'].setdefault(group, {'seconds': 0.0, 'n': 0})
        bucket['seconds'] = round(bucket['seconds'] + seconds, 1)
        bucket['n'] += 1
        spent = entry['events'].setdefault(row.get('event') or '?', {'seconds': 0.0, 'n': 0})
        spent['seconds'] = round(spent['seconds'] + seconds, 1)
        spent['n'] += 1
    for entry in floors.values():
        for bucket in entry['groups'].values():
            bucket['seconds'] = round(bucket['seconds'], 1)
        for group, bucket in entry['groups'].items():
            bucket['share'] = round(bucket['seconds'] / entry['seconds'], 3) if entry['seconds'] else 0.0
        entry['events'] = dict(sorted(entry['events'].items(),
                                      key=lambda pair: -pair[1]['seconds'])[:8])
    return dict(sorted(floors.items()))


def floor_dwell(rows):
    """How long the run stayed inside each floor it could name, and what ended it.

    `floor_pace` needs two floors, so a run that ends inside one floor has no pace at
    all -- and that is exactly the run an operator asking "is a floor ten minutes?" has
    in front of them.  Measured 2026-10-24 on `packaged-mirror-20261024-124531` (610 s):
    the harness reported `floors [3]` while the pace was `None`, because the run entered
    floor 3 and never left it.  The dwell is the honest figure for that run: first and
    last time the floor was *seen*, the seconds between, and whether the run ended while
    still on it (no later floor was ever named).
    """
    seen = {}
    order = []
    for row in rows:
        if row.get('event') != 'map_observed':
            continue
        floor = _floor_of(row.get('floor'))
        at = _stamp(row)
        if floor is None or at is None:
            continue
        if floor not in seen:
            seen[floor] = {'first': at, 'last': at, 'reads': 0}
            order.append(floor)
        entry = seen[floor]
        entry['last'] = at if at > entry['last'] else entry['last']
        entry['reads'] += 1
    if not order:
        return {}
    result = {}
    for index, floor in enumerate(order):
        entry = seen[floor]
        ended_here = index == len(order) - 1
        result[floor] = {'seconds': round((entry['last'] - entry['first']).total_seconds(), 1),
                         'reads': entry['reads'],
                         'ended_here': ended_here}
    return result




CAPABILITY_MARKERS = {
    'stop_path': 'a stop can name its writer (D37)',
    'timed': 'a read can time itself (D68)',
    'harness': 'the budget killer can leave a record (D78)',
}


def capability(rows, directory=None):
    """What this run's own writers could have said -- measured, not assumed."""
    pathed = any(row.get('stop_path') for row in rows
                 if row.get('event') == 'mirror_loop_stopped')
    timed = any(isinstance(row.get('seconds'), (int, float))
                for row in rows if row.get('event') in ('map_observed', 'battle_observed'))
    import pathlib as _pathlib  # local: this module imports lazily (D61)
    harness = bool(directory is not None and (_pathlib.Path(directory) / HARNESS_FILE).exists())
    return {'stop_path': pathed, 'timed': timed, 'harness': harness,
            'can_write_a_stop': bool(pathed or harness)}


def reads_by_page(directories=None):
    """Where the reads per input go, grouped by the page the input was sent from (D187).

    `reads_per_input` (D182) says how many reads an input costs; this says which pages cost
    them.  A run is read only when it can say how long a read took or carries a stop path
    (D181), so a legacy run's shape is not quoted as today's.  Reads are counted to the next
    input, which is the same window the corpus figure uses.
    """
    groups = {}
    for directory in _archives(directories):
        rows = _rows_of(directory)
        if not capability(rows, directory)['can_write_a_stop']:
            continue
        page = None
        pending = None
        for row in rows:
            event = row.get('event')
            if event in PAGE_READ_EVENTS:
                if pending is not None:
                    pending[1] += 1
                continue
            if event == 'scene_mismatch':
                if pending is not None:
                    pending[2] += 1
                continue
            if event != 'window_intent':
                continue
            if pending is not None:
                groups.setdefault(pending[0], []).append((pending[1], pending[2]))
            pending = [str(row.get('page') or '?'), 0, 0]
            page = pending[0]
        if pending is not None:
            groups.setdefault(pending[0], []).append((pending[1], pending[2]))
    table = {}
    for name, values in groups.items():
        if len(values) < READS_PER_INPUT_FLOOR:
            continue
        reads = sorted(value[0] for value in values)
        probes = sorted(value[1] for value in values)
        table[name] = {'inputs': len(values),
                       'median': reads[len(reads) // 2],
                       'p90': reads[min(len(reads) - 1, int(len(reads) * 0.9))],
                       'probes': probes[len(probes) // 2]}
    return table


def silent_rate(runs):
    """A rate over the runs that could have written a stop, never over all of them."""
    capable = [run for run in runs if run.get('capability', {}).get('can_write_a_stop')]
    silent = [run for run in capable if run.get('ending', {}).get('kind') == 'died']
    if not capable:
        return {'value': None, 'basis': 'no run of %d could write a stop' % len(runs),
                'note': 'a run from before the writers existed cannot die silently: it had no pen'}
    return {'value': len(silent) / len(capable),
            'basis': '%d of %d runs that could write a stop wrote none' % (len(silent), len(capable)),
            'note': None}


def stopped_in_events(records):
    """Did this run end on a recorded stop?

    One definition, because two existed and disagreed: `tools/audit_runs.py` read the
    summary report (76 stopped / 33 died of 109) while `tools/audit_silent.py` read the
    journal (86 / 23 of the same corpus).  The journal is the durable record -- the
    report is written by the same process that may have died -- so the journal decides,
    and the report is only a fallback when no events were written at all.
    """
    return any(record.get('event') in STOP_EVENTS for record in records)



# --- what a recovery rung did to the view ------------------------------------
# The ladder does not change the page -- it moves the viewport, so its effect is a change
# in what the reader can see on the *same* page.  D58 measured 0 of 274 recoveries landing
# on a different page name, which said nothing about the rungs: the journal already carries
# the evidence in `map_observed`, whose boxes are what the reader found.  Measured over
# `evidence/runtime/packaged-mirror-*` (2026-10-23): pinch_out on MAP changed 73 of 110
# frames, drag_down on MAP 18 of 72, drag_up 14 of 14, pan_left 7 of 8, pan_right 6 of 7,
# and `wait` 7 of 59 -- a wait is not supposed to move anything, and on DRIVE (a fixed
# layout) it is the only rung allowed, changing nothing 38 of 38 times by design.
VIEW_KEYS = ('scene', 'floor', 'header_box', 'pack_box', 'battle_box',
             'clear_selection_box', 'panel_enter_box')


def view(row):
    """What the reader could see in a frame, as a signature two frames can be compared by."""
    parts = []
    for key in VIEW_KEYS:
        value = row.get(key)
        parts.append(tuple(value) if isinstance(value, (list, tuple)) else value)
    return tuple(parts)


NODE_EVENTS = ('map_nodes_offered',)


def node_view(row):
    """The destinations a frame offered, as a signature two frames can be compared by.

    Added after D62 measured the ladder by page chrome alone: a gesture can pull a node
    into view without moving the header, pack or panel boxes, so the chrome signal can
    only ever lower-bound a rung's effect. Positions are compared as a sorted set of box
    centres, because the offer is ordered by adjacency and a re-order is not a change.
    """
    points = []
    for box in row.get('boxes') or ():
        if not isinstance(box, (list, tuple)) or len(box) < 4:
            continue
        points.append((int(float(box[0]) + float(box[2]) / 2),
                       int(float(box[1]) + float(box[3]) / 2)))
    return (row.get('offered'), tuple(sorted(points)))


def _nearest(rows, index, direction, event):
    other = index + direction
    while 0 <= other < len(rows):
        if rows[other].get('event') == event:
            return rows[other]
        other += direction
    return None


def rung_effect(rows):
    """Per (gesture, page): did spending this rung change the view?

    `seen` counts the rung, `measured` the ones with a readable frame on both sides, and
    the rest is the answer.  A rung spent on an unreadable page (`UNKNOWN`) is measured
    too: it is exactly the case where a gesture has nothing to move.
    """
    found = {}
    for index, row in enumerate(rows):
        if row.get('event') != 'window_recovery':
            continue
        gesture = row.get('gesture')
        page = row.get('page')
        entry = found.setdefault((gesture, page),
                                 {'seen': 0, 'measured': 0, 'changed': 0, 'same': 0,
                                  'nodes_measured': 0, 'nodes_changed': 0})
        entry['seen'] += 1
        before = _nearest(rows, index, -1, 'map_observed')
        after = _nearest(rows, index, 1, 'map_observed')
        if before is None or after is None:
            continue
        entry['measured'] += 1
        chrome = view(before) != view(after)
        nodes_before = _nearest(rows, index, -1, NODE_EVENTS[0])
        nodes_after = _nearest(rows, index, 1, NODE_EVENTS[0])
        nodes = (nodes_before is not None and nodes_after is not None
                 and node_view(nodes_before) != node_view(nodes_after))
        if nodes_before is not None and nodes_after is not None:
            entry['nodes_measured'] += 1
            if nodes:
                entry['nodes_changed'] += 1
        if chrome or nodes:
            entry['changed'] += 1
        else:
            entry['same'] += 1
    for entry in found.values():
        entry['change_rate'] = (round(entry['changed'] / entry['measured'], 3)
                                if entry['measured'] else None)
    return found


def ladder_effect(directories=None):
    """The same answer over the whole corpus, as rows a report can print."""
    total = {}
    for directory in _archives(directories):
        for (gesture, page), entry in rung_effect(_rows_of(directory)).items():
            into = total.setdefault((gesture, page),
                                    {'seen': 0, 'measured': 0, 'changed': 0, 'same': 0})
            for key in ('seen', 'measured', 'changed', 'same'):
                into[key] += entry[key]
    rows = []
    for (gesture, page), entry in total.items():
        entry = dict(entry)
        entry['gesture'] = gesture
        entry['page'] = page
        entry['change_rate'] = (round(entry['changed'] / entry['measured'], 3)
                                if entry['measured'] else None)
        rows.append(entry)
    return sorted(rows, key=lambda row: (-row['seen'], row['gesture'], str(row['page'])))


# --- the six figures phase 6 asks for, from one definition --------------------
# A frame the observer actually read.  `scene_mismatch` is the map node's own record of a
# frame it read and could not identify -- still a recognition call.  Leaving it out made a
# run that spent its whole window on an unreadable page look like it read nothing
# (`evidence/runtime/map-live-20261023-203103`: 19 frames, 19 `scene_mismatch`).
READ_EVENTS = ('map_observed', 'battle_observed', 'scene_mismatch')
# A read that named a page.  `scene_mismatch` is written by a pipeline guard node whose
# expected scene was not on screen (D191): it is a probe the pipeline runs by itself, not
# a read the loop spent, and counting it as one made the entry page look like 108 reads.
PAGE_READ_EVENTS = ('map_observed', 'battle_observed')
# Only the two writers that run on a page can time themselves (D68): a `scene_mismatch` is
# the pipeline's own refusal record, with no action body to measure.
TIMED_READ_EVENTS = ('map_observed', 'battle_observed')

# Five verified floors is the dungeon's own definition of a finished exploration.  A
# complete *run* also claims the payout -- and until D63 no journal event recorded it, so
# this counted the exploration half and the report said so.  `reward_task` now writes
# `reward_task_executed` / `reward_task_stopped` / `reward_task_skipped`, so `payout_rate`
# can ask the other half instead of guessing at it.
CLEAR_FLOORS = 5
READS_PER_INPUT_FLOOR = 5
PAYOUT_EVENTS = ('reward_task_executed', 'reward_task_stopped', 'reward_task_skipped',
                 'reward_claimed')  # D251: the loop's own claim walk (RUN_CLAIM family)

MEASURES = (
    'clear_rate',
    'floor_progress',
    'seconds_per_floor',
    'floor_dwell',
    'payout_rate',
    'mean_seconds',
    'reads_per_step',
    'reads_per_input',
    'recovery_advanced_rate',
    'no_progress_stop_rate',
    'unconfirmed_purchases',
)


def _stamps(rows):
    """The journal's own clock, sorted.  `utc` is ISO-8601 with an offset."""
    from datetime import datetime
    stamps = []
    for row in rows:
        value = row.get('utc')
        if not isinstance(value, str):
            continue
        try:
            stamps.append(datetime.fromisoformat(value))
        except ValueError:
            continue
    return sorted(stamps)


def efficiency(rows, directory=None):
    """One run's efficiency numbers; `None` where the journal cannot supply one.

    Kept apart from `summarise`, which counts *events*: these are what phase 6 asks for,
    and a figure that was not measured must be `None` rather than zero -- a zero is a
    claim, and this session has already published two wrong numbers by letting a default
    stand in for a measurement (D50's denominator, D56's dismissal).
    """
    base = summarise(rows, directory)
    stamps = _stamps(rows)
    seconds = (stamps[-1] - stamps[0]).total_seconds() if len(stamps) >= 2 else None
    reads = sum(1 for row in rows if row.get('event') in PAGE_READ_EVENTS)
    probes = sum(1 for row in rows if row.get('event') == 'scene_mismatch')
    intents = sum(1 for row in rows if row.get('event') == 'window_intent')
    # A heartbeat is not a step.  `loop_heartbeat` is written before each loop iteration
    # only since 2026-10-23 (it was added for the runs that died with no cause), so an
    # archive that spans older builds has far fewer heartbeats than steps -- 303 against
    # the 1065 steps those same runs declare.  Using the heartbeat count as the
    # denominator published `reads_per_step 34.2` for a corpus whose real figure is 9.73
    # (D67).  The step count the loop declares when it stops is the denominator; the
    # heartbeats are kept beside it as what the journal documents.
    heartbeats = sum(1 for row in rows if row.get('event') == 'loop_heartbeat')
    declared = [row.get('steps') for row in rows
                if row.get('event') == 'mirror_loop_stopped' and isinstance(row.get('steps'), int)]
    steps = max(declared) if declared else None
    floors = [row.get('floor') for row in rows
              if row.get('event') == 'map_observed' and isinstance(row.get('floor'), int)]
    sent = sum(1 for row in rows if row.get('event') == 'shop_purchase_sent')
    confirmed = sum(1 for row in rows if row.get('event') == 'shop_purchase_confirmed')
    payouts = [row for row in rows if row.get('event') in PAYOUT_EVENTS]
    payout = None
    if payouts:
        claimed = [row for row in payouts
                   if (row.get('event') == 'reward_task_executed'
                       and row.get('passed') is not False)
                   or row.get('event') == 'reward_claimed']
        payout = {'claimed': bool(claimed), 'events': len(payouts),
                  'reason': (claimed[-1].get('reason') if claimed
                             else (payouts[-1].get('reason') or payouts[-1].get('error')))}
    return {
        'seconds': None if seconds is None else round(seconds, 1),
        'reads': reads,
        'probes': probes,
        'payout': payout,
        'steps': steps,
        'dwell': floor_dwell(rows),
        'floor_pace': floor_pace(rows),
        'heartbeats': heartbeats,
        'reads_per_step': round(reads / steps, 2) if steps else None,
        'reads_per_input': round(reads / intents, 2) if intents else None,
        'inputs': intents,
        'reached_floor': max(floors) if floors else None,
        'explored': bool(floors) and max(floors) >= CLEAR_FLOORS,
        # D80: a run that ended on `loop_deadline_exceeded` was stopped by its caller's
        # wall clock, not by anything the loop learned.  Every rate that divides by the
        # corpus has to say how much of it was capped, because a corpus of 150 s runs
        # cannot measure a five-floor clear no matter how many runs it holds.
        'budget_ended': (base.get('ending') or {}).get('reason') == 'loop_deadline_exceeded',
        'ending': base['ending'],
        'recoveries': base['recoveries'],
        'advanced': base['recovery_advanced']['advanced'],
        'recovery_advanced_rate': base['recovery_advanced']['rate'],
        'unconfirmed_purchases': (max(0, sent - confirmed)
                                  if (sent or confirmed) else None),
        'events': base['events'],
    }


def _archives(directories=None):
    import pathlib
    if directories is None:
        root = pathlib.Path(__file__).resolve().parents[2] / 'evidence' / 'runtime'
        # The corpus is "directories that wrote a journal", the same definition
        # `tools/audit_runs.py` uses: a directory with no journal is not a run that
        # measured zero, it is a run there is nothing to measure.
        directories = sorted(path.parent
                             for path in root.glob('packaged-mirror-*/events.jsonl'))
    return [pathlib.Path(directory) for directory in directories]


def _rows_of(directory):
    import json
    import pathlib
    path = pathlib.Path(directory) / 'events.jsonl'
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()
            if line.strip()]


def metrics(runs):
    """The six figures across many runs, each with its basis and its honest note."""
    total = len(runs)
    timed = [run['seconds'] for run in runs if run['seconds'] is not None]
    documented = [run for run in runs if run['steps'] is not None]
    stepped = sum(run['steps'] for run in documented)
    # The numerator has to come from the same set as the denominator: reads from the runs
    # that declare steps, never from the whole corpus (D67).  Mixing them is how a rate
    # stops being a rate.
    reads = sum(run['reads'] or 0 for run in documented)
    recoveries = sum(run['recoveries'] or 0 for run in runs)
    advanced = sum(run['advanced'] or 0 for run in runs)
    purchases = [run['unconfirmed_purchases'] for run in runs
                 if run['unconfirmed_purchases'] is not None]
    died = sum(1 for run in runs if run['ending']['kind'] == 'died')
    errored = sum(1 for run in runs if run['ending']['kind'] == 'error')
    # How many runs could name their ending at all: `stop_path` only exists since D37, and a
    # run that wrote nothing is indistinguishable from one that could not write (D176).
    able = sum(1 for run in runs if (run['ending'].get('path') or '') not in ('', 'process_died'))
    explored = sum(1 for run in runs if run['explored'])
    capped = sum(1 for run in runs if run.get('budget_ended'))
    walked = [run['reached_floor'] for run in runs if run.get('reached_floor')]
    pace = [run['floor_pace']['per_floor'] for run in runs
            if run.get('floor_pace') and run['floor_pace'].get('per_floor')]
    dwell = [entry['seconds']
             for run in runs
             for entry in (run.get('dwell') or {}).values() if entry.get('ended_here')]
    paid = [run['payout'] for run in runs if run['payout'] is not None]
    claimed = sum(1 for payout in paid if payout['claimed'])
    values = [run['reads_per_input'] for run in runs
              if run.get('reads_per_input') is not None
              and (run.get('inputs') or 0) >= READS_PER_INPUT_FLOOR]
    return {
        'clear_rate': {
            'value': round(explored / total, 3) if total else None,
            'basis': f'{explored} of {total} runs reached floor {CLEAR_FLOORS}',
            'note': ('exploration half only: a complete run also claims the payout, which '
                     '`payout_rate` reports; before D63 no journal event recorded the claim. '
                     f'{capped} of {total} runs were ended by their callers budget '
                     '(`loop_deadline_exceeded`), so this rate is a statement about the '
                     'budget as much as about the loop (D80)')},
        # A clear rate over runs nobody gave enough time to clear says nothing about the
        # loop; the floor the loop actually reached per run is the figure that moves.  It
        # is measured over the runs that walked at least one floor, because a run capped
        # before its first floor is not evidence about progress.
        # A run that ends inside one floor has no pace (`floor_pace` needs two), which is
        # exactly the run an operator asking "is a floor ten minutes?" is looking at
        # (D121).  The dwell is how long the floor it ended in was on screen.
        'floor_dwell': {
            'value': round(sum(dwell) / len(dwell), 1) if dwell else None,
            'basis': (f'mean time inside the floor a run ended in, over {len(dwell)} run(s) '
                      'that ended inside a floor' if dwell else
                      'no run recorded a floor it stayed in'),
            'note': (None if dwell else
                     'no run named a floor, so there is no time inside one to average')},
        'floor_progress': {
            'value': round(sum(walked) / len(walked), 2) if walked else None,
            'basis': (f'best floor {max(walked)}; {len(walked)} of {total} runs reached a '
                      'floor (mean over those runs)' if walked else
                      f'none of {total} runs reached a floor'),
            'note': (None if walked else
                     'no run walked a floor, so there is no progress to average')},
        # The player's requirement, in the units they stated it in: ten minutes per
        # floor, fifty for five.  Measured over the runs that actually gained a floor,
        # because a run capped before its second floor cannot say how long a floor takes.
        'seconds_per_floor': {
            'value': round(sum(pace) / len(pace), 1) if pace else None,
            'basis': (f"mean over {len(pace)} run(s) that gained a floor; target "
                      f"{int(TARGET_SECONDS_PER_FLOOR)} s per floor, "
                      f"{sum(1 for value in pace if value <= TARGET_SECONDS_PER_FLOOR)} of "
                      f"{len(pace)} at or under it" if pace else
                      f'no run gained a floor; target {int(TARGET_SECONDS_PER_FLOOR)} s'),
            'note': (None if pace else
                     'a floor takes at least two floor readings, and no retained run has '
                     'two of them: the caller budget, not the loop, is what these runs '
                     'measured (D80/D95)')},
        'payout_rate': {
            'value': round(claimed / len(paid), 3) if paid else None,
            'basis': f'{claimed} of {len(paid)} runs that recorded a payout outcome claimed it',
            'note': (None if paid else
                     'no run wrote a reward-task outcome, so no payout was measured: the '
                     'reward branch used to return before the journal line every other '
                     'task action writes (D63)')},
        'mean_seconds': {
            'value': round(sum(timed) / len(timed), 1) if timed else None,
            'basis': f'{len(timed)} of {total} runs carry two or more timestamps',
            'note': None if timed else 'no run carries two timestamps, so there is no duration to average'},
        'reads_per_step': {
            'value': round(reads / stepped, 2) if stepped else None,
            'basis': (f"{reads} reads over {stepped} steps declared by "
                      f"{len(documented)} of {total} runs"),
            'note': ('one read is one observer call, retries included; a heartbeat is not a '
                     'step, and the builds before 2026-10-23 wrote none at all (D67)'
                     if stepped else
                     'no run declares its step count, so there is no per-step rate')},
        'reads_per_input': {
            # A run that sent one input and read once has a rate of 1.0 and says nothing;
            # the median over runs that sent at least READS_PER_INPUT_FLOOR inputs is the
            # only figure that can be compared with the best observed run.
            'value': (round(sorted(values)[len(values) // 2], 2) if values else None),
            'basis': ('median over %d run(s) that sent at least %d input(s); best observed %.2f'
                      % (len(values), READS_PER_INPUT_FLOOR, min(values)) if values
                      else 'no run sent %d inputs' % READS_PER_INPUT_FLOOR),
            'note': ('a read here is one observer call that named a page (PAGE_READ_EVENTS: map and '
                     'battle, retries included); a scene_mismatch is a pipeline guard node probing a scene '
                     'it expected, not a read the loop spent, and it is reported separately (D191).  '
                     'The read that proves the input plus the read after it is the floor')},
        'recovery_advanced_rate': {
            'value': round(advanced / recoveries, 3) if recoveries else None,
            'basis': f'{advanced} of {recoveries} recoveries advanced the run',
            'note': None if recoveries else 'no recovery was recorded, so there is no rate'},
        'no_progress_stop_rate': {
            # The corpus mixes two eras: `stop_path` exists since D37, so a run recorded
            # before it wrote an `unrecorded` stop while a modern one would have named the
            # path.  The rate stays over every run (a death is a death) and the eras are
            # published beside it, because the split is what says whether the number
            # describes the loop or the instrument (D176).
            'value': round((died + errored) / total, 3) if total else None,
            'basis': (f'{died} died + {errored} errored of {total}; '
                      f'{able} of {total} could name their ending'),
            'note': ('a run that ended without a stop record counts here; a run the '
                     'harness killed at its budget does not, because the caller ended it '
                     'and the loop never got to speak (D78)')},
        # Two different facts look alike here: a corpus where every purchase was confirmed
        # and a corpus where nothing was ever bought.  The first is a measurement of the
        # risk; the second is the absence of one, and saying "0 unconfirmed" for both would
        # publish a zero that was never observed.
        'unconfirmed_purchases': (
            {'value': sum(purchases) if purchases else 0,
             'basis': f'{sum(purchases) if purchases else 0} purchases sent without a '
                      'confirmed read-back',
             'note': 'the risk figure: an unconfirmed spend is what the reservation '
                     'layer protects'} if any(purchases) else
            {'value': 0,
             'basis': (f'{len(purchases)} run(s) wrote purchase events and every one was '
                       'confirmed' if purchases else
                       f'no run of {total} wrote a purchase event'),
             'note': ('every spend in these runs was confirmed; a different corpus '
                      'would be needed to show the failure the reservation protects'
                      if purchases else
                      'the risk is absent, not measured: nothing was bought')}),
    }


# ------------------------------------------------------------------ map clicks (D75)

# The map's candidate list is nine kinds of detected box (`map_clicks`), and a click's
# verdict used to say which box was refused but not what the reader thought it was.
# `gold_badge_node` and `lattice_step` arrive as 190x190 tiles whose centre is often
# empty space, while `lit_icon`/`bright_lit_icon` arrive as the 40x40 glyph the game
# marks the step it will accept with -- so "which kind lands" is the question a run has
# to answer before the map can be trusted, and the journal now carries it.

# A click whose panel opens one read late is recorded as `unjudged` and settled by the
# next read (D76).  It is not a refusal and must not be counted as one: a refusal
# feeds `map_refused_streak`, and a streak of one leaves the exploration.
CLICK_VERDICTS = ('accepted', 'rejected', 'superseded', 'unjudged')


SETTLED_VERDICTS = ('accepted', 'rejected', 'superseded')


def settled_clicks(rows):
    """One entry per map click that has a verdict, not one per row (D198).

    A click is recorded twice: `unjudged` when it goes out, then `accepted`/`rejected` when
    the next read answers it.  Counting rows therefore counted each click twice and made
    the accepted share look half of what it is (`packaged-mirror-20261025-011222`: 14 rows,
    7 clicks, 3 accepted).  A click with no answer yet stays `pending` and is left out of the
    rate, because an unanswered click is not a refusal.
    """
    settled, pending = [], []
    for row in rows:
        if row.get('event') != 'map_click_result':
            continue
        outcome = row.get('outcome')
        if outcome == 'unjudged':
            pending.append(row)
            continue
        settled.append(row)
        if pending:
            pending.pop()
    return {'settled': settled, 'pending': pending}


def click_kinds(directories=None):
    """Clicks by candidate kind: sent, accepted, rejected, superseded, unjudged."""
    by_kind = {}
    declared = 0
    sent = 0
    for directory in _archives(directories):
        for row in _rows_of(directory):
            if row.get('event') != 'map_click_result':
                continue
            sent += 1
            kind = row.get('kind')
            if kind:
                declared += 1
            entry = by_kind.setdefault(kind or 'unrecorded',
                                       {name: 0 for name in CLICK_VERDICTS})
            entry['sent'] = entry.get('sent', 0) + 1
            verdict = row.get('outcome')
            if verdict in CLICK_VERDICTS:
                entry[verdict] += 1
    return {'sent': sent, 'declared': declared, 'by_kind': by_kind}


def click_kind_report(kinds):
    """A table plus the line that says whether it is measured at all."""
    rows = []
    for kind in sorted(kinds['by_kind'], key=lambda name: -kinds['by_kind'][name]['sent']):
        entry = kinds['by_kind'][kind]
        taken = entry['accepted'] + entry['rejected']
        rows.append({**entry, 'kind': kind,
                     'rate': round(entry['accepted'] / taken, 2) if taken else None})
    measured = kinds['declared'] > 0
    return {'rows': rows, 'measured': measured,
            'basis': '%d of %d click verdicts name a candidate kind' % (kinds['declared'],
                                                                       kinds['sent']),
            'note': None if measured else
                    'no verdict names a kind, because the writer that records it is newer (D75)'}


def portfolio(directories=None):
    """Every run plus the six figures, so a report is one command, not a recount."""
    runs = []
    budgets = []
    costs = []
    for directory in _archives(directories):
        rows = _rows_of(directory)
        if not rows:
            continue
        entry = {'run': directory.name}
        entry.update(efficiency(rows, directory))
        runs.append(entry)
        budget = time_budget(rows)
        budgets.append(budget)
        cost = read_cost(rows)
        cost['reads_group'] = (budget['groups'].get('reads') or {}).get('seconds')
        costs.append(cost)
    return {'runs': runs, 'measures': metrics(runs), 'time': time_portfolio(budgets),
            'reads': read_portfolio(costs), 'split': read_split(costs)}


# ------------------------------------------------------------------------ time (D66)


# Phase 6 asked for a mean duration and `mean_seconds` supplied one.  The question the
# next sentence always asks is *which event owns that time*, and the journal can answer
# it without any new instrumentation, because every row already carries its own `utc`:
# the gap from a row to the next stamped row is the time that row cost.  Measured on the
# 142 retained runs on 2026-10-23: 29 538 s attributable, of which `map_observed` held
# 13 650 s (46.2%, 2.45 s per read) and `window_unknown_wait` 4 434 s (15.0%, 8.9 s per
# round).  That is the number a speed claim has to move, and it was not on any report.
#
# A gap is only attributed when it is a step and not a stall: a run that was paused by the
# host, or one whose clock jumped, would otherwise hand one event minutes it did not cost.
MAX_GAP_SECONDS = 120.0
TIME_GROUPS = (
    ('reads', ('map_observed', 'battle_observed', 'scene_mismatch')),
    ('waits', ('window_unknown_wait', 'window_transition_wait', 'loop_heartbeat',
               'pi_controller', 'window_unknown_probe', 'window_page_wait')),
    ('inputs', ('window_intent', 'map_click_result')),
    ('recovery', ('window_recovery',)),
)
GROUP_OF = {event: group for group, events in TIME_GROUPS for event in events}
OTHER_GROUP = 'other'


def group_of(event):
    """Which budget line an event belongs to; an unknown event is `other`, never dropped."""
    return GROUP_OF.get(str(event), OTHER_GROUP)


def _stamp(row):
    """One row's `utc` as a datetime, or None when it does not parse (D81)."""
    from datetime import datetime
    value = row.get('utc')
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def stamped(rows):
    """[(event, stamp)] for the rows whose `utc` really parses, in journal order."""
    from datetime import datetime
    out = []
    for row in rows:
        value = row.get('utc')
        if not isinstance(value, str):
            continue
        try:
            out.append((str(row.get('event')), datetime.fromisoformat(value)))
        except ValueError:
            continue
    return out


def time_budget(rows, *, cap=MAX_GAP_SECONDS):
    """One run's seconds attributed to the event that cost them.

    `attributed_seconds` is what the journal can explain; `unattributed_seconds` is the
    rest (no stamps, a single stamp, or a gap beyond `cap`).  Both are reported, because
    a budget that silently drops the unexplained part is a share of nothing.
    """
    pairs = stamped(rows)
    # The gap after a row belongs to that row, so the row itself is what can explain it.
    # Before D81 the pairing threw the row away and kept only its name, which is why an
    # unknown wait could not say which page it followed.
    rows_by_stamp = []
    for row in rows:
        when = _stamp(row)
        if when is not None:
            rows_by_stamp.append((row, when))
    per_event = {}
    # D81: an unknown page is not one behaviour, so its cost is also kept by the page it
    # followed.  Rows written before D81 carry no `after`, which is its own bucket rather
    # than silently joining the named ones.
    waits = {}
    attributed = 0.0
    capped = 0
    for (row, when), (_, then) in zip(rows_by_stamp, rows_by_stamp[1:]):
        event = row.get('event')
        gap = (then - when).total_seconds()
        if gap < 0:
            continue
        if gap > cap:
            capped += 1
            continue
        attributed += gap
        entry = per_event.setdefault(event, {'seconds': 0.0, 'n': 0})
        entry['seconds'] += gap
        entry['n'] += 1
        if event == 'window_unknown_wait':
            after = row.get('after') or 'unrecorded'
            bucket = waits.setdefault(after, {'seconds': 0.0, 'n': 0})
            bucket['seconds'] += gap
            bucket['n'] += 1
    total = (pairs[-1][1] - pairs[0][1]).total_seconds() if len(pairs) >= 2 else None
    events = {}
    for event, entry in per_event.items():
        events[event] = {'seconds': round(entry['seconds'], 1), 'n': entry['n'],
                         'mean': round(entry['seconds'] / entry['n'], 2),
                         'group': group_of(event)}
    groups = {}
    for event, entry in events.items():
        bucket = groups.setdefault(entry['group'], {'seconds': 0.0, 'n': 0, 'events': []})
        bucket['seconds'] += entry['seconds']
        bucket['n'] += entry['n']
        bucket['events'].append(event)
    for bucket in groups.values():
        bucket['seconds'] = round(bucket['seconds'], 1)
        bucket['events'] = sorted(bucket['events'],
                                  key=lambda name: -events[name]['seconds'])
    return {
        'total_seconds': None if total is None else round(total, 1),
        'attributed_seconds': round(attributed, 1),
        'unattributed_seconds': (None if total is None
                                 else round(max(0.0, total - attributed), 1)),
        'capped_gaps': capped,
        'events': events,
        'groups': groups,
        # D81: the unknown-page group split by the page that preceded it.
        'unknown_waits': {after: {'seconds': round(entry['seconds'], 1),
                                  'n': entry['n'],
                                  'mean': round(entry['seconds'] / entry['n'], 2)}
                          for after, entry in sorted(waits.items(),
                                                     key=lambda item: -item[1]['seconds'])},
    }


def read_cost(rows):
    """How long the observation node itself took, when it said so.

    D66 attributed 2.45 s to every `map_observed` row from the gaps between journal
    lines, and a gap cannot say whether that is the node's screencap+OCR or the wrapper
    around it: the gap after a read starts where the read's line was written and lasts
    until the *next* line, which includes the next read.  Since D68 every observation
    writer records its own `seconds`, so the two halves can be subtracted instead of
    guessed.  Rows written before D68 carry no number, and a corpus of those reports
    "not measured" rather than zero.
    """
    rows = list(rows)
    total = [row for row in rows if row.get('event') in TIMED_READ_EVENTS]
    measured = []
    for row in total:
        seconds = row.get('seconds')
        if isinstance(seconds, (int, float)) and not isinstance(seconds, bool):
            measured.append((row.get('event'), float(seconds)))
    if not measured:
        return {'rows': len(total), 'measured': 0, 'seconds': None, 'mean': None,
                'median': None, 'by_event': {}, 'phases': read_phases(total)}
    by_event = {}
    for event, seconds in measured:
        entry = by_event.setdefault(event, {'seconds': 0.0, 'n': 0})
        entry['seconds'] += seconds
        entry['n'] += 1
    for entry in by_event.values():
        entry['seconds'] = round(entry['seconds'], 1)
        entry['mean'] = round(entry['seconds'] / entry['n'], 2) if entry['n'] else None
    values = sorted(seconds for _, seconds in measured)
    middle = len(values) // 2
    median = (values[middle] if len(values) % 2 else
              round((values[middle - 1] + values[middle]) / 2, 2))
    return {'rows': len(total), 'measured': len(values),
            'seconds': round(sum(values), 1),
            'mean': round(sum(values) / len(values), 2),
            'median': median,
            'by_event': dict(sorted(by_event.items(),
                                    key=lambda pair: -pair[1]['seconds'])),
            'phases': read_phases(total)}


PHASE_KEYS = ('ocr_seconds', 'roi_seconds', 'classify_seconds')


def read_phases(rows):
    """Split a read's own `seconds` into the full-frame OCR, the ROI re-reads and the rest.

    D70 writes the three on the row because one unexplained 1.39 s per read is not a basis
    for choosing between fewer reads and cheaper reads.  A row written before D70 carries
    none of them, and a corpus of those reports "not measured" rather than three zeros.
    """
    measured = []
    for row in rows:
        if row.get('event') not in TIMED_READ_EVENTS:
            continue
        values = [row.get(key) for key in PHASE_KEYS]
        if all(isinstance(value, (int, float)) and not isinstance(value, bool)
               for value in values):
            measured.append(values)
    if not measured:
        return {'measured': 0, 'mean': {key: None for key in PHASE_KEYS}}
    return {
        'measured': len(measured),
        'mean': {key: round(sum(entry[index] for entry in measured) / len(measured), 2)
                 for index, key in enumerate(PHASE_KEYS)},
    }


def read_portfolio(costs):
    """Many runs' read costs folded into one, with the coverage it was read from."""
    costs = [cost for cost in costs if cost is not None]
    measured = sum(cost['measured'] for cost in costs)
    rows = sum(cost['rows'] for cost in costs)
    if not measured:
        return {'value': None,
                'basis': f'0 of {rows} read(s) carry their own duration',
                'note': ('no observation row records how long it took, so the cost of a '
                         'read can only be inferred from the gaps (D66) and not split '
                         'into node time and wrapper time (D68)')}
    seconds = round(sum(cost['seconds'] for cost in costs
                        if cost['seconds'] is not None), 1)
    by_event = {}
    for cost in costs:
        for event, entry in cost['by_event'].items():
            merged = by_event.setdefault(event, {'seconds': 0.0, 'n': 0})
            merged['seconds'] += entry['seconds']
            merged['n'] += entry['n']
    for entry in by_event.values():
        entry['seconds'] = round(entry['seconds'], 1)
        entry['mean'] = round(entry['seconds'] / entry['n'], 2) if entry['n'] else None
    phases = read_phases_of([cost.get('phases') for cost in costs])
    return {'value': {'measured': measured, 'rows': rows, 'seconds': seconds,
                      'mean': round(seconds / measured, 2),
                      'phases': phases,
                      'by_event': dict(sorted(by_event.items(),
                                              key=lambda pair: -pair[1]['seconds']))},
            'basis': f'{measured} of {rows} read(s) carry their own duration',
            'note': None}


def read_phases_of(phases):
    """Add up the per-run phase splits that were actually measured.

    The split is measured per read (D70) and per run (read_phases); this is the corpus
    total.  A run that did not split counts as absent, never as zero seconds, so a corpus
    of one splitting run beside 142 older ones reports that one run's split.
    """
    usable = [entry for entry in phases
              if isinstance(entry, dict) and entry.get('measured')]
    if not usable:
        return {'measured': 0, 'mean': {key: None for key in PHASE_KEYS}}
    measured = sum(entry['measured'] for entry in usable)
    mean = {}
    for key in PHASE_KEYS:
        # weight each run's mean by how many reads it measured, or a run of 1 read would
        # count as much as a run of 26
        total = sum(((entry.get('mean') or {}).get(key) or 0.0) * entry['measured']
                    for entry in usable)
        mean[key] = round(total / measured, 2) if measured else None
    return {'measured': measured, 'mean': mean}


def read_split(costs):
    """What the reads group cost, and how much of it the node itself accounts for.

    Both halves are summed over the runs that measured both (a run needs gap timestamps
    *and* read durations), so the subtraction compares one sample with itself.  A
    negative overhead is reported as-is rather than clamped: it would mean the gaps were
    capped inside the reads, which is a fact about the corpus and not a number to fix.
    """
    pairs = [cost for cost in costs
             if cost.get('seconds') is not None and cost.get('reads_group') is not None]
    if not pairs:
        return {'value': None,
                'basis': 'no run measured both its read durations and its gaps',
                'note': ('the split needs a run that carries read durations and two '
                         'parseable timestamps; the retained corpus predates D68')}
    node = round(sum(cost['seconds'] for cost in pairs), 1)
    group = round(sum(cost['reads_group'] for cost in pairs), 1)
    measured = sum(cost['measured'] for cost in pairs)
    return {'value': {'node_seconds': node, 'reads_group_seconds': group,
                      'overhead_seconds': round(group - node, 1),
                      'measured_reads': measured,
                      'node_mean': round(node / measured, 2) if measured else None},
            'basis': f'{len(pairs)} run(s) measured both, over {measured} read(s)',
            'note': ('the node half is the observation action\'s own `seconds`; the '
                     'remainder is everything the loop does around it, including the '
                     'next read\'s wait')}


def time_portfolio(budgets, reads=None):
    """Many runs' budgets folded into one, with the share each group owns.

    `None` when no run carried two parseable timestamps: a mean duration over an empty
    corpus is not zero seconds, it is not a duration.
    """
    timed = [budget for budget in budgets if budget['total_seconds'] is not None]
    attributed = round(sum(budget['attributed_seconds'] for budget in timed), 1)
    total = round(sum(budget['total_seconds'] for budget in timed), 1)
    groups = {}
    events = {}
    for budget in timed:
        for group, bucket in budget['groups'].items():
            entry = groups.setdefault(group, {'seconds': 0.0, 'n': 0, 'events': {}})
            entry['seconds'] += bucket['seconds']
            entry['n'] += bucket['n']
            for event in bucket['events']:
                detail = budget['events'][event]
                kept = entry['events'].setdefault(event, {'seconds': 0.0, 'n': 0})
                kept['seconds'] += detail['seconds']
                kept['n'] += detail['n']
        for event, detail in budget['events'].items():
            merged = events.setdefault(event, {'seconds': 0.0, 'n': 0,
                                               'group': detail['group']})
            merged['seconds'] += detail['seconds']
            merged['n'] += detail['n']
    for entry in groups.values():
        entry['seconds'] = round(entry['seconds'], 1)
        entry['share'] = round(entry['seconds'] / attributed, 3) if attributed else None
        entry['events'] = sorted(entry['events'],
                                 key=lambda name: -entry['events'][name]['seconds'])
    for entry in events.values():
        entry['seconds'] = round(entry['seconds'], 1)
        entry['mean'] = round(entry['seconds'] / entry['n'], 2) if entry['n'] else None
        entry['share'] = round(entry['seconds'] / attributed, 3) if attributed else None
    # D81: the unknown-page group is only worth its share if it can be split by what the
    # loop was waiting for; a loading screen after a battle and a transition after the
    # menu are different behaviours sharing one event name.
    waits = {}
    for budget in timed:
        for after, detail in (budget.get('unknown_waits') or {}).items():
            entry = waits.setdefault(after, {'seconds': 0.0, 'n': 0})
            entry['seconds'] += detail['seconds']
            entry['n'] += detail['n']
    for entry in waits.values():
        entry['seconds'] = round(entry['seconds'], 1)
        entry['mean'] = round(entry['seconds'] / entry['n'], 2) if entry['n'] else None
    return {
        'value': None if not timed else {
            'attributed_seconds': attributed,
            'total_seconds': total,
            'per_event': dict(sorted(events.items(),
                                     key=lambda pair: -pair[1]['seconds'])[:10]),
            'groups': dict(sorted(groups.items(),
                                  key=lambda pair: -pair[1]['seconds'])),
            'unknown_waits': dict(sorted(waits.items(),
                                         key=lambda pair: -pair[1]['seconds'])),
        },
        'basis': f'{len(timed)} of {len(budgets)} runs carry two or more timestamps, '
                 f'{round(sum(b["capped_gaps"] for b in timed))} gap(s) beyond '
                 f'{MAX_GAP_SECONDS:.0f} s excluded',
        'note': (None if timed else
                 'no run carries two parseable timestamps, so no time was attributed'),
    }
