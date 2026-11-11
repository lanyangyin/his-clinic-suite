"""Windows 原生标题栏浅色化（Qt 样式管不到非客户区）。"""
import ctypes
import sys

from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QDialog, QMainWindow

from his_client.ui.theme import is_dark


def apply_light_titlebar(widget) -> None:
    if sys.platform != "win32":
        return
    try:
        hwnd = int(widget.winId())
    except (TypeError, ValueError):
        return
    try:
        dwm = ctypes.windll.dwmapi
        dark = is_dark()
        # 0 = 浅色标题栏，1 = 深色；旧版 Windows 10 用 19，新版用 20
        value = ctypes.c_int(1 if dark else 0)
        for attribute in (20, 19):
            result = dwm.DwmSetWindowAttribute(
                hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value)
            )
            if result == 0:
                break
        # Windows 11：标题栏底色 / 文字 / 边框
        # COLORREF = 0x00BBGGRR
        colors = (
            {
                35: 0x001A170F,  # #0F172A
                36: 0x00F0E8E2,  # #E2E8F0
                34: 0x00554133,  # #334155
            }
            if dark
            else {
                35: 0x00FDF8F4,  # #F4F8FD
                36: 0x003B291E,  # #1E293B
                34: 0x00F3E7DB,  # #DBE7F3
            }
        )
        for attribute, color in colors.items():
            c = ctypes.c_int(color)
            dwm.DwmSetWindowAttribute(hwnd, attribute, ctypes.byref(c), ctypes.sizeof(c))
    except (AttributeError, OSError):
        return


class _LightTitleBarFilter(QObject):
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Show and isinstance(obj, (QMainWindow, QDialog)):
            apply_light_titlebar(obj)
        return False


def install_light_titlebars(app) -> None:
    """应用级：所有后续弹出的 QDialog/QMainWindow 都用浅色标题栏。"""
    if sys.platform != "win32":
        return
    if getattr(app, "_light_titlebar_filter", None) is None:
        app._light_titlebar_filter = _LightTitleBarFilter(app)
        app.installEventFilter(app._light_titlebar_filter)
