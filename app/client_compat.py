"""服务端对独立客户端的兼容矩阵。

客户端版本独立递增；服务端只声明每个岗位客户端支持的最低/最高/推荐版本。
"""
CLIENT_TITLES = {
    "cashier": "收费挂号客户端", "doctor": "医生工作站客户端", "pharmacy": "药房客户端",
    "warehouse": "库房客户端", "nurse": "护士站客户端", "lab": "检验科客户端",
    "radiology": "影像科客户端", "treatment": "治疗室客户端", "surgery": "手术室客户端",
    "archive": "病案档案客户端", "director": "院长审批客户端", "hr": "人事客户端",
    "decoction": "煎药室客户端", "admin": "管理端客户端", "universal": "开发兼容客户端",
}

CLIENT_COMPATIBILITY = {
    "cashier": {"min": "1.0.0", "max": "1.0.3", "recommended": "1.0.3"},
    "doctor": {"min": "1.0.0", "max": "1.0.3", "recommended": "1.0.3"},
    "pharmacy": {"min": "1.0.0", "max": "1.0.3", "recommended": "1.0.3"},
    "warehouse": {"min": "1.0.0", "max": "1.0.3", "recommended": "1.0.3"},
    "nurse": {"min": "1.0.0", "max": "1.0.3", "recommended": "1.0.3"},
    "lab": {"min": "1.0.0", "max": "1.0.3", "recommended": "1.0.3"},
    "radiology": {"min": "1.0.0", "max": "1.0.3", "recommended": "1.0.3"},
    "treatment": {"min": "1.0.0", "max": "1.0.3", "recommended": "1.0.3"},
    "surgery": {"min": "1.0.0", "max": "1.0.3", "recommended": "1.0.3"},
    "archive": {"min": "1.0.0", "max": "1.0.3", "recommended": "1.0.3"},
    "director": {"min": "1.0.0", "max": "1.0.3", "recommended": "1.0.3"},
    "hr": {"min": "1.0.0", "max": "1.0.3", "recommended": "1.0.3"},
    "decoction": {"min": "1.0.0", "max": "1.0.3", "recommended": "1.0.3"},
    "admin": {"min": "1.0.0", "max": "1.0.3", "recommended": "1.0.3"},
    "universal": {"min": "1.0.0", "max": "1.0.3", "recommended": "1.0.3"},
}


def _tuple(version: str) -> tuple[int, ...]:
    parts = []
    for part in str(version or "").replace("-", ".").split("."):
        digits = "".join(ch for ch in part if ch.isdigit())
        if digits:
            parts.append(int(digits))
    return tuple(parts)


def check_client(profile: str, version: str) -> dict:
    spec = CLIENT_COMPATIBILITY.get(profile)
    if not spec:
        return {
            "profile": profile, "version": version, "supported": False,
            "reason": "未知客户端岗位", "min": "", "max": "", "recommended": "",
        }
    current = _tuple(version)
    supported = _tuple(spec["min"]) <= current <= _tuple(spec["max"])
    reason = ""
    if current < _tuple(spec["min"]):
        reason = "客户端版本过低，请升级"
    elif current > _tuple(spec["max"]):
        reason = "客户端版本高于服务端支持范围，请升级服务端或使用兼容客户端"
    return {
        "profile": profile, "version": version, "supported": supported,
        "reason": reason, **spec,
    }
