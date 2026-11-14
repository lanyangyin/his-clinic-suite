"""出生日期 ↔ 年龄（年月日）↔ 身份证号 联动控件。

原则：
- 出生日期是权威值，年龄由出生日期计算；
- 输入年龄时反推出生日期，并明确提示这是近似值；
- 年龄不详独立勾选，绝不默认成 1 岁。
"""
from __future__ import annotations

import calendar
from datetime import date, timedelta

from PySide6.QtCore import QDate, Signal
from his_client.ui.theme import colors, register_theme_listener
from PySide6.QtWidgets import (
    QCheckBox,
    QDateEdit,
    QGridLayout,
    QLabel,
    QSpinBox,
    QWidget,
)

_ID_WEIGHTS = (7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)
_ID_CHECK = "10X98765432"


def parse_id_birth(value: str) -> tuple[date | None, str]:
    """从 18/15 位身份证提取出生日期；返回 (日期, 错误说明)。"""
    digits = (value or "").strip().upper()
    if not digits:
        return None, ""
    if len(digits) == 18:
        if not digits[:17].isdigit():
            return None, "身份证号前 17 位必须是数字"
        try:
            born = date(int(digits[6:10]), int(digits[10:12]), int(digits[12:14]))
        except ValueError:
            return None, "身份证中的出生日期无效"
        checksum = sum(int(digits[i]) * _ID_WEIGHTS[i] for i in range(17))
        expected = _ID_CHECK[checksum % 11]
        if digits[17] != expected:
            return born, "身份证校验位不正确，已提取出生日期，请核对"
        return born, ""
    if len(digits) == 15 and digits.isdigit():
        try:
            born = date(1900 + int(digits[6:8]), int(digits[8:10]), int(digits[10:12]))
        except ValueError:
            return None, "15 位身份证中的出生日期无效"
        return born, "15 位身份证已提取出生日期"
    return None, "身份证号应为 18 位（或 15 位老号）"


def age_parts(birth: date, today: date | None = None) -> tuple[int, int, int]:
    """返回周岁、月、日；出生日期晚于今天时返回 0。"""
    today = today or date.today()
    if birth > today:
        return 0, 0, 0
    years = today.year - birth.year
    months = today.month - birth.month
    days = today.day - birth.day
    if days < 0:
        months -= 1
        prev_year = today.year
        prev_month = today.month - 1
        if prev_month == 0:
            prev_month = 12
            prev_year -= 1
        days += calendar.monthrange(prev_year, prev_month)[1]
    if months < 0:
        years -= 1
        months += 12
    return max(0, years), max(0, months), max(0, days)


def age_text(birth: date | None, today: date | None = None) -> str:
    if birth is None:
        return "年龄不详"
    years, months, days = age_parts(birth, today)
    return f"{years}岁{months}个月{days}天"


def add_months(value: date, months: int) -> date:
    total = value.year * 12 + (value.month - 1) + months
    year, month0 = divmod(total, 12)
    month = month0 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def birth_from_age(years: int, months: int, days: int, today: date | None = None) -> date:
    """按“今天 - 年龄”反推出生日期，作为年龄输入时的近似值。"""
    today = today or date.today()
    value = add_months(today, -(max(0, years) * 12 + max(0, months)))
    return value - timedelta(days=max(0, days))


class BirthAgeEditor(QWidget):
    """出生日期选择 + 周岁/月/日输入 + 年龄不详。"""

    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._syncing = False
        self._birth: date | None = None
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(6)
        layout.setVerticalSpacing(3)
        layout.setColumnMinimumWidth(0, 78)
        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(2, 0)

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_edit.setDateRange(QDate(1900, 1, 1), QDate.currentDate())
        self.date_edit.setSpecialValueText("未填写")
        self.date_edit.setDate(self.date_edit.minimumDate())
        self.date_edit.setToolTip("点击右侧箭头打开日期选择框")
        self.unknown = QCheckBox("年龄不详")
        self.unknown.setChecked(True)
        self.unknown.setToolTip("勾选后不保存出生日期；身份证提取到日期时会自动取消")

        self.years = QSpinBox()
        self.years.setRange(0, 150)
        self.years.setSuffix(" 岁")
        self.years.setFixedWidth(90)
        self.months = QSpinBox()
        self.months.setRange(0, 11)
        self.months.setSuffix(" 月")
        self.months.setFixedWidth(82)
        self.days = QSpinBox()
        self.days.setRange(0, 30)
        self.days.setSuffix(" 天")
        self.days.setFixedWidth(82)
        self.calculated = QLabel("年龄不详")
        self.calculated.setStyleSheet(f"color:{colors()['muted']};")
        self.status = QLabel("")
        self.status.setStyleSheet(f"color:{colors()['warning']};")
        self.status.setWordWrap(True)

        layout.addWidget(QLabel("出生日期"), 0, 0)
        layout.addWidget(self.date_edit, 0, 1)
        layout.addWidget(self.unknown, 0, 2)
        layout.addWidget(QLabel("年龄"), 1, 0)
        age_row = QWidget()
        age_layout = QGridLayout(age_row)
        age_layout.setContentsMargins(0, 0, 0, 0)
        age_layout.setHorizontalSpacing(4)
        age_layout.addWidget(self.years, 0, 0)
        age_layout.addWidget(self.months, 0, 1)
        age_layout.addWidget(self.days, 0, 2)
        age_layout.setColumnStretch(3, 1)
        age_layout.addWidget(self.calculated, 0, 3)
        layout.addWidget(age_row, 1, 1, 1, 2)
        layout.addWidget(self.status, 2, 0, 1, 3)

        self.date_edit.dateChanged.connect(self._date_changed)
        self.unknown.toggled.connect(self._unknown_changed)
        for spin in (self.years, self.months, self.days):
            spin.valueChanged.connect(self._age_changed)
        self._set_enabled(False)
        self._update_label()
        register_theme_listener(self)

    def _set_enabled(self, enabled: bool) -> None:
        self.date_edit.setEnabled(enabled)
        for spin in (self.years, self.months, self.days):
            spin.setEnabled(enabled)

    def _update_label(self) -> None:
        if self.unknown.isChecked():
            self.calculated.setText("")
            self.calculated.setStyleSheet(f"color:{colors()['muted']};")
            return
        if self._birth is None:
            self.calculated.setText("请选择出生日期")
            self.calculated.setStyleSheet(f"color:{colors()['warning']};")
            return
        self.calculated.setText(age_text(self._birth))
        self.calculated.setStyleSheet(f"color:{colors()['success']};font-weight:bold;")

    def _date_changed(self, qdate: QDate) -> None:
        if self._syncing or self.unknown.isChecked():
            return
        born = qdate.toPython()
        self._birth = born
        years, months, days = age_parts(born)
        self._syncing = True
        self.years.setValue(years)
        self.months.setValue(months)
        self.days.setValue(days)
        self._syncing = False
        self._update_label()
        self.changed.emit()

    def _age_changed(self, _value: int) -> None:
        if self._syncing or self.unknown.isChecked():
            return
        born = birth_from_age(self.years.value(), self.months.value(), self.days.value())
        self._birth = born
        self._syncing = True
        self.date_edit.setDate(QDate(born.year, born.month, born.day))
        self._syncing = False
        self.status.setText("年龄反推的出生日期为近似值；有身份证时以身份证为准")
        self._update_label()
        self.changed.emit()

    def _unknown_changed(self, checked: bool) -> None:
        self._set_enabled(not checked)
        if checked:
            self._birth = None
            self._syncing = True
            self.date_edit.setDate(self.date_edit.minimumDate())
            self._syncing = False
            self.status.clear()
        else:
            if self._birth is None:
                self._birth = date.today()
                self._syncing = True
                self.date_edit.setDate(QDate.currentDate())
                self._syncing = False
            years, months, days = age_parts(self._birth)
            self._syncing = True
            self.years.setValue(years)
            self.months.setValue(months)
            self.days.setValue(days)
            self._syncing = False
        self._update_label()
        self.changed.emit()

    def apply_theme(self) -> None:
        self.status.setStyleSheet(f"color:{colors()['warning']};")
        self._update_label()
        self.update()

    def set_id_number(self, value: str) -> bool:
        born, error = parse_id_birth(value)
        if error:
            self.status.setText(error)
        elif not error:
            self.status.clear()
        if born is not None:
            self.set_birth_date(born)
            return True
        return False

    def set_birth_date(self, value: date | None) -> None:
        if value is None:
            self.unknown.setChecked(True)
            return
        self.unknown.setChecked(False)
        self._birth = value
        self._syncing = True
        self.date_edit.setDate(QDate(value.year, value.month, value.day))
        self._syncing = False
        years, months, days = age_parts(value)
        self._syncing = True
        self.years.setValue(years)
        self.months.setValue(months)
        self.days.setValue(days)
        self._syncing = False
        self._update_label()

    def birth_date(self) -> date | None:
        if self.unknown.isChecked():
            return None
        return self._birth

    def birth_date_text(self) -> str:
        value = self.birth_date()
        return value.isoformat() if value else ""

    def reset(self) -> None:
        self._birth = None
        self.unknown.setChecked(True)
        self._syncing = True
        self.date_edit.setDate(self.date_edit.minimumDate())
        self._syncing = False
        self.status.clear()
        self._syncing = True
        self.years.setValue(0)
        self.months.setValue(0)
        self.days.setValue(0)
        self._syncing = False
        self._update_label()
