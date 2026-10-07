"""Read or seed the rotation ledger the window walks with.

The ledger is the player's own order of saved teams; the window asks it which team to
bring and records the run's five floor clears, the final victory, the claimed reward
and the entry back in. This tool only inspects and seeds it -- a run is never invented
here, because every ledger event has to name the frame it was read from.
"""
import argparse
import sys
from pathlib import Path

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
    args = parser.parse_args()

    if args.action == 'seed':
        slots = [int(part) for part in args.slots.replace(' ', '').split(',') if part]
        seed_run_store(args.path, slots, rotation=args.rotation)
        print('seeded %s with slots=%s rotation=%d' % (args.path, slots, args.rotation))

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
