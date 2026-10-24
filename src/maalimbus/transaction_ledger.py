"""Which transaction records the loop writes, and whether each one is read back.

A transaction module in this repo has one shape: something is *reserved* or
*intended* before the input lands, and *observed* or *reconciled* after the screen
answers.  The reservation is what keeps an interrupted run from spending twice:
if the process dies between the click and the observation, the next run reads the
pending record and asks the screen about it instead of buying again.

That pairing is a property of the whole loop, so it cannot live inside any one
transaction module, and until this file existed nothing compared the two halves.
The measurement that motivated it (2026-10-23): ``shop_tx.reconcile_purchase``
and ``shop_tx.reconcile_refresh`` -- the only readers of a reserved purchase --
appear in ``MirrorRunner.step`` **only as bare attribute references**, handed to a
helper as ``shop_reconcile=`` and called there.  No call-site census sees them,
``grep`` finds no ``reconcile_purchase(`` in the runner, and a reviewer reading
``step`` would conclude the reservation is never reconciled.  The same class as
D48's dead hook: a writer whose reader exists but is unreachable by inspection.

So the ledger is derived, not declared:

* the API families come from the transaction modules' own method names
  (:func:`family`), so a new method is classified without editing a list;
* the call sites come from ``MirrorRunner.step``'s AST, with bare attribute
  references counted as *injections* rather than missing calls;
* an intent whose receiver shows no reconciler and no injection is **unpaired** --
  a reservation nobody reads back, which is exactly the duplicate-spend risk the
  acceptance document names.

The ledger deliberately does not decide whether an injection is *called*.  It can
prove the reference exists; only a run can prove the helper reaches it.
"""

from __future__ import annotations

import ast
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
RUNNER = ROOT / 'src' / 'maalimbus' / 'runner.py'
PACKAGE = ROOT / 'src' / 'maalimbus'

#: Modules whose public methods are transaction records.  Derived names are not
#: listed here: :func:`api` discovers every ``*_transaction`` module on disk, and
#: this tuple only names the ones that do not follow the suffix convention.
EXTRA_MODULES = ('shop_transaction',)

#: Longest prefix rules first: ``reserve_confirm`` is an intent, ``confirm_intent``
#: is one too, and after that a name is unknown rather than guessed.
INTENT_PREFIXES = ('intent', 'reserve', 'book_', 'refuse_', 'confirm_clear')
INTENT_SUFFIXES = ('_intent',)
RECONCILE_PREFIXES = ('observe', 'reconcile', 'recover')
RECONCILE_NAMES = ('commit',)
CLEANUP_PREFIXES = ('prepare', 'begin', 'reset', 'seal', 'adopt', 'rebase', 'retire')
CLEANUP_NAMES = ('retire_pending', 'close_visit', 'retire', 'extend', 'prune')
QUERY_PREFIXES = ('matches', 'bought', 'refreshes', 'signature', 'validate', 'retained',
                  'held', 'revived', 'cards', 'budget', 'limit', 'is_', 'frame', 'data',
                  'path', 'offers', 'count', 'notice')


def family(method):
    """``intent`` / ``reconcile`` / ``cleanup`` / ``unknown`` for one method name."""
    name = str(method)
    if name in CLEANUP_NAMES or name.startswith(CLEANUP_PREFIXES):
        return 'cleanup'
    if name in RECONCILE_NAMES or name.startswith(RECONCILE_PREFIXES):
        return 'reconcile'
    if name.startswith(INTENT_PREFIXES) or name.endswith(INTENT_SUFFIXES):
        return 'intent'
    if name.startswith(QUERY_PREFIXES):
        return 'query'
    return 'unknown'


def _modules():
    names = sorted(p.stem for p in PACKAGE.glob('*_transaction.py'))
    for extra in EXTRA_MODULES:
        if extra not in names:
            names.append(extra)
    return names


def api():
    """``{module: {method: family}}`` read off the transaction modules themselves."""
    out = {}
    for name in _modules():
        path = PACKAGE / ('%s.py' % name)
        if not path.exists():
            continue
        tree = ast.parse(path.read_text(encoding='utf-8'))
        methods = {}
        classes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
        for node in (classes[0].body if classes else []):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name.startswith('_'):
                continue
            methods[node.name] = family(node.name)
        out[name] = methods
    return out


def _receiver_is_transaction(text):
    return text.endswith('_transaction') or text.endswith('_tx')


def _word_of(node, parents):
    """The plan reason the enclosing branch asks about, if there is one."""
    for parent in parents:
        if not isinstance(parent, ast.If):
            continue
        for inner in ast.walk(parent.test):
            if isinstance(inner, ast.Constant) and isinstance(inner.value, str):
                if inner.value and ' ' not in inner.value:
                    return inner.value
    return None


def sites(source=None):
    """Every transaction touchpoint in ``MirrorRunner.step``.

    Each row is ``{'line', 'receiver', 'method', 'family', 'word', 'injected'}``.
    ``injected`` marks a bare attribute reference (a callable handed to a helper)
    rather than a call made right there.
    """
    text = (RUNNER.read_text(encoding='utf-8') if source is None else source)
    tree = ast.parse(text)
    step = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == 'step':
            step = node
            break
    if step is None:
        return []
    rows = []
    seen_calls = set()

    def walk(node, parents):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.Call):
                func = child.func
                if isinstance(func, ast.Attribute) and isinstance(func.value, (ast.Attribute, ast.Name)):
                    receiver = ast.unparse(func.value)
                    if _receiver_is_transaction(receiver):
                        rows.append({'line': child.lineno, 'receiver': receiver,
                                     'method': func.attr, 'family': family(func.attr),
                                     'word': _word_of(child, parents), 'injected': False})
                        seen_calls.add((child.lineno, func.attr))
            elif isinstance(child, ast.Attribute) and isinstance(child.value, (ast.Attribute, ast.Name)):
                receiver = ast.unparse(child.value)
                if _receiver_is_transaction(receiver) and (child.lineno, child.attr) not in seen_calls:
                    rows.append({'line': child.lineno, 'receiver': receiver,
                                 'method': child.attr, 'family': family(child.attr),
                                 'word': _word_of(child, parents), 'injected': True})
            walk(child, [child] + parents)

    walk(step, [])
    rows.sort(key=lambda row: (row['line'], row['method']))
    return rows


def ledger(source=None):
    """Per transaction receiver: what is written, what reads it, what is unknown."""
    rows = sites(source)
    out = {}
    for row in rows:
        entry = out.setdefault(row['receiver'], {
            'intents': [], 'reconciles': [], 'cleanup': [], 'unknown': [],
            'queries': [], 'injected': [], 'words': []})
        bucket = {'intent': 'intents', 'reconcile': 'reconciles',
                  'cleanup': 'cleanup', 'query': 'queries'}.get(row['family'], 'unknown')
        if row['method'] not in entry[bucket]:
            entry[bucket].append(row['method'])
        if row['injected'] and row['method'] not in entry['injected']:
            entry['injected'].append(row['method'])
        if row['word'] and row['word'] not in entry['words']:
            entry['words'].append(row['word'])
    for entry in out.values():
        for key in ('intents', 'reconciles', 'cleanup', 'queries', 'unknown', 'injected', 'words'):
            entry[key].sort()
    return out


def unpaired(source=None):
    """Receivers that write an intent but show no reader and no injected reader."""
    out = []
    for receiver, entry in ledger(source).items():
        if not entry['intents']:
            continue
        if entry['reconciles'] or entry['injected']:
            continue
        out.append(receiver)
    return sorted(out)


def unknown_methods(source=None):
    """Transaction API methods the family rules cannot place (fields are not methods)."""
    known = {method for methods in api().values() for method in methods}
    out = []
    for row in sites(source):
        if row['family'] == 'unknown' and row['method'] in known and row['method'] not in out:
            out.append(row['method'])
    return sorted(out)


def dead_api(source=None):
    """Public transaction methods no module references at all."""
    referenced = set()
    for path in PACKAGE.glob('*.py'):
        tree = ast.parse(path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                referenced.add(node.attr)
            # A method reached by name is still referenced: `retire_foreign` is asked
            # for with `getattr(tx, 'retire_foreign', None)` so the loop can treat a
            # ledger that predates the method as quiet instead of crashing (D98).
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == 'getattr' and len(node.args) >= 2
                    and isinstance(node.args[1], ast.Constant)
                    and isinstance(node.args[1].value, str)):
                referenced.add(node.args[1].value)
    out = []
    for module, methods in api().items():
        for method in methods:
            if method not in referenced:
                out.append('%s.%s' % (module, method))
    return sorted(out)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    as_json = '--json' in argv
    source = None
    if '--source' in argv:
        path = pathlib.Path(argv[argv.index('--source') + 1])
        if not path.exists():
            print('no such file: %s' % path, file=sys.stderr)
            return 1
        source = path.read_text(encoding='utf-8')
    modules = api()
    rows = sites(source)
    book = ledger()
    report = {
        'transactions': {name: {'methods': len(methods),
                                'unknown': sorted(m for m, f in methods.items() if f == 'unknown')}
                         for name, methods in modules.items()},
        'sites': len(rows),
        'intent_sites': [row['method'] for row in rows if row['family'] == 'intent'],
        'reconcile_sites': [row['method'] for row in rows if row['family'] == 'reconcile'],
        'injected': sorted({row['method'] for row in rows if row['injected']
                            and row['method'] in {m for methods in modules.values() for m in methods}}),
        'unpaired': unpaired(),
        'unknown_in_loop': unknown_methods(),
        'dead_api': dead_api(),
        'ledger': book,
    }
    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print('transaction modules: %d  public methods: %d'
              % (len(modules), sum(len(m) for m in modules.values())))
        print('touchpoints in the loop: %d  intents: %d  reconciles: %d  injected readers: %s'
              % (report['sites'], len(report['intent_sites']),
                 len(report['reconcile_sites']), ', '.join(report['injected']) or 'none'))
        for receiver in sorted(book):
            entry = book[receiver]
            print('  %-30s intents=%-2d reconciles=%-2d queries=%-2d cleanup=%-2d'
                  % (receiver, len(entry['intents']), len(entry['reconciles']),
                     len(entry['queries']), len(entry['cleanup'])))
        print('intents nothing reads back: %s' % (', '.join(report['unpaired']) or 'none'))
        print('methods the loop calls that the families cannot place: %s'
              % (', '.join(report['unknown_in_loop']) or 'none'))
        print('public methods no module references: %s'
              % (', '.join(report['dead_api']) or 'none'))
        print('unclassified transaction methods: %s'
              % (', '.join(sorted({m for methods in modules.values()
                                   for m, f in methods.items() if f == 'unknown'})) or 'none'))
    bad = report['unpaired'] or report['unknown_in_loop']
    return 1 if bad else 0


if __name__ == '__main__':
    raise SystemExit(main())
