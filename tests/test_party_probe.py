"""The same frame read in the loop's own process answers "is this a release gap?" (D286)."""
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from maalimbus import runner  # noqa: E402

FRAME_DIR = ROOT / 'evidence/runtime/packaged-mirror-20261025-083447'


@pytest.mark.skipif(not (FRAME_DIR / 'frame-0001.png').exists(),
                    reason='retained live frame is not present')
def test_the_frame_the_agent_could_not_read_reads_here():
    probe = runner.party_probe(FRAME_DIR, {})
    assert probe['read'] is True, probe
    assert probe['point'] == [1012, 595]
    assert probe['size'] == [1920, 1080] and probe['channels'] == 3


def test_a_missing_frame_is_reported_instead_of_raised():
    probe = runner.party_probe(ROOT / 'evidence/runtime/does-not-exist', {})
    assert probe['read'] is False
    assert str(probe['reason']).startswith('probe_failed')


def test_the_probe_result_is_written_where_it_is_used():
    """D287 replaced "write the probe" with "use the probe", so the event moved too."""
    source = (ROOT / 'src' / 'maalimbus' / 'runner.py').read_text(encoding='utf-8')
    assert "note('map_party_from_probe'" in source
    assert "note('map_party_unread'" in source
    assert source.index('probe = party_probe(directory, record)')         < source.index('frame, candidates = candidates_of(directory, record')
