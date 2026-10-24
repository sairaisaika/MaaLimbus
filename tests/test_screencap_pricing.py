"""The read half of a binding is priceable, and capture is not the missing second.

D68 measured the observation node at 1.08-1.44 s per read and D66's gaps put a read at
2.45 s, so roughly a second sat outside the node. The obvious candidate was device
capture, and it was never priced -- only assumed.

`tools/measure_screencap.py` prices it: on MuMu 12 the binding offers exactly one method
(`EmulatorExtras`) and one capture costs a median 0.051 s. So the missing second is not
the capture, and the read half needs no method preference on this device; what it needed
was to be measured instead of named.

The other half of this file is the symmetry: `pin_input` existed and `pin_screencap` did
not, so a future A/B of methods would have had to build a controller by hand.
"""
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from maalimbus import adb_device


def _record(methods=64, input_methods=8):
    return {'source': 'maa_toolkit_discovery', 'address': '127.0.0.1:16416',
            'adb_path': 'adb', 'config': {}, 'screencap_methods': methods,
            'input_methods': input_methods,
            'screencap_names': adb_device.names(methods, adb_device.SCREENCAP_NAMES),
            'input_names': adb_device.names(input_methods, adb_device.INPUT_NAMES)}


def test_pinning_a_capture_method_narrows_the_binding():
    pinned = adb_device.pin_screencap(_record(64 | 2), 'Encode')
    assert pinned['screencap_methods'] == 2
    assert pinned['screencap_names'] == ['Encode']
    assert pinned['pinned_screencap'] == 'Encode'
    assert pinned['input_methods'] == 8, 'pinning a read must not touch the input half'


def test_the_record_that_was_handed_in_is_not_mutated():
    record = _record(64 | 2)
    adb_device.pin_screencap(record, 'Encode')
    assert record['screencap_methods'] == 64 | 2
    assert 'pinned_screencap' not in record


def test_a_method_the_binding_does_not_offer_is_refused():
    with pytest.raises(ValueError, match='does not offer'):
        adb_device.pin_screencap(_record(64), 'Encode')


def test_a_method_this_framework_does_not_name_is_refused():
    with pytest.raises(ValueError, match='Unknown ADB screencap method'):
        adb_device.pin_screencap(_record(64), 'Nope')


def test_the_input_half_still_pins_the_way_it_did():
    pinned = adb_device.pin_input(_record(input_methods=8), 'EmulatorExtras')
    assert pinned['input_methods'] == 8 and pinned['pinned'] == 'EmulatorExtras'


def test_the_priced_methods_are_the_ones_maa_names():
    # The table is the only place a name and a bit are tied together; a new method in
    # the framework must arrive here as a name, not as a bare bitmask bit.
    assert adb_device.SCREENCAP_NAMES == {1: 'EncodeToFileAndPull', 2: 'Encode',
                                         4: 'RawWithGzip', 8: 'RawByNetcat',
                                         16: 'MinicapDirect', 32: 'MinicapStream',
                                         64: 'EmulatorExtras'}
    assert adb_device.names(1 | 32, adb_device.SCREENCAP_NAMES) == ['EncodeToFileAndPull',
                                                                    'MinicapStream']


def test_the_tool_prices_every_offered_method_without_sending_input():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        'measure_screencap', ROOT / 'tools' / 'measure_screencap.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    priced = []

    def fake_price(record, bit, *, count, timeout):
        priced.append(adb_device.SCREENCAP_NAMES[bit])
        # A method that never returned must not be reported as 0 s.
        return [0.05, 0.06] if bit != 4 else [None, None]

    module.price = fake_price
    rows = module.survey(_record(64 | 4), count=2)
    assert [row['method'] for row in rows] == ['RawWithGzip', 'EmulatorExtras']
    assert [row['median'] for row in rows] == [None, 0.055]
    assert module.fastest(rows)['method'] == 'EmulatorExtras'
    assert priced == ['RawWithGzip', 'EmulatorExtras']


def test_a_survey_of_failures_reports_that_nothing_was_measured():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        'measure_screencap', ROOT / 'tools' / 'measure_screencap.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.price = lambda record, bit, *, count, timeout: [None]
    rows = module.survey(_record(64), count=1)
    assert module.fastest(rows) is None
