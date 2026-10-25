import importlib.util
import pathlib

REPO = pathlib.Path(__file__).resolve().parent.parent


def _tool():
    spec = importlib.util.spec_from_file_location("run_guards", REPO / "tools" / "run_guards.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_guard_list_is_not_empty_and_holds_the_core_suites():
    names = {p.name for p in _tool().guard_files()}
    assert len(names) >= 20
    assert "test_runner.py" in names
    assert "test_pages.py" in names


def test_the_command_runs_pytest_itself_so_the_exit_code_is_pytests():
    tool = _tool()
    cmd = tool.command([REPO / "tests" / "test_pages.py"])
    assert cmd[1:3] == ["-m", "pytest"]
    assert any(part.endswith("test_pages.py") for part in cmd)


def test_a_directory_with_no_guards_is_an_empty_list(tmp_path):
    assert _tool().guard_files(tmp_path) == []


def test_listing_reports_the_count(capsys):
    assert _tool().main(["--list"]) == 0
    out = capsys.readouterr().out
    assert "guards: " in out
    assert "test_runner.py" in out


def test_asking_for_a_suite_that_is_not_a_guard_is_refused(capsys):
    assert _tool().main(["test_nope.py"]) == 2
    assert "none of the requested suites" in capsys.readouterr().out
