"""医保医用耗材目录：CSV/XLSX 导入、检索、落地为本地物资。"""
import csv
import hashlib
import io
from datetime import datetime

import requests
from sqlalchemy.orm import Session

from app.modules.materials.models import MaterialItem

from .models import InsuranceMaterial

_HEADER_MAP = {
    "code": "code",
    "医用耗材编码": "code",
    "医保耗材编码": "code",
    "耗材编码": "code",
    "医保代码": "code",
    "材料编码": "code",
    "name": "name",
    "耗材名称": "name",
    "医用耗材名称": "name",
    "材料名称": "name",
    "名称": "name",
    "category": "category",
    "类别": "category",
    "医保类别": "category",
    "材料类别": "category",
    "分类": "category",
    "spec": "spec",
    "规格": "spec",
    "model": "model",
    "型号": "model",
    "规格型号": "model",
    "manufacturer": "manufacturer",
    "生产厂家": "manufacturer",
    "生产企业": "manufacturer",
    "unit": "unit",
    "单位": "unit",
    "material_type": "material_type",
    "耗材类型": "material_type",
    "类型": "material_type",
    "registration_no": "registration_no",
    "注册证号": "registration_no",
    "注册证编号": "registration_no",
    "note": "note",
    "备注": "note",
    "限定支付范围": "note",
}


def _map_row(row: dict) -> dict:
    data = {}
    for key, value in row.items():
        field = _HEADER_MAP.get(str(key).strip())
        if field and value is not None:
            data[field] = str(value).strip()
    return data


def _read_csv(data: bytes) -> list[dict]:
    text = None
    for encoding in ("utf-8-sig", "gbk"):
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise ValueError("无法识别文件编码（支持 UTF-8/GBK）")
    reader = csv.DictReader(io.StringIO(text))
    return [_map_row(row) for row in reader]


def _read_xlsx(data: bytes) -> list[dict]:
    from openpyxl import load_workbook

    workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    sheet = workbook.active
    rows = sheet.iter_rows(values_only=True)
    headers = [str(cell).strip() if cell is not None else "" for cell in next(rows)]
    result = []
    for values in rows:
        row = {
            headers[index]: value
            for index, value in enumerate(values)
            if index < len(headers)
        }
        result.append(_map_row(row))
    workbook.close()
    return result


def parse_bytes(data: bytes, file_name: str) -> list[dict]:
    lower = file_name.lower()
    if lower.endswith(".xlsx") or lower.endswith(".xlsm"):
        rows = _read_xlsx(data)
    elif lower.endswith(".csv") or lower.endswith(".txt"):
        rows = _read_csv(data)
    else:
        raise ValueError("仅支持 CSV/XLSX 文件")
    if not rows:
        raise ValueError("文件没有数据行")
    return rows


def import_bytes(
    db: Session, data: bytes, file_name: str, imported_by: str = ""
) -> dict:
    rows = parse_bytes(data, file_name)
    inserted = updated = total = 0
    for row in rows:
        code = row.get("code", "")
        name = row.get("name", "")
        if not code or not name:
            continue
        total += 1
        entry = (
            db.query(InsuranceMaterial)
            .filter(InsuranceMaterial.code == code)
            .first()
        )
        if entry:
            entry.name = name
            entry.category = row.get("category", entry.category)
            entry.spec = row.get("spec", entry.spec)
            entry.model = row.get("model", entry.model)
            entry.manufacturer = row.get("manufacturer", entry.manufacturer)
            entry.unit = row.get("unit", entry.unit)
            entry.material_type = row.get("material_type", entry.material_type)
            entry.registration_no = row.get(
                "registration_no", entry.registration_no
            )
            entry.note = row.get("note", entry.note)
            entry.updated_at = datetime.now()
            updated += 1
        else:
            db.add(
                InsuranceMaterial(
                    code=code,
                    name=name,
                    category=row.get("category", ""),
                    spec=row.get("spec", ""),
                    model=row.get("model", ""),
                    manufacturer=row.get("manufacturer", ""),
                    unit=row.get("unit", ""),
                    material_type=row.get("material_type", "耗材") or "耗材",
                    registration_no=row.get("registration_no", ""),
                    note=row.get("note", ""),
                )
            )
            inserted += 1
    if total == 0:
        raise ValueError("没有识别到有效耗材行（需包含编码与名称列）")
    db.commit()
    return {"total": total, "inserted": inserted, "updated": updated}


def sync_from_url(db: Session, url: str, imported_by: str = "") -> dict:
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        raise ValueError(f"拉取耗材目录失败：{e}")
    file_name = url.split("?")[0].rsplit("/", 1)[-1] or "materials.csv"
    return import_bytes(db, response.content, file_name, imported_by)


def get_by_code(db: Session, code: str) -> InsuranceMaterial | None:
    return (
        db.query(InsuranceMaterial)
        .filter(InsuranceMaterial.code == code.strip())
        .first()
    )


def search(
    db: Session,
    q: str | None = None,
    category: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[InsuranceMaterial]:
    query = db.query(InsuranceMaterial)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(
            InsuranceMaterial.name.like(like)
            | InsuranceMaterial.code.like(like)
            | InsuranceMaterial.manufacturer.like(like)
        )
    if category:
        query = query.filter(InsuranceMaterial.category == category)
    return (
        query.order_by(InsuranceMaterial.id)
        .offset(max(offset, 0))
        .limit(min(max(limit, 1), 500))
        .all()
    )


def ensure_material_item(db: Session, code: str) -> MaterialItem:
    """把医保耗材目录落地/复用为本地物资（入库下拉用）。"""
    entry = get_by_code(db, code)
    if not entry:
        raise ValueError("医保耗材目录中无此编码")

    item = (
        db.query(MaterialItem)
        .filter(MaterialItem.insurance_code == entry.code)
        .first()
    )
    if item:
        return item

    local_code = entry.code if len(entry.code) <= 30 else "HC" + hashlib.md5(
        entry.code.encode("utf-8")
    ).hexdigest()[:12].upper()
    while (
        db.query(MaterialItem)
        .filter(MaterialItem.code == local_code)
        .first()
    ):
        local_code = "HC" + hashlib.md5(
            (entry.code + local_code).encode("utf-8")
        ).hexdigest()[:12].upper()

    material_type = (entry.material_type or "").strip()
    if "器械" in material_type or material_type.lower() == "device":
        category = "device"
    elif "办公" in material_type or material_type.lower() == "office":
        category = "office"
    else:
        category = "consumable"

    item = MaterialItem(
        code=local_code,
        name=entry.name,
        spec=entry.spec or entry.model,
        unit=entry.unit,
        price=0.0,
        category=category,
        manufacturer=entry.manufacturer,
        registration_no=entry.registration_no,
        insurance_code=entry.code,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item
