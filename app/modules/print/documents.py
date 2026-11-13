"""门诊病历 / 西药处方笺 / 中药处方笺打印文档。"""
from datetime import datetime
from html import escape

from app import settings
from app.modules.print.barcode import code128_svg

PAGE_CSS = """
@page { size: A4; margin: 12mm; }
* { box-sizing: border-box; }
body { font-family: "Microsoft YaHei", "SimSun", sans-serif; color: #111; font-size: 13px; line-height: 1.6; }
.page { page-break-after: always; }
.page:last-child { page-break-after: auto; }
.clinic { text-align: center; font-size: 22px; font-weight: bold; letter-spacing: 2px; margin: 2px 0 0; }
.doc-title { text-align: center; font-size: 17px; letter-spacing: 5px; margin: 2px 0 8px; }
.rule { border-top: 2px solid #111; margin: 4px 0 8px; }
.rule-thin { border-top: 1px solid #333; margin: 8px 0; }
.info { width: 100%; border-collapse: collapse; margin-bottom: 6px; }
.info td { padding: 3px 4px; font-size: 13px; vertical-align: bottom; }
.label { color: #333; white-space: nowrap; }
.line { border-bottom: 1px solid #555; display: inline-block; min-width: 90px; padding: 0 4px; }
.section { margin: 8px 0; }
.section-title { font-weight: bold; margin-right: 6px; }
.rx-line { margin: 3px 0 2px 18px; }
.usage { margin: 0 0 4px 42px; color: #222; }
.herbs { width: 100%; border-collapse: collapse; margin: 4px 0; }
.herbs td { padding: 2px 6px; font-size: 13px; }
.rp { font-size: 17px; font-weight: bold; margin: 8px 0 4px; }
.blank { color: #666; }
.sign { margin-top: 26px; display: flex; justify-content: space-between; font-size: 13px; }
.footer { margin-top: 10px; font-size: 12px; color: #333; }
.barcode { margin: 2px 0 2px; line-height: 0; }
.barcode svg { display: block; max-width: 100%; height: auto; }
.barcode-no { font-family: monospace; font-size: 11px; letter-spacing: 2px; }
.rx-meta { width: 100%; border-collapse: collapse; margin: 4px 0 8px; }
.rx-meta td { padding: 2px 4px; font-size: 13px; }
.prescription-box { border: 1px solid #777; padding: 8px 10px; min-height: 58mm; }
.no-print { text-align: center; margin: 8px 0; }
@media print { .no-print { display: none; } }
"""


def _value(value, fallback="—"):
    text = str(value or "").strip()
    return escape(text) if text else fallback


def _barcode(code: str) -> str:
    return f'<div class="barcode">{code128_svg(code)}</div>'


def _print_button() -> str:
    return '<p class="no-print"><button onclick="window.print()">打印</button></p>'


def _herb_table(items: list[dict]) -> str:
    cells = [
        f'<td>{escape(item["name"])} {item["dose"]:g}g'
        f'{"（" + escape(item["special"]) + "）" if item.get("special") and item["special"] != "none" else ""}</td>'
        for item in items
    ]
    rows = []
    for index in range(0, len(cells), 4):
        row = cells[index:index + 4]
        row += ["<td></td>"] * (4 - len(row))
        rows.append("<tr>" + "".join(row) + "</tr>")
    return '<table class="herbs">' + "".join(rows) + "</table>"


def _record_page(data: dict) -> str:
    meta = {
        "name": settings.CLINIC_NAME,
        "phone": settings.CLINIC_PHONE,
        "address": settings.CLINIC_ADDRESS,
    }
    record = data.get("record")
    diagnosis = data["encounter"].diagnosis or ""
    diagnoses = data.get("diagnoses")
    if not diagnoses:
        diagnoses = (
            [{"diagnosis_code": "", "diagnosis": diagnosis, "diagnosis_type": "primary"}]
            if diagnosis
            else []
        )
    diagnosis_html = "".join(
        f'<div>{index + 1}. {"【主诊断】" if item.get("diagnosis_type") == "primary" else "【其他诊断】"}'
        f'{escape(item.get("diagnosis_code") or "")} {escape(item.get("diagnosis") or "")}'
        f'{"（" + escape(item.get("note") or "") + "）" if item.get("note") else ""}</div>'
        for index, item in enumerate(diagnoses)
    ) or "—"
    western = "".join(
        f'<div class="rx-line">{index + 1}. {escape(line["name"])}　'
        f'{escape(line.get("spec") or "")}　×{line["qty"]}{escape(line.get("unit") or "")}</div>'
        f'<div class="usage">用法：{escape(line["usage"])}</div>'
        for index, line in enumerate(data.get("lines") or [])
    ) or '<p class="blank">（无）</p>'
    tcm_html = ""
    for rx in data.get("tcm") or []:
        tcm_html += (
            f'<p><b>{escape(rx["formula_name"] or "中药方")}</b>　'
            f'配{rx["packs"]}付　'
            f'{"代煎" if rx["decoct_service"] == "decoct" else "自煎"}　'
            f'{escape(rx["decoction_method"])}</p>'
            f'{_herb_table(rx["items"])}'
        )
    tcm_html = tcm_html or '<p class="blank">（无）</p>'
    aux = data.get("aux_exams") or []
    aux_html = "<br>".join(
        f'{escape(item["type"])}：{escape(item["name"])}　{escape(item["result"])}'
        f'{"　【危急值】" if item.get("critical") else ""}'
        f'{"　" + escape(item["date"]) if item.get("date") else ""}'
        for item in aux
    ) or "—"
    return f"""
<div class="page">
  <div class="clinic">{escape(meta['name'])}</div>
  <div class="doc-title">门诊病历</div>
  <div class="rule"></div>
  <table class="info">
    <tr><td class="label">病历编号：</td><td>{_value(data.get('record_no'))}</td>
        <td class="label">就诊日期：</td><td>{_value(data.get('visit_date'))}</td></tr>
    <tr><td class="label">姓名：</td><td>{_value(data.get('patient_name'))}</td>
        <td class="label">性别：</td><td>{_value(data.get('patient_gender'))}</td>
        <td class="label">年龄：</td><td>{data.get('patient_age') if data.get('patient_age') is not None else '—'}岁</td>
        <td class="label">科别：</td><td>{_value(data.get('department_name'))}</td></tr>
    <tr><td class="label">住址：</td><td colspan="3">{_value(data.get('patient_address'))}</td>
        <td class="label">电话：</td><td colspan="3">{_value(data.get('patient_phone'))}</td></tr>
    <tr><td class="label">过敏史：</td><td colspan="7">{_value(data.get('allergy'))}</td></tr>
    <tr><td class="label">特殊既往史：</td><td colspan="7">{_value(data.get('special_history'))}</td></tr>
  </table>
  <div class="rule-thin"></div>
  <div class="section"><span class="section-title">主诉：</span>{_value(record.chief_complaint if record else '')}</div>
  <div class="section"><span class="section-title">现病史：</span>{_value(record.present_illness if record else '')}</div>
  <div class="section"><span class="section-title">既往史：</span>{_value(record.past_history if record else '')}</div>
  <div class="section"><span class="section-title">个人史：</span>{_value(record.personal_history if record else '')}</div>
  <div class="section"><span class="section-title">婚育史：</span>{_value(record.marital_history if record else '')}</div>
  <div class="section"><span class="section-title">家族史：</span>{_value(record.family_history if record else '')}</div>
  <div class="section"><span class="section-title">体格检查：</span>{_value(record.physical_exam if record else '')}</div>
  <div class="section"><span class="section-title">辅助检查（病历记录）：</span>{_value(record.auxiliary_exam if record else '')}</div>
  <div class="section"><span class="section-title">辅助检查（本次）：</span>{aux_html}</div>
  <div class="section"><span class="section-title">诊断：</span>{diagnosis_html}</div>
  <div class="section"><span class="section-title">西药处方：</span>{western}</div>
  <div class="section"><span class="section-title">中药处方：</span>{tcm_html}</div>
  <div class="section"><span class="section-title">建议：</span>{_value(record.treatment_advice if record else '')}</div>
  <div class="section"><span class="section-title">合计：</span>{data['total']:.2f} 元</div>
  <div class="sign">
    <span>医师：{_value(data.get('doctor_name'))}</span>
    <span>医师签名：__________</span>
  </div>
</div>"""


def _western_page(data: dict) -> str:
    meta = _clinic_meta()
    lines = "".join(
        f'<div class="rx-line">{index + 1}. {escape(line["name"])}　'
        f'{escape(line.get("spec") or "")}　×{line["qty"]}{escape(line.get("unit") or "")}</div>'
        f'<div class="usage">用法：{escape(line["usage"])}</div>'
        for index, line in enumerate(data.get("lines") or [])
    ) or '<p class="blank">（无）</p>'
    fee_type = "医保" if settings.INSURANCE_ENABLED else "自费"
    rx_no = f"RX{data['encounter'].id:06d}"
    return f"""
<div class="page">
  {_barcode(rx_no)}
  <div class="barcode-no">{rx_no}</div>
  <div class="clinic">{escape(meta['name'])}</div>
  <div class="doc-title">处方笺</div>
  <table class="rx-meta">
    <tr><td>费别：{fee_type}</td><td>医保卡号：</td><td>处方编号：{rx_no}</td></tr>
    <tr><td>姓名：{_value(data.get('patient_name'))}</td>
        <td>性别：{_value(data.get('patient_gender'))}</td>
        <td>年龄：{data.get('patient_age') if data.get('patient_age') is not None else '—'}岁</td></tr>
    <tr><td>门诊/住院病历号：{_value(data.get('record_no'))}</td>
        <td>科室：{_value(data.get('department_name'))}</td>
        <td>开具日期：{_value(data.get('visit_date'))}</td></tr>
    <tr><td colspan="2">临床诊断：{_value(data['encounter'].diagnosis)}</td><td></td></tr>
  </table>
  <div class="rule-thin"></div>
  <div class="prescription-box">
    <div class="rp">Rp.</div>
    {lines}
    <p>合计：{data['total']:.2f} 元</p>
    <p class="blank">（以下空白）</p>
  </div>
  <div class="footer">
    <div class="sign">
      <span>医师：{_value(data.get('doctor_name'))}</span>
      <span>审核药师：__________</span>
      <span>调配药师：__________</span>
      <span>核对、发药药师：__________</span>
    </div>
  </div>
</div>"""


def _tcm_page(data: dict, rx: dict) -> str:
    meta = _clinic_meta()
    herbs = _herb_table(rx["items"])
    fee_type = "医保" if settings.INSURANCE_ENABLED else "自费"
    return f"""
<div class="page">
  {_barcode(rx["prescription_no"])}
  <div class="barcode-no">{escape(rx["prescription_no"])}</div>
  <div class="clinic">{escape(meta['name'])}</div>
  <div class="doc-title">处方笺</div>
  <table class="rx-meta">
    <tr><td>费别：{fee_type}</td><td>医保卡号：</td><td>处方编号：{escape(rx["prescription_no"])}</td></tr>
    <tr><td>姓名：{_value(data.get('patient_name'))}</td>
        <td>性别：{_value(data.get('patient_gender'))}</td>
        <td>年龄：{data.get('patient_age') if data.get('patient_age') is not None else '—'}岁</td></tr>
    <tr><td>门诊/住院病历号：{_value(data.get('record_no'))}</td>
        <td>科室：{_value(data.get('department_name'))}</td>
        <td>开具日期：{_value(data.get('visit_date'))}</td></tr>
    <tr><td colspan="2">临床诊断：{_value(data['encounter'].diagnosis)}</td><td></td></tr>
  </table>
  <div class="rule-thin"></div>
  <div class="prescription-box">
    <div class="rp">Rp.</div>
    <p><b>{escape(rx["formula_name"] or "中药方")}</b></p>
    <table class="herbs">{herbs}</table>
    <p>配{rx["packs"]}付　每日一剂　{"水煎服 每日两次" if rx["decoct_service"] == "decoct" else "自煎"}</p>
    <p class="blank">（以下空白）</p>
  </div>
  <div class="footer">
    <div class="sign">
      <span>医师：{_value(data.get('doctor_name'))}</span>
      <span>审核药师：__________</span>
      <span>调配药师：__________</span>
      <span>核对、发药药师：__________</span>
    </div>
  </div>
</div>"""


def _clinic_meta() -> dict:
    return {
        "name": settings.CLINIC_NAME,
        "phone": settings.CLINIC_PHONE,
        "address": settings.CLINIC_ADDRESS,
    }


def _html(body: str, title: str = "门诊病历 / 处方笺") -> str:
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>{escape(title)}</title>
<style>{PAGE_CSS}</style></head><body>
{_print_button()}
{body}
</body></html>"""


def render_record(data: dict) -> str:
    return _html(_record_page(data), "门诊病历")


def render_western(data: dict) -> str:
    return _html(_western_page(data), "处方笺")


def render_tcm(data: dict) -> str:
    pages = "".join(_tcm_page(data, rx) for rx in data.get("tcm") or [])
    return _html(pages or '<div class="page"><p class="blank">（无中药处方）</p></div>', "中药处方笺")


def render_full_set(data: dict) -> str:
    pages = [_record_page(data)]
    if data.get("lines"):
        pages.append(_western_page(data))
    for rx in data.get("tcm") or []:
        pages.append(_tcm_page(data, rx))
    return _html("".join(pages))
