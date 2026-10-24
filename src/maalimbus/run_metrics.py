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


ENDING_KINDS = ('stop', 'error', 'died', 'no_events')


def ending(rows):
    """Which of the four ways this run ended; the four are exhaustive by construction.

    `tools/audit_runs.py` used to classify a run as "stopped" or "died" and nothing else,
    so the ten retained runs that ended on `mirror_loop_error` alone appeared in neither
    column (81 + 51 = 132 of 142 on 2026-10-23).  A census whose buckets do not partition
    the corpus is not a denominator, it is a sample that looks like one.

    `path` names the writer, and defaults to `unrecorded` for an ending written before
    the path existed -- which is a dated fact about the archive, not a silent default.
    """
    if not rows:
        return {'kind': 'no_events', 'path': None, 'reason': None}
    for row in rows:
        if row.get('event') == 'mirror_loop_stopped':
            return {'kind': 'stop', 'path': str(row.get('stop_path') or 'unrecorded'),
                    'reason': row.get('reason')}
    for row in rows:
        if row.get('event') == 'mirror_loop_error':
            return {'kind': 'error', 'path': str(row.get('stop_path') or 'unrecorded'),
                    'reason': row.get('reason') or row.get('error_type')
                    or 'an_error_was_recorded_without_a_reason'}
    return {'kind': 'died', 'path': 'process_died', 'reason': None}


def unknown_stop_paths(rows):
    """Paths in this record that no writer is allowed to name, or none."""
    from maalimbus.pages import STOP_PATHS
    seen = {str(row.get('stop_path')) for row in rows
            if row.get('event') in STOP_EVENTS and row.get('stop_path')}
    return sorted(seen - set(STOP_PATHS))


def summarise(rows):
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
        'ending': ending(rows),
        'floors': sorted({row.get('floor') for row in rows
                          if row.get('event') == 'map_observed' and row.get('floor')}),
    }

STOP_EVENTS = ('mirror_loop_stopped', 'mirror_loop_error')


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

# Five verified floors is the dungeon's own definition of a finished exploration.  A
# complete *run* also claims the payout -- and until D63 no journal event recorded it, so
# this counted the exploration half and the report said so.  `reward_task` now writes
# `reward_task_executed` / `reward_task_stopped` / `reward_task_skipped`, so `payout_rate`
# can ask the other half instead of guessing at it.
CLEAR_FLOORS = 5
PAYOUT_EVENTS = ('reward_task_executed', 'reward_task_stopped', 'reward_task_skipped')

MEASURES = (
    'clear_rate',
    'payout_rate',
    'mean_seconds',
    'reads_per_step',
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


def efficiency(rows):
    """One run's efficiency numbers; `None` where the journal cannot supply one.

    Kept apart from `summarise`, which counts *events*: these are what phase 6 asks for,
    and a figure that was not measured must be `None` rather than zero -- a zero is a
    claim, and this session has already published two wrong numbers by letting a default
    stand in for a measurement (D50's denominator, D56's dismissal).
    """
    base = summarise(rows)
    stamps = _stamps(rows)
    seconds = (stamps[-1] - stamps[0]).total_seconds() if len(stamps) >= 2 else None
    reads = sum(1 for row in rows if row.get('event') in READ_EVENTS)
    steps = sum(1 for row in rows if row.get('event') == 'loop_heartbeat')
    floors = [row.get('floor') for row in rows
              if row.get('event') == 'map_observed' and isinstance(row.get('floor'), int)]
    sent = sum(1 for row in rows if row.get('event') == 'shop_purchase_sent')
    confirmed = sum(1 for row in rows if row.get('event') == 'shop_purchase_confirmed')
    payouts = [row for row in rows if row.get('event') in PAYOUT_EVENTS]
    payout = None
    if payouts:
        claimed = [row for row in payouts if row.get('event') == 'reward_task_executed'
                   and row.get('passed') is not False]
        payout = {'claimed': bool(claimed), 'events': len(payouts),
                  'reason': (claimed[-1].get('reason') if claimed
                             else (payouts[-1].get('reason') or payouts[-1].get('error')))}
    return {
        'seconds': None if seconds is None else round(seconds, 1),
        'reads': reads,
        'payout': payout,
        'steps': steps,
        'reads_per_step': round(reads / steps, 2) if steps else None,
        'reached_floor': max(floors) if floors else None,
        'explored': bool(floors) and max(floors) >= CLEAR_FLOORS,
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
    stepped = sum(run['steps'] or 0 for run in runs)
    reads = sum(run['reads'] or 0 for run in runs)
    recoveries = sum(run['recoveries'] or 0 for run in runs)
    advanced = sum(run['advanced'] or 0 for run in runs)
    purchases = [run['unconfirmed_purchases'] for run in runs
                 if run['unconfirmed_purchases'] is not None]
    died = sum(1 for run in runs if run['ending']['kind'] == 'died')
    errored = sum(1 for run in runs if run['ending']['kind'] == 'error')
    explored = sum(1 for run in runs if run['explored'])
    paid = [run['payout'] for run in runs if run['payout'] is not None]
    claimed = sum(1 for payout in paid if payout['claimed'])
    return {
        'clear_rate': {
            'value': round(explored / total, 3) if total else None,
            'basis': f'{explored} of {total} runs reached floor {CLEAR_FLOORS}',
            'note': 'exploration half only: a complete run also claims the payout, which '
                    '`payout_rate` reports; before D63 no journal event recorded the claim'},
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
            'basis': f'{reads} reads over {stepped} heartbeats',
            'note': ('one read is one observer call, retries included' if stepped else
                     'no run wrote a heartbeat, so there is no per-step rate')},
        'recovery_advanced_rate': {
            'value': round(advanced / recoveries, 3) if recoveries else None,
            'basis': f'{advanced} of {recoveries} recoveries advanced the run',
            'note': None if recoveries else 'no recovery was recorded, so there is no rate'},
        'no_progress_stop_rate': {
            'value': round((died + errored) / total, 3) if total else None,
            'basis': f'{died} died + {errored} errored of {total}',
            'note': 'a run that ended without a stop record counts here'},
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


def portfolio(directories=None):
    """Every run plus the six figures, so a report is one command, not a recount."""
    runs = []
    for directory in _archives(directories):
        rows = _rows_of(directory)
        if not rows:
            continue
        entry = {'run': directory.name}
        entry.update(efficiency(rows))
        runs.append(entry)
    return {'runs': runs, 'measures': metrics(runs)}
