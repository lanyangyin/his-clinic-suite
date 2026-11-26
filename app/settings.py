"""服务端运行配置：程序目录基准 + config.ini + 环境变量覆盖。

原则：所有运行期文件（数据库、备份、日志）都相对**程序所在目录**，
与启动时的工作目录无关；换机器/换目录只需整体拷贝。
"""
import configparser
import os
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    # PyInstaller 打包后：exe 所在目录
    BASE_DIR = Path(sys.executable).resolve().parent
    # PyInstaller 数据文件目录（--add-data 内容）
    BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", BASE_DIR))
else:
    # 源码运行：项目根目录（app/settings.py 的上一级）
    BASE_DIR = Path(__file__).resolve().parent.parent
    BUNDLE_DIR = BASE_DIR

# 管理台模板目录（打包后位于 _MEIPASS 数据目录）
ADMIN_TEMPLATES_DIR = BUNDLE_DIR / "app" / "modules" / "admin" / "templates"
# 内置的 Alembic 脚本目录（打包版启动时自动升级数据库）
ALEMBIC_DIR = BUNDLE_DIR / "alembic"
ALEMBIC_INI = BUNDLE_DIR / "alembic.ini"


def _load_ini() -> configparser.ConfigParser:
    parser = configparser.ConfigParser()
    # 先读主配置，再用本地覆盖配置（config.local.ini，不入库；后读的覆盖前面的）
    for candidate in (
        BASE_DIR / "config.ini",
        Path.cwd() / "config.ini",
        BASE_DIR / "config.local.ini",
        Path.cwd() / "config.local.ini",
    ):
        if candidate.is_file():
            parser.read(candidate, encoding="utf-8")
    return parser


_ini = _load_ini()

# 监听地址：局域网部署用 0.0.0.0；仅本机用 127.0.0.1
HOST = os.environ.get("HIS_HOST") or _ini.get("server", "host", fallback="0.0.0.0")
PORT = int(os.environ.get("HIS_PORT") or _ini.get("server", "port", fallback="8000"))
SECRET_KEY = (
    os.environ.get("HIS_SECRET_KEY")
    or _ini.get("server", "secret_key", fallback="his-dev-secret-change-me-0123456789")
)
STRICT_CONFIG = (
    os.environ.get("HIS_STRICT_CONFIG", "").lower() in {"1", "true", "yes", "on"}
    or _ini.getboolean("server", "strict_config", fallback=False)
)
_INSECURE_SECRETS = {
    "his-dev-secret-change-me-0123456789",
    "CHANGE_ME_TO_A_RANDOM_LONG_STRING",
    "",
}


def validate_runtime_settings() -> None:
    """严格模式禁止占位密钥启动，避免管理台 Cookie 被伪造。"""
    if STRICT_CONFIG and SECRET_KEY in _INSECURE_SECRETS:
        raise RuntimeError("严格模式要求配置非占位 SECRET_KEY")

# 医保总开关：默认关闭（未接入医保的门诊）。测试通过 HIS_INSURANCE_ENABLED=1 打开。
INSURANCE_PRESCRIPTION_UPLOAD_URL = (
    os.environ.get("HIS_INSURANCE_PRESCRIPTION_UPLOAD_URL")
    or _ini.get("insurance", "prescription_upload_url", fallback="")
)
INSURANCE_PRESCRIPTION_UPLOAD_TOKEN = (
    os.environ.get("HIS_INSURANCE_PRESCRIPTION_UPLOAD_TOKEN")
    or _ini.get("insurance", "prescription_upload_token", fallback="")
)

KIOSK_TOKEN = (
    os.environ.get("HIS_KIOSK_TOKEN")
    or _ini.get("features", "kiosk_token", fallback="")
)

PUBLIC_HEALTH_GATEWAY_URL = os.environ.get(
    "HIS_PUBLIC_HEALTH_GATEWAY_URL", ""
) or _ini.get("public_health", "gateway_url", fallback="")
PUBLIC_HEALTH_GATEWAY_TOKEN = os.environ.get(
    "HIS_PUBLIC_HEALTH_GATEWAY_TOKEN", ""
) or _ini.get("public_health", "gateway_token", fallback="")

PUBLIC_HEALTH_ALLOW_MOCK = (
    os.environ.get("HIS_PUBLIC_HEALTH_ALLOW_MOCK", "").lower()
    in {"1", "true", "yes", "on"}
    or _ini.getboolean("features", "public_health_mock", fallback=False)
)

NURSING_REQUIRE_PAID_DISPENSED = (
    os.environ.get("HIS_NURSING_REQUIRE_PAID_DISPENSED", "").lower()
    in {"1", "true", "yes", "on"}
    or _ini.getboolean("features", "nursing_require_paid_dispensed", fallback=False)
)

SURGERY_REQUIRE_SIGNATURES = (
    os.environ.get("HIS_SURGERY_REQUIRE_SIGNATURES", "").lower() in {"1", "true", "yes", "on"}
    or _ini.getboolean("features", "surgery_require_signatures", fallback=False)
)

LIS_REQUIRE_SAMPLE = (
    os.environ.get("HIS_LIS_REQUIRE_SAMPLE", "").lower() in {"1", "true", "yes", "on"}
    or _ini.getboolean("features", "lis_require_sample", fallback=False)
)

SMS_GATEWAY_URL = os.environ.get("HIS_SMS_GATEWAY_URL", "") or _ini.get(
    "sms", "gateway_url", fallback=""
)
SMS_GATEWAY_TOKEN = os.environ.get("HIS_SMS_GATEWAY_TOKEN", "") or _ini.get(
    "sms", "gateway_token", fallback=""
)

SMS_ALLOW_MOCK = (
    os.environ.get("HIS_SMS_ALLOW_MOCK", "").lower() in {"1", "true", "yes", "on"}
    or _ini.getboolean("features", "sms_mock", fallback=False)
)

PORTAL_REQUIRE_OTP = (
    os.environ.get("HIS_PORTAL_REQUIRE_OTP", "").lower() in {"1", "true", "yes", "on"}
    or _ini.getboolean("features", "portal_require_otp", fallback=False)
)

INSURANCE_GATEWAY_URL = os.environ.get("HIS_INSURANCE_GATEWAY_URL", "") or _ini.get(
    "insurance", "gateway_url", fallback=""
)
INSURANCE_GATEWAY_TOKEN = os.environ.get("HIS_INSURANCE_GATEWAY_TOKEN", "") or _ini.get(
    "insurance", "gateway_token", fallback=""
)

INSURANCE_NATIONAL_URL = os.environ.get("HIS_INSURANCE_NATIONAL_URL", "") or _ini.get(
    "insurance", "national_url", fallback=""
)
INSURANCE_NATIONAL_TOKEN = os.environ.get("HIS_INSURANCE_NATIONAL_TOKEN", "") or _ini.get(
    "insurance", "national_token", fallback=""
)
INSURANCE_NATIONAL_ORG_CODE = os.environ.get("HIS_INSURANCE_NATIONAL_ORG_CODE", "") or _ini.get(
    "insurance", "national_org_code", fallback=""
)
INSURANCE_NATIONAL_REGION_CODE = os.environ.get("HIS_INSURANCE_NATIONAL_REGION_CODE", "") or _ini.get(
    "insurance", "national_region_code", fallback=""
)
INSURANCE_NATIONAL_OPERATOR = os.environ.get("HIS_INSURANCE_NATIONAL_OPERATOR", "") or _ini.get(
    "insurance", "national_operator", fallback="HIS"
)
INSURANCE_NATIONAL_MOCK = (
    os.environ.get("HIS_INSURANCE_NATIONAL_MOCK", "").lower() in {"1", "true", "yes", "on"}
    or _ini.getboolean("features", "insurance_national_mock", fallback=False)
)
INSURANCE_NATIONAL_ORG_NAME = os.environ.get("HIS_INSURANCE_NATIONAL_ORG_NAME", "") or _ini.get(
    "insurance", "national_org_name", fallback=""
)
INSURANCE_NATIONAL_INFVER = os.environ.get("HIS_INSURANCE_NATIONAL_INFVER", "") or _ini.get(
    "insurance", "national_infver", fallback="V1.0"
)
INSURANCE_NATIONAL_RECER_SYS_CODE = os.environ.get(
    "HIS_INSURANCE_NATIONAL_RECER_SYS_CODE", ""
) or _ini.get("insurance", "national_recer_sys_code", fallback="HIS")
INSURANCE_NATIONAL_MDTRTAREA_CODE = os.environ.get(
    "HIS_INSURANCE_NATIONAL_MDTRTAREA_CODE", ""
) or _ini.get("insurance", "national_mdtrtarea_code", fallback="")
INSURANCE_NATIONAL_INSUPLC_CODE = os.environ.get(
    "HIS_INSURANCE_NATIONAL_INSUPLC_CODE", ""
) or _ini.get("insurance", "national_insuplc_code", fallback="")
INSURANCE_NATIONAL_MED_TYPE = os.environ.get("HIS_INSURANCE_NATIONAL_MED_TYPE", "") or _ini.get(
    "insurance", "national_med_type", fallback="11"
)
INSURANCE_NATIONAL_SIGN_TYPE = os.environ.get("HIS_INSURANCE_NATIONAL_SIGN_TYPE", "") or _ini.get(
    "insurance", "national_sign_type", fallback="SM2"
)
INSURANCE_NATIONAL_SECURITY_MODE = os.environ.get(
    "HIS_INSURANCE_NATIONAL_SECURITY_MODE", ""
) or _ini.get("insurance", "national_security_mode", fallback="plain")
INSURANCE_NATIONAL_TIMEOUT = int(
    os.environ.get("HIS_INSURANCE_NATIONAL_TIMEOUT", "")
    or _ini.get("insurance", "national_timeout", fallback="15")
)
INSURANCE_NATIONAL_RETRY = int(
    os.environ.get("HIS_INSURANCE_NATIONAL_RETRY", "")
    or _ini.get("insurance", "national_retry", fallback="0")
)
INSURANCE_NATIONAL_DEV_NO = os.environ.get("HIS_INSURANCE_NATIONAL_DEV_NO", "") or _ini.get(
    "insurance", "national_dev_no", fallback=""
)
INSURANCE_NATIONAL_DEV_SAFE_INFO = os.environ.get(
    "HIS_INSURANCE_NATIONAL_DEV_SAFE_INFO", ""
) or _ini.get("insurance", "national_dev_safe_info", fallback="")
INSURANCE_NATIONAL_CERT_PATH = os.environ.get("HIS_INSURANCE_NATIONAL_CERT_PATH", "") or _ini.get(
    "insurance", "national_cert_path", fallback=""
)
INSURANCE_NATIONAL_CERT_PASSWORD = os.environ.get(
    "HIS_INSURANCE_NATIONAL_CERT_PASSWORD", ""
) or _ini.get("insurance", "national_cert_password", fallback="")
INSURANCE_NATIONAL_SM2_PRIVATE_KEY = os.environ.get(
    "HIS_INSURANCE_NATIONAL_SM2_PRIVATE_KEY", ""
) or _ini.get("insurance", "national_sm2_private_key", fallback="")
INSURANCE_NATIONAL_SM2_PUBLIC_KEY = os.environ.get(
    "HIS_INSURANCE_NATIONAL_SM2_PUBLIC_KEY", ""
) or _ini.get("insurance", "national_sm2_public_key", fallback="")
INSURANCE_NATIONAL_SM4_KEY = os.environ.get("HIS_INSURANCE_NATIONAL_SM4_KEY", "") or _ini.get(
    "insurance", "national_sm4_key", fallback=""
)

INSURANCE_ALLOW_MOCK = (
    os.environ.get("HIS_INSURANCE_ALLOW_MOCK", "").lower() in {"1", "true", "yes", "on"}
    or _ini.getboolean("features", "insurance_mock", fallback=False)
)

REFUND_APPROVAL_THRESHOLD = float(
    os.environ.get("HIS_REFUND_APPROVAL_THRESHOLD", "")
    or _ini.get("features", "refund_approval_threshold", fallback="500")
)

NOTIFY_AUTO_DISPATCH = (
    os.environ.get("HIS_NOTIFY_AUTO_DISPATCH", "").lower() in {"1", "true", "yes", "on"}
    or _ini.getboolean("features", "notify_auto_dispatch", fallback=False)
)
NOTIFY_DISPATCH_INTERVAL = int(
    os.environ.get("HIS_NOTIFY_DISPATCH_INTERVAL", "")
    or _ini.get("features", "notify_dispatch_interval", fallback="60")
)

ALLOW_ANONYMOUS_READ = (
    os.environ.get("HIS_ALLOW_ANONYMOUS_READ", "").lower() in {"1", "true", "yes", "on"}
    or _ini.getboolean("features", "anonymous_read", fallback=False)
)

PAYMENT_ALLOW_MOCK = (
    os.environ.get("HIS_PAYMENT_ALLOW_MOCK", "").lower() in {"1", "true", "yes", "on"}
    or _ini.getboolean("features", "payment_mock", fallback=False)
)

WECOM_WEBHOOK_URL = (
    os.environ.get("HIS_WECOM_WEBHOOK_URL")
    or _ini.get("notify", "wecom_webhook_url", fallback="")
)
SMS_WEBHOOK_URL = (
    os.environ.get("HIS_SMS_WEBHOOK_URL")
    or _ini.get("notify", "sms_webhook_url", fallback="")
)

INSURANCE_ENABLED = (
    os.environ.get("HIS_INSURANCE_ENABLED", "").lower() in {"1", "true", "yes", "on"}
    or _ini.getboolean("features", "insurance", fallback=False)
)

# 处方是否必须经药师审方后才能发药。生产默认开启；自动化测试通过环境变量关闭以保留旧用例，
# 审方/阻断行为另用显式测试覆盖。
REQUIRE_PRESCRIPTION_REVIEW = (
    os.environ.get("HIS_REQUIRE_PRESCRIPTION_REVIEW", "").lower() not in {"0", "false", "no", "off"}
    and _ini.getboolean("features", "prescription_review", fallback=True)
)

# 打印抬头（可在 config.ini [clinic] 覆盖）
CLINIC_NAME = _ini.get("clinic", "name", fallback="邹治国中西医结合诊所")
CLINIC_ADDRESS = _ini.get("clinic", "address", fallback="")
CLINIC_PHONE = _ini.get("clinic", "phone", fallback="")

# 数据库：默认程序目录下 his.db（绝对路径，与 CWD 无关）
_DEFAULT_DB_PATH = BASE_DIR / "his.db"
DATABASE_URL = (
    os.environ.get("HIS_DATABASE_URL")
    or _ini.get("database", "url", fallback="")
    or f"sqlite:///{_DEFAULT_DB_PATH.as_posix()}"
)

# 客户端下载包位置（相对程序目录）
CLIENT_ZIP_PATH = BASE_DIR / "dist" / "his-client.zip"

# 备份目录
BACKUP_DIR = BASE_DIR / "backups"
