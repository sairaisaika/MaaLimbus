"""Finite public Maa job polling; wall-clock changes cannot extend input sessions."""
import time


def wait_job(job, *, timeout=10, deadline=None, clock=time.monotonic, sleep=time.sleep):
    end = clock() + timeout
    if deadline is not None:
        end = min(end, deadline)
    while not job.done:
        remaining = end - clock()
        if remaining <= 0:
            raise TimeoutError('Maa job exceeded its deadline')
        sleep(min(.05, remaining))
    if not job.succeeded:
        raise RuntimeError('Maa job failed')
    return job



def call_with_a_deadline(call, *, timeout, clock=time.monotonic):
    """Run one native call on a daemon thread and abandon it at the deadline.

    A MaaFW request that is never answered cannot be interrupted from Python: live
    `packaged-mirror-20261024-032301` logged `unexpected msg [... controller_id=""]` for an
    input request and then returned nothing for the remaining 740 s of the run, with the
    interpreter blocked inside `controller.post_click`.  Polling `job.done` does not help
    when the block happens *before* a job exists, so the call itself gets a thread and a
    deadline.  The thread is a daemon: an abandoned call cannot keep the process alive, and
    the caller is told it was abandoned instead of waiting for an answer that may never
    come.

    Returns `{'answered': bool, 'value': ..., 'error': Exception|None}`; an abandoned call
    has `answered=False`, and an exception raised by the call is returned rather than
    propagated so the caller can classify it (a refusal is not a crash).
    """
    import threading
    box = {'answered': False, 'value': None, 'error': None}

    def run():
        try:
            box['value'] = call()
        except BaseException as error:            # noqa: BLE001 - reported, not swallowed
            box['error'] = error
        finally:
            box['answered'] = True

    worker = threading.Thread(target=run, name='maalimbus-call', daemon=True)
    worker.start()
    worker.join(max(0.0, float(timeout)))
    return box

def wait_task(tasker, job, *, deadline, clock=time.monotonic, sleep=time.sleep):
    timed_out = interrupted = False
    stop_error = None
    stop_confirmed = False
    try:
        while not job.done:
            remaining = deadline - clock()
            if remaining <= 0:
                timed_out = True
                break
            sleep(min(.2, remaining))
    except KeyboardInterrupt:
        interrupted = True
    finally:
        if job.done:
            stop_confirmed = True
        else:
            try:
                wait_job(tasker.post_stop(), timeout=5, clock=clock, sleep=sleep)
                stop_confirmed = job.done
            except (TimeoutError, RuntimeError, AttributeError) as error:
                # AttributeError: the stop handle itself was unusable (`None` or a
                # dead object).  Same verdict -- an unconfirmed stop -- not a crash.
                stop_error = str(error) or type(error).__name__
    # A live run crashed (0xC0000409) right after `wait_job` raised
    # `Maa job exceeded its deadline`, and the crash was in the controller's reverse
    # request path -- i.e. the native task was still alive when the Python side moved
    # on.  Name that state instead of returning a dict that looks like a clean finish:
    # `completed` / `stopped` / `the_controller_did_not_confirm_the_stop`.
    if stop_confirmed:
        verdict = 'completed' if job.succeeded else 'stopped'
    else:
        verdict = 'the_controller_did_not_confirm_the_stop'
    return {'task_succeeded': job.succeeded, 'timed_out': timed_out,
            'interrupted': interrupted, 'stop_confirmed': stop_confirmed,
            'stop_error': stop_error, 'verified_clear': False, 'verdict': verdict}


class ScreenshotNeverReturned(TimeoutError):
    """A screencap did not come back inside its deadline.

    Raised instead of a bare ``TimeoutError`` so the caller can tell "the picture was
    slow" from "the controller is wedged", and so the pending request is drained
    before anything else uses the same controller.
    """


def screencap(controller, *, timeout=5, drain=2, clock=time.monotonic, sleep=time.sleep):
    """Ask for one screen, and never leave a pending capture behind.

    Seven sites in the agent called ``wait_job(post_screencap(), timeout=5)`` directly;
    a timeout there left the capture pending while the loop went on to click, which is
    the same "use a request that is still in flight" shape as the 0xC0000409 crash.
    """
    job = controller.post_screencap()
    try:
        return wait_job(job, timeout=timeout, clock=clock, sleep=sleep)
    except TimeoutError as error:
        try:
            wait_job(controller.post_stop(), timeout=drain, clock=clock, sleep=sleep)
        except (TimeoutError, RuntimeError, AttributeError):
            pass
        raise ScreenshotNeverReturned(str(error) or 'the screenshot never returned') from error


class InputNeverReturned(TimeoutError):
    """A click/swipe did not come back inside its deadline.

    ``drained`` says whether the pending request was cancelled.  ``lost`` says the
    screen stopped answering after that drain, which means the controller itself is
    gone: a click sent now is posted with an empty ``controller_id`` and the
    framework rejects it (live: ``controller not found [controller_id=]``), while the
    agent side waits for a request that will never be handled.
    """

    def __init__(self, message, *, drained=True, lost=False):
        super().__init__(message)
        self.drained = drained
        self.lost = lost
    """A click/swipe/launch did not come back inside its deadline.

    The live runs died with 0xC0000409 right after `Maa job exceeded its deadline`,
    and the click path at `src/maalimbus/runner.py:1617` used a bare
    ``wait_job(controller.post_click(...), timeout=10)``: a click that timed out was
    left pending while the loop went on to the next capture.  This wrapper drains the
    pending request and names the state, so the run can stop cleanly instead of
    touching a request that is still in flight.
    """


SOFT_INPUT_REASON = 'the_click_outlived_its_deadline_but_the_screen_still_answers'


class InputLost(RuntimeError):
    """The controller went away under a click, so the run must stop, not retry.

    Sent as a ``RuntimeError`` because that is the shape the loop already ends on;
    ``reason`` carries the name the journal should record.
    """

    reason = 'the_controller_was_lost_before_the_next_input'


EMPTY_CONTROLLER_REASON = 'the_controller_id_is_empty_so_no_input_can_be_routed'


def controller_ready(controller) -> dict:
    """Can this controller route an input right now, and if not, why not.

    Negative case (measured live 2026-10-23, run
    `evidence/runtime/packaged-mirror-20261023-160749`): MaaFW rejected a click with
    `controller not found [req.controller_id=]` while the loop believed it had a
    controller -- the request went out with an empty id and nothing on the Python side
    noticed.  An empty id is not a slow call; it is a request that cannot be routed.
    """
    ident = getattr(controller, 'controller_id', None)
    if ident is None:
        getter = getattr(controller, 'get_controller_id', None)
        if callable(getter):
            try:
                ident = getter()
            except (RuntimeError, OSError, ValueError):
                ident = None
    if ident is None:
        # Unknown is not empty: a controller that does not expose an id cannot be
        # proven unroutable, and refusing every such object would turn a missing
        # attribute into a dead click.  Only a *readable* empty id is refused.
        return {'ready': True, 'reason': 'the_controller_id_is_not_exposed',
                'controller_id': ''}
    text = str(ident).strip()
    if not text:
        return {'ready': False, 'reason': EMPTY_CONTROLLER_REASON, 'controller_id': text}
    return {'ready': True, 'reason': 'the_controller_id_is_present', 'controller_id': text}


def dispatch(controller, job, *, timeout, deadline=None, drain=2, probe=None, on_soft=None,
             clock=time.monotonic, sleep=time.sleep):
    """Wait for one device action; never leave it pending on timeout.

    A click that opens a long transition (dungeon resume, floor load) legitimately
    outlives a 10 s job deadline: the job's completion is not the game's completion.
    When a ``probe`` is supplied and still sees a live screen after the drain, the
    click is treated as delivered and ``on_soft`` is told why; without a probe, or
    with a probe that also fails, the state is ``InputNeverReturned``.
    """

    # An empty id cannot be routed by MaaFW: it answers `controller not found
    # [req.controller_id=]` and the caller would read that as a slow click
    # (measured 2026-10-23, run `packaged-mirror-20261023-160749`).
    verdict = controller_ready(controller)
    if not verdict['ready']:
        raise InputLost(verdict['reason'])
    try:
        return wait_job(job, timeout=timeout, deadline=deadline, clock=clock, sleep=sleep)
    except TimeoutError as error:
        drained = True
        try:
            wait_job(controller.post_stop(), timeout=drain, clock=clock, sleep=sleep)
        except (TimeoutError, RuntimeError, AttributeError):
            drained = False
        lost = False
        if probe is not None:
            try:
                alive = bool(probe())
            except Exception:
                alive = False
            if not alive:
                # The controller is gone, not merely slow: any further click would be
                # posted with an empty id and hang the agent side.
                lost = True
            if alive:
                if on_soft is not None:
                    on_soft(SOFT_INPUT_REASON)
                return job
        if lost:
            raise InputLost(str(error) or 'the input never returned') from error
        raise InputNeverReturned(str(error) or 'the input never returned',
                                 drained=drained, lost=lost) from error


def stop_tasker(tasker, *, timeout=8, clock=time.monotonic, sleep=time.sleep):
    """Ask the tasker to stop and report whether it confirmed -- never raise.

    Evidence: `tools/verify_packaged_mirror_loop.py:208` called
    ``wait_job(tasker.post_stop(), timeout=8)`` bare.  When the stop did not confirm
    the TimeoutError unwound *inside* the native teardown and the process died with
    0xC0000409 -- every long run "crashed" at exactly its budget, because the crash
    was in the reporting path, not in the run.  A teardown must record, not throw.
    """
    try:
        wait_job(tasker.post_stop(), timeout=timeout, clock=clock, sleep=sleep)
        return True
    except (TimeoutError, RuntimeError, AttributeError):
        return False


def bounded_limit(limit, deadline, clock=time.monotonic):
    """Clamp a watchdog window to what is left of the run's own budget.

    One live run was given 450 s and took 1058 s: a single step blocked for 905 s and
    only the 900 s no-progress watch noticed (``evidence/runtime/
    packaged-mirror-20261023-124006``, gap ``window_intent -> window_no_progress``).
    A watchdog may never be longer than the budget it is supposed to protect.
    """
    if deadline is None or limit is None:
        return limit
    left = deadline - clock()
    return max(1.0, min(float(limit), float(left)))
