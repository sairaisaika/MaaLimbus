"""Use the same public Win32 profiles in PI and the native runner."""
import json
from pathlib import Path


DEFAULT_CONTROLLER = 'windows-window'


def controller_profile(interface_path: Path, name: str):
    interface = json.loads(interface_path.read_text(encoding='utf-8'))
    matches = [c for c in interface['controller'] if c['name'] == name and c['type'] == 'Win32']
    if len(matches) != 1:
        raise ValueError(f'Unknown Windows controller: {name}')
    return matches[0]


def native_methods(profile):
    from maa.define import MaaWin32ScreencapMethodEnum, MaaWin32InputMethodEnum
    settings = profile['win32']
    return (MaaWin32ScreencapMethodEnum[settings['screencap']],
            MaaWin32InputMethodEnum[settings['mouse']],
            MaaWin32InputMethodEnum[settings['keyboard']])
