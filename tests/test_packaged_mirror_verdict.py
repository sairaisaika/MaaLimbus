import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('packaged_verify', Path(__file__).resolve().parents[1]/'tools/verify_packaged_mirror_loop.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_started_then_failed_is_not_a_pass():
    actual = dict(reason='Deployment successor participant count not proven', passed=False,
                  steps=[dict(passed=False)], verified_clear=False)
    verdict = module.verdict(actual, dict(task_succeeded=True), True)
    assert verdict['entry_connected'] and not verdict['passed']
    assert not verdict['dungeon_complete']


def test_bounded_progress_is_not_dungeon_completion():
    actual = dict(reason='window_steps_passed', passed=True, steps=[dict(passed=True)], verified_clear=False)
    verdict = module.verdict(actual, dict(task_succeeded=True), True)
    assert verdict['bounded_progress_verified'] and not verdict['dungeon_complete']
    assert not module.verdict(actual, dict(task_succeeded=True, timed_out=True), True)['passed']
    assert not module.verdict(None, dict(task_succeeded=True), True)['passed']
