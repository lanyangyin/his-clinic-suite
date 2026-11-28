"""独立客户端岗位配置。

每个客户端只显示本岗位需要的页签；版本号独立维护，不与服务端或其他客户端联动。
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ClientProfile:
    key: str
    title: str
    roles: tuple[str, ...]
    tabs: tuple[str, ...]
    version: str
    description: str = ""


# 版本号独立：所有客户端从 1.0.0 起，后续按客户端单独递增。
CLIENT_PROFILES: dict[str, ClientProfile] = {
    "cashier": ClientProfile(
        "cashier", "HIS 收费挂号客户端", ("cashier", "admin"),
        ("cashier",), "1.0.2", "建档、挂号、收费、退费、发票、交班日结",
    ),
    "doctor": ClientProfile(
        "doctor", "HIS 医生工作站客户端", ("doctor", "admin"),
        ("doctor", "patient360", "tcm_doctor"), "1.0.2", "接诊、病历、诊断、开方、检验检查治疗、复诊",
    ),
    "pharmacy": ClientProfile(
        "pharmacy", "HIS 药房客户端", ("pharmacist", "admin"),
        ("pharmacy", "pharmacy_review", "rx_review", "narcotic", "tcm_pharmacy", "approval_inbox", "notifications"),
        "1.0.2", "审方、发药、退药、麻精、中药房/煎药",
    ),
    "warehouse": ClientProfile(
        "warehouse", "HIS 库房客户端", ("warehouse", "admin"),
        ("warehouse", "warehouse_review", "purchase", "approval_inbox", "notifications"),
        "1.0.2", "入库、出库、总库、效期、采购到货",
    ),
    "nurse": ClientProfile(
        "nurse", "HIS 护士站客户端", ("nurse", "admin"),
        ("nurse",), "1.0.2", "分诊叫号、配药、执行、巡视、完成",
    ),
    "lab": ClientProfile(
        "lab", "HIS 检验科客户端", ("lab", "admin"),
        ("lab",), "1.0.2", "采样、签收、报告、审核、危急值",
    ),
    "radiology": ClientProfile(
        "radiology", "HIS 影像科客户端", ("radiology", "admin"),
        ("radiology",), "1.0.2", "检查登记、报告、审核",
    ),
    "treatment": ClientProfile(
        "treatment", "HIS 治疗室客户端", ("treatment", "admin"),
        ("treatment",), "1.0.2", "处置、知情同意、耗材、随访",
    ),
    "surgery": ClientProfile(
        "surgery", "HIS 手术室客户端", ("surgery", "anesthesia", "surgery_nurse", "admin"),
        ("surgery",), "1.0.2", "手术排程、三方核查、麻醉/护理",
    ),
    "archive": ClientProfile(
        "archive", "HIS 病案档案客户端", ("archive", "admin"),
        ("archive",), "1.0.2", "病案归档、借阅、复印、封存",
    ),
    "director": ClientProfile(
        "director", "HIS 院长审批客户端", ("director", "admin"),
        ("director", "audit", "narcotic", "treatment_review", "approval_inbox", "notifications"),
        "1.0.2", "审批、审计、麻精、治疗项目审批",
    ),
    "hr": ClientProfile(
        "hr", "HIS 人事客户端", ("hr", "admin"),
        ("hr", "approval_inbox", "notifications"), "1.0.2", "员工档案、入职离职、账号",
    ),
    "decoction": ClientProfile(
        "decoction", "HIS 煎药室客户端", ("decoction", "admin"),
        ("tcm_decoction",), "1.0.2", "中药煎药、发药",
    ),
    "admin": ClientProfile(
        "admin", "HIS 管理端客户端", ("admin",),
        ("hr", "approval_inbox", "approval_flow", "integration", "notifications", "cashier",
         "doctor", "patient360", "pharmacy", "pharmacy_review", "rx_review", "warehouse",
         "warehouse_review", "purchase", "nurse", "lab", "radiology", "surgery", "archive",
         "narcotic", "audit", "director", "treatment_review", "tcm_admin", "treatment"),
        "1.0.2", "全功能管理端",
    ),
    "universal": ClientProfile(
        "universal", "HIS 门诊部客户端", (), tuple(), "1.0.2", "源码开发用通用客户端",
    ),
}

CLIENT_VERSIONS = {key: profile.version for key, profile in CLIENT_PROFILES.items()}


def detect_profile() -> ClientProfile:
    """优先环境变量，其次 exe 同目录 client_profile.json，其次 exe 文件名。"""
    key = os.environ.get("HIS_CLIENT_PROFILE", "").strip().lower()
    if not key:
        candidates = []
        if getattr(sys, "frozen", False):
            candidates.append(Path(sys.executable).resolve().parent / "client_profile.json")
        candidates.append(Path.cwd() / "client_profile.json")
        for path in candidates:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                key = str(data.get("profile") or "").strip().lower()
                if key:
                    break
            except (OSError, ValueError):
                continue
    if not key and getattr(sys, "frozen", False):
        stem = Path(sys.executable).stem.lower()
        for profile_key in CLIENT_PROFILES:
            if profile_key != "universal" and profile_key in stem:
                key = profile_key
                break
    return CLIENT_PROFILES.get(key, CLIENT_PROFILES["universal"])


def profile_for_role(role: str) -> ClientProfile:
    for profile in CLIENT_PROFILES.values():
        if profile.key != "universal" and role in profile.roles:
            return profile
    return CLIENT_PROFILES["universal"]


def profile_manifest() -> dict:
    return {
        "server_compatible": True,
        "clients": {
            key: {
                "title": profile.title,
                "version": profile.version,
                "roles": list(profile.roles),
                "tabs": list(profile.tabs),
            }
            for key, profile in CLIENT_PROFILES.items()
        },
    }
