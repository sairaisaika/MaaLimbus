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
ACCEPTED_MOVEMENT = ('the_party_moved_after_the_click', 'the_click_opened_the_next_page')


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
        'recovery_rate': (recoveries / refusals) if refusals else None,
        'stops': len(stops),
        'stop_reasons': sorted({str(row.get('reason')) for row in stops}),
        'no_progress_stops': sum(
            1 for row in stops
            if str(row.get('reason')) not in ('loop_deadline_exceeded',)),
        'floors': sorted({row.get('floor') for row in rows
                          if row.get('event') == 'map_observed' and row.get('floor')}),
    }
