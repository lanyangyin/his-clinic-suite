"""治疗室日报 Excel 导出。"""
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

FILL = PatternFill("solid", fgColor="2563EB")
FONT = Font(color="FFFFFF", bold=True)


def _sheet(wb, title, headers, rows, widths):
    ws = wb.create_sheet(title)
    ws.append(headers)
    for cell in ws[1]:
        cell.fill = FILL
        cell.font = FONT
        cell.alignment = Alignment(horizontal="center")
    for row in rows:
        ws.append(row)
    for index, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(index)].width = width
    ws.freeze_panes = "A2"
    return ws


def report_workbook(data: dict, followups: list) -> BytesIO:
    wb = Workbook()
    wb.remove(wb.active)
    _sheet(
        wb,
        "日报概览",
        ["指标", "数值"],
        [
            ["日期", str(data["date"])],
            ["当日处置", data["total"]],
            ["已完成", data["completed"]],
            ["候诊", data["waiting"]],
            ["处置中", data["in_progress"]],
            ["已取消", data["cancelled"]],
            ["处置收入", data["revenue"]],
            ["材料费", data["material_amount"]],
            ["到期随访", data["followups_due"]],
        ],
        [20, 16],
    )
    _sheet(
        wb,
        "按模板",
        ["模板", "已完成"],
        [[key, count] for key, count in data["by_template"].items()],
        [24, 12],
    )
    _sheet(
        wb,
        "按治疗室",
        ["治疗室", "已完成"],
        [[key, count] for key, count in data["by_room"].items()],
        [24, 12],
    )
    _sheet(
        wb,
        "待随访",
        ["患者", "日期", "目的", "备注", "状态"],
        [
            [row.patient_name, str(row.due_date), row.purpose, row.note, row.status]
            for row in followups
        ],
        [18, 14, 14, 30, 12],
    )
    stream = BytesIO()
    wb.save(stream)
    stream.seek(0)
    return stream
