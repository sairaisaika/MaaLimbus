"""Decide a reason name's role from where it is written, not from how it reads.

Three times I tried to classify the repository's reason strings by their shape and three
times the denominator was wrong: 71 of 189 were plan intents, 75 more were imperative
action names, ~54 were evidence labels.  Shape cannot tell them apart -- `flow_token_seen`
and `caption_not_read` are both noun phrases.

Provenance can.  A string written at a `_refuse(...)` call site is a refusal; one written
as `_plan(reason=...)` is an intent; one written into an evidence dict, an assertion or a
modelcard is a label.  This module records that, so the classification has a source of
truth that a human can check against the line it came from.
"""
import ast
import pathlib

FAILURE_SITES = ('_refuse', '_stop', 'refuse', 'stop')
FAILURE_KEYS = ('stopped', 'stopped_reason', 'stop_reason')
INTENT_KEYS = ('plan_reason',)
EVIDENCE_KEYS = ()            # default: anything else

# A record that already says what it decided does not need its prose classified.
# `{'kind': 'the_loop_is_alive', 'action': 'keep_waiting', 'reason': ...}` names its own
# class, and `{'ready': True, 'reason': 'the_controller_id_is_present'}` names its own
# verdict; the reason beside them is the label for that decision, not a fourth place to
# look for a recovery action.  (Measured 2026-10-23: the failure count without a kind was
# 7, and every one of them was a label inside such a record -- including
# `the_controller_id_is_present`, a *success* the prose inferer had read as a failure.)
DECIDED_KEYS = ('kind', 'verdict')                 # a class, as a string constant
DECIDED_BOOLS = ('ready', 'passed', 'ok', 'succeeded', 'stop')   # a verdict, as a bool


def _call_name(node):
    func = getattr(node, 'func', None)
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ''


class _Walk(ast.NodeVisitor):
    def __init__(self, filename):
        self.filename = filename
        self.scope = []
        self.found = {}       # name -> set of (role, site)

    def _record(self, value, role, site):
        if isinstance(value, str) and value:
            self.found.setdefault(value, set()).add((role, site))

    def visit_FunctionDef(self, node):
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Dict(self, node):
        # Does this record already say what it decided?  Then its `reason` is the label
        # for that decision and needs no recovery class of its own.
        decided = any(
            isinstance(key, ast.Constant)
            and ((key.value in DECIDED_KEYS and isinstance(value, ast.Constant)
                  and isinstance(value.value, str))
                 or (key.value in DECIDED_BOOLS and isinstance(value, ast.Constant)
                     and isinstance(value.value, bool)))
            for key, value in zip(node.keys, node.values))
        for key, value in zip(node.keys, node.values):
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                key_name = key.value
                if key_name in FAILURE_KEYS:
                    self._record(getattr(value, 'value', None), 'failure', f'dict:{key_name}')
                elif key_name in INTENT_KEYS:
                    self._record(getattr(value, 'value', None), 'intent', f'dict:{key_name}')
                elif key_name == 'reason':
                    owner = self.scope[-1] if self.scope else ''
                    if decided:
                        role, site = 'evidence', f'decided@{owner}'
                    else:
                        role = ('intent' if owner.startswith('_plan') or owner.endswith('_plan')
                                else 'failure')
                        site = f'reason@{owner}'
                    self._record(getattr(value, 'value', None), role, site)
                else:
                    self._record(getattr(value, 'value', None), 'evidence', f'dict:{key_name}')
        self.generic_visit(node)

    def visit_Call(self, node):
        name = _call_name(node)
        for keyword in node.keywords:
            if keyword.arg in FAILURE_KEYS:
                self._record(getattr(keyword.value, 'value', None), 'failure', f'{name}({keyword.arg})')
            elif keyword.arg in INTENT_KEYS:
                self._record(getattr(keyword.value, 'value', None), 'intent', f'{name}({keyword.arg})')
            elif keyword.arg == 'reason':
                role = 'failure' if name in FAILURE_SITES else (
                    'intent' if 'plan' in name else 'evidence')
                self._record(getattr(keyword.value, 'value', None), role, f'{name}(reason)')
        if name in FAILURE_SITES and len(node.args) >= 2:
            self._record(getattr(node.args[1], 'value', None), 'failure', f'{name}(arg1)')
        if len(node.args) >= 2 and name.endswith('_plan'):
            self._record(getattr(node.args[1], 'value', None), 'intent', f'{name}(arg1)')
        self.generic_visit(node)


def scan(directory=None):
    """{name: {(role, site), ...}} for every string written at a reason-like position."""
    root = pathlib.Path(directory or pathlib.Path(__file__).resolve().parent)
    found = {}
    for path in sorted(root.glob('*.py')):
        walker = _Walk(path.name)
        walker.visit(ast.parse(path.read_text(encoding='utf-8')))
        for name, sites in walker.found.items():
            found.setdefault(name, set()).update(sites)
    return found


def roles(found=None):
    """{name: role} using provenance, plus the names whose sites disagree."""
    found = found if found is not None else scan()
    decided, conflicted = {}, {}
    for name, sites in found.items():
        kinds = {role for role, _site in sites}
        if len(kinds) == 1:
            decided[name] = kinds.pop()
        else:
            conflicted[name] = sorted(sites)
    return decided, conflicted
