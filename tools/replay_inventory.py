"""Which replay tools share the one controller, and which still carry their own.

The promise of an offline replay is one sentence -- a retained frame is not a
game, so nothing is clicked unless the scenario names the click it expects -- but
before `maalimbus.replay` existed the sentence was implemented ten times, and the
other twenty-nine tools inherited whichever copy was closest. This tool prints the
provider graph so a reader can see that: for every `tools/verify_*_replay.py`,
where its `Replay` comes from, whether that class is a subclass of the shared
layer, and which scenario expectations it keeps.

Exit 0 when every controller in the tools inherits the shared layer and none of
them re-implements the mechanical surface; exit 1 otherwise.
"""
from __future__ import annotations

import argparse
import ast
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

MECHANICAL = ('connect', 'request_uuid', 'get_features', 'disconnect')
INPUT_METHODS = ('click', 'swipe', 'touch_down', 'touch_move', 'touch_up',
                 'key', 'key_down', 'key_up', 'press_key', 'click_key', 'screencap')
LAYER = 'ReplayController'


def _tools(directory=None):
    """Every tool, not only the ones named `*_replay`: the population that carried
    a controller before this layer existed was 16, and five of them were nested
    inside `main()` with unrelated file names."""
    directory = pathlib.Path(directory or ROOT / 'tools')
    return sorted(directory.glob('*.py'))


def _controllers(tree):
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            bases = {getattr(b, 'id', None) or getattr(b, 'attr', None) for b in node.bases}
            if bases & {'CustomController', LAYER}:
                out.append((node, bases))
    return out


def providers(tree):
    """module name -> the module a tool says it imports `Replay` from."""
    found = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                if alias.name == 'Replay':
                    found[node.module] = True
    return sorted(found)


def describe(path):
    source = path.read_text(encoding='utf-8')
    tree = ast.parse(source)
    rows = []
    for node, bases in _controllers(tree):
        methods = {m.name for m in node.body if isinstance(m, ast.FunctionDef)}
        rows.append({
            'class': node.name,
            'bases': sorted(b for b in bases if b),
            'shared': LAYER in bases,
            'mechanical_redefined': sorted(methods & set(MECHANICAL)),
            'expectations': sorted(methods & set(INPUT_METHODS)),
        })
    return {
        'tool': path.name,
        'controllers': rows,
        'imports_replay_from': providers(tree),
        'direct_input_calls': sorted({
            n.func.attr for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr in INPUT_METHODS
        }),
    }


def report(directory=None):
    rows = [describe(p) for p in _tools(directory)]
    problems = []
    for row in rows:
        for controller in row['controllers']:
            if controller['mechanical_redefined']:
                problems.append('%s: %s re-implements %s' % (
                    row['tool'], controller['class'], ', '.join(controller['mechanical_redefined'])))
            if not controller['shared']:
                problems.append('%s: %s does not inherit %s' % (
                    row['tool'], controller['class'], LAYER))
    by_owner = {}
    for row in rows:
        for controller in row['controllers']:
            by_owner.setdefault(controller['class'], 0)
    return {
        'tools': len(rows),
        'owning_a_controller': sum(1 for row in rows if row['controllers']),
        'inheriting_from_the_layer': sum(1 for row in rows if any(c['shared'] for c in row['controllers'])),
        'importing_a_replay_class': sum(1 for row in rows if row['imports_replay_from']),
        'rows': rows,
        'problems': problems,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--directory', type=pathlib.Path)
    args = parser.parse_args(argv)
    data = report(args.directory)
    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print('replay tools: %d  owning a controller: %d  inheriting the shared layer: %d'
              % (data['tools'], data['owning_a_controller'], data['inheriting_from_the_layer']))
        for row in data['rows']:
            for controller in row['controllers']:
                print('  %-40s %-8s bases=%s expectations=%s'
                      % (row['tool'], controller['class'], ','.join(controller['bases']),
                         ','.join(controller['expectations']) or '-'))
            if row['imports_replay_from']:
                print('  %-40s imports Replay from %s' % (row['tool'], ','.join(row['imports_replay_from'])))
        print('problems: %s' % (data['problems'] or 'none'))
    return 1 if data['problems'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
