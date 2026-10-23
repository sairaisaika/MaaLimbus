import os
import subprocess
import sys
from pathlib import Path
import pytest
from maalimbus.controller_lease import ControllerLease, LeaseUnavailable, lease_path


def test_a_refused_lease_is_an_os_error():
    """The installer's refusal contract is `OSError`, and it must stay that way.

    `LeaseUnavailable` was introduced as a `RuntimeError` (`2ee48ba`, 2026-10-23 12:00)
    while only its *name* was being improved. That stopped
    `tests/test_update_install.py::test_real_controller_lock_blocks_installation` from
    matching -- its contract is `pytest.raises(OSError)` -- so the install gate was
    effectively unguarded. A refusal by the operating system is an `OSError`.
    """
    assert issubclass(LeaseUnavailable, OSError)


def test_only_the_production_name_is_mapped_to_the_machine_wide_lease(tmp_path):
    """The mapping is a feature, and also the way a test can take the real lock.

    `lease_path` sends any file *named* `controller.lock` to
    `%LOCALAPPDATA%/MaaLimbus/controller.lock` so a source CLI and an installed Agent
    share one lock system-wide. The consequence is that a test which grabs a tmp
    `controller.lock` takes the production lease and fails whenever a real agent owns
    the controller (measured 2026-10-23). Both halves are asserted here.
    """
    mapped = lease_path(tmp_path/'controller.lock')
    assert mapped.name == 'controller.lock'
    assert mapped.parent != tmp_path.resolve()
    assert lease_path(tmp_path/'exclusive.lock') == (tmp_path/'exclusive.lock').resolve()


@pytest.mark.skipif(sys.platform!='win32',reason='Windows OS file lock')
def test_cli_and_agent_cannot_acquire_another_process_controller(tmp_path):
    # Named so it stays in tmp_path: taking the machine-wide lease here would make the
    # suite fail whenever a real agent owns the controller.
    path=tmp_path/'exclusive.lock'
    lease=ControllerLease.acquire(path)
    assert ControllerLease.acquire(path) is lease
    code='from maalimbus.controller_lease import ControllerLease; import sys; ControllerLease.acquire(sys.argv[1])'
    env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parents[1]/'src')}
    blocked=subprocess.run([sys.executable,'-c',code,str(path)],env=env,capture_output=True,timeout=10)
    assert blocked.returncode!=0
    lease.close()
    success=subprocess.run([sys.executable,'-c',code,str(path)],env=env,capture_output=True,timeout=10)
    assert success.returncode==0
