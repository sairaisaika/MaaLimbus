"""The adb channel builds one command and reports whether it was delivered."""

import pytest

from maalimbus import adb_input


class Finished:
    def __init__(self, code):
        self.returncode = code
        self.stdout = ''
        self.stderr = ''


def test_a_tap_is_one_named_command():
    argv = adb_input.tap_command('127.0.0.1:16416', 937, 601, adb='adb')
    assert argv == ['adb', '-s', '127.0.0.1:16416', 'shell', 'input', 'tap', '937', '601']


def test_a_missing_serial_is_refused_not_guessed():
    with pytest.raises(ValueError):
        adb_input.tap_command('', 1, 2)


def test_coordinates_are_whole_numbers():
    argv = adb_input.tap_command('s', 937.7, 601.2, adb='adb')
    assert argv[-2:] == ['937', '601']


def test_a_zero_exit_is_delivered():
    calls = []

    def run(argv, **kwargs):
        calls.append(argv)
        return Finished(0)

    verdict = adb_input.tap('s', 1, 2, adb='adb', run=run)
    assert verdict['delivered'] is True
    assert len(calls) == 1, 'exactly one command per tap'


def test_a_non_zero_exit_is_not_delivered():
    verdict = adb_input.tap('s', 1, 2, adb='adb', run=lambda *a, **k: Finished(1))
    assert verdict['delivered'] is False
