"""Read-only Maa Windows capture. Does not send input or launch the game."""
import argparse
import json
import os
from pathlib import Path

import cv2
from maa.controller import Win32Controller
from maa.define import MaaWin32ScreencapMethodEnum, MaaWin32InputMethodEnum
from maa.library import Library
from maa.toolkit import Toolkit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', default=os.environ.get('MAAFW_BINARY_PATH'))
    parser.add_argument('--output', default='evidence/runtime/win32-probe')
    args = parser.parse_args()
    if not args.binary:
        parser.error('An explicit Maa binary path is required')
    Library.open(Path(args.binary), agent_server=False)
    candidates = [w for w in Toolkit.find_desktop_windows()
                  if w.window_name.casefold() == 'limbuscompany' and w.class_name == 'UnityWndClass']
    if len(candidates) != 1:
        raise RuntimeError(f'Expected one LimbusCompany Unity window; got {candidates!r}')
    window = candidates[0]
    controller = Win32Controller(window.hwnd, MaaWin32ScreencapMethodEnum.FramePool,
                                 MaaWin32InputMethodEnum.Seize, MaaWin32InputMethodEnum.Seize)
    assert controller.post_connection().wait().succeeded
    controller.set_screenshot_target_long_side(1920)
    assert controller.post_screencap().wait().succeeded
    frame = controller.cached_image
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    assert cv2.imwrite(str(output / 'frame.png'), frame)
    result = {'title': window.window_name, 'class': window.class_name,
              'hwnd': window.hwnd, 'size': [frame.shape[1], frame.shape[0]],
              'capture': 'FramePool', 'input_sent': False}
    (output / 'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
