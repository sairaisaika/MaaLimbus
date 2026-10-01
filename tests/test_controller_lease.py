import os
import subprocess
import sys
from pathlib import Path
import pytest
from maalimbus.controller_lease import ControllerLease


@pytest.mark.skipif(sys.platform!='win32',reason='Windows OS file lock')
def test_cli_and_agent_cannot_acquire_another_process_controller(tmp_path):
    path=tmp_path/'controller.lock'
    lease=ControllerLease.acquire(path)
    assert ControllerLease.acquire(path) is lease
    code='from maalimbus.controller_lease import ControllerLease; import sys; ControllerLease.acquire(sys.argv[1])'
    env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parents[1]/'src')}
    blocked=subprocess.run([sys.executable,'-c',code,str(path)],env=env,capture_output=True,timeout=10)
    assert blocked.returncode!=0
    lease.close()
    success=subprocess.run([sys.executable,'-c',code,str(path)],env=env,capture_output=True,timeout=10)
    assert success.returncode==0
