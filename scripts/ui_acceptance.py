"""管理员客户端逐页签冒烟：真实服务端、真实控件树。"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from his_client.api import ApiClient
from his_client.ui.main_window import MainWindow


def main() -> int:
    app = QApplication.instance() or QApplication([])
    api = ApiClient("http://127.0.0.1:8001", "admin", "admin123", timeout=10)
    user = api.me()
    window = MainWindow(api, user)
    window.show()
    app.processEvents()
    failures = []
    for index in range(window.tabs.count()):
        window.tabs.setCurrentIndex(index)
        app.processEvents()
        name = window.tabs.tabText(index)
        try:
            widget = window.tabs.widget(index)
            if widget is None:
                raise RuntimeError("页面为空")
        except Exception as exc:  # noqa: BLE001 - 冒烟需记录所有页面异常
            failures.append((name, str(exc)))
        print(f"[{index:02d}] {name}")
    window.grab().save("docs/ui_acceptance_admin.png")
    print(f"TABS={window.tabs.count()} FAILURES={len(failures)}")
    for name, message in failures:
        print(f"FAIL {name}: {message}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
