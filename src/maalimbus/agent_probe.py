"""Can the packaged agent start at all?  One answer, asked by every caller.

On 2026-10-25 four attempts burned their whole wall clock writing a single event: the
frozen agent exits inside `agent_server.start_up` with `WinError 1073741845` and a zeromq
"Socket operation on non-socket", before any project code runs.  The harness grew its own
probe for it, and an installer check needs the same answer -- so the question is asked
here once instead of being answered in each caller (D170).
"""
from __future__ import annotations
import subprocess
import sys
from pathlib import Path

DEFAULT_SECONDS = 8.0
IDENTIFIER = 'MaaLimbusAgentPreflight'
# What the tail means, so the next reader does not have to know zeromq's test names.
SIGNATURES = (
    ('ipc_socket_unavailable', ('Socket operation on non-socket', 'signaler.cpp',
                                'WinError 1073741845')),
    ('missing_binary', ('no such file', 'FileNotFoundError')),
    ('python_startup_error', ('Failed to execute script', 'ModuleNotFoundError',
                              'ImportError')),
)


def classify(verdict: dict) -> str:
    """Name the failure class from what the process said, not from what we expected.

    Measured on 2026-10-25: four builds and three launch styles all ended in the same
    zeromq signaler assertion; "it failed" is not a diagnosis, and the class decides
    whether the operator restarts the emulator or looks at the bundle.
    """
    tail = str(verdict.get('tail') or '')
    for name, needles in SIGNATURES:
        if any(needle in tail for needle in needles):
            return name
    if verdict.get('survived'):
        return 'started'
    return 'unknown_failure'


def probe(agent, seconds: float = DEFAULT_SECONDS, *, run=None) -> dict:
    """Start the agent with a throwaway identifier and say whether it stayed up.

    A process still running when the probe gives up has passed the only thing this probe
    can prove: that start_up returned.  A process that exited is reported with its own
    code and tail, because "it failed" is not a diagnosis.
    """
    agent = Path(agent)
    command = [str(agent), IDENTIFIER]
    runner = run or subprocess.run
    try:
        done = runner(command, cwd=str(agent.parent.parent), capture_output=True,
                      text=True, timeout=seconds)
    except subprocess.TimeoutExpired:
        return {'survived': True, 'exit': None, 'agent': str(agent),
                'tail': 'still running after %.0f s' % seconds}
    except OSError as error:
        return {'survived': False, 'exit': None, 'agent': str(agent),
                'tail': str(error)[:300]}
    tail = ((done.stdout or '') + (done.stderr or '')).strip().splitlines()[-2:]
    return {'survived': False, 'exit': done.returncode, 'agent': str(agent),
            'tail': ' | '.join(tail)[:300]}


def main(argv=None) -> int:
    import argparse
    import json
    parser = argparse.ArgumentParser(description='Probe whether the packaged agent starts.')
    parser.add_argument('--agent', type=Path,
                        default=Path(__file__).resolve().parents[2] / 'dist/MaaLimbus/agent/MaaLimbusAgent.exe')
    parser.add_argument('--seconds', type=float, default=DEFAULT_SECONDS)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    verdict = probe(args.agent, args.seconds)
    verdict['class'] = classify(verdict)
    if args.json:
        print(json.dumps(verdict, ensure_ascii=False))
    else:
        print('agent:', verdict['agent'])
        print('survived:', verdict['survived'], 'exit:', verdict['exit'])
        print('class:', verdict['class'])
        print('tail:', verdict['tail'])
    return 0 if verdict['survived'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
