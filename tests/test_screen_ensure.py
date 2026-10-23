from maalimbus import screen_state


def test_an_awake_device_is_never_woken():
    calls = []

    def run(argv):
        calls.append(argv)
        return 'KeyguardShowing=false'

    seen = screen_state.ensure_awake(run)
    assert seen == {'locked': False, 'woken': False}
    assert len(calls) == 1, 'only the dump may be spent'


def test_a_locked_device_is_woken_and_the_success_is_reported():
    calls = []

    def run(argv):
        calls.append(argv)
        return 'KeyguardShowing=true' if argv[1] == 'dumpsys' else ''

    seen = screen_state.ensure_awake(run)
    assert seen == {'locked': True, 'woken': True}
    assert len(calls) == 1 + len(screen_state.TO_WAKE)


def test_a_failing_wake_stops_instead_of_retrying_forever():
    def run(argv):
        if argv[1] == 'dumpsys':
            return 'KeyguardShowing=true'
        raise RuntimeError('adb is gone')

    seen = screen_state.ensure_awake(run)
    assert seen == {'locked': True, 'woken': False}


def test_a_dump_that_cannot_be_read_is_reported_as_unknown_not_as_awake():
    def run(argv):
        raise OSError('no device')

    assert screen_state.ensure_awake(run) == {'locked': None, 'woken': False}
