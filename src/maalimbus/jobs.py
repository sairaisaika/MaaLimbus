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
            except (TimeoutError, RuntimeError) as error:
                stop_error = str(error)
    return {'task_succeeded': job.succeeded, 'timed_out': timed_out,
            'interrupted': interrupted, 'stop_confirmed': stop_confirmed,
            'stop_error': stop_error, 'verified_clear': False}
