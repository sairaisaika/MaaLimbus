import pytest
from maalimbus.windows_preflight import validate_identity,InputPermissionError


def test_permission_mismatch_rejected_with_read_only_identity():
    game=dict(pid=1,executable=r'E:\Steam\LimbusCompany.exe',integrity_rid=0x3000)
    own=dict(pid=2,executable=r'C:\python.exe',integrity_rid=0x2000)
    with pytest.raises(InputPermissionError) as found: validate_identity(game,own)
    assert found.value.identity['input_allowed'] is False
    assert validate_identity(game,{**own,'integrity_rid':0x3000})['input_allowed']


def test_mismatched_process_name_cannot_authorize_input():
    with pytest.raises(RuntimeError):
        validate_identity(dict(executable='unrelated.exe',integrity_rid=0x2000),dict(integrity_rid=0x3000))
