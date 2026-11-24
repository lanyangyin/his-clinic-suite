from sqlalchemy.orm import Session

from .models import PatientAccessLog


def record_access(
    db: Session,
    user,
    patient_id: int,
    *,
    action: str = "view",
    encounter_id: int | None = None,
    path: str = "",
    method: str = "GET",
    ip: str = "",
) -> None:
    if not user or not patient_id:
        return
    db.add(
        PatientAccessLog(
            username=user.username,
            role=user.role,
            patient_id=patient_id,
            encounter_id=encounter_id,
            action=action,
            path=path,
            method=method,
            ip=ip,
        )
    )
    db.commit()
