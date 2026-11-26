"""门诊病历 / 西药处方笺 / 中药处方笺打印文档。"""
from datetime import datetime
from html import escape
import re

from app import settings
from app.modules.print.barcode import code128_svg

PAGE_CSS = """
@page { size: A4; margin: 12mm; }
* { box-sizing: border-box; }
body { font-family: "Microsoft YaHei", "SimSun", sans-serif; color: #111; font-size: 13px; line-height: 1.6; }
.page { page-break-after: always; position: relative; }
.watermark { position: absolute; top: 38%; left: 22%; transform: rotate(-25deg);
    font-size: 64px; color: rgba(185,28,28,.22); font-weight: 700; z-index: 0; pointer-events: none; }
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


def _profile(profile: dict | None = None) -> dict:
    base = {
        "clinic_name": settings.CLINIC_NAME,
        "clinic_address": settings.CLINIC_ADDRESS,
        "clinic_phone": settings.CLINIC_PHONE,
        "logo_url": "",
        "theme_color": "#111111",
        "font_family": '"Microsoft YaHei", "SimSun", sans-serif',
        "paper_size": "A4",
        "margin_mm": 12,
        "header_note": "",
        "footer_note": "",
        "doctor_label": "医师",
        "reviewer_label": "审核药师",
        "dispenser_label": "调配药师",
        "checker_label": "核对、发药药师",
        "custom_css": "",
    }
    if profile:
        base.update({key: value for key, value in profile.items() if value not in (None, "")})
    paper = base.get("paper_size") if base.get("paper_size") in ("A4", "A5") else "A4"
    margin = base.get("margin_mm")
    try:
        margin = max(5, min(40, int(margin)))
    except (TypeError, ValueError):
        margin = 12
    color = str(base.get("theme_color") or "#111111")
    if not re.fullmatch(r"#[0-9a-fA-F]{3,8}", color):
        color = "#111111"
    base["paper_size"] = paper
    base["margin_mm"] = margin
    base["theme_color"] = color
    return base


def _page_css(profile: dict) -> str:
    css = PAGE_CSS.replace(
        "@page { size: A4; margin: 12mm; }",
        f"@page {{ size: {profile['paper_size']}; margin: {profile['margin_mm']}mm; }}",
    )
    css = css.replace(
        'font-family: "Microsoft YaHei", "SimSun", sans-serif;',
        f"font-family: {profile['font_family']};",
    )
    css = css.replace("color: #111;", f"color: {profile['theme_color']};", 1)
    css += """
.clinic-logo { display: block; max-height: 48px; max-width: 180px; margin: 0 auto 4px; }
.header-note { text-align: center; font-size: 12px; color: #444; margin: 2px 0 4px; }
.footer-note { margin-top: 8px; font-size: 12px; color: #333; border-top: 1px dotted #999; padding-top: 4px; }
"""
    custom = str(profile.get("custom_css") or "").strip()
    if custom:
        css += "\n/* institution custom css */\n" + custom
    return css


def _logo_html(profile: dict) -> str:
    url = str(profile.get("logo_url") or "").strip()
    if not url:
        return ""
    if not (url.startswith("http://") or url.startswith("https://") or url.startswith("data:image/")):
        return ""
    return f'<img class="clinic-logo" src="{escape(url, quote=True)}" alt="机构标识">'


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


def _record_page(data: dict, profile: dict | None = None) -> str:
    profile = _profile(profile)
    meta = _clinic_meta(profile)
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
  {_logo_html(profile)}
  <div class="clinic">{escape(meta['name'])}</div>
  {f'<div class="header-note">{escape(profile["header_note"])}</div>' if profile.get('header_note') else ''}
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
    <span>{escape(profile.get('doctor_label') or '医师')}：{_value(data.get('doctor_name'))}</span>
    {_signature_html(data.get('signature') or {})}
  </div>
  {f'<div class="footer-note">{escape(profile["footer_note"])}</div>' if profile.get('footer_note') else ''}
</div>"""


def _signature_html(signature: dict) -> str:
    if not signature.get("signed"):
        return "<span>医师签名：__________</span>"
    return (
        f"<span>医师签名：{_value(signature.get('signed_by'))}（已签名）</span>"
        f"<span>签名时间：{_value(signature.get('signed_at'))}</span>"
        f"<span>验签码：{_value(signature.get('verify_code'))}</span>"
    )


def _western_page(data: dict, profile: dict | None = None) -> str:
    profile = _profile(profile)
    meta = _clinic_meta(profile)
    lines = "".join(
        f'<div class="rx-line">{index + 1}. {escape(line["name"])}　'
        f'{escape(line.get("spec") or "")}　×{line["qty"]}{escape(line.get("unit") or "")}</div>'
        f'<div class="usage">用法：{escape(line["usage"])}</div>'
        for index, line in enumerate(data.get("lines") or [])
    ) or '<p class="blank">（无）</p>'
    fee_type = "医保" if settings.INSURANCE_ENABLED else "自费"
    rx_no = data.get("prescription_no") or f"RX{data['encounter'].id:06d}"
    rx_status = {
        "pending_review": "待药师审核",
        "approved": "已审核",
        "rejected": "已退回",
        "dispensing": "调配中",
        "dispensed": "已发药",
        "cancelled": "已作废",
    }.get(data.get("prescription_status") or "", data.get("prescription_status") or "")
    watermark = ""
    if data.get("prescription_status") == "pending_review":
        watermark = '<div class="watermark">待审</div>'
    elif data.get("prescription_status") == "cancelled":
        watermark = '<div class="watermark">作废</div>'
    return f"""
<div class="page">{watermark}
  {_barcode(rx_no)}
  <div class="barcode-no">{rx_no}</div>
  {_logo_html(profile)}
  <div class="clinic">{escape(meta['name'])}</div>
  {f'<div class="header-note">{escape(profile["header_note"])}</div>' if profile.get('header_note') else ''}
  <div class="doc-title">处方笺</div>
  <table class="rx-meta">
    <tr><td>费别：{fee_type}</td><td>医保卡号：</td><td>处方编号：{rx_no}</td></tr>
    <tr><td>姓名：{_value(data.get('patient_name'))}</td>
        <td>性别：{_value(data.get('patient_gender'))}</td>
        <td>年龄：{data.get('patient_age') if data.get('patient_age') is not None else '—'}岁</td></tr>
    <tr><td>门诊/住院病历号：{_value(data.get('record_no'))}</td>
        <td>科室：{_value(data.get('department_name'))}</td>
        <td>开具日期：{_value(data.get('visit_date'))}</td></tr>
    <tr><td colspan="2">临床诊断：{_value(data['encounter'].diagnosis)}</td><td>处方状态：{_value(rx_status)}</td></tr>
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
      <span>{escape(profile.get('doctor_label') or '医师')}：{_value(data.get('doctor_name'))}</span>
      <span>{escape(profile.get('reviewer_label') or '审核药师')}：__________</span>
      <span>{escape(profile.get('dispenser_label') or '调配药师')}：__________</span>
      <span>{escape(profile.get('checker_label') or '核对、发药药师')}：__________</span>
    </div>
    <div>打印时间：{_value(data.get('printed_at'))}　打印人：{_value(data.get('printed_by'))}</div>
    {f'<div class="footer-note">{escape(profile["footer_note"])}</div>' if profile.get('footer_note') else ''}
  </div>
</div>"""


def _tcm_page(data: dict, rx: dict, profile: dict | None = None) -> str:
    profile = _profile(profile)
    meta = _clinic_meta(profile)
    herbs = _herb_table(rx["items"])
    fee_type = "医保" if settings.INSURANCE_ENABLED else "自费"
    rx_status = {
        "pending": "待药师审核",
        "reviewed": "已审核",
        "dispensed": "已发药",
        "decocting": "煎药中",
        "completed": "已完成",
        "cancelled": "已作废",
    }.get(rx.get("status") or "", rx.get("status") or "")
    watermark = ""
    if rx.get("status") == "pending":
        watermark = '<div class="watermark">待审</div>'
    elif rx.get("status") == "cancelled":
        watermark = '<div class="watermark">作废</div>'
    return f"""
<div class="page">{watermark}
  {_barcode(rx["prescription_no"])}
  <div class="barcode-no">{escape(rx["prescription_no"])}</div>
  {_logo_html(profile)}
  <div class="clinic">{escape(meta['name'])}</div>
  {f'<div class="header-note">{escape(profile["header_note"])}</div>' if profile.get('header_note') else ''}
  <div class="doc-title">处方笺</div>
  <table class="rx-meta">
    <tr><td>费别：{fee_type}</td><td>医保卡号：</td><td>处方编号：{escape(rx["prescription_no"])}</td></tr>
    <tr><td>姓名：{_value(data.get('patient_name'))}</td>
        <td>性别：{_value(data.get('patient_gender'))}</td>
        <td>年龄：{data.get('patient_age') if data.get('patient_age') is not None else '—'}岁</td></tr>
    <tr><td>门诊/住院病历号：{_value(data.get('record_no'))}</td>
        <td>科室：{_value(data.get('department_name'))}</td>
        <td>开具日期：{_value(data.get('visit_date'))}</td></tr>
    <tr><td colspan="2">临床诊断：{_value(data['encounter'].diagnosis)}</td><td>处方状态：{_value(rx_status)}</td></tr>
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
      <span>{escape(profile.get('doctor_label') or '医师')}：{_value(data.get('doctor_name'))}</span>
      <span>{escape(profile.get('reviewer_label') or '审核药师')}：__________</span>
      <span>{escape(profile.get('dispenser_label') or '调配药师')}：__________</span>
      <span>{escape(profile.get('checker_label') or '核对、发药药师')}：__________</span>
    </div>
    <div>打印时间：{_value(data.get('printed_at'))}　打印人：{_value(data.get('printed_by'))}</div>
    {f'<div class="footer-note">{escape(profile["footer_note"])}</div>' if profile.get('footer_note') else ''}
  </div>
</div>"""


def _clinic_meta(profile: dict | None = None) -> dict:
    profile = _profile(profile)
    return {
        "name": profile["clinic_name"],
        "phone": profile["clinic_phone"],
        "address": profile["clinic_address"],
    }


def _html(body: str, title: str = "门诊病历 / 处方笺", profile: dict | None = None) -> str:
    profile = _profile(profile)
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>{escape(title)}</title>
<style>{_page_css(profile)}</style></head><body>
{_print_button()}
{body}
</body></html>"""


def render_record(data: dict, profile: dict | None = None) -> str:
    return _html(_record_page(data, profile), "门诊病历", profile)


def render_western(data: dict, profile: dict | None = None) -> str:
    return _html(_western_page(data, profile), "处方笺", profile)


def render_tcm(data: dict, profile: dict | None = None) -> str:
    pages = "".join(_tcm_page(data, rx, profile) for rx in data.get("tcm") or [])
    return _html(pages or '<div class="page"><p class="blank">（无中药处方）</p></div>', "中药处方笺", profile)


def render_full_set(data: dict, profile: dict | None = None) -> str:
    pages = [_record_page(data, profile)]
    if data.get("lines"):
        pages.append(_western_page(data, profile))
    for rx in data.get("tcm") or []:
        pages.append(_tcm_page(data, rx, profile))
    return _html("".join(pages), "门诊病历 / 处方笺", profile)


def apply_print_profile(html: str, profile: dict | None = None) -> str:
    """让收据/检验/标签等非病历模板也套用机构打印外观。"""
    p = _profile(profile)
    old_name = str(settings.CLINIC_NAME or "")
    new_name = str(p.get("clinic_name") or "")
    if old_name and new_name:
        html = html.replace(escape(old_name), escape(new_name))
        html = html.replace(old_name, new_name)
    logo = _logo_html(p)
    header = (
        f'<div class="profile-header-note">{escape(p["header_note"])}</div>'
        if p.get("header_note") else ""
    )
    if logo or header:
        html = re.sub(r"(<h2[^>]*>)", logo + r"\1", html, count=1)
        html = re.sub(r"(</h2>)", r"\1" + header, html, count=1)
    extra_css = f"""
<style>
body {{ font-family: {p['font_family']}; }}
h2 {{ color: {p['theme_color']}; }}
.profile-footer {{ margin-top: 10px; border-top: 1px dotted #999; padding-top: 4px; font-size: 11px; color: #444; }}
</style>"""
    html = html.replace("</head>", extra_css + "\n</head>", 1)
    footer = (
        f'<div class="profile-footer">{escape(p["footer_note"])}</div>'
        if p.get("footer_note") else ""
    )
    if footer:
        html = html.replace("</body>", footer + "\n</body>", 1)
    custom = str(p.get("custom_css") or "").strip()
    if custom:
        html = html.replace("</head>", f"<style>{custom}</style></head>", 1)
    return html
