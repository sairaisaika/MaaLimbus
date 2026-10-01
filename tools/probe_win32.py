"""Read-only Maa Windows capture. Does not send input or launch the game."""
import argparse
import json
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

import cv2
from maa.controller import Win32Controller
from maa.define import MaaWin32ScreencapMethodEnum, MaaWin32InputMethodEnum
from maa.library import Library
from maa.toolkit import Toolkit
from maalimbus.jobs import wait_job
from maalimbus.windows_preflight import process_identity
from maalimbus.controller_lease import ControllerLease


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', default=os.environ.get('MAAFW_BINARY_PATH'))
    parser.add_argument('--output', default='evidence/runtime/win32-probe')
    parser.add_argument('--title', default='LimbusCompany', help='Exact title for read-only capture')
    parser.add_argument('--capture', choices=['Background', 'FramePool', 'ScreenDC', 'GDI'], default='Background')
    args = parser.parse_args()
    if not args.binary:
        parser.error('An explicit Maa binary path is required')
    Library.open(Path(args.binary), agent_server=False)
    lease = ControllerLease.acquire(Path(__file__).resolve().parents[1] / 'build/controller.lock')
    candidates = [w for w in Toolkit.find_desktop_windows()
                  if w.window_name.casefold() == args.title.casefold()]
    if len(candidates) != 1:
        raise RuntimeError(f'Expected one exact-title window; got {candidates!r}')
    window = candidates[0]
    controller = Win32Controller(window.hwnd, MaaWin32ScreencapMethodEnum[args.capture],
                                 MaaWin32InputMethodEnum.Null, MaaWin32InputMethodEnum.Null)
    wait_job(controller.post_connection(), timeout=10)
    controller.set_screenshot_target_long_side(1920)
    wait_job(controller.post_screencap(), timeout=10)
    frame = controller.cached_image
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    assert cv2.imwrite(str(output / 'frame.png'), frame)
    result = {'title': window.window_name, 'class': window.class_name,
              'hwnd': window.hwnd, 'size': [frame.shape[1], frame.shape[0]],
              'capture': args.capture, 'input_methods': ['Null', 'Null'], 'input_sent': False,
              'controller_identity': process_identity(os.getpid())}
    (output / 'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result))
    lease.close()


if __name__ == '__main__':
    main()
