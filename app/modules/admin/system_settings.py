"""网页可维护的系统参数：数据库持久化 + 运行时应用到 app.settings。"""
from datetime import datetime

from sqlalchemy.orm import Session

from app import settings
from app.modules.admin.models import SystemSetting

# key, label, group, type, secret, mutable(无需重启)
FIELDS = [
    ("CLINIC_NAME", "机构名称", "机构", "str", False, True),
    ("CLINIC_ADDRESS", "机构地址", "机构", "str", False, True),
    ("CLINIC_PHONE", "机构电话", "机构", "str", False, True),
    ("REQUIRE_PRESCRIPTION_REVIEW", "处方需药师审核", "业务开关", "bool", False, True),
    ("PAYMENT_ALLOW_MOCK", "允许支付模拟", "业务开关", "bool", False, True),
    ("ALLOW_ANONYMOUS_READ", "允许匿名只读", "业务开关", "bool", False, True),
    ("REFUND_APPROVAL_THRESHOLD", "退费审批阈值", "业务开关", "float", False, True),
    ("NURSING_REQUIRE_PAID_DISPENSED", "护理要求已收费已发药", "业务开关", "bool", False, True),
    ("SURGERY_REQUIRE_SIGNATURES", "手术强制三方签名", "业务开关", "bool", False, True),
    ("LIS_REQUIRE_SAMPLE", "检验要求采样签收", "业务开关", "bool", False, True),
    ("PORTAL_REQUIRE_OTP", "患者门户要求短信验证码", "业务开关", "bool", False, True),
    ("NOTIFY_AUTO_DISPATCH", "通知自动派发", "业务开关", "bool", False, True),
    ("NOTIFY_DISPATCH_INTERVAL", "通知派发间隔秒", "业务开关", "int", False, True),
    ("INSURANCE_ENABLED", "启用医保业务", "医保", "bool", False, True),
    ("INSURANCE_ALLOW_MOCK", "允许医保 Mock", "医保", "bool", False, True),
    ("INSURANCE_GATEWAY_URL", "医保网关地址", "医保", "str", False, True),
    ("INSURANCE_GATEWAY_TOKEN", "医保网关令牌", "医保", "str", True, True),
    ("INSURANCE_PRESCRIPTION_UPLOAD_URL", "处方上传地址", "医保", "str", False, True),
    ("INSURANCE_PRESCRIPTION_UPLOAD_TOKEN", "处方上传令牌", "医保", "str", True, True),
    ("PUBLIC_HEALTH_GATEWAY_URL", "公卫网关地址", "公卫/短信", "str", False, True),
    ("PUBLIC_HEALTH_GATEWAY_TOKEN", "公卫网关令牌", "公卫/短信", "str", True, True),
    ("PUBLIC_HEALTH_ALLOW_MOCK", "允许公卫 Mock", "公卫/短信", "bool", False, True),
    ("SMS_GATEWAY_URL", "短信网关地址", "公卫/短信", "str", False, True),
    ("SMS_GATEWAY_TOKEN", "短信网关令牌", "公卫/短信", "str", True, True),
    ("SMS_ALLOW_MOCK", "允许短信 Mock", "公卫/短信", "bool", False, True),
    ("WECOM_WEBHOOK_URL", "企业微信 Webhook", "公卫/短信", "str", False, True),
    ("SMS_WEBHOOK_URL", "短信 Webhook", "公卫/短信", "str", False, True),
    ("KIOSK_TOKEN", "自助机终端令牌", "公卫/短信", "str", True, True),
    ("HOST", "监听地址", "部署（需重启）", "str", False, False),
    ("PORT", "端口", "部署（需重启）", "int", False, False),
    ("SECRET_KEY", "会话密钥", "部署（需重启）", "str", True, False),
    ("DATABASE_URL", "数据库 URL", "部署（需重启）", "str", False, False),
    ("BACKUP_DIR", "备份目录", "部署（需重启）", "str", False, False),
    ("CLIENT_ZIP_PATH", "客户端下载包", "部署（需重启）", "str", False, False),
]
BY_KEY = {item[0]: item for item in FIELDS}
SECRET_KEYS = {item[0] for item in FIELDS if item[4]}
MUTABLE_KEYS = {item[0] for item in FIELDS if item[5]}


def _default(key: str):
    return getattr(settings, key, "")


def load(db: Session) -> dict:
    values = {key: _default(key) for key, *_ in FIELDS}
    for row in db.query(SystemSetting).all():
        if row.key in BY_KEY:
            values[row.key] = row.value
    return values


def _convert(kind: str, value):
    if kind == "bool":
        return str(value).strip().lower() in {"1", "true", "on", "yes"}
    if kind == "int":
        return int(value or 0)
    if kind == "float":
        return float(value or 0)
    return str(value or "")


def save(db: Session, values: dict, operator: str = "") -> dict:
    for key, _label, _group, kind, secret, _mutable in FIELDS:
        if key not in values:
            continue
        value = values[key]
        if secret and value in (None, ""):
            continue
        text = ("1" if value else "0") if kind == "bool" else str(value)
        row = db.get(SystemSetting, key)
        if row is None:
            row = SystemSetting(key=key)
            db.add(row)
        row.value = text
        row.updated_by = operator
        row.updated_at = datetime.now()
    db.commit()
    apply(db)
    return load(db)


def apply(db: Session) -> None:
    """把数据库参数写回 app.settings；只处理可热更新字段。"""
    for row in db.query(SystemSetting).all():
        if row.key not in MUTABLE_KEYS:
            continue
        item = BY_KEY.get(row.key)
        if not item:
            continue
        kind = item[3]
        try:
            setattr(settings, row.key, _convert(kind, row.value))
        except (TypeError, ValueError):
            continue


def apply_startup(db: Session) -> None:
    try:
        apply(db)
    except Exception:
        # 迁移未完成/表不存在时不阻塞启动
        pass
