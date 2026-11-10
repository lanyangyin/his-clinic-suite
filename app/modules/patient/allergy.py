"""患者过敏史与药品名称的交叉核对（门诊 P0 安全规则）。

说明：这是名称/类别级别的初筛，不替代药师审方；目的是一次拦截明确冲突。
"""
import re

# (类别, 患者过敏史关键词, 药品名称关键词)
ALLERGY_GROUPS = (
    (
        "青霉素类",
        ("青霉素", "阿莫西林", "氨苄西林", "哌拉西林", "苄星青霉素", "阿莫仙"),
        ("青霉素", "阿莫西林", "氨苄西林", "哌拉西林", "苄星青霉素"),
    ),
    (
        "头孢菌素类",
        ("头孢", "先锋"),
        ("头孢", "先锋"),
    ),
    (
        "磺胺类",
        ("磺胺", "新诺明", "复方新诺明"),
        ("磺胺", "新诺明"),
    ),
    (
        "碘造影剂",
        ("碘", "造影剂"),
        ("碘", "造影"),
    ),
    (
        "阿司匹林",
        ("阿司匹林", "拜阿司匹灵", "乙酰水杨酸"),
        ("阿司匹林", "拜阿司匹灵", "乙酰水杨酸"),
    ),
    (
        "酒精/乙醇",
        ("酒精", "乙醇"),
        ("酒精", "乙醇", "酊"),
    ),
)


def _terms(text: str) -> list[str]:
    return [part for part in re.split(r"[,，/;；、\s]+", text or "") if len(part) >= 2]


def allergy_conflict(allergy_detail: str, drug_name: str) -> str | None:
    """返回冲突说明；无冲突返回 None。"""
    detail = (allergy_detail or "").strip()
    name = (drug_name or "").strip()
    if not detail or not name:
        return None

    for label, patient_terms, drug_terms in ALLERGY_GROUPS:
        patient_hit = next((term for term in patient_terms if term in detail), "")
        if not patient_hit:
            continue
        drug_hit = next((term for term in drug_terms if term in name), "")
        if drug_hit:
            return f"{label}：患者过敏史「{detail}」与药品「{name}」存在交叉过敏风险"

    for term in _terms(detail):
        if term in name:
            return f"患者过敏史「{detail}」与药品「{name}」名称匹配"
    return None
