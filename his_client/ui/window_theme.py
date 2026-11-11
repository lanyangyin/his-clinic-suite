"""Windows 原生标题栏浅色化（Qt 样式管不到非客户区）。"""
import ctypes
import sys


def apply_light_titlebar(widget) -> None:
    if sys.platform != "win32":
        return
    try:
        hwnd = int(widget.winId())
    except (TypeError, ValueError):
        return
    try:
        dwm = ctypes.windll.dwmapi
        # 0 = 浅色标题栏；旧版 Windows 10 用 19，新版用 20
        value = ctypes.c_int(0)
        for attribute in (20, 19):
            result = dwm.DwmSetWindowAttribute(
                hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value)
            )
            if result == 0:
                break
        # Windows 11：标题栏底色 / 文字 / 边框
        # COLORREF = 0x00BBGGRR
        colors = {
            35: 0x00FDF8F4,  # #F4F8FD 浅蓝白
            36: 0x003B291E,  # #1E293B 深蓝灰文字
            34: 0x00F3E7DB,  # #DBE7F3 边框
        }
        for attribute, color in colors.items():
            c = ctypes.c_int(color)
            dwm.DwmSetWindowAttribute(hwnd, attribute, ctypes.byref(c), ctypes.sizeof(c))
    except (AttributeError, OSError):
        return
