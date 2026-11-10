"""医保后台真实页面截图演示视频。

说明：医保目录/对码/进销存/工作台是后台网页，实际表单已由
scripts/e2e_insurance_admin.py 提交并截图；本脚本把真实页面截图
按慢速字幕串成演示视频，不伪造页面内容。

产出：docs/科室独立演示/10_医保后台.mp4
"""
import shutil
import subprocess
from pathlib import Path

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parent.parent
SHOT_DIR = ROOT / "docs" / "screenshots"
FRAME_DIR = ROOT / "docs" / "dept_frames" / "insurance"
VIDEO = ROOT / "docs" / "科室独立演示" / "10_医保后台.mp4"
FFMPEG = shutil.which("ffmpeg") or "ffmpeg"

SLIDES = [
    (
        "医保药品目录",
        "实际导入医保 CSV 后，目录显示药品编码、类别与匹配状态；本页执行自动对码。",
        SHOT_DIR / "insurance_catalog.png",
    ),
    (
        "医保工作台",
        "药品总数、已对码/未对码、结算金额、医保支付、自费与合规风险一目了然。",
        SHOT_DIR / "insurance_workbench.png",
    ),
    (
        "医保进销存",
        "按周期上传进销存，页面显示上传单号、笔数与状态，供医保核对。",
        SHOT_DIR / "insurance_inventory.png",
    ),
    (
        "发票号段",
        "收费后台维护发票号段：前缀、起止号、领用人、使用情况。",
        SHOT_DIR / "invoice_batches.png",
    ),
]


def render(title: str, body: str, image_path: Path | None) -> QImage:
    canvas = QImage(1600, 900, QImage.Format_RGB32)
    canvas.fill(QColor("#0f172a"))
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.Antialiasing)
    if image_path and image_path.is_file():
        image = QImage(str(image_path))
        crop = image.copy(0, 0, image.width(), min(image.height(), 700))
        scaled = crop.scaled(1600, 746, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        painter.drawImage((1600 - scaled.width()) // 2, 54, scaled)
        painter.fillRect(QRect(0, 0, 1600, 54), QColor("#0f172a"))
    painter.setPen(QColor("#f8fafc"))
    painter.setFont(QFont("Microsoft YaHei", 24, QFont.Bold))
    painter.drawText(QRect(30, 0, 1540, 54), Qt.AlignLeft | Qt.AlignVCenter, title)
    painter.fillRect(QRect(0, 800, 1600, 100), QColor(15, 23, 42, 235))
    painter.setPen(QColor("#e2e8f0"))
    painter.setFont(QFont("Microsoft YaHei", 16))
    painter.drawText(QRect(40, 812, 1520, 76), Qt.AlignLeft | Qt.AlignVCenter | Qt.TextWordWrap, body)
    painter.end()
    return canvas


def main() -> int:
    app = QApplication([])
    FRAME_DIR.mkdir(parents=True, exist_ok=True)
    for old in FRAME_DIR.glob("*.jpg"):
        old.unlink()
    index = 0
    sequence: list[tuple[str, str, Path | None, float]] = [
        ("医保 / 收费后台", "真实后台页面演示：目录导入、对码、进销存、工作台、发票号段。", None, 3.5),
    ]
    sequence += [(title, body, img, 4.0) for title, body, img in SLIDES]
    sequence.append(("演示完成", "以上页面均由真实后台表单提交后截图，非静态伪造页面。", None, 3.5))
    for title, body, image, seconds in sequence:
        image_obj = render(title, body, image)
        count = int(seconds * 5)
        for _ in range(count):
            index += 1
            image_obj.save(str(FRAME_DIR / f"frame_{index:04d}.jpg"), "JPEG", 90)
    VIDEO.parent.mkdir(parents=True, exist_ok=True)
    VIDEO.unlink(missing_ok=True)
    subprocess.run(
        [
            FFMPEG, "-y", "-framerate", "5", "-i", str(FRAME_DIR / "frame_%04d.jpg"),
            "-vf", "scale=1600:900", "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-r", "30", str(VIDEO),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True,
    )
    print(f"录像：{VIDEO}（{index} 帧）")
    app.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
