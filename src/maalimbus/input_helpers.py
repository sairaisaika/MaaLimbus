"""Whether the ADB input helpers MaaFramework pushes to the device are present.

MaaFramework's `Maatouch` and `MinitouchAndAdbKey` input units push a helper
binary to the device. The packaged application points the control unit at
`<app>/maafw/MaaAgentBinary`; when that directory is missing, every candidate
except `AdbShell` fails to initialize and MaaFramework silently falls back to
`adb shell input tap`.

That fallback is what makes this module worth having. `AdbShellInput::click`
reports success and the controller logs `Controller.Action.Succeeded`, so a run
looks healthy in the Maa log while the game ignores the tap: the planner sees the
page it just clicked stay exactly the same and stops with `unexpected_successor`.
Live proof (2026-10-12): the packaged application's `debug/maafw.log` recorded
`[x=125] [y=527]` for the DUNGEON_TEAM slot click and `Controller.Action.Succeeded`
while the page never moved, and a source run of the same plan with the helper
binaries available used `MaatouchInput` and walked six pages in a row.

Nothing here sends input; it only reports and explains the posture so a silent
fallback becomes a named line in the run's own log.
"""
from pathlib import Path

#: the framework directory the application ships next to its executables
FRAMEWORK_DIRECTORY = 'maafw'
#: the helper directory MaaFramework reads when `agent_path` names it
BINARY_DIRECTORY = 'MaaAgentBinary'
#: fingerprint of a packaged layout: a source checkout has no framework of its own
FRAMEWORK_LIBRARY = 'MaaFramework.dll'
#: the helpers, as (name, relative path inside the binary directory)
MAATOUCH = ('maatouch', 'maatouch/universal/maatouch')
MINITOUCH = ('minitouch', 'minitouch/x86_64/minitouch')
MINITOUCH_ARM = ('minitouch-arm64', 'minitouch/arm64-v8a/minitouch')


def framework_directory(root):
    return Path(root) / FRAMEWORK_DIRECTORY


def helper_directory(root):
    return framework_directory(root) / BINARY_DIRECTORY


def packaged(root):
    """True when `root` ships its own MaaFramework (an installed application)."""
    return (framework_directory(root) / FRAMEWORK_LIBRARY).is_file()


def report(root):
    """The input-helper posture of one application root, as plain data."""
    directory = helper_directory(root)
    helpers = {}
    for name, relative in (MAATOUCH, MINITOUCH, MINITOUCH_ARM):
        helpers[name] = (directory / relative).is_file()
    return {'root': str(Path(root)), 'packaged': packaged(root),
            'directory': str(directory), 'present': directory.is_dir(),
            'helpers': helpers,
            'maatouch': helpers[MAATOUCH[0]],
            'minitouch': helpers[MINITOUCH[0]] or helpers[MINITOUCH_ARM[0]]}


def usable(report_value):
    return bool(report_value.get('maatouch') or report_value.get('minitouch'))


def warning(report_value):
    """A sentence for the run log, or None when nothing needs saying.

    A source checkout is silent: its framework resolves the helpers from the
    installed MaaFw wheel, so an absent directory is normal there. Only a packaged
    application that cannot offer an agent-based input unit is a fault, because its
    clicks will be delivered by `adb shell input tap` and ignored.
    """
    if not report_value.get('packaged') or usable(report_value):
        return None
    return ('input helpers missing: ' + report_value['directory'] + ' holds no '
            'maatouch/minitouch binary, so every ADB input unit except AdbShell fails '
            'and clicks fall back to "adb shell input tap" — the controller reports '
            'success while the game ignores the tap, and the run stops on the first '
            'page that does not move. Repair the installation (the packaging step must '
            'copy MaaAgentBinary next to MaaFramework.dll).')


def line(report_value):
    """One short status line for a human-readable run log."""
    if not report_value.get('packaged'):
        return 'input helpers: source layout, MaaFw resolves them'
    if usable(report_value):
        named = [name for name, value in sorted(report_value['helpers'].items()) if value]
        return 'input helpers: ok (' + ', '.join(named) + ')'
    return 'input helpers: MISSING in ' + report_value['directory']
