from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_role
from app.modules.materials.schemas import MaterialItemResponse

from .schemas import (
    InsuranceMaterialResponse,
    MaterialImportResult,
    MaterialSyncRequest,
)
from .service import (
    ensure_material_item,
    get_by_code,
    import_bytes,
    search,
    sync_from_url,
)

router = APIRouter(prefix="/insurance/materials", tags=["insurance-materials"])


@router.post("/import", response_model=MaterialImportResult)
async def import_materials(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="文件为空")
    try:
        return import_bytes(
            db, data, file.filename or "materials.csv", imported_by=user.username
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/sync", response_model=MaterialImportResult)
def sync_materials(
    data: MaterialSyncRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    try:
        return sync_from_url(db, data.url, imported_by=user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/search", response_model=list[InsuranceMaterialResponse])
def search_materials(
    q: str | None = None,
    category: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("warehouse", "pharmacist")),
):
    return search(db, q, category, limit, offset)


@router.post("/{code}/ensure-item", response_model=MaterialItemResponse)
def ensure_item(
    code: str,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin", "warehouse")),
):
    try:
        return ensure_material_item(db, code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{code}", response_model=InsuranceMaterialResponse)
def get_one(code: str, db: Session = Depends(get_db)):
    entry = get_by_code(db, code)
    if not entry:
        raise HTTPException(status_code=404, detail="耗材目录中无此编码")
    return entry
