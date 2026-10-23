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

