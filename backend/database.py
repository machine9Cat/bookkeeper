"""数据库模型 - 适配单位采购支出记账"""
import aiosqlite
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "bookkeeper.db")


async def get_db():
    """获取数据库连接"""
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    try:
        yield db
    finally:
        await db.close()


async def init_db():
    """初始化数据库表"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA foreign_keys=ON")

        # 用户表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                raw_password TEXT,
                email TEXT,
                role TEXT DEFAULT 'user',
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT (datetime('now', 'localtime')),
                updated_at TEXT DEFAULT (datetime('now', 'localtime'))
            )
        """)
        # 兼容旧表：添加 raw_password 列（若不存在）
        try:
            await db.execute("ALTER TABLE users ADD COLUMN raw_password TEXT")
        except Exception:
            pass

        # 大类表 (如：生产物料、办公用品等)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                name TEXT NOT NULL,
                icon TEXT DEFAULT '📦',
                is_system INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # 支出记录表 (核心表，对应 Excel 的每一行)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                category_id INTEGER,
                item_name TEXT NOT NULL,
                specification TEXT,
                quantity REAL DEFAULT 1,
                unit TEXT DEFAULT '个',
                unit_price REAL DEFAULT 0,
                total_price REAL DEFAULT 0,
                expense_date TEXT,
                inventory_in TEXT,
                booked TEXT,
                handler TEXT,
                invoice TEXT,
                payment_method TEXT,
                purchase_channel TEXT,
                invoice_type TEXT,
                accounting_date TEXT,
                reviewed INTEGER DEFAULT 0,
                reviewed_by INTEGER,
                reviewed_at TEXT,
                note TEXT,
                created_at TEXT DEFAULT (datetime('now', 'localtime')),
                updated_at TEXT DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (category_id) REFERENCES categories(id)
            )
        """)

        # 付款方式表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS payment_methods (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                name TEXT NOT NULL,
                is_system INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # 购买渠道表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                name TEXT NOT NULL,
                is_system INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # 经手人表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS handlers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                name TEXT NOT NULL,
                is_system INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # 单位表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS units (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                name TEXT NOT NULL,
                is_system INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # 物品名称字典表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS item_names (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                name TEXT NOT NULL,
                is_system INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # 规格型号字典表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS specifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                name TEXT NOT NULL,
                is_system INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # 插入默认单位
        cursor = await db.execute("SELECT COUNT(*) FROM units WHERE is_system = 1")
        count = (await cursor.fetchone())[0]
        if count == 0:
            default_units = [
                ("个", 1), ("只", 1), ("套", 1), ("件", 1), ("箱", 1),
                ("包", 1), ("瓶", 1), ("盒", 1), ("条", 1), ("双", 1),
                ("台", 1), ("张", 1), ("把", 1), ("根", 1), ("米", 1),
                ("千克", 1), ("斤", 1), ("两", 1), ("升", 1), ("毫升", 1),
                ("罐", 1), ("卷", 1), ("袋", 1), ("副", 1), ("块", 1),
            ]
            await db.executemany(
                "INSERT INTO units (name, is_system, user_id) VALUES (?, ?, NULL)",
                default_units
            )

        # 备份记录表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS backup_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                type TEXT NOT NULL,
                status TEXT NOT NULL,
                file_path TEXT,
                file_size INTEGER,
                message TEXT,
                created_at TEXT DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # 用户设置表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                updated_at TEXT DEFAULT (datetime('now', 'localtime')),
                PRIMARY KEY (user_id, key),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # 创建索引
        await db.execute("CREATE INDEX IF NOT EXISTS idx_expenses_user ON expenses(user_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(expense_date)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses(category_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_expenses_month ON expenses(accounting_date)")

        await db.commit()

        # 插入默认系统大类
        cursor = await db.execute("SELECT COUNT(*) FROM categories WHERE is_system = 1")
        count = (await cursor.fetchone())[0]
        if count == 0:
            default_categories = [
                ("生产物料", "🏭", 1),
                ("办公用品", "📎", 1),
                ("劳保用品", "🧤", 1),
                ("设备配件", "🔧", 1),
                ("五金工具", "🔨", 1),
                ("电器电料", "💡", 1),
                ("清洁用品", "🧹", 1),
                ("包装材料", "📦", 1),
                ("运输费用", "🚚", 1),
                ("维修费用", "🛠️", 1),
                ("其他支出", "💰", 1),
            ]
            await db.executemany(
                "INSERT INTO categories (name, icon, is_system, user_id) VALUES (?, ?, ?, NULL)",
                default_categories
            )

        # 插入默认付款方式
        cursor = await db.execute("SELECT COUNT(*) FROM payment_methods WHERE is_system = 1")
        count = (await cursor.fetchone())[0]
        if count == 0:
            default_methods = [
                ("现金", 1), ("银行转账", 1), ("微信", 1),
                ("支付宝", 1), ("支票", 1), ("其他", 1),
            ]
            await db.executemany(
                "INSERT INTO payment_methods (name, is_system, user_id) VALUES (?, ?, NULL)",
                default_methods
            )

        # 插入默认购买渠道
        cursor = await db.execute("SELECT COUNT(*) FROM channels WHERE is_system = 1")
        count = (await cursor.fetchone())[0]
        if count == 0:
            default_channels = [
                ("淘宝", 1), ("京东", 1), ("拼多多", 1),
                ("实体店", 1), ("批发市场", 1), ("厂家直销", 1),
                ("其他", 1),
            ]
            await db.executemany(
                "INSERT INTO channels (name, is_system, user_id) VALUES (?, ?, NULL)",
                default_channels
            )

        await db.commit()
        print("✅ 数据库初始化完成")
