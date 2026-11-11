"""患者信息侧卡：基本信息、就诊信息、过敏史、现存疾病各自独立成框。"""
import re

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

from his_client.ui.theme import colors

_TIME_PATTERN = re.compile(
    r"(约|大约|近|余|多)?\s*\d+(?:\.\d+)?\s*(?:余)?\s*"
    r"(?:年|个月|月|周|天|日|小时|分钟|h|岁)"
)
_DATE_PATTERN = re.compile(r"\d{4}\s*[-/年]\s*\d{1,2}\s*[-/月]?\s*\d{0,2}\s*日?")
_PREFIX_PATTERN = re.compile(r"^(?:既往|现患|患有|有|发现|诊断|病史[:：]?)")


def condition_names(text: str) -> list[str]:
    """从自由文本中提取现存疾病名，去掉时间/年限/约数。"""
    names: list[str] = []
    for raw in re.split(r"[；;、,，\n]+", text or ""):
        value = _DATE_PATTERN.sub("", raw.strip())
        value = _TIME_PATTERN.sub("", value)
        value = re.sub(r"^前", "", value.strip())
        value = _PREFIX_PATTERN.sub("", value)
        value = re.sub(r"(?:史|病史)$", "", value.strip())
        value = re.sub(r"(?:前|余|左右|多)$", "", value).strip(" ：:，,。")
        value = re.sub(r"\s+", "", value)
        if value in ("吸烟", "饮酒", "冶游", "旅游", "旅居", "疫区接触"):
            continue
        if value and value not in ("无", "无特殊", "不详", "无病史"):
            if value not in names:
                names.append(value)
    return names


class PatientInfoPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("patientInfoPanel")
        self.setMinimumWidth(210)
        self.setMaximumWidth(280)
        c = colors()
        self.setStyleSheet(
            f"""
            #patientInfoPanel {{ background: transparent; }}
            #headerCard, #infoCard {{
                background: {c['card']};
                border: 1px solid {c['border']};
                border-radius: 8px;
            }}
            #allergyCard {{
                background: {c['card']};
                border: 1px solid {c['danger']};
                border-left: 4px solid {c['danger']};
                border-radius: 8px;
            }}
            #historyCard {{
                background: {c['card']};
                border: 1px solid {c['warning']};
                border-left: 4px solid {c['warning']};
                border-radius: 8px;
            }}
            #patientInfoPanel QLabel {{ color: {c['text']}; font-size: 12px; }}
            #patientInfoPanel QLabel#title {{
                font-size: 15px; font-weight: bold; color: {c['title']};
            }}
            #patientInfoPanel QLabel#cardTitle {{
                font-size: 12px; font-weight: bold; color: {c['muted']};
            }}
            #patientInfoPanel QLabel#allergyValue {{
                color: {c['danger']}; font-weight: bold;
            }}
            #patientInfoPanel QLabel#historyValue {{
                color: {c['warning']}; font-weight: bold;
            }}
            """
        )
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)

        header = QFrame()
        header.setObjectName("headerCard")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(10, 8, 10, 8)
        header_layout.setSpacing(3)
        self.title = QLabel("当前患者")
        self.title.setObjectName("title")
        self.name = QLabel("未选择")
        self.name.setStyleSheet(f"font-size:16px;font-weight:bold;color:{c['title']};")
        self.demo = QLabel("")
        header_layout.addWidget(self.title)
        header_layout.addWidget(self.name)
        header_layout.addWidget(self.demo)
        outer.addWidget(header)

        info = QFrame()
        info.setObjectName("infoCard")
        info_layout = QVBoxLayout(info)
        info_layout.setContentsMargins(10, 7, 10, 7)
        info_layout.setSpacing(2)
        self.encounter = QLabel("")
        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.phone = QLabel("")
        self.extra = QLabel("")
        self.extra.setWordWrap(True)
        for widget in (self.encounter, self.status, self.phone, self.extra):
            info_layout.addWidget(widget)
        outer.addWidget(info)

        allergy_card = QFrame()
        allergy_card.setObjectName("allergyCard")
        allergy_layout = QVBoxLayout(allergy_card)
        allergy_layout.setContentsMargins(10, 7, 10, 7)
        allergy_layout.setSpacing(2)
        allergy_title = QLabel("过敏史")
        allergy_title.setObjectName("cardTitle")
        self.allergy = QLabel("过敏史不详")
        self.allergy.setObjectName("allergyValue")
        self.allergy.setWordWrap(True)
        allergy_layout.addWidget(allergy_title)
        allergy_layout.addWidget(self.allergy)
        outer.addWidget(allergy_card)

        history_card = QFrame()
        history_card.setObjectName("historyCard")
        history_layout = QVBoxLayout(history_card)
        history_layout.setContentsMargins(10, 7, 10, 7)
        history_layout.setSpacing(2)
        history_title = QLabel("现存疾病")
        history_title.setObjectName("cardTitle")
        self.history = QLabel("无特殊")
        self.history.setObjectName("historyValue")
        self.history.setWordWrap(True)
        history_layout.addWidget(history_title)
        history_layout.addWidget(self.history)
        outer.addWidget(history_card)
        self.history_card = history_card

        outer.addStretch(1)
        self.patient_id = 0
        self.encounter_id = 0

    def set_patient(
        self,
        patient: dict | None,
        encounter_id: int | None = None,
        status: str = "",
        extra: str = "",
    ) -> None:
        if not patient:
            self.clear()
            return
        self.patient_id = int(patient.get("id") or 0)
        self.encounter_id = int(encounter_id or patient.get("encounter_id") or 0)
        gender = {"male": "男", "female": "女"}.get(patient.get("gender"), "不详")
        age = patient.get("age")
        self.name.setText(str(patient.get("name") or "未命名"))
        self.demo.setText(
            f"{gender} / {age if age is not None else '—'}岁  "
            f"{patient.get('patient_no') or ''}"
        )
        allergy = patient.get("allergy_label") or "过敏史不详"
        self.allergy.setText(allergy)
        conditions = condition_names(patient.get("special_history") or "")
        self.history.setText("、".join(conditions))
        self.history_card.setVisible(bool(conditions))
        self.encounter.setText(
            f"就诊：{self.encounter_id}" if self.encounter_id else "就诊：未接诊"
        )
        self.status.setText(f"状态：{status}" if status else "")
        self.phone.setText(f"电话：{patient.get('phone') or '—'}")
        self.extra.setText(extra)
        self.extra.setVisible(bool(extra))

    def clear(self) -> None:
        self.patient_id = 0
        self.encounter_id = 0
        self.name.setText("未选择")
        self.demo.setText("")
        self.allergy.setText("过敏史不详")
        self.history.setText("")
        self.history_card.setVisible(False)
        self.encounter.setText("")
        self.status.setText("")
        self.phone.setText("")
        self.extra.setText("")
        self.extra.setVisible(False)
