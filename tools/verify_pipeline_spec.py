"""Check this project's assets against the MaaFramework protocols they name.

The manual is the contract, and each check below says which page it comes from:

* `docs/zh_cn/3.3-ProjectInterfaceV2协议.md` — `interface_version: 2` fields: the
  controller `type` set, the `display_*` mutual exclusion, the note that an `Adb`
  controller's input/screencap are auto-detected (so a local `adb.screencap` /
  `adb.input` would be a claim the protocol does not make), the Win32
  `screencap`/`mouse`/`keyboard` names, `task.entry`, and `option` cases whose
  `pipeline_override` must name pipeline nodes.
* `docs/zh_cn/3.1-任务流水线协议.md` — the node field set, `next`/`on_error`/
  `interrupt` naming other nodes (with the `[JumpBack]` / `[Error]` / `[Stop]` /
  `[DetectionMissed]` markers), and `target: true` meaning the box this node just
  recognized.
* `docs/zh_cn/1.3-Custom&Agent.md` — a node's `custom_recognition` /
  `custom_action` name must have been registered by the agent before the task runs;
  `agent/main.py` is that registration list here.

Read-only. Exit 1 when an asset names something the protocols do not define.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# docs/zh_cn/3.3-ProjectInterfaceV2协议.md:161 — the controller `type` values the
# protocol defines. Anything else is our invention.
CONTROLLER_TYPES = ('Adb', 'Win32', 'MacOS', 'PlayCover', 'Gamepad', 'Linux')

# docs/zh_cn/2.4-控制方式说明.md (Win32 Input / Win32 Screencap tables), the string
# names ProjectInterface V2 uses instead of the bit values: the tip at the top of
# 2.4 says "对于 ProjectInterface V2，使用 string 类型（直接使用名称）".
WIN32_MOUSE = ('Seize', 'SendMessage', 'PostMessage', 'LegacyEvent', 'PostThreadMessage',
               'SendMessageWithCursorPos', 'PostMessageWithCursorPos',
               'SendMessageWithWindowPos', 'PostMessageWithWindowPos',
               'Interception', 'AnchoredTouch')
WIN32_KEYBOARD = ('Seize', 'SendMessage', 'PostMessage', 'LegacyEvent', 'PostThreadMessage',
                  'SendMessageWithCursorPos', 'PostMessageWithCursorPos',
                  'SendMessageWithWindowPos', 'PostMessageWithWindowPos',
                  'Interception')
WIN32_SCREENCAP = ('GDI', 'FramePool', 'DXGI_DesktopDup', 'DXGI_DesktopDup_Window',
                   'PrintWindow', 'ScreenDC', 'Foreground', 'Background')

# docs/zh_cn/3.3:165-171 — one scaling mode per controller, never two.
DISPLAY_KEYS = ('display_short_side', 'display_long_side', 'display_expand', 'display_raw')

# docs/zh_cn/3.1-任务流水线协议.md — the node fields this project may use. The list
# is the protocol's own set; a field outside it would be ignored by the runtime, so
# it is reported instead of silently dropped.
NODE_FIELDS = (
    'recognition', 'action', 'next', 'on_error', 'interrupt', 'is_sub',
    'rate_limit', 'timeout', 'on_timeout', 'times_limit', 'inverse', 'enabled',
    'pre_delay', 'post_delay', 'pre_wait_freezes', 'post_wait_freezes',
    'focus', 'attach', 'repeat', 'repeat_times', 'repeat_delay', 'max_hit',
    'roi', 'roi_offset', 'template', 'threshold', 'order_by', 'method',
    'green_mask', 'index', 'count', 'connected', 'expected', 'replace',
    'only_rec', 'model', 'labels', 'custom_recognition', 'custom_recognition_param',
    'custom_action', 'custom_action_param', 'target', 'target_offset', 'key',
    'input_text', 'contact', 'pressure', 'duration', 'starting', 'begin',
    'end', 'begin_offset', 'end_offset', 'swipes', 'package', 'exec', 'args',
    'detach', 'stop_app', 'now', 'definition', 'name', 'mode', 'full', 'images',
    'clamp', 'region', 'screen', 'virtual', 'device', 'display', 'width',
    'height', 'bit', 'channel', 'time', 'on_true', 'on_false', 'delay',
)

# docs/zh_cn/3.1 — these markers may prefix a `next`/`on_error`/`interrupt` entry;
# they are control flow, not node names.
MARKERS = ('[JumpBack]', '[Error]', '[Stop]', '[DetectionMissed]', '[Timeout]', '[JumpBack]')

REGISTRATION = re.compile(r"register_custom_(?:recognition|action)\(\s*'([^']+)'")


def load(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def registered_names(agent_main: Path):
    text = agent_main.read_text(encoding='utf-8')
    return set(REGISTRATION.findall(text))


def strip_markers(name: str):
    for marker in MARKERS:
        while name.startswith(marker):
            name = name[len(marker):]
    return name


def targets(value):
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    return []


def check_interface(interface, pipeline_names, *, root: Path, problems: list):
    if interface.get('interface_version') != 2:
        problems.append(f'interface.json: interface_version is {interface.get("interface_version")!r}, '
                        'the协议 in use is 2 (docs/zh_cn/3.3-ProjectInterfaceV2协议.md:50)')
    for controller in interface.get('controller') or []:
        name = controller.get('name') or controller.get('label') or '<unnamed>'
        kind = controller.get('type')
        if kind not in CONTROLLER_TYPES:
            problems.append(f'interface.json controller {name!r}: type {kind!r} is not one of {CONTROLLER_TYPES}')
        present = [key for key in DISPLAY_KEYS if key in controller]
        if len(present) > 1:
            problems.append(f'interface.json controller {name!r}: {present} are mutually exclusive '
                            '(docs/zh_cn/3.3-ProjectInterfaceV2协议.md:165-171)')
        if kind == 'Adb':
            adb = controller.get('adb') or {}
            for key in ('screencap', 'input', 'mouse', 'keyboard'):
                if key in adb:
                    problems.append(f'interface.json controller {name!r}: adb.{key} claims a manual choice, '
                                    'but the protocol says Adb input/screencap are auto-detected '
                                    '(docs/zh_cn/3.3-ProjectInterfaceV2协议.md:191)')
        if kind == 'Win32':
            win32 = controller.get('win32') or {}
            for key, allowed in (('mouse', WIN32_MOUSE), ('keyboard', WIN32_KEYBOARD),
                                 ('screencap', WIN32_SCREENCAP)):
                value = win32.get(key)
                if value is not None and value not in allowed:
                    problems.append(f'interface.json controller {name!r}: win32.{key} {value!r} is not a name '
                                    f'from docs/zh_cn/2.4-控制方式说明.md ({allowed})')
    options = interface.get('option') or {}
    for task in interface.get('task') or []:
        entry = task.get('entry')
        if entry and entry not in pipeline_names:
            problems.append(f'interface.json task {task.get("name")!r}: entry {entry!r} is not a pipeline node')
        for option_name in task.get('option') or []:
            if option_name not in options:
                problems.append(f'interface.json task {task.get("name")!r}: option {option_name!r} is undefined')
    for option_name, option in options.items():
        for case in option.get('cases') or []:
            for node in (case.get('pipeline_override') or {}):
                if node not in pipeline_names:
                    problems.append(f'interface.json option {option_name!r} case {case.get("name")!r}: '
                                    f'pipeline_override names {node!r}, which is not a pipeline node')
            for nested in case.get('option') or {}:
                if isinstance(nested, str) and nested not in options:
                    problems.append(f'interface.json option {option_name!r} case {case.get("name")!r}: '
                                    f'nested option {nested!r} is undefined')
            for nested in case.get('option') or []:
                if isinstance(nested, str) and nested not in options:
                    problems.append(f'interface.json option {option_name!r} case {case.get("name")!r}: '
                                    f'nested option {nested!r} is undefined')
        for node in (option.get('pipeline_override') or {}):
            if node not in pipeline_names:
                problems.append(f'interface.json option {option_name!r}: pipeline_override names {node!r}, '
                                'which is not a pipeline node')
    for resource in interface.get('resource') or []:
        for path in resource.get('path') or []:
            if not (root / 'assets' / path).exists():
                problems.append(f'interface.json resource {resource.get("name")!r}: path {path!r} does not exist')
    agent = interface.get('agent') or {}
    if not agent.get('child_exec'):
        problems.append('interface.json: agent.child_exec is missing')
    for arg in agent.get('child_args') or []:
        candidate = (root / 'assets' / arg).resolve()
        if arg.endswith('.py') and not candidate.exists():
            problems.append(f'interface.json: agent.child_args {arg!r} does not resolve ({candidate})')


def reachable(pipeline, entries):
    seen, stack = set(), list(entries)
    while stack:
        node = stack.pop()
        if node in seen or node not in pipeline:
            continue
        seen.add(node)
        body = pipeline[node]
        for field in ('next', 'on_error', 'interrupt', 'on_timeout'):
            stack.extend(targets(body.get(field)))
    return seen


def check_pipeline(pipeline, *, registered, entries, problems: list):
    for node, body in pipeline.items():
        for field in body:
            if field not in NODE_FIELDS:
                problems.append(f'pipeline node {node!r}: field {field!r} is not in '
                                'docs/zh_cn/3.1-任务流水线协议.md')
        for field in ('next', 'on_error', 'interrupt', 'on_timeout'):
            for target in targets(body.get(field)):
                name = strip_markers(target)
                if name and name not in pipeline:
                    problems.append(f'pipeline node {node!r}: {field} names {target!r}, which is not a node')
        for field in ('custom_recognition', 'custom_action'):
            name = body.get(field)
            if name and name not in registered:
                problems.append(f'pipeline node {node!r}: {field} {name!r} is not registered by agent/main.py '
                                '(docs/zh_cn/1.3-Custom&Agent.md)')
    live = reachable(pipeline, entries)
    return sorted(set(pipeline) - live)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--interface', default=str(ROOT / 'assets/interface.json'))
    parser.add_argument('--pipeline', action='append', default=None,
                        help='pipeline json (repeatable); default: every assets/resource/*/pipeline/*.json')
    parser.add_argument('--agent-main', default=str(ROOT / 'agent/main.py'))
    parser.add_argument('--report', default=None)
    args = parser.parse_args(argv)

    interface_path = Path(args.interface)
    interface = load(interface_path)
    pipelines = ([Path(p) for p in args.pipeline] if args.pipeline
                 else sorted((ROOT / 'assets/resource').glob('*/pipeline/*.json')))
    registered = registered_names(Path(args.agent_main))
    entries = [task.get('entry') for task in interface.get('task') or [] if task.get('entry')]

    problems: list = []
    nodes: dict = {}
    for path in pipelines:
        nodes.update(load(path))
    check_interface(interface, set(nodes), root=ROOT, problems=problems)
    dead = check_pipeline(nodes, registered=registered, entries=entries, problems=problems)

    print(f'interface : {interface_path.relative_to(ROOT)} (interface_version {interface.get("interface_version")})')
    for path in pipelines:
        print(f'pipeline  : {path.relative_to(ROOT)}')
    print(f'agent     : {Path(args.agent_main).relative_to(ROOT)} registers {len(registered)} names')
    print(f'nodes     : {len(nodes)};  entries: {entries}')
    print(f'reachable : {len(set(nodes) - set(dead))} node(s)')
    if dead:
        print(f'note      : {len(dead)} node(s) unreachable from the task entries: {dead}')
    for problem in problems:
        print(f'PROBLEM   : {problem}')
    print(f'{"ok" if not problems else "broken"} — {len(problems)} problem(s)')

    if args.report:
        Path(args.report).write_text(json.dumps(
            {'interface': str(interface_path), 'pipelines': [str(p) for p in pipelines],
             'registered': sorted(registered), 'nodes': len(nodes), 'entries': entries,
             'unreachable': dead, 'problems': problems}, indent=2, ensure_ascii=False),
            encoding='utf-8')
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
