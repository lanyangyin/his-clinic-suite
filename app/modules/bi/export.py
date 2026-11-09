"""运营报表 Excel 导出。"""
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

_HEADER_FILL = PatternFill("solid", fgColor="2563EB")
_HEADER_FONT = Font(color="FFFFFF", bold=True)


def _sheet(wb: Workbook, title: str, headers: list[str], rows: list[list], widths: list[int] | None = None):
    ws = wb.create_sheet(title)
    ws.append(headers)
    for cell in ws[1]:
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
        cell.alignment = Alignment(horizontal="center")
    for row in rows:
        ws.append(row)
    for index, width in enumerate(widths or [], start=1):
        ws.column_dimensions[get_column_letter(index)].width = width
    ws.freeze_panes = "A2"
    return ws


def _money(value) -> float:
    return round(float(value or 0), 2)


def executive_workbook(data: dict) -> BytesIO:
    wb = Workbook()
    wb.remove(wb.active)

    kpi = data["kpi"]
    overview_rows = [
        ["统计期间", f"{data['start_date']} ~ {data['end_date']}", ""],
        ["门诊人次", kpi["visits"], "人次"],
        ["收费笔数", kpi["paid_count"], "笔"],
        ["医疗收入", _money(kpi["revenue"]), "元"],
        ["医保支付", _money(kpi["insurance"]), "元"],
        ["个人自费", _money(kpi["self_pay"]), "元"],
        ["退费金额", _money(kpi["refunds"]), "元"],
        ["次均费用", _money(kpi["avg_cost"]), "元"],
        ["药占比", kpi["drug_ratio"], "%"],
        ["处方条目", kpi["prescriptions"], "条"],
        ["检验申请", kpi["lab_requests"], "项"],
        ["完成手术", kpi["surgeries"], "台"],
        ["治疗室处置", kpi["treatments"], "例"],
    ]
    _sheet(wb, "运营概览", ["指标", "数值", "单位"], overview_rows, [24, 20, 10])

    _sheet(
        wb,
        "收入趋势",
        ["日期", "门诊人次", "收费笔数", "收入(元)"],
        [
            [row["date"], row["visits"], row["paid_count"], _money(row["paid_amount"])]
            for row in data["trend"]
        ],
        [14, 12, 12, 14],
    )

    _sheet(
        wb,
        "科室收入",
        ["科室", "就诊人次", "已收", "已退", "挂号", "诊疗", "药品", "检验", "检查", "治疗", "其他"],
        [
            [
                row["department_name"],
                row["encounter_count"],
                _money(row["paid_amount"]),
                _money(row["refunded_amount"]),
                _money(row["registration_amount"]),
                _money(row["consultation_amount"]),
                _money(row["drug_amount"]),
                _money(row["lab_amount"]),
                _money(row["imaging_amount"]),
                _money(row["treatment_amount"]),
                _money(row.get("other_amount", 0)),
            ]
            for row in data["departments"]
        ],
        [16, 10, 12, 12, 10, 10, 10, 10, 10, 10, 10],
    )

    _sheet(
        wb,
        "医生工作量",
        ["医生", "接诊人次"],
        [[row["doctor_name"], row["visits"]] for row in data["doctors"]],
        [18, 12],
    )

    _sheet(
        wb,
        "药品Top10",
        ["药品", "数量", "金额(元)"],
        [
            [row["drug_name"], row["quantity"], _money(row["amount"])]
            for row in data["top_drugs"]
        ],
        [24, 10, 14],
    )

    _sheet(
        wb,
        "支付方式",
        ["渠道", "笔数", "金额(元)"],
        [[row["label"], row["count"], _money(row["amount"])] for row in data["channels"]],
        [14, 10, 14],
    )

    risks = data["risks"]
    _sheet(
        wb,
        "库存与风险",
        ["项目", "数量"],
        [
            ["待处理采购申请", risks["purchase_pending"]],
            ["医保合规风险", risks["insurance_risks"]],
            ["GSP 不合格验收", risks["gsp_unqualified"]],
            ["GSP 温湿度异常", risks["gsp_storage"]],
            ["进行中召回", risks["gsp_recalls"]],
        ],
        [24, 10],
    )

    _sheet(
        wb,
        "库存预警",
        ["类型", "名称", "库存"],
        [[row["kind"], row["name"], row["quantity"]] for row in data["inventory_alerts"]],
        [10, 24, 10],
    )

    stream = BytesIO()
    wb.save(stream)
    stream.seek(0)
    return stream


def department_workbook(rows: list[dict]) -> BytesIO:
    wb = Workbook()
    ws = wb.active
    ws.title = "科室收入"
    headers = ["科室", "就诊人次", "已收", "已退", "挂号", "诊疗", "药品", "检验", "检查", "治疗", "其他"]
    ws.append(headers)
    for cell in ws[1]:
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
    for row in rows:
        ws.append(
            [
                row["department_name"],
                row["encounter_count"],
                _money(row["paid_amount"]),
                _money(row["refunded_amount"]),
                _money(row["registration_amount"]),
                _money(row["consultation_amount"]),
                _money(row["drug_amount"]),
                _money(row["lab_amount"]),
                _money(row["imaging_amount"]),
                _money(row["treatment_amount"]),
                _money(row.get("other_amount", 0)),
            ]
        )
    for index, width in enumerate([16, 10, 12, 12, 10, 10, 10, 10, 10, 10, 10], start=1):
        ws.column_dimensions[get_column_letter(index)].width = width
    ws.freeze_panes = "A2"
    stream = BytesIO()
    wb.save(stream)
    stream.seek(0)
    return stream
