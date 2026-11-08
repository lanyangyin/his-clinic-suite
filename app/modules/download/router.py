from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

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
    }


@router.get("/download/client")
def download_client():
    """下载客户端绿色包（局域网内部分发）。"""
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
