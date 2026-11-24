"""药品/中药注射剂目录 CSV 导入：默认 dry-run。

CSV 表头：
    name,spec,unit,base_price,dosage_form,insurance_ratio,insurance_code,controlled_level

用法：
    python scripts/import_drugs_csv.py --csv drugs.csv           # 只校验
    python scripts/import_drugs_csv.py --csv drugs.csv --apply   # 写入
"""
import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.modules.drug.models import Drug


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True, help="CSV 文件路径")
    parser.add_argument("--apply", action="store_true", help="实际写入")
    args = parser.parse_args()
    path = Path(args.csv)
    if not path.exists():
        print(f"文件不存在：{path}")
        return 2
    db = SessionLocal()
    created = updated = 0
    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            for line_no, row in enumerate(csv.DictReader(handle), start=2):
                name = (row.get("name") or "").strip()
                if not name:
                    print(f"第 {line_no} 行缺少 name，跳过")
                    continue
                try:
                    price = float(row.get("base_price") or 0)
                    ratio = float(row.get("insurance_ratio") or 0.7)
                except ValueError:
                    print(f"第 {line_no} 行价格/比例非法，跳过")
                    continue
                existing = db.query(Drug).filter(Drug.name == name).first()
                if existing:
                    existing.spec = (row.get("spec") or existing.spec or "").strip()
                    existing.unit = (row.get("unit") or existing.unit or "").strip()
                    existing.base_price = price
                    existing.dosage_form = (row.get("dosage_form") or existing.dosage_form or "").strip()
                    existing.insurance_ratio = ratio
                    existing.insurance_code = (row.get("insurance_code") or existing.insurance_code or "").strip()
                    existing.controlled_level = (row.get("controlled_level") or existing.controlled_level or "").strip()
                    updated += 1
                else:
                    db.add(
                        Drug(
                            name=name,
                            spec=(row.get("spec") or "").strip(),
                            unit=(row.get("unit") or "").strip(),
                            base_price=price,
                            dosage_form=(row.get("dosage_form") or "").strip(),
                            insurance_ratio=ratio,
                            insurance_code=(row.get("insurance_code") or "").strip(),
                            controlled_level=(row.get("controlled_level") or "").strip(),
                        )
                    )
                    created += 1
        if args.apply:
            db.commit()
            print(f"已导入：新增 {created}，更新 {updated}")
        else:
            db.rollback()
            print(f"dry-run：将新增 {created}，更新 {updated}（加 --apply 写入）")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
