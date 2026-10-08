"""Read or seed the rotation ledger the window walks with.

The ledger is the player's own order of saved teams; the window asks it which team to
bring and records the run's five floor clears, the final victory, the claimed reward
and the entry back in. This tool inspects it, seeds it at a known rotation, files the
active run when the player gives one up, and points the rotation at a slot the player
names for the next entry -- a run is never invented here, because every ledger event
has to name the frame it was read from.
"""
import argparse
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from maalimbus.storage import RunStore, read_json, seed_run_store  # noqa: E402

DEFAULT = 'config/user-run-ledger.json'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--path', default=DEFAULT, help='the ledger file')
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('status', help='print the rotation and what the active run holds')
    seed = sub.add_parser('seed', help='create the ledger at a known rotation')
    seed.add_argument('--slots', required=True,
                      help='saved-team slots in rotation order, e.g. 5,4,1,6,2,7,3')
    seed.add_argument('--rotation', type=int, default=0,
                      help='which of those slots the next run brings (0-based)')
    seed.add_argument('--force', action='store_true',
                      help='replace an existing ledger, but only one that recorded '
                           'nothing; use it when a run finished out of the harness '
                           'sight and moved the player order')
    give_up = sub.add_parser('abandon', help='drop the active run and keep the rotation')
    give_up.add_argument('--note', default=None,
                         help='why the run is being given up (kept with the record)')
    point = sub.add_parser('point', help='aim the next entry at one saved-team slot')
    point.add_argument('--slot', type=int, required=True,
                       help='the saved-team slot the next run should bring, e.g. 2')
    args = parser.parse_args()

    if args.action == 'seed':
        slots = [int(part) for part in args.slots.replace(' ', '').split(',') if part]
        seed_run_store(args.path, slots, rotation=args.rotation, overwrite=args.force)
        print('seeded %s with slots=%s rotation=%d' % (args.path, slots, args.rotation))
    elif args.action == 'abandon':
        value = read_json(args.path)
        # RunStore only reads ``slot`` off the teams it is handed, so a plain stand-in is
        # enough here and the tool stays a ledger reader rather than a team planner.
        store = RunStore(args.path, [SimpleNamespace(slot=s) for s in value['team_slots']])
        try:
            dropped = store.abandon(note=args.note)
        except ValueError as error:
            raise SystemExit(str(error))
        print('abandoned run %s team %d floors=%s (rotation stays at %d -> team %d)'
              % (dropped['id'][:8], dropped['team'], dropped['floors'],
                 store.data['rotation'], store.team_slot))
    elif args.action == 'point':
        value = read_json(args.path)
        store = RunStore(args.path, [SimpleNamespace(slot=s) for s in value['team_slots']])
        try:
            index = store.point_at(args.slot)
        except ValueError as error:
            raise SystemExit(str(error))
        print('rotation now %d -> team %d (of %s)'
              % (index, store.team_slot, value['team_slots']))

    value = read_json(args.path)
    active = value.get('active')
    print('slots        %s' % value['team_slots'])
    print('rotation     %d -> team %d' % (value['rotation'],
                                          value['team_slots'][value['rotation']]))
    print('completed    %d' % value['completed_runs'])
    if active is None:
        print('active run   none')
    else:
        print('active run   %s team %d floors=%s victory=%s reward=%s'
              % (active['id'][:8], active['team'], active['floors'],
                 active['victory'], active['reward']))


if __name__ == '__main__':
    main()
