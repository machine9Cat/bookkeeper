"""单位采购支出记账系统 - 主应用"""
import os
import sys
import shutil
import uuid
import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Optional
from fastapi import FastAPI, HTTPException, Depends, Query, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
import aiosqlite

sys.path.insert(0, os.path.dirname(__file__))

from database import get_db, init_db, DB_PATH
from auth import hash_password, verify_password, create_access_token, get_current_user, get_admin_user
from backup import backup_to_webdaV, restore_from_webdaV
from reports import generate_monthly_report

# 数据变更跟踪（用于自动备份）
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
_last_data_change: Optional[datetime] = None
_last_auto_backup: Optional[datetime] = None
_auto_backup_interval = timedelta(minutes=30)


def touch_data_change():
    """标记数据已变更"""
    global _last_data_change
    _last_data_change = datetime.now()


async def auto_backup_loop():
    """后台任务：每60秒检查一次，数据变更满30分钟且未备份则自动备份"""
    global _last_auto_backup
    while True:
        await asyncio.sleep(60)
        if _last_data_change is None:
            continue
        now = datetime.now()
        # 距离上次变更已超过30分钟，且本次窗口尚未备份过
        if now - _last_data_change >= _auto_backup_interval:
            if _last_auto_backup is None or _last_auto_backup < _last_data_change:
                try:
                    bak_name = f"bookkeeper.db.auto.{now.strftime('%Y%m%d_%H%M%S')}"
                    bak_path = os.path.join(DATA_DIR, bak_name)
                    shutil.copy2(DB_PATH, bak_path)
                    _last_auto_backup = now
                    # 记录日志
                    log_file = os.path.join(DATA_DIR, "backup_log.txt")
                    with open(log_file, "a") as f:
                        f.write(f"{now}: 自动备份成功 -> {bak_name}\n")
                    print(f"📀 自动备份完成: {bak_name}")
                except Exception as e:
                    print(f"⚠️ 自动备份失败: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    task = asyncio.create_task(auto_backup_loop())
    print("🚀 采购支出记账系统已启动")
    print(f"📊 数据库: {DB_PATH}")
    print(f"🌐 访问: http://localhost:8000")
    yield
    task.cancel()


app = FastAPI(title="采购支出记账系统", version="2.0.0", lifespan=lifespan)

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

# 导入任务进度跟踪
_import_tasks = {}


# ==================== 请求模型 ====================

class UserRegister(BaseModel):
    username: str
    password: str
    email: Optional[str] = None

class UserLogin(BaseModel):
    username: str
    password: str

class CategoryCreate(BaseModel):
    name: str
    icon: str = "📦"

class ExpenseCreate(BaseModel):
    category_id: Optional[int] = None
    item_name: str
    specification: Optional[str] = None
    quantity: float = 1
    unit: str = "个"
    unit_price: float = 0
    total_price: float = 0
    expense_date: Optional[str] = None
    inventory_in: Optional[str] = None
    booked: Optional[str] = None
    handler: Optional[str] = None
    invoice: Optional[str] = None
    payment_method: Optional[str] = None
    purchase_channel: Optional[str] = None
    invoice_type: Optional[str] = None
    accounting_date: Optional[str] = None
    note: Optional[str] = None

class ExpenseUpdate(ExpenseCreate):
    pass

class PaymentMethodCreate(BaseModel):
    name: str

class ChannelCreate(BaseModel):
    name: str

class HandlerCreate(BaseModel):
    name: str

class UnitCreate(BaseModel):
    name: str

class BackupConfig(BaseModel):
    webdav_url: str
    webdav_user: str
    webdav_password: str
    remote_path: str = "/bookkeeper/"


# ==================== 用户认证 ====================

@app.post("/api/register")
async def register(user: UserRegister, db=Depends(get_db)):
    cursor = await db.execute("SELECT id FROM users WHERE username = ?", (user.username,))
    if await cursor.fetchone():
        raise HTTPException(status_code=400, detail="用户名已存在")
    password_hash = hash_password(user.password)
    cursor = await db.execute(
        "INSERT INTO users (username, password_hash, raw_password, email) VALUES (?, ?, ?, ?)",
        (user.username, password_hash, user.password, user.email)
    )
    user_id = cursor.lastrowid
    await db.commit()
    # 第一个注册的用户自动成为管理员(免审核)
    cursor = await db.execute("SELECT COUNT(*) FROM users")
    user_count = (await cursor.fetchone())[0]
    role = "admin" if user_count == 1 else "user"
    status = "approved" if user_count == 1 else "pending"
    await db.execute("UPDATE users SET role=?, status=? WHERE id=?", (role, status, user_id))
    await db.commit()
    touch_data_change()
    if status == "pending":
        return {"token": None, "user_id": user_id, "username": user.username, "role": role, "status": "pending",
                "message": "注册成功，请等待管理员审核后再登录"}
    token = create_access_token(user_id, user.username, role)
    return {"token": token, "user_id": user_id, "username": user.username, "role": role, "status": status}


@app.post("/api/login")
async def login(user: UserLogin, db=Depends(get_db)):
    cursor = await db.execute("SELECT id, username, password_hash, role, status FROM users WHERE username = ?", (user.username,))
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=401, detail="用户名不存在")
    if not verify_password(user.password, row[2]):
        raise HTTPException(status_code=401, detail="密码错误")
    if row[4] == "pending":
        raise HTTPException(status_code=403, detail="账号待审核，请等待管理员审批")
    if row[4] == "disabled":
        raise HTTPException(status_code=403, detail="账号已被禁用，请联系管理员")
    role = row[3] or "user"
    token = create_access_token(row[0], row[1], role)
    return {"token": token, "user_id": row[0], "username": row[1], "role": role, "status": row[4]}


@app.get("/api/me")
async def get_me(user=Depends(get_current_user)):
    return user


@app.get("/api/version")
async def get_version():
    import tomllib
    with open(os.path.join(os.path.dirname(__file__), "..", "pyproject.toml"), "rb") as f:
        data = tomllib.load(f)
    return {"version": data["project"]["version"]}


# ==================== 大类管理 ====================

@app.get("/api/categories")
async def list_categories(user=Depends(get_current_user), db=Depends(get_db)):
    cursor = await db.execute(
        "SELECT * FROM categories ORDER BY is_system DESC, id"
    )
    return [dict(row) for row in await cursor.fetchall()]


@app.post("/api/categories")
async def create_category(cat: CategoryCreate, user=Depends(get_current_user), db=Depends(get_db)):
    cursor = await db.execute(
        "INSERT INTO categories (name, icon, is_system) VALUES (?, ?, 0)",
        (cat.name, cat.icon)
    )
    await db.commit()
    touch_data_change()
    return {"id": cursor.lastrowid, "message": "创建成功"}


@app.delete("/api/categories/{cat_id}")
async def delete_category(cat_id: int, user=Depends(get_current_user), db=Depends(get_db)):
    cursor = await db.execute("SELECT id FROM categories WHERE id=? AND is_system=0", (cat_id,))
    if not await cursor.fetchone():
        raise HTTPException(status_code=403, detail="无法删除系统分类")
    await db.execute("DELETE FROM categories WHERE id=?", (cat_id,))
    await db.commit()
    touch_data_change()
    return {"message": "删除成功"}


# ==================== 付款方式 ====================

@app.get("/api/payment-methods")
async def list_payment_methods(user=Depends(get_current_user), db=Depends(get_db)):
    cursor = await db.execute(
        "SELECT * FROM payment_methods ORDER BY is_system DESC, id"
    )
    return [dict(row) for row in await cursor.fetchall()]


@app.post("/api/payment-methods")
async def create_payment_method(pm: PaymentMethodCreate, user=Depends(get_current_user), db=Depends(get_db)):
    cursor = await db.execute(
        "INSERT INTO payment_methods (name, is_system) VALUES (?, 0)",
        (pm.name,)
    )
    await db.commit()
    touch_data_change()
    return {"id": cursor.lastrowid}


# ==================== 购买渠道 ====================

@app.get("/api/channels")
async def list_channels(user=Depends(get_current_user), db=Depends(get_db)):
    cursor = await db.execute(
        "SELECT * FROM channels ORDER BY is_system DESC, id"
    )
    return [dict(row) for row in await cursor.fetchall()]


@app.post("/api/channels")
async def create_channel(ch: ChannelCreate, user=Depends(get_current_user), db=Depends(get_db)):
    cursor = await db.execute(
        "INSERT INTO channels (name, is_system) VALUES (?, 0)",
        (ch.name,)
    )
    await db.commit()
    touch_data_change()
    return {"id": cursor.lastrowid}


# ==================== 经手人 ====================

@app.get("/api/handlers")
async def list_handlers(user=Depends(get_current_user), db=Depends(get_db)):
    cursor = await db.execute(
        "SELECT * FROM handlers ORDER BY is_system DESC, id"
    )
    return [dict(row) for row in await cursor.fetchall()]


@app.post("/api/handlers")
async def create_handler(h: HandlerCreate, user=Depends(get_current_user), db=Depends(get_db)):
    cursor = await db.execute(
        "INSERT INTO handlers (name, is_system) VALUES (?, 0)",
        (h.name,)
    )
    await db.commit()
    touch_data_change()
    return {"id": cursor.lastrowid}


@app.delete("/api/payment-methods/{pm_id}")
async def delete_payment_method(pm_id: int, user=Depends(get_current_user), db=Depends(get_db)):
    await db.execute("DELETE FROM payment_methods WHERE id=? AND is_system=0", (pm_id,))
    await db.commit()
    touch_data_change()
    return {"message": "删除成功"}


@app.delete("/api/channels/{ch_id}")
async def delete_channel(ch_id: int, user=Depends(get_current_user), db=Depends(get_db)):
    await db.execute("DELETE FROM channels WHERE id=? AND is_system=0", (ch_id,))
    await db.commit()
    touch_data_change()
    return {"message": "删除成功"}


@app.delete("/api/handlers/{h_id}")
async def delete_handler(h_id: int, user=Depends(get_current_user), db=Depends(get_db)):
    await db.execute("DELETE FROM handlers WHERE id=? AND is_system=0", (h_id,))
    await db.commit()
    touch_data_change()
    return {"message": "删除成功"}


# ==================== 单位 ====================

@app.get("/api/units")
async def list_units(user=Depends(get_current_user), db=Depends(get_db)):
    cursor = await db.execute(
        "SELECT * FROM units ORDER BY is_system DESC, id"
    )
    return [dict(row) for row in await cursor.fetchall()]


@app.post("/api/units")
async def create_unit(unit: UnitCreate, user=Depends(get_current_user), db=Depends(get_db)):
    cursor = await db.execute(
        "INSERT INTO units (name, is_system) VALUES (?, 0)",
        (unit.name,)
    )
    await db.commit()
    touch_data_change()
    return {"id": cursor.lastrowid}


@app.delete("/api/units/{unit_id}")
async def delete_unit(unit_id: int, user=Depends(get_current_user), db=Depends(get_db)):
    await db.execute("DELETE FROM units WHERE id=? AND is_system=0", (unit_id,))
    await db.commit()
    touch_data_change()
    return {"message": "删除成功"}

# ==================== 物品名称字典 ====================

@app.get("/api/item-names")
async def list_item_names(user=Depends(get_current_user), db=Depends(get_db)):
    cursor = await db.execute(
        "SELECT * FROM item_names ORDER BY is_system DESC, id"
    )
    return [dict(row) for row in await cursor.fetchall()]

@app.post("/api/item-names")
async def create_item_name(h: HandlerCreate, user=Depends(get_current_user), db=Depends(get_db)):
    cursor = await db.execute(
        "INSERT INTO item_names (name, is_system) VALUES (?, 0)",
        (h.name,)
    )
    await db.commit()
    touch_data_change()
    return {"id": cursor.lastrowid, "name": h.name}

@app.delete("/api/item-names/{item_id}")
async def delete_item_name(item_id: int, user=Depends(get_current_user), db=Depends(get_db)):
    await db.execute("DELETE FROM item_names WHERE id=? AND is_system=0", (item_id,))
    await db.commit()
    touch_data_change()
    return {"message": "删除成功"}


# ==================== 规格型号字典 ====================

@app.get("/api/specifications")
async def list_specifications(user=Depends(get_current_user), db=Depends(get_db)):
    cursor = await db.execute(
        "SELECT * FROM specifications ORDER BY is_system DESC, id"
    )
    return [dict(row) for row in await cursor.fetchall()]

@app.post("/api/specifications")
async def create_specification(h: HandlerCreate, user=Depends(get_current_user), db=Depends(get_db)):
    cursor = await db.execute(
        "INSERT INTO specifications (name, is_system) VALUES (?, 0)",
        (h.name,)
    )
    await db.commit()
    touch_data_change()
    return {"id": cursor.lastrowid, "name": h.name}

@app.delete("/api/specifications/{item_id}")
async def delete_specification(item_id: int, user=Depends(get_current_user), db=Depends(get_db)):
    await db.execute("DELETE FROM specifications WHERE id=? AND is_system=0", (item_id,))
    await db.commit()
    touch_data_change()
    return {"message": "删除成功"}


# ==================== 支出记录 (核心) ====================

def validate_expense(exp):
    """校验支出记录数据"""
    errors = []
    if not exp.category_id:
        errors.append("大类不能为空")
    if not exp.item_name or not exp.item_name.strip():
        errors.append("物品名称不能为空")
    if not exp.handler or not exp.handler.strip():
        errors.append("经手人不能为空")
    if not exp.payment_method or not exp.payment_method.strip():
        errors.append("付款方式不能为空")
    if not exp.purchase_channel or not exp.purchase_channel.strip():
        errors.append("购买渠道不能为空")
    if not exp.quantity or exp.quantity <= 0:
        errors.append("数量必须大于零")
    if (not exp.unit_price or exp.unit_price <= 0) and (not exp.total_price or exp.total_price <= 0):
        errors.append("单价或总价不能为零")
    return errors

@app.get("/api/expenses")
async def list_expenses(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category_id: Optional[int] = None,
    month: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    handler: Optional[str] = None,
    payment_method: Optional[str] = None,
    purchase_channel: Optional[str] = None,
    search: Optional[str] = None,
    sort_field: Optional[str] = None,
    sort_dir: str = Query("desc"),
    user=Depends(get_current_user),
    db=Depends(get_db)
):
    conditions = []
    params = []

    if category_id:
        conditions.append("e.category_id = ?")
        params.append(category_id)
    if month:
        conditions.append("e.accounting_date LIKE ?")
        params.append(f"{month}%")
    if start_date:
        conditions.append("e.expense_date >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("e.expense_date <= ?")
        params.append(end_date)
    if handler:
        conditions.append("e.handler = ?")
        params.append(handler)
    if payment_method:
        conditions.append("e.payment_method = ?")
        params.append(payment_method)
    if purchase_channel:
        conditions.append("e.purchase_channel = ?")
        params.append(purchase_channel)
    if search:
        conditions.append("(e.item_name LIKE ? OR e.specification LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])

    where = " AND ".join(conditions)
    where_clause = f"WHERE {where}" if where else ""
    
    # 排序
    allowed_sort_fields = {
        "category_name": "c.name",
        "item_name": "e.item_name",
        "specification": "e.specification",
        "quantity": "e.quantity",
        "unit_price": "e.unit_price",
        "total_price": "e.total_price",
        "expense_date": "e.expense_date",
        "handler": "e.handler",
        "payment_method": "e.payment_method",
        "purchase_channel": "e.purchase_channel",
        "accounting_date": "e.accounting_date",
        "reviewed": "e.reviewed",
        "created_at": "e.created_at",
    }
    if sort_field and sort_field in allowed_sort_fields:
        direction = "ASC" if sort_dir.lower() == "asc" else "DESC"
        sort_clause = f"{allowed_sort_fields[sort_field]} {direction}, e.id DESC"
    else:
        sort_clause = "e.expense_date DESC, e.id DESC"

    cursor = await db.execute(f"SELECT COUNT(*) FROM expenses e {where_clause}", params)
    total = (await cursor.fetchone())[0]

    offset = (page - 1) * page_size
    cursor = await db.execute(f"""
        SELECT e.*, c.name as category_name, c.icon as category_icon, u.username as creator_name
        FROM expenses e
        LEFT JOIN categories c ON e.category_id = c.id
        LEFT JOIN users u ON e.user_id = u.id
        {where_clause}
        ORDER BY {sort_clause}
        LIMIT ? OFFSET ?
    """, params + [page_size, offset])
    rows = await cursor.fetchall()

    return {"total": total, "page": page, "page_size": page_size, "items": [dict(row) for row in rows]}


@app.post("/api/expenses")
async def create_expense(exp: ExpenseCreate, user=Depends(get_current_user), db=Depends(get_db)):
    # 数据校验
    errors = validate_expense(exp)
    if errors:
        raise HTTPException(status_code=422, detail="；".join(errors))
    # 自动计算总价
    total = exp.total_price if exp.total_price else exp.quantity * exp.unit_price

    cursor = await db.execute("""
        INSERT INTO expenses (user_id, category_id, item_name, specification, quantity, unit,
            unit_price, total_price, expense_date, inventory_in, booked, handler, invoice,
            payment_method, purchase_channel, invoice_type, accounting_date, note)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        user["user_id"], exp.category_id, exp.item_name, exp.specification,
        exp.quantity, exp.unit, exp.unit_price, total,
        exp.expense_date, exp.inventory_in, exp.booked, exp.handler,
        exp.invoice, exp.payment_method, exp.purchase_channel,
        exp.invoice_type, exp.accounting_date, exp.note
    ))
    await db.commit()
    touch_data_change()
    return {"id": cursor.lastrowid, "message": "记录成功"}


@app.put("/api/expenses/{expense_id}")
async def update_expense(expense_id: int, exp: ExpenseUpdate, user=Depends(get_current_user), db=Depends(get_db)):
    cursor = await db.execute("SELECT reviewed FROM expenses WHERE id=?", (expense_id,))
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="记录不存在")
    if row[0]:
        raise HTTPException(status_code=403, detail="已审核记录不可修改，需先取消审核")
    errors = validate_expense(exp)
    if errors:
        raise HTTPException(status_code=422, detail="；".join(errors))
    total = exp.total_price if exp.total_price else exp.quantity * exp.unit_price
    today = datetime.now().strftime("%Y-%m-%d")
    await db.execute("""
        UPDATE expenses SET category_id=?, item_name=?, specification=?, quantity=?, unit=?,
            unit_price=?, total_price=?, expense_date=?, inventory_in=?, booked=?, handler=?,
            invoice=?, payment_method=?, purchase_channel=?, invoice_type=?, accounting_date=?, note=?,
            user_id=?, updated_at=datetime('now','localtime')
        WHERE id=?
    """, (
        exp.category_id, exp.item_name, exp.specification, exp.quantity, exp.unit,
        exp.unit_price, total, exp.expense_date, exp.inventory_in, exp.booked,
        exp.handler, exp.invoice, exp.payment_method, exp.purchase_channel,
        exp.invoice_type, today, exp.note,
        user["user_id"], expense_id
    ))
    await db.commit()
    touch_data_change()
    return {"message": "更新成功"}


@app.delete("/api/expenses/{expense_id}")
async def delete_expense(expense_id: int, user=Depends(get_current_user), db=Depends(get_db)):
    cursor = await db.execute("SELECT reviewed FROM expenses WHERE id=?", (expense_id,))
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="记录不存在")
    if row[0]:
        raise HTTPException(status_code=403, detail="已审核记录不可删除，需先取消审核")
    await db.execute("DELETE FROM expenses WHERE id=?", (expense_id,))
    await db.commit()
    touch_data_change()
    return {"message": "删除成功"}


# ==================== 审核管理 ====================

@app.post("/api/expenses/{expense_id}/review")
async def review_expense(expense_id: int, user=Depends(get_admin_user), db=Depends(get_db)):
    """管理员审核标记"""
    cursor = await db.execute("SELECT id FROM expenses WHERE id=?", (expense_id,))
    if not await cursor.fetchone():
        raise HTTPException(status_code=404, detail="记录不存在")
    await db.execute(
        "UPDATE expenses SET reviewed=1, reviewed_by=?, reviewed_at=datetime('now','localtime') WHERE id=?",
        (user["user_id"], expense_id)
    )
    await db.commit()
    touch_data_change()
    return {"message": "审核通过"}


@app.post("/api/expenses/{expense_id}/unreview")
async def unreview_expense(expense_id: int, user=Depends(get_admin_user), db=Depends(get_db)):
    """管理员取消审核"""
    cursor = await db.execute("SELECT id FROM expenses WHERE id=?", (expense_id,))
    if not await cursor.fetchone():
        raise HTTPException(status_code=404, detail="记录不存在")
    await db.execute(
        "UPDATE expenses SET reviewed=0, reviewed_by=NULL, reviewed_at=NULL WHERE id=?",
        (expense_id,)
    )
    await db.commit()
    touch_data_change()
    return {"message": "已取消审核"}


@app.post("/api/expenses/batch-review")
async def batch_review(data: dict, user=Depends(get_admin_user), db=Depends(get_db)):
    """批量审核"""
    ids = data.get("ids", [])
    if not ids:
        raise HTTPException(status_code=400, detail="请选择要审核的记录")
    placeholders = ",".join("?" * len(ids))
    await db.execute(
        f"UPDATE expenses SET reviewed=1, reviewed_by=?, reviewed_at=datetime('now','localtime') WHERE id IN ({placeholders})",
        [user["user_id"]] + ids
    )
    await db.commit()
    touch_data_change()
    return {"message": f"已审核 {len(ids)} 条记录"}


@app.post("/api/expenses/batch-delete")
async def batch_delete(data: dict, user=Depends(get_current_user), db=Depends(get_db)):
    """批量删除（跳过已审核的记录）"""
    ids = data.get("ids", [])
    if not ids:
        raise HTTPException(status_code=400, detail="请选择要删除的记录")
    placeholders = ",".join("?" * len(ids))
    # 只删除未审核的记录；已审核的保留
    cursor = await db.execute(
        f"SELECT id, reviewed FROM expenses WHERE id IN ({placeholders})",
        ids
    )
    rows = await cursor.fetchall()
    to_delete = [row[0] for row in rows if not row[1]]
    skipped = [row[0] for row in rows if row[1]]
    if to_delete:
        del_placeholders = ",".join("?" * len(to_delete))
        await db.execute(f"DELETE FROM expenses WHERE id IN ({del_placeholders})", to_delete)
        await db.commit()
    touch_data_change()
    return {"message": f"成功删除 {len(to_delete)} 条记录",
        "deleted": len(to_delete),
        "skipped": len(skipped),
        "skipped_ids": skipped,
    }


@app.get("/api/users")
async def list_users(user=Depends(get_admin_user), db=Depends(get_db)):
    """管理员查看用户列表"""
    cursor = await db.execute("SELECT id, username, raw_password, role, status, created_at FROM users ORDER BY status, id")
    return [dict(row) for row in await cursor.fetchall()]


@app.post("/api/users/{user_id}/approve")
async def approve_user(user_id: int, user=Depends(get_admin_user), db=Depends(get_db)):
    """管理员审核通过用户"""
    cursor = await db.execute("SELECT id, username, status FROM users WHERE id=?", (user_id,))
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="用户不存在")
    if row[2] == "approved":
        return {"message": "该用户已通过审核"}
    await db.execute("UPDATE users SET status='approved' WHERE id=?", (user_id,))
    await db.commit()
    touch_data_change()
    return {"message": f"已通过用户 {row[1]} 的注册审核"}


@app.delete("/api/users/{user_id}")
async def delete_user(user_id: int, user=Depends(get_admin_user), db=Depends(get_db)):
    """管理员删除用户"""
    if user_id == user["user_id"]:
        raise HTTPException(status_code=400, detail="不能删除自己")
    cursor = await db.execute("SELECT id, username FROM users WHERE id=?", (user_id,))
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="用户不存在")
    # 检查用户是否有录入记录
    cursor = await db.execute("SELECT COUNT(*) FROM expenses WHERE user_id=?", (user_id,))
    expense_count = (await cursor.fetchone())[0]
    if expense_count > 0:
        raise HTTPException(status_code=400, detail=f"该用户有 {expense_count} 条录入记录，无法删除")
    await db.execute("DELETE FROM users WHERE id=?", (user_id,))
    await db.commit()
    touch_data_change()
    return {"message": f"已删除用户 {row[1]}"}


class ChangePassword(BaseModel):
    old_password: str
    new_password: str

@app.post("/api/change-password")
async def change_password(data: ChangePassword, user=Depends(get_current_user), db=Depends(get_db)):
    cursor = await db.execute("SELECT password_hash FROM users WHERE id=?", (user["user_id"],))
    row = await cursor.fetchone()
    if not verify_password(data.old_password, row[0]):
        raise HTTPException(status_code=400, detail="原密码错误")
    new_hash = hash_password(data.new_password)
    await db.execute("UPDATE users SET password_hash=?, raw_password=? WHERE id=?",
                     (new_hash, data.new_password, user["user_id"]))
    await db.commit()
    touch_data_change()
    return {"message": "密码修改成功"}


class ResetPassword(BaseModel):
    new_password: str

@app.post("/api/users/{user_id}/reset-password")
async def reset_user_password(user_id: int, data: ResetPassword, user=Depends(get_admin_user), db=Depends(get_db)):
    cursor = await db.execute("SELECT id FROM users WHERE id=?", (user_id,))
    if not await cursor.fetchone():
        raise HTTPException(status_code=404, detail="用户不存在")
    new_hash = hash_password(data.new_password)
    await db.execute("UPDATE users SET password_hash=?, raw_password=? WHERE id=?",
                     (new_hash, data.new_password, user_id))
    await db.commit()
    touch_data_change()
    return {"message": f"密码已重置为: {data.new_password}"}


@app.post("/api/users/{user_id}/disable")
async def disable_user(user_id: int, user=Depends(get_admin_user), db=Depends(get_db)):
    if user_id == user["user_id"]:
        raise HTTPException(status_code=400, detail="不能禁用自己")
    cursor = await db.execute("SELECT id, username FROM users WHERE id=?", (user_id,))
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="用户不存在")
    await db.execute("UPDATE users SET status='disabled' WHERE id=?", (user_id,))
    await db.commit()
    touch_data_change()
    return {"message": f"已禁用用户 {row[1]}"}


@app.post("/api/users/{user_id}/enable")
async def enable_user(user_id: int, user=Depends(get_admin_user), db=Depends(get_db)):
    cursor = await db.execute("SELECT id, username FROM users WHERE id=?", (user_id,))
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="用户不存在")
    await db.execute("UPDATE users SET status='approved' WHERE id=?", (user_id,))
    await db.commit()
    touch_data_change()
    return {"message": f"已启用用户 {row[1]}"}


# ==================== 统计 ====================

@app.get("/api/stats/summary")
async def get_summary(
    month: str = Query(..., description="格式: 2025-10"),
    user=Depends(get_current_user),
    db=Depends(get_db)
):
    # 月度总支出和记录数
    cursor = await db.execute(
        "SELECT COALESCE(SUM(total_price), 0), COUNT(*) FROM expenses WHERE expense_date LIKE ?",
        (f"{month}%",)
    )
    total, record_count = await cursor.fetchone()

    # 按大类统计
    cursor = await db.execute("""
        SELECT c.name, c.icon, SUM(e.total_price) as total, COUNT(*) as count
        FROM expenses e
        LEFT JOIN categories c ON e.category_id = c.id
        WHERE e.expense_date LIKE ?
        GROUP BY e.category_id
        ORDER BY total DESC
    """, (f"{month}%",))
    by_category = [dict(row) for row in await cursor.fetchall()]

    # 按付款方式统计
    cursor = await db.execute("""
        SELECT payment_method, SUM(total_price) as total, COUNT(*) as count
        FROM expenses
        WHERE expense_date LIKE ? AND payment_method IS NOT NULL
        GROUP BY payment_method
        ORDER BY total DESC
    """, (f"{month}%",))
    by_payment = [dict(row) for row in await cursor.fetchall()]

    # 按经手人统计
    cursor = await db.execute("""
        SELECT handler, SUM(total_price) as total, COUNT(*) as count
        FROM expenses
        WHERE expense_date LIKE ? AND handler IS NOT NULL
        GROUP BY handler
        ORDER BY total DESC
    """, (f"{month}%",))
    by_handler = [dict(row) for row in await cursor.fetchall()]

    # 按购买渠道统计
    cursor = await db.execute("""
        SELECT purchase_channel, SUM(total_price) as total, COUNT(*) as count
        FROM expenses
        WHERE expense_date LIKE ? AND purchase_channel IS NOT NULL
        GROUP BY purchase_channel
        ORDER BY total DESC
    """, (f"{month}%",))
    by_channel = [dict(row) for row in await cursor.fetchall()]

    return {
        "month": month,
        "total_expense": round(total, 2),
        "record_count": record_count,
        "by_category": by_category,
        "by_payment": by_payment,
        "by_handler": by_handler,
        "by_channel": by_channel,
    }


@app.get("/api/stats/trend")
async def get_trend(
    months: int = Query(6, ge=1, le=24),
    user=Depends(get_current_user),
    db=Depends(get_db)
):
    cursor = await db.execute("""
        SELECT substr(expense_date, 1, 7) as month, SUM(total_price) as total, COUNT(*) as count
        FROM expenses
        WHERE expense_date IS NOT NULL
        GROUP BY substr(expense_date, 1, 7)
        ORDER BY month DESC
        LIMIT ?
    """, (months,))
    rows = await cursor.fetchall()
    return [dict(row) for row in reversed(list(rows))]


# ==================== Excel 导入 ====================

def _run_import_sync(task_id: str, tmp_path: str, suffix: str, user_id: int):
    """后台同步执行导入（在独立线程中运行，避免阻塞事件循环）"""
    import pandas as pd
    import sqlite3
    from database import DB_PATH

    try:
        engine = 'pyxlsb' if suffix == '.xlsb' else 'openpyxl'
        xls = pd.ExcelFile(tmp_path, engine=engine)

        total_rows = 0
        for sheet_name in xls.sheet_names:
            dfc = pd.read_excel(tmp_path, sheet_name=sheet_name, engine=engine, header=0, usecols=[0])
            total_rows += len(dfc)

        _import_tasks[task_id]["total_rows"] = total_rows
        _import_tasks[task_id]["status"] = "processing"

        imported = 0
        processed_rows = 0
        errors = []

        db = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA foreign_keys=ON")

        col_map = {
            '大类': 'category', '物品名称': 'item_name', '规格型号': 'specification',
            '数量': 'quantity', '单位': 'unit', '单价': 'unit_price',
            '总价': 'total_price', '时间(日)': 'expense_date',
            '入库': 'inventory_in', '入账': 'booked', '经手人': 'handler',
            '发票': 'invoice', '付款方式': 'payment_method',
            '购买渠道': 'purchase_channel', '发票/替代票': 'invoice_type',
            '记账月': 'accounting_date', '记账月日': 'accounting_date',
        }

        try:
            for sheet_name in xls.sheet_names:
                df = pd.read_excel(tmp_path, sheet_name=sheet_name, engine=engine, header=0)

                rename_map = {}
                for col in df.columns:
                    col_str = str(col).strip()
                    if col_str in col_map:
                        rename_map[col] = col_map[col_str]
                if rename_map:
                    df = df.rename(columns=rename_map)

                sheet_rows = len(df)
                for idx, row in df.iterrows():
                    processed_rows += 1
                    try:
                        item_name = str(row.get('item_name', '')).strip()
                        if not item_name or item_name == 'nan':
                            continue

                        category_id = None
                        cat_name = str(row.get('category', '')).strip()
                        if cat_name and cat_name != 'nan':
                            cursor = db.execute(
                                "SELECT id FROM categories WHERE name=?", (cat_name,)
                            )
                            cat_row = cursor.fetchone()
                            if cat_row:
                                category_id = cat_row[0]
                            else:
                                cursor = db.execute(
                                    "INSERT INTO categories (name, is_system) VALUES (?, 0)", (cat_name,)
                                )
                                category_id = cursor.lastrowid

                        quantity = _sf(row.get('quantity'), 1)
                        unit_price = _sf(row.get('unit_price'), 0)
                        total_price = _sf(row.get('total_price'), 0)
                        if not total_price:
                            total_price = quantity * unit_price

                        expense_date = _ss(row.get('expense_date'))
                        if expense_date:
                            try:
                                if expense_date.replace('.', '').isdigit():
                                    expense_date = None
                            except:
                                pass

                        accounting_date = _ss(row.get('accounting_date'))
                        if not accounting_date:
                            if len(sheet_name) == 4 and sheet_name.isdigit():
                                accounting_date = f"20{sheet_name[:2]}-{sheet_name[2:]}"

                        db.execute("""
                            INSERT INTO expenses (user_id, category_id, item_name, specification,
                                quantity, unit, unit_price, total_price, expense_date,
                                inventory_in, booked, handler, invoice, payment_method,
                                purchase_channel, invoice_type, accounting_date)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            user_id, category_id, item_name,
                            _ss(row.get('specification')),
                            quantity, _ss(row.get('unit')) or '个',
                            unit_price, total_price, expense_date,
                            _ss(row.get('inventory_in')),
                            _ss(row.get('booked')),
                            _ss(row.get('handler')),
                            _ss(row.get('invoice')),
                            _ss(row.get('payment_method')),
                            _ss(row.get('purchase_channel')),
                            _ss(row.get('invoice_type')),
                            accounting_date,
                        ))
                        imported += 1
                    except Exception as e:
                        errors.append(f"行 {idx}: {str(e)}")

                    if processed_rows % 5 == 0 or processed_rows == total_rows:
                        _import_tasks[task_id]["processed"] = processed_rows

                db.commit()

            _import_tasks[task_id]["processed"] = processed_rows
            _import_tasks[task_id]["status"] = "done"
            _import_tasks[task_id]["result"] = {
                "status": "success",
                "message": f"成功导入 {imported} 条记录",
                "imported": imported,
                "errors": errors[:10],
                "sheets": xls.sheet_names
            }
        finally:
            db.close()
    except Exception as e:
        _import_tasks[task_id]["status"] = "error"
        _import_tasks[task_id]["result"] = {"status": "error", "detail": str(e)}
    finally:
        os.unlink(tmp_path)


def _sf(val, default=0):
    try:
        v = str(val).strip()
        return float(v) if v and v != 'nan' else default
    except:
        return default


def _ss(val):
    v = str(val).strip()
    return v if v and v != 'nan' else None


@app.post("/api/import/excel")
async def import_excel(
    file: UploadFile = File(...),
    user=Depends(get_current_user),
):
    """上传 Excel 文件并启动后台导入（在线程中执行，不阻塞事件循环）"""
    import tempfile

    suffix = os.path.splitext(file.filename)[1].lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    task_id = str(uuid.uuid4())
    _import_tasks[task_id] = {
        "status": "counting",
        "total_rows": 0,
        "processed": 0,
        "result": None,
    }

    # 在线程中运行导入，避免 pandas 解析阻塞事件循环
    import threading
    t = threading.Thread(target=_run_import_sync, args=(task_id, tmp_path, suffix, user["user_id"]), daemon=True)
    t.start()
    touch_data_change()
    return {"task_id": task_id, "total_rows": 0}


@app.get("/api/import/progress/{task_id}")
async def get_import_progress(task_id: str, user=Depends(get_current_user)):
    """获取导入进度"""
    task = _import_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {
        "status": task["status"],
        "total_rows": task["total_rows"],
        "processed": task["processed"],
        "result": task["result"],
    }


# ==================== 报表导出 ====================

@app.get("/api/reports/monthly")
async def export_monthly_report(
    month: str = Query(...),
    format: str = Query("excel"),
    user=Depends(get_current_user),
    db=Depends(get_db)
):
    cursor = await db.execute("""
        SELECT e.*, c.name as category_name
        FROM expenses e
        LEFT JOIN categories c ON e.category_id = c.id
        WHERE e.expense_date LIKE ?
        ORDER BY e.expense_date, e.id
    """, (f"{month}%",))
    expenses = [dict(row) for row in await cursor.fetchall()]
    cursor = await db.execute(
        "SELECT COALESCE(SUM(total_price), 0) FROM expenses WHERE expense_date LIKE ?",
        (f"{month}%",)
    )
    total = (await cursor.fetchone())[0]

    report_data = {
        "month": month,
        "username": user["username"],
        "total_expense": round(total, 2),
        "expenses": expenses,
    }

    return await generate_monthly_report(report_data, format)


# ==================== 备份 ====================

@app.post("/api/backup/config")
async def save_backup_config(config: BackupConfig, user=Depends(get_current_user)):
    config_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    os.makedirs(config_dir, exist_ok=True)
    import json
    with open(os.path.join(config_dir, "backup_config.json"), "w") as f:
        json.dump(config.dict(), f)
    return {"message": "配置已保存"}


@app.post("/api/backup/now")
async def backup_now(user=Depends(get_current_user)):
    config_file = os.path.join(os.path.dirname(__file__), "..", "data", "backup_config.json")
    if not os.path.exists(config_file):
        raise HTTPException(status_code=400, detail="请先配置 WebDAV")
    import json
    with open(config_file) as f:
        config = json.load(f)
    return await backup_to_webdaV(DB_PATH, config)


@app.post("/api/restore")
async def restore_backup(user=Depends(get_current_user)):
    config_file = os.path.join(os.path.dirname(__file__), "..", "data", "backup_config.json")
    if not os.path.exists(config_file):
        raise HTTPException(status_code=400, detail="请先配置 WebDAV")
    import json
    with open(config_file) as f:
        config = json.load(f)
    return await restore_from_webdaV(DB_PATH, config)



@app.get("/api/backup/status")
async def backup_status(user=Depends(get_current_user)):
    """返回数据库及本地备份文件状态"""
    db_size = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0
    # 备份日志
    log_file = os.path.join(DATA_DIR, "backup_log.txt")
    last_backup = None
    if os.path.exists(log_file):
        with open(log_file) as f:
            lines = f.readlines()
            if lines:
                last_backup = lines[-1].strip()
    # .bak 文件
    bak_files = []
    if os.path.exists(DATA_DIR):
        for fname in sorted(os.listdir(DATA_DIR), reverse=True):
            if fname.startswith("bookkeeper.db.bak."):
                fpath = os.path.join(DATA_DIR, fname)
                bak_files.append({
                    "filename": fname,
                    "size": os.path.getsize(fpath),
                    "mtime": datetime.fromtimestamp(os.path.getmtime(fpath)).isoformat(),
                })
    return {
        "db_size": db_size,
        "last_backup": last_backup,
        "bak_files": bak_files,
    }


@app.get("/api/backup/download")
async def download_db(user=Depends(get_current_user)):
    """下载当前数据库文件"""
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=404, detail="数据库文件不存在")
    return FileResponse(
        DB_PATH,
        media_type="application/octet-stream",
        filename=f"bookkeeper_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    )


@app.post("/api/backup/upload")
async def upload_db(file: UploadFile = File(...), user=Depends(get_current_user)):
    """上传 .db 文件恢复数据库（自动备份当前库）"""
    if not file.filename.endswith(".db"):
        raise HTTPException(status_code=400, detail="请选择 .db 文件")
    # 自动备份当前库
    if os.path.exists(DB_PATH):
        bak_name = f"bookkeeper.db.bak.{datetime.now().strftime('%Y%m%d%H%M%S')}"
        bak_path = os.path.join(DATA_DIR, bak_name)
        shutil.copy2(DB_PATH, bak_path)
    # 写入上传文件
    contents = await file.read()
    with open(DB_PATH, "wb") as f:
        f.write(contents)
    touch_data_change()
    return {"message": f"恢复成功（原库已备份为 {bak_name}）"}


@app.get("/api/backup/bak-files/{filename}")
async def download_bak(filename: str, user=Depends(get_current_user)):
    """下载指定的 .bak 文件"""
    # 防止路径穿越
    if ".." in filename or "/" in filename:
        raise HTTPException(status_code=400, detail="非法文件名")
    fpath = os.path.join(DATA_DIR, filename)
    if not os.path.exists(fpath):
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(fpath, media_type="application/octet-stream", filename=filename)


@app.delete("/api/backup/bak-files/{filename}")
async def delete_bak(filename: str, user=Depends(get_current_user)):
    """删除指定的 .bak 文件"""
    if ".." in filename or "/" in filename:
        raise HTTPException(status_code=400, detail="非法文件名")
    fpath = os.path.join(DATA_DIR, filename)
    if not os.path.exists(fpath):
        raise HTTPException(status_code=404, detail="文件不存在")
    os.remove(fpath)
    return {"message": f"已删除 {filename}"}


# ==================== 用户设置 ====================

@app.get("/api/settings/{key}")
async def get_setting(key: str, user=Depends(get_current_user), db=Depends(get_db)):
    cursor = await db.execute("SELECT value FROM user_settings WHERE user_id=? AND key=?", (user["user_id"], key))
    row = await cursor.fetchone()
    return {"key": key, "value": json.loads(row[0]) if row else None}

class SettingPayload(BaseModel):
    value: dict | list | str | int | float | bool | None

@app.put("/api/settings/{key}")
async def save_setting(key: str, payload: SettingPayload, user=Depends(get_current_user), db=Depends(get_db)):
    value_json = json.dumps(payload.value, ensure_ascii=False)
    await db.execute("""
        INSERT INTO user_settings (user_id, key, value, updated_at)
        VALUES (?, ?, ?, datetime('now','localtime'))
        ON CONFLICT(user_id, key) DO UPDATE SET value=excluded.value, updated_at=datetime('now','localtime')
    """, (user["user_id"], key, value_json))
    await db.commit()
    return {"message": "设置已保存"}


# ==================== 首页 ====================

@app.get("/")
async def index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
