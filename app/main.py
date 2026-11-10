import asyncio

from fastapi import FastAPI, Request
from sqlalchemy.exc import OperationalError
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import JSONResponse, Response

from app import settings

from app.database import get_db
from app.modules.idempotency import service as idempotency
from app.modules.patient.router import router as patient_router
from app.modules.registration.router import router as registration_router
from app.modules.registration.router import schedule_router
from app.modules.encounter.router import router as encounter_router
from app.modules.billing.router import router as billing_router
from app.modules.pharmacy.router import router as pharmacy_router
from app.modules.staff.router import router as staff_router
from app.modules.drug.router import router as drug_router
from app.modules.auth.router import router as auth_router
from app.modules.inpatient.router import router as inpatient_router
from app.modules.triage.router import router as triage_router
from app.modules.lis.router import router as lis_router
from app.modules.pacs.router import router as pacs_router
from app.modules.warehouse.router import router as warehouse_router
from app.modules.materials.router import router as materials_router
from app.modules.supplier.router import router as supplier_router
from app.modules.pathway.router import router as pathway_router
from app.modules.finance.router import router as finance_router
from app.modules.bi.router import router as bi_router
from app.modules.bi.executive_router import router as bi_executive_router
from app.modules.performance.router import router as performance_router
from app.modules.hr.router import router as hr_router
from app.modules.integration.router import router as integration_router
from app.modules.dict.router import router as dict_router
from app.modules.publichealth.router import router as publichealth_router
from app.modules.ca.router import router as ca_router
from app.modules.portal.router import router as portal_router
from app.modules.kiosk.router import router as kiosk_router
from app.modules.print.router import router as print_router
from app.modules.charges.router import router as charges_router
from app.modules.treatment.router import router as treatment_router
from app.modules.appointment.router import router as appointment_router
from app.modules.facility.router import router as facility_router
from app.modules.sms.router import router as sms_router
from app.modules.receiving.router import router as receiving_router
from app.modules.insurance_catalog.router import router as insurance_catalog_router
from app.modules.stock_ledger.router import router as stock_ledger_router
from app.modules.traceability.router import router as traceability_router
from app.modules.linen.router import router as linen_router
from app.modules.cssd.router import router as cssd_router
from app.modules.archive.router import router as archive_router
from app.modules.nursing.router import router as nursing_router
from app.modules.tcm.router import router as tcm_router
from app.modules.insurance.router import router as insurance_router
from app.modules.gsp.router import router as gsp_router
from app.modules.surgery.router import router as surgery_router
from app.modules.treatment_room.router import router as treatment_room_router
from app.modules.cashier.router import router as cashier_router
from app.modules.invoice.router import router as invoice_router
from app.modules.procedure_materials import models as procedure_material_models  # noqa: F401
from app.modules.insurance_inventory.router import router as insurance_inventory_router
from app.modules.insurance_materials.router import router as insurance_materials_router
from app.modules.reports.router import router as reports_router
from app.modules.review.router import router as review_router
from app.modules.admin.router import router as admin_router
from app.modules.download.router import router as download_router
from app.modules.auth.service import log_action

# 表结构由 Alembic 管理：uv run alembic upgrade head
app = FastAPI(title="HIS")

_IDEMPOTENT_METHODS = ("POST", "PUT", "PATCH", "DELETE")
_IDEMPOTENCY_HEADER = "Idempotency-Key"


@app.middleware("http")
async def idempotency_middleware(request: Request, call_next):
    """幂等键：写请求带 Idempotency-Key 时，重放返回首次响应，不重复执行。

    机制：原子占位（唯一约束）→ 执行 → 缓存响应；并发同 key 时短暂等待，
    仍在处理中返回 409；5xx/异常释放占位允许重试。
    """
    key = (request.headers.get(_IDEMPOTENCY_HEADER) or "").strip()[:100]
    if request.method not in _IDEMPOTENT_METHODS or not key:
        return await call_next(request)

    endpoint = f"{request.method} {request.url.path}"

    reserved = await asyncio.to_thread(idempotency.reserve, key, endpoint)
    if not reserved:
        cached = await asyncio.to_thread(
            idempotency.wait_for_cached, key, endpoint, 2.0
        )
        if cached is None:
            return JSONResponse(
                status_code=409,
                content={"detail": "请求正在处理中，请稍后重试"},
            )
        status_code, body = cached
        return Response(
            content=body,
            status_code=status_code,
            media_type="application/json",
            headers={"Idempotent-Replayed": "true"},
        )

    try:
        response = await call_next(request)
    except Exception:
        await asyncio.to_thread(idempotency.release, key, endpoint)
        raise

    chunks = []
    async for chunk in response.body_iterator:
        chunks.append(chunk.encode() if isinstance(chunk, str) else chunk)
    body = b"".join(chunks)

    if response.status_code >= 500:
        await asyncio.to_thread(idempotency.release, key, endpoint)
    else:
        await asyncio.to_thread(
            idempotency.store_response,
            key,
            endpoint,
            response.status_code,
            body.decode("utf-8", "replace"),
        )

    headers = {
        name: value
        for name, value in response.headers.items()
        if name.lower() != "content-length"
    }
    return Response(
        content=body,
        status_code=response.status_code,
        headers=headers,
        media_type=response.media_type,
    )


def _write_audit_safely(username: str, role: str, method: str, path: str, status_code: int) -> None:
    """审计日志写入：并发锁冲突时重试，最终失败也不阻断业务响应。

    审计是旁路能力——不能因为日志写不进去就把已成功的业务请求变成 500。
    """
    for attempt in range(3):
        db = next(get_db())
        try:
            log_action(
                db=db,
                username=username,
                role=role,
                method=method,
                path=path,
                status_code=status_code,
            )
            return
        except OperationalError:
            db.rollback()
        finally:
            db.close()


@app.middleware("http")
async def audit_middleware(request: Request, call_next):
    response = await call_next(request)
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        # 使用认证时保存的字符串，避免 ORM 对象在会话关闭/回滚后过期
        await asyncio.to_thread(
            _write_audit_safely,
            getattr(request.state, "user_name", None) or "anonymous",
            getattr(request.state, "user_role", None) or "-",
            request.method,
            request.url.path,
            response.status_code,
        )
    return response


app.include_router(patient_router)
app.include_router(registration_router)
app.include_router(schedule_router)
app.include_router(encounter_router)
app.include_router(billing_router)
app.include_router(pharmacy_router)
app.include_router(staff_router)
app.include_router(drug_router)
app.include_router(auth_router)
app.include_router(inpatient_router)
app.include_router(triage_router)
app.include_router(lis_router)
app.include_router(pacs_router)
app.include_router(warehouse_router)
app.include_router(materials_router)
app.include_router(supplier_router)
app.include_router(pathway_router)
app.include_router(finance_router)
app.include_router(bi_router)
app.include_router(bi_executive_router)
app.include_router(performance_router)
app.include_router(hr_router)
app.include_router(integration_router)
app.include_router(dict_router)
app.include_router(publichealth_router)
app.include_router(ca_router)
app.include_router(portal_router)
app.include_router(kiosk_router)
app.include_router(print_router)
app.include_router(charges_router)
app.include_router(treatment_router)
app.include_router(appointment_router)
app.include_router(facility_router)
app.include_router(sms_router)
app.include_router(receiving_router)
app.include_router(insurance_catalog_router)
app.include_router(stock_ledger_router)
app.include_router(traceability_router)
app.include_router(linen_router)
app.include_router(cssd_router)
app.include_router(archive_router)
app.include_router(nursing_router)
app.include_router(tcm_router)
app.include_router(insurance_router)
app.include_router(gsp_router)
app.include_router(surgery_router)
app.include_router(treatment_room_router)
app.include_router(cashier_router)
app.include_router(invoice_router)
app.include_router(insurance_inventory_router)
app.include_router(insurance_materials_router)
app.include_router(reports_router)
app.include_router(review_router)

# 管理台会话（签名 Cookie）；生产请通过 HIS_SECRET_KEY 环境变量或 config.ini 注入
app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)
app.include_router(admin_router)
app.include_router(download_router)
