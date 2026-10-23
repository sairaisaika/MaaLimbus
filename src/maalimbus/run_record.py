"""One finished attempt -> a record whose cause is never blank.

Why this is a module and not a few lines inside the driver: the driver is the
entry point of every live attempt and had no test at all, so two rounds in a row
a rename inside it shipped as a `NameError` that only a live run could find.
"""

from maalimbus import crash_codes

STOP_EVENTS = ('mirror_loop_stopped', 'mirror_loop_error')


def summarise(events, exit_code):
    """Return ``{'events','floors','stop','reached_floor_5'}`` for one attempt.

    A native death writes no stop event, so the exit code is the only cause left;
    without it the run counts as "ended without a stop" and its cause vanishes.
    """
    floors = sorted({e['floor'] for e in events
                     if e['event'] == 'map_observed' and e.get('floor')})
    stops = [e.get('reason') for e in events if e['event'] in STOP_EVENTS]
    return {'events': len(events), 'floors': floors,
            'stop': stops[0] if stops else (crash_codes.name_for(int(exit_code))
                                           or ('the_loop_returned_without_naming_why'
                                               if events else None)),
            'reached_floor_5': 5 in floors}
