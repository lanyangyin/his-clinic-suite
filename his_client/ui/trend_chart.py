"""轻量检验趋势折线图：不依赖 QtCharts，直接 QPainter 绘制。"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget


class TrendChart(QWidget):
    def __init__(
        self,
        labels: list[str],
        values: list[float],
        unit: str = "",
        reference_low: float | None = None,
        reference_high: float | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.labels = labels
        self.values = values
        self.unit = unit
        self.reference_low = reference_low
        self.reference_high = reference_high
        self.setMinimumHeight(180)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("#ffffff"))
        if not self.values:
            painter.setPen(QColor("#64748b"))
            painter.drawText(self.rect(), Qt.AlignCenter, "暂无可绘制的数值结果")
            return
        left, top, right, bottom = 48, 24, 24, 34
        width = max(self.width() - left - right, 1)
        height = max(self.height() - top - bottom, 1)
        low, high = min(self.values), max(self.values)
        if high == low:
            high = low + 1
        painter.setPen(QPen(QColor("#cbd5e1"), 1))
        painter.drawLine(left, top, left, top + height)
        painter.drawLine(left, top + height, left + width, top + height)

        def point(index: int, value: float):
            x = left + (width * index / max(len(self.values) - 1, 1))
            y = top + height - ((value - low) / (high - low) * height)
            return int(x), int(y)

        if self.reference_low is not None and self.reference_high is not None:
            band_low = max(min(self.reference_low, high), low)
            band_high = min(max(self.reference_high, low), high)
            if band_high > band_low:
                y_high = top + height - ((band_high - low) / (high - low) * height)
                y_low = top + height - ((band_low - low) / (high - low) * height)
                painter.fillRect(
                    left, int(y_high), width, max(int(y_low - y_high), 1),
                    QColor(34, 197, 94, 35),
                )

        painter.setPen(QPen(QColor("#2563eb"), 2))
        for index in range(1, len(self.values)):
            painter.drawLine(
                *point(index - 1, self.values[index - 1]),
                *point(index, self.values[index]),
            )
        painter.setBrush(QColor("#2563eb"))
        painter.setPen(QPen(QColor("#1d4ed8"), 1))
        for index, value in enumerate(self.values):
            x, y = point(index, value)
            painter.drawEllipse(x - 3, y - 3, 6, 6)

        painter.setPen(QColor("#334155"))
        painter.setFont(QFont("Microsoft YaHei", 8))
        painter.drawText(4, top + 8, f"{high:g}")
        painter.drawText(4, top + height, f"{low:g}")
        if self.unit:
            painter.drawText(left + width - 70, top + 12, self.unit)
        for index, label in enumerate(self.labels):
            if len(self.values) > 8 and index % 2:
                continue
            x, _ = point(index, self.values[index])
            painter.drawText(x - 24, top + height + 20, label[-5:])
