"""识别帧的坐标，和 controller 要的坐标，不是同一个空间。

实测（D368）：设备截图 1280×720、识别帧 1920×1080（`set_screenshot_target_long_side(1920)`
把画面放大给识别用），而 `post_click` 的坐标是按**设备**算的。脚本把识别帧坐标原样发出去，
于是每次点击都偏 1.5 倍——八次点击一次都没推动局面（`map_attempts=9 / map_tries=8`）。

这一层只做一件事：把一个「识别帧里的点」换成「controller 要的点」。
"""
from __future__ import annotations


def scale_point(point, frame_size, screen_size):
    """把识别帧坐标换算到设备坐标。

    ``frame_size`` 是识别看到的画面尺寸（如 1920×1080），``screen_size`` 是设备真实分辨率
    （如 1280×720）。任一缺失、非正数或两端相等时原样返回——**不知道就不动**，
    这比按错的比值缩放安全。
    """
    try:
        x, y = float(point[0]), float(point[1])
        fw, fh = float(frame_size[0]), float(frame_size[1])
        sw, sh = float(screen_size[0]), float(screen_size[1])
    except (TypeError, IndexError, ValueError):
        return point
    if not (fw > 0 and fh > 0 and sw > 0 and sh > 0):
        return point
    if (fw, fh) == (sw, sh):
        return point
    return [int(round(x * sw / fw)), int(round(y * sh / fh))]


def scale_box(box, frame_size, screen_size):
    """把一个框（x, y, w, h）换算到设备坐标。"""
    try:
        left, top, width, height = float(box[0]), float(box[1]), float(box[2]), float(box[3])
    except (TypeError, IndexError, ValueError):
        return box
    corner = scale_point([left, top], frame_size, screen_size)
    far = scale_point([left + width, top + height], frame_size, screen_size)
    return [corner[0], corner[1], far[0] - corner[0], far[1] - corner[1]]
