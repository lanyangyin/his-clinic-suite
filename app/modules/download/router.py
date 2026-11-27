from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, RedirectResponse

from app import settings
from app.client_compat import CLIENT_COMPATIBILITY, check_client
from app.version import CLIENT_RELEASE_TAG
from app.settings import CLIENT_ZIP_PATH
from app.version import API_VERSION, APP_NAME, APP_VERSION, CLIENT_MIN_VERSION

router = APIRouter(tags=["distribution"])

# 客户端绿色包输出位置（scripts/build_client.bat 生成，相对程序目录）
CLIENT_ZIP = CLIENT_ZIP_PATH


@router.get("/version")
def version():
    """版本信息（客户端启动时检查，用于判断是否需要升级）。"""
    return {
        "name": APP_NAME,
        "version": APP_VERSION,
        "api_version": API_VERSION,
        "client_min_version": CLIENT_MIN_VERSION,
        "server_version": APP_VERSION,
        "download_url": str(getattr(settings, "CLIENT_DOWNLOAD_URL", "") or ""),
        "clients": {
            key: {
                **spec,
                "download_url": (
                    f"https://github.com/lanyangyin/his-clinic-suite/releases/download/"
                    f"{CLIENT_RELEASE_TAG}/his-client-{key}-{spec['recommended']}.zip"
                ),
            }
            for key, spec in CLIENT_COMPATIBILITY.items()
        },
    }


@router.get("/client/compatibility")
def client_compatibility(profile: str, version: str):
    return check_client(profile, version)


@router.get("/download/client/{profile}")
def download_profile_client(profile: str):
    spec = CLIENT_COMPATIBILITY.get(profile)
    if not spec:
        raise HTTPException(status_code=404, detail="未知客户端岗位")
    version = spec["recommended"]
    url = (
        f"https://github.com/lanyangyin/his-clinic-suite/releases/download/"
        f"{CLIENT_RELEASE_TAG}/his-client-{profile}-{version}.zip"
    )
    return RedirectResponse(url, status_code=307)


@router.get("/download/client")
def download_client():
    """下载客户端：优先跳转机构配置的 GitHub/镜像地址，未配置时回退本地包。"""
    url = str(getattr(settings, "CLIENT_DOWNLOAD_URL", "") or "").strip()
    if url:
        return RedirectResponse(url, status_code=307)
    # 兼容旧入口：引导到客户端独立 Release 页面
    return RedirectResponse(
        f"https://github.com/lanyangyin/his-clinic-suite/releases/tag/{CLIENT_RELEASE_TAG}",
        status_code=307,
    )
    if not CLIENT_ZIP.exists():
        raise HTTPException(
            status_code=404,
            detail="客户端安装包尚未生成，请先在服务器执行 scripts/build_client.bat",
        )
    return FileResponse(
        path=str(CLIENT_ZIP),
        filename="his-client.zip",
        media_type="application/zip",
    )
