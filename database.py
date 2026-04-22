import aiosqlite
import shutil
import os

class BotDatabase:
    def __init__(self, db_path="/app/data/database.db"):
        self.db_path = db_path

        if not os.path.exists(self.db_path) and os.path.exists("database.db"):
            print("Found database on GitHub, copying to Volume...")
            shutil.copy("database.db", self.db_path)

    async def create_tables(self):
        async with aiosqlite.connect(self.db_path) as db:
            
            await db.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    money INTEGER DEFAULT 1000,
                    active_waifu TEXT DEFAULT NULL,
                    last_work TEXT DEFAULT NULL
                )
            ''')
            
            
            try:
                await db.execute("ALTER TABLE users ADD COLUMN last_work TEXT DEFAULT NULL")
                print("✅ Đã nâng cấp bảng users: Thêm cột last_work thành công.")
            except aiosqlite.OperationalError:
                # Nếu cột đã tồn tại thì bỏ qua lỗi này
                pass
            
            # Bảng kho đồ Waifu
            await db.execute('''
                CREATE TABLE IF NOT EXISTS inventory (
                    user_id INTEGER,
                    waifu_name TEXT,
                    level INTEGER DEFAULT 1,
                    exp INTEGER DEFAULT 0,
                    PRIMARY KEY (user_id, waifu_name)
                )
            ''')
            
            for col in [("level", "INTEGER DEFAULT 1"), ("exp", "INTEGER DEFAULT 0")]:
                try:
                    await db.execute(f"ALTER TABLE inventory ADD COLUMN {col[0]} {col[1]}")
                except aiosqlite.OperationalError: pass
            
            await db.execute('''
                CREATE TABLE IF NOT EXISTS user_items (
                    user_id INTEGER,
                    item_name TEXT,
                    quantity INTEGER DEFAULT 0,
                    PRIMARY KEY (user_id, item_name)
                )
            ''')
            
            await db.commit()
            print("✅ Database đã được nâng cấp: Thêm Level, Exp và bảng Items.")
            
    async def update_money(self, user_id, amount):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
            await db.execute("UPDATE users SET money = money + ? WHERE user_id = ?", (amount, user_id))
            await db.commit()
            
    async def get_money(self, user_id):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT money FROM users WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return row[0]
                return 1000

    async def get_user(self, user_id):
        async with aiosqlite.connect(self.db_path) as db:
            # Trả về cả 3 giá trị để khớp với các lệnh gọi unpack
            async with db.execute("SELECT money, active_waifu, last_work FROM users WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                if not row:
                    await db.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
                    await db.commit()
                    return (1000, None, None)
                return row
            
    async def get_inventory(self, user_id):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT waifu_name FROM inventory WHERE user_id = ?", (user_id,)) as cursor:
                rows = await cursor.fetchall()
                return [row[0] for row in rows]

    async def set_active_waifu(self, user_id, waifu_name):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE users SET active_waifu = ? WHERE user_id = ?", (waifu_name, user_id))
            await db.commit()
        
    async def add_waifu(self, user_id, waifu_name):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT OR IGNORE INTO inventory (user_id, waifu_name) VALUES (?, ?)", (user_id, waifu_name))
            await db.commit()
            
    async def update_work_time(self, user_id, time_str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE users SET last_work = ? WHERE user_id = ?", (time_str, user_id))
            await db.commit()
            
    async def get_user_full(self, user_id):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row 
            # JOIN để lấy level của waifu đang đeo từ bảng inventory
            sql = '''
                SELECT u.money, u.active_waifu, u.last_work, i.level, i.exp 
                FROM users u
                LEFT JOIN inventory i ON u.user_id = i.user_id AND u.active_waifu = i.waifu_name
                WHERE u.user_id = ?
            '''
            async with db.execute(sql, (user_id,)) as cursor:
                row = await cursor.fetchone()
                if not row:
                    await db.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
                    await db.commit()
                    return 1000, None, None, 1, 0
                
                # Sửa lỗi: Truy cập trực tiếp theo tên cột và xử lý giá trị None
                money = row['money']
                active = row['active_waifu']
                last_work = row['last_work']
                
                # Nếu waifu chưa có trong inventory (NULL), mặc định lv 1 và 0 exp
                level = row['level'] if row['level'] is not None else 1
                exp = row['exp'] if row['exp'] is not None else 0
                
                return money, active, last_work, level, exp
            
    # Hàm cập nhật EXP và Level
    async def update_waifu_exp(self, user_id, waifu_name, amount):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT exp, level FROM inventory WHERE user_id = ? AND waifu_name = ?", 
                (user_id, waifu_name)
            ) as cursor:
                row = await cursor.fetchone()
                if not row: return None
                
                new_exp = row[0] + amount
                new_level = row[1]
                
                # --- LOGIC GIỚI HẠN LEVEL 4 ---
                MAX_LEVEL = 4
                
                while new_exp >= (new_level * 100):
                    if new_level >= MAX_LEVEL:
                        new_exp = 0 # Nếu đạt max level thì reset exp dư hoặc giữ nguyên tùy An
                        break
                    new_exp -= (new_level * 100)
                    new_level += 1
                
                # Nếu đã ở Level 4 thì exp luôn là 0 hoặc một mốc cố định
                if new_level >= MAX_LEVEL:
                    new_level = MAX_LEVEL
                    new_exp = 0 
                # ------------------------------

                await db.execute(
                    "UPDATE inventory SET exp = ?, level = ? WHERE user_id = ? AND waifu_name = ?",
                    (new_exp, new_level, user_id, waifu_name)
                )
                await db.commit()
                return new_level, new_exp

    # Hàm quản lý Item (Mua/Dùng)
    async def update_item_quantity(self, user_id, item_name, amount):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT INTO user_items (user_id, item_name, quantity) 
                VALUES (?, ?, ?)
                ON CONFLICT(user_id, item_name) 
                DO UPDATE SET quantity = quantity + ?
            ''', (user_id, item_name, amount, amount))
            await db.commit()
            
    async def get_all_waifus(self, user_id):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            # Giả sử bảng inventory của An có cột joined_at để hiện ngày nhận
            sql = "SELECT waifu_name, level FROM inventory WHERE user_id = ?"
            async with db.execute(sql, (user_id,)) as cursor:
                return await cursor.fetchall()
            
    async def get_waifu_data(self, user_id, waifu_name):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            sql = "SELECT level, exp FROM inventory WHERE user_id = ? AND waifu_name = ?"
            async with db.execute(sql, (user_id, waifu_name)) as cursor:
                return await cursor.fetchone()
