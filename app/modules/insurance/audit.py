from sqlalchemy.orm import Session

from .models import InsuranceTransaction


def record_check(
    db: Session,
    *,
    encounter_id: int | None,
    drug_name: str,
    quantity: int,
    ratio: float,
    result: str,
    message: str = "",
    operator: str = "",
) -> None:
    db.add(
        InsuranceTransaction(
            encounter_id=encounter_id,
            kind="precheck",
            drug_name=drug_name,
            quantity=quantity,
            ratio=ratio,
            result=result,
            message=message[:300],
            operator=operator,
        )
    )
