from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_role

from .schemas import (
    CatalogImportResult,
    CatalogSyncRequest,
    CatalogVersionResponse,
    InsuranceDrugResponse,
)
from .service import (
    get_by_code,
    import_bytes,
    list_matches,
    list_versions,
    match_all,
    resolve_prescription_insurance,
    search,
    sync_from_url,
)
from app.modules.drug.service import get_drug

router = APIRouter(prefix="/insurance/catalog", tags=["insurance-catalog"])


@router.post("/import", response_model=CatalogImportResult)
async def import_catalog(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    """手动导入医保药品目录（CSV/XLSX）。"""
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="文件为空")
    try:
        return import_bytes(
            db,
            data,
            file_name=file.filename or "catalog.csv",
            source="manual",
            imported_by=user.username,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/search", response_model=list[InsuranceDrugResponse])
def search_catalog(
    q: str | None = None,
    category: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    return search(db, q, category, limit, offset)


@router.get("/versions", response_model=list[CatalogVersionResponse])
def get_versions(limit: int = 20, db: Session = Depends(get_db)):
    return list_versions(db, limit)


@router.post("/sync", response_model=CatalogImportResult)
def sync_catalog(
    data: CatalogSyncRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    """从 URL 拉取目录更新（手动触发；也可用脚本定时执行）。"""
    try:
        return sync_from_url(db, data.url, imported_by=user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/matches")
def get_matches(
    status: str | None = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    """药品对码状态列表（matched/ambiguous/unmatched）。"""
    return list_matches(db, status)


@router.post("/match")
def run_match(
    only_unmatched: bool = True,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    """批量对码：按贯标码优先，其次名称+剂型+规格。"""
    return match_all(db, only_unmatched=only_unmatched)


@router.get("/resolve/{drug_id}")
def resolve_drug_insurance(
    drug_id: int,
    db: Session = Depends(get_db),
):
    """查询单个药品的目录校验结果（类别/报销比例/提示）。"""
    drug = get_drug(db, drug_id)
    if not drug:
        raise HTTPException(status_code=404, detail="药品不存在")
    category, ratio, warning = resolve_prescription_insurance(db, drug)
    return {
        "drug_id": drug.id,
        "name": drug.name,
        "insurance_code": drug.insurance_code,
        "insurance_match_status": drug.insurance_match_status,
        "category": category,
        "ratio": ratio,
        "warning": warning,
    }


@router.get("/{national_code}", response_model=InsuranceDrugResponse)
def get_one(national_code: str, db: Session = Depends(get_db)):
    drug = get_by_code(db, national_code)
    if not drug:
        raise HTTPException(status_code=404, detail="医保目录中无此药品")
    return drug
