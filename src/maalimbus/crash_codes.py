"""A process that dies natively is a named end, not a missing one.

Evidence: `evidence/runtime/packaged-mirror-20261023-110815` ends on a
`window_intent` for ``RESUME_DIALOG`` and the process left with
``0xC0000409`` (``3221226505``).  ``selfrun_mirror`` recorded ``stop: null``,
so the run entered the metrics as "ended without a stop" and the cause
disappeared into the same bucket as an operator kill.
"""

# Windows NTSTATUS values as the harness observes them in an exit code.
CRASH_CODES = {
    3221226505: 'the_controller_crashed_inside_a_click',   # 0xC0000409 fail-fast
    3221225477: 'the_process_crashed_with_an_access_violation',  # 0xC0000005
    3221225725: 'the_process_ran_out_of_stack',            # 0xC00000FD
    3221225786: 'the_process_was_killed_by_the_console',   # 0xC000013A
}


def name_for(exit_code):
    """Return the recorded reason for a native exit code, or ``None``.

    ``None`` means "not a native crash": the caller must not invent a cause
    for an ordinary timeout, a requested end, or an unknown non-zero code.
    """
    try:
        code = int(exit_code)
    except (TypeError, ValueError):
        return None
    if code < 0:  # a Python-side negative wraps the same NTSTATUS values
        code += 2 ** 32
    return CRASH_CODES.get(code)
