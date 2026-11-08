"""医保药品目录：导入（CSV/XLSX）、检索、版本、URL 同步。

真实医保目录需从医保局官方渠道获取表格（Excel/CSV），本模块负责：
- 手动上传导入（保留版本与校验和）
- 从配置的 URL 拉取更新（自动/手动）
- 内容未变化时自动跳过（checksum 比对）
"""
import csv
import hashlib
import io
from datetime import date, datetime
from pathlib import Path

import requests
from sqlalchemy.orm import Session

from .models import InsuranceCatalogVersion, InsuranceDrug
from app.modules.drug.models import Drug

# 表头映射：兼容常见中英文列名
_HEADER_MAP = {
    "national_code": "national_code",
    "医保代码": "national_code",
    "医保编码": "national_code",
    "国家医保代码": "national_code",
    "国家医保药品代码": "national_code",
    "药品代码": "national_code",
    "name": "name",
    "药品名称": "name",
    "通用名": "name",
    "药品通用名": "name",
    "dosage_form": "dosage_form",
    "剂型": "dosage_form",
    "spec": "spec",
    "规格": "spec",
    "manufacturer": "manufacturer",
    "生产厂家": "manufacturer",
    "生产企业": "manufacturer",
    "unit": "unit",
    "单位": "unit",
    "category": "category",
    "医保类别": "category",
    "甲乙类": "category",
    "类别": "category",
    "reimbursement_note": "reimbursement_note",
    "限定支付范围": "reimbursement_note",
    "备注": "reimbursement_note",
    "approval_no": "approval_no",
    "批准文号": "approval_no",
    "valid_from": "valid_from",
    "有效期起": "valid_from",
    "valid_to": "valid_to",
    "有效期止": "valid_to",
}

_DATE_FIELDS = ("valid_from", "valid_to")


def _norm_header(value) -> str:
    text = str(value or "").strip()
    return _HEADER_MAP.get(text, _HEADER_MAP.get(text.lower(), text.lower()))


def _norm_category(value) -> str:
    text = str(value or "").strip()
    if "甲" in text:
        return "甲"
    if "丙" in text or "自费" in text:
        return "丙"
    return "乙"


def _parse_date(value) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip().replace("/", "-").replace(".", "-")
    if len(text) == 8 and text.isdigit():
        text = f"{text[:4]}-{text[4:6]}-{text[6:]}"
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _rows_to_dicts(headers: list, rows: list) -> list[dict]:
    keys = [_norm_header(h) for h in headers]
    result = []
    for row in rows:
        values = list(row)
        record = {}
        for index, key in enumerate(keys):
            if not key:
                continue
            record[key] = values[index] if index < len(values) else None
        if record.get("national_code") and record.get("name"):
            result.append(record)
    return result


def _parse_csv(data: bytes) -> list[dict]:
    for encoding in ("utf-8-sig", "gbk", "utf-8"):
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError("CSV 编码无法识别（支持 UTF-8/GBK）")

    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return []
    return _rows_to_dicts(rows[0], rows[1:])


def _parse_xlsx(data: bytes) -> list[dict]:
    from openpyxl import load_workbook

    workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    sheet = workbook.active
    rows = list(sheet.iter_rows(values_only=True))
    workbook.close()
    if not rows:
        return []
    return _rows_to_dicts(list(rows[0]), rows[1:])


def parse_file(data: bytes, file_name: str) -> list[dict]:
    suffix = Path(file_name or "").suffix.lower()
    if suffix in (".xlsx", ".xlsm"):
        return _parse_xlsx(data)
    return _parse_csv(data)


def import_bytes(
    db: Session,
    data: bytes,
    file_name: str,
    source: str = "manual",
    imported_by: str = "",
) -> dict:
    """导入目录文件：按贯标码 upsert；内容未变化则跳过。"""
    checksum = hashlib.sha256(data).hexdigest()
    latest = (
        db.query(InsuranceCatalogVersion)
        .order_by(InsuranceCatalogVersion.id.desc())
        .first()
    )
    if latest and latest.checksum == checksum:
        return {
            "status": "unchanged",
            "version": latest.version,
            "inserted": 0,
            "updated": 0,
            "skipped": 0,
            "row_count": latest.row_count,
            "checksum": checksum,
        }

    rows = parse_file(data, file_name)
    if not rows:
        return {
            "status": "skipped",
            "version": None,
            "inserted": 0,
            "updated": 0,
            "skipped": 0,
            "row_count": 0,
            "checksum": checksum,
        }

    version = f"V{(latest.id + 1) if latest else 1:04d}"
    inserted = updated = skipped = 0
    for row in rows:
        code = str(row["national_code"]).strip()
        if not code:
            skipped += 1
            continue
        existing = (
            db.query(InsuranceDrug)
            .filter(InsuranceDrug.national_code == code)
            .first()
        )
        values = {
            "name": str(row.get("name") or "").strip()[:100],
            "dosage_form": str(row.get("dosage_form") or "").strip()[:30],
            "spec": str(row.get("spec") or "").strip()[:60],
            "manufacturer": str(row.get("manufacturer") or "").strip()[:100],
            "unit": str(row.get("unit") or "").strip()[:20],
            "category": _norm_category(row.get("category")),
            "reimbursement_note": str(row.get("reimbursement_note") or "").strip()[:200],
            "approval_no": str(row.get("approval_no") or "").strip()[:60],
            "valid_from": _parse_date(row.get("valid_from")),
            "valid_to": _parse_date(row.get("valid_to")),
            "source_version": version,
            "updated_at": datetime.now(),
        }
        if existing:
            changed = any(getattr(existing, k) != v for k, v in values.items())
            if changed:
                for key, value in values.items():
                    setattr(existing, key, value)
                updated += 1
            else:
                skipped += 1
        else:
            db.add(InsuranceDrug(national_code=code, **values))
            inserted += 1

    db.add(
        InsuranceCatalogVersion(
            version=version,
            source=source,
            file_name=(file_name or "")[:200],
            row_count=len(rows),
            checksum=checksum,
            imported_by=imported_by,
        )
    )
    db.commit()
    return {
        "status": "created",
        "version": version,
        "inserted": inserted,
        "updated": updated,
        "skipped": skipped,
        "row_count": len(rows),
        "checksum": checksum,
    }


def search(
    db: Session,
    keyword: str | None = None,
    category: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[InsuranceDrug]:
    query = db.query(InsuranceDrug)
    if keyword:
        like = f"%{keyword.strip()}%"
        query = query.filter(
            (InsuranceDrug.name.like(like))
            | (InsuranceDrug.national_code.like(like))
            | (InsuranceDrug.manufacturer.like(like))
        )
    if category:
        query = query.filter(InsuranceDrug.category == category)
    return (
        query.order_by(InsuranceDrug.id)
        .offset(max(offset, 0))
        .limit(min(max(limit, 1), 200))
        .all()
    )


def get_by_code(db: Session, national_code: str) -> InsuranceDrug | None:
    return (
        db.query(InsuranceDrug)
        .filter(InsuranceDrug.national_code == national_code)
        .first()
    )


def list_versions(db: Session, limit: int = 20) -> list[InsuranceCatalogVersion]:
    return (
        db.query(InsuranceCatalogVersion)
        .order_by(InsuranceCatalogVersion.id.desc())
        .limit(limit)
        .all()
    )


def sync_from_url(
    db: Session, url: str, imported_by: str = "", timeout: int = 30
) -> dict:
    """从 URL 拉取目录文件并导入（自动更新入口）。"""
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as e:
        raise ValueError(f"拉取目录失败：{e}")

    file_name = Path(url.split("?")[0]).name or "insurance_catalog.csv"
    return import_bytes(
        db,
        response.content,
        file_name=file_name,
        source="auto",
        imported_by=imported_by,
    )

# ---------- 药品与医保目录对码 ----------
def _norm(text) -> str:
    return "".join(str(text or "").split()).replace("（", "(").replace("）", ")").lower()


def _candidates(db: Session, drug) -> list[InsuranceDrug]:
    """按贯标码优先，其次名称+剂型+规格匹配候选。"""
    if drug.insurance_code:
        entry = (
            db.query(InsuranceDrug)
            .filter(InsuranceDrug.national_code == drug.insurance_code)
            .first()
        )
        if entry:
            return [entry]

    if not drug.name:
        return []
    rows = db.query(InsuranceDrug).filter(InsuranceDrug.name == drug.name).all()
    if not rows:
        # 容错：忽略空格/全角字符差异
        rows = [
            row
            for row in db.query(InsuranceDrug).all()
            if _norm(row.name) == _norm(drug.name)
        ]
    candidates = []
    for row in rows:
        if drug.dosage_form and _norm(row.dosage_form) != _norm(drug.dosage_form):
            continue
        if drug.spec and _norm(row.spec) != _norm(drug.spec):
            continue
        candidates.append(row)
    return candidates


def analyze_drug(db: Session, drug) -> tuple[str, InsuranceDrug | None, list]:
    """对单个药品做对码，返回 (matched/ambiguous/unmatched, 命中目录, 候选)。"""
    candidates = _candidates(db, drug)
    if len(candidates) == 1:
        entry = candidates[0]
        drug.insurance_match_status = "matched"
        drug.insurance_category = (entry.category or "").rstrip("类")
        if not drug.insurance_code:
            drug.insurance_code = entry.national_code
        return "matched", entry, candidates
    if len(candidates) > 1:
        drug.insurance_match_status = "ambiguous"
        drug.insurance_category = ""
        return "ambiguous", None, candidates
    drug.insurance_match_status = "unmatched"
    drug.insurance_category = ""
    return "unmatched", None, []


def match_all(db: Session, only_unmatched: bool = False) -> dict:
    """批量对码：按贯标码/名称+剂型+规格匹配全部药品。"""
    query = db.query(Drug)
    if only_unmatched:
        query = query.filter(Drug.insurance_match_status != "matched")
    stats = {"total": 0, "matched": 0, "ambiguous": 0, "unmatched": 0}
    for drug in query.order_by(Drug.id).all():
        status, _entry, _candidates = analyze_drug(db, drug)
        stats["total"] += 1
        stats[status] += 1
    db.commit()
    return stats


def list_matches(db: Session, status: str | None = None) -> list[dict]:
    """药品对码状态列表（含命中目录名称）。"""
    query = db.query(Drug)
    if status:
        query = query.filter(Drug.insurance_match_status == status)
    cache: dict[str, InsuranceDrug] = {}
    result = []
    for drug in query.order_by(Drug.id).all():
        entry = None
        if drug.insurance_code:
            if drug.insurance_code not in cache:
                cache[drug.insurance_code] = (
                    db.query(InsuranceDrug)
                    .filter(InsuranceDrug.national_code == drug.insurance_code)
                    .first()
                )
            entry = cache[drug.insurance_code]
        result.append(
            {
                "drug_id": drug.id,
                "name": drug.name,
                "spec": drug.spec,
                "dosage_form": drug.dosage_form,
                "insurance_code": drug.insurance_code,
                "insurance_category": drug.insurance_category,
                "insurance_match_status": drug.insurance_match_status,
                "insurance_ratio": drug.insurance_ratio,
                "catalog_name": entry.name if entry else "",
                "catalog_category": entry.category if entry else "",
            }
        )
    return result


def resolve_prescription_insurance(db: Session, drug) -> tuple[str, float, str | None]:
    """处方/收费目录校验：返回 (类别, 报销比例快照, 提示)。

    - 命中目录：甲类 100%，乙类按药品维护比例，丙类自费。
    - 有医保代码但未匹配：按自费。
    - 未对码药品：保留原有手工比例（兼容历史），不强制自费。
    """
    entry = None
    if drug.insurance_code:
        entry = (
            db.query(InsuranceDrug)
            .filter(InsuranceDrug.national_code == drug.insurance_code)
            .first()
        )
    if entry is None:
        candidates = _candidates(db, drug)
        if len(candidates) == 1:
            entry = candidates[0]

    if entry is not None:
        category = (entry.category or "").rstrip("类")
        if category == "甲":
            ratio = 1.0
        elif category == "丙":
            ratio = 0.0
        else:
            ratio = drug.insurance_ratio
        if category == "丙":
            warning = "医保目录：丙类（自费）"
        else:
            warning = f"医保目录：{category or '未标注'}类"
        return category, ratio, warning

    if drug.insurance_code:
        return "", 0.0, "医保代码未匹配目录，按自费结算"
    return "", drug.insurance_ratio, None
