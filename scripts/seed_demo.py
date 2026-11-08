"""演示账号与基础数据初始化（幂等，可重复运行）。

演示账号：
  admin      / admin123      管理员（科室、医生、药品主数据）
  doctor     / doctor123     医生（接诊、开方）
  cashier    / cashier123    收费员（建档、挂号、收费、退费）
  pharmacist / pharm123      药师（入库、发药）

用法：uv run python scripts/seed_demo.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal
from app.modules.auth.schemas import UserCreate
from app.modules.auth.service import create_user, get_user_by_username
from app.modules.charges.schemas import ChargeItemCreate
from app.modules.charges.service import create_item as create_charge_item
from app.modules.charges.service import get_item_by_code
from app.modules.staff.models import Doctor
from app.modules.staff.schemas import DepartmentCreate, DoctorCreate
from app.modules.staff.service import create_department, create_doctor
from app.modules.drug.schemas import DrugCreate
from app.modules.drug.service import create_drug
from app.modules.facility.schemas import CampusCreate
from app.modules.facility.service import create_campus, create_room, get_campus
from app.modules.facility.schemas import RoomCreate


def seed(db) -> None:
    # 演示账号（用户名已存在则跳过）
    demo_users = [
        UserCreate(username="admin", password="admin123", role="admin", display_name="管理员"),
        UserCreate(username="doctor", password="doctor123", role="doctor", display_name="陈医生"),
        UserCreate(username="nurse", password="nurse123", role="nurse", display_name="李护士"),
        UserCreate(username="cashier", password="cashier123", role="cashier", display_name="收费员"),
        UserCreate(username="pharmacist", password="pharm123", role="pharmacist", display_name="药师"),
        UserCreate(username="lab", password="lab123", role="lab", display_name="检验技师"),
        UserCreate(username="radiology", password="rad123", role="radiology", display_name="影像技师"),
    ]
    for data in demo_users:
        if get_user_by_username(db, data.username):
            print(f"  已存在 用户 {data.username}（{data.role}）")
            continue
        create_user(db, data)
        print(f"  创建   用户 {data.username} / {data.password}（{data.role}）")

    # 科室与医生（同名科室幂等，医生按姓名查重）
    departments = ["内科", "儿科"]
    dep_ids = {}
    for name in departments:
        dep = create_department(db, DepartmentCreate(name=name))
        dep_ids[name] = dep.id
        print(f"  就绪   科室 {name}（id={dep.id}）")

    doctors = [("陈医生", "内科"), ("林医生", "儿科")]
    for name, dep_name in doctors:
        if db.query(Doctor).filter(Doctor.name == name).first():
            print(f"  已存在 医生 {name}")
            continue
        create_doctor(db, DoctorCreate(name=name, department_id=dep_ids[dep_name]))
        print(f"  创建   医生 {name}（{dep_name}）")

    # 院区与诊室（中大型门诊部基础设置）
    from app.modules.facility.models import Campus, Room

    campus = db.query(Campus).filter(Campus.code == "CAMP1").first()
    if not campus:
        campus = create_campus(
            db, CampusCreate(code="CAMP1", name="总院门诊部", address="演示路 1 号")
        )
        print(f"  创建   院区 {campus.code} {campus.name}")
    else:
        print(f"  已存在 院区 {campus.code} {campus.name}")

    room = db.query(Room).filter(Room.code == "101").first()
    if not room:
        room = create_room(
            db, RoomCreate(campus_id=campus.id, code="101", name="内科诊室1")
        )
        print(f"  创建   诊室 {room.code} {room.name}")

    # 收费项目字典（挂号费/诊疗费/治疗费；供自动计费）
    charge_items = [
        ChargeItemCreate(code="REG", name="挂号费", category="registration", price=10.0, insurance_ratio=0.7),
        ChargeItemCreate(code="CONSULT", name="诊疗费", category="consultation", price=20.0, insurance_ratio=0.7),
        ChargeItemCreate(code="TREAT_INFUSION", name="静脉输液", category="treatment", price=15.0, insurance_ratio=0.7),
    ]
    for data in charge_items:
        if get_item_by_code(db, data.code):
            print(f"  已存在 收费项目 {data.code} {data.name}")
            continue
        item = create_charge_item(db, data)
        print(f"  创建   收费项目 {item.code} {item.name}（{item.price} 元）")

    # 药品主数据（同名幂等；报销比例收敛更新）
    demo_drugs = [
        DrugCreate(name="阿莫西林胶囊", spec="0.25g*24粒", unit="盒", base_price=12.5, insurance_ratio=0.8, antibiotic_level=1),
        DrugCreate(name="布洛芬片", spec="0.2g*20片", unit="盒", base_price=9.8, insurance_ratio=0.6),
        DrugCreate(name="维生素C片", spec="100mg*100片", unit="瓶", base_price=8.5, insurance_ratio=0.9),
    ]
    for data in demo_drugs:
        drug = create_drug(db, data)
        if abs(drug.insurance_ratio - data.insurance_ratio) > 1e-9:
            drug.insurance_ratio = data.insurance_ratio
            db.commit()
        if drug.antibiotic_level != data.antibiotic_level:
            drug.antibiotic_level = data.antibiotic_level
            db.commit()
        print(f"  就绪   药品 {drug.name}（id={drug.id}，基准价 {drug.base_price}，报销比例 {drug.insurance_ratio}，抗菌等级 {drug.antibiotic_level}）")


if __name__ == "__main__":
    db = SessionLocal()
    try:
        print("初始化演示数据 …")
        seed(db)
        print("完成。演示账号见文件头部注释，演示流程：uv run python scripts/demo.py")
    finally:
        db.close()
