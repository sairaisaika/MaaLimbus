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
    """A click/swipe/launch did not come back inside its deadline.

    The live runs died with 0xC0000409 right after `Maa job exceeded its deadline`,
    and the click path at `src/maalimbus/runner.py:1617` used a bare
    ``wait_job(controller.post_click(...), timeout=10)``: a click that timed out was
    left pending while the loop went on to the next capture.  This wrapper drains the
    pending request and names the state, so the run can stop cleanly instead of
    touching a request that is still in flight.
    """


def dispatch(controller, job, *, timeout, deadline=None, drain=2,
             clock=time.monotonic, sleep=time.sleep):
    """Wait for one device action; never leave it pending on timeout."""
    try:
        return wait_job(job, timeout=timeout, deadline=deadline, clock=clock, sleep=sleep)
    except TimeoutError as error:
        try:
            wait_job(controller.post_stop(), timeout=drain, clock=clock, sleep=sleep)
        except (TimeoutError, RuntimeError, AttributeError):
            pass
        raise InputNeverReturned(str(error) or 'the input never returned') from error
