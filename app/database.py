import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from zoneinfo import ZoneInfo

DATABASE_URL = os.getenv("DATABASE_URL")
UZ_TZ = ZoneInfo("Asia/Tashkent")


def get_connection():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


def init_db():
    conn = get_connection()
    cur = conn.cursor()
    
    # Foydalanuvchilar jadvali
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            first_name TEXT,
            latitude FLOAT,
            longitude FLOAT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    
    # Vazifalar jadvali
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id SERIAL PRIMARY KEY,
            user_id BIGINT REFERENCES users(user_id),
            task_text TEXT,
            scheduled_time TIMESTAMP WITH TIME ZONE,
            is_done BOOLEAN DEFAULT FALSE,
            reminded BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    
    # Status ustunini qo'shish (migratsiya)
    cur.execute("""
        ALTER TABLE tasks 
        ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'pending'
    """)
    
    # Xabarlar tarixi (AI kontekst uchun)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            role VARCHAR(20) NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    
    # YANGI: Namoz vaqtlari jadvali
    cur.execute("""
        CREATE TABLE IF NOT EXISTS prayer_times (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            date DATE NOT NULL,
            fajr TIME NOT NULL,
            dhuhr TIME NOT NULL,
            asr TIME NOT NULL,
            maghrib TIME NOT NULL,
            isha TIME NOT NULL,
            reminded_fajr BOOLEAN DEFAULT FALSE,
            reminded_dhuhr BOOLEAN DEFAULT FALSE,
            reminded_asr BOOLEAN DEFAULT FALSE,
            reminded_maghrib BOOLEAN DEFAULT FALSE,
            reminded_isha BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(user_id, date)
        )
    """)
    
    # Index'lar
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_tasks_pending 
        ON tasks(scheduled_time) 
        WHERE is_done = FALSE AND reminded = FALSE
    """)
    
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_messages_user 
        ON messages(user_id, created_at DESC)
    """)
    
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_prayer_times_user_date 
        ON prayer_times(user_id, date)
    """)
    
    conn.commit()
    cur.close()
    conn.close()
    print("✅ Database initialized!")


def save_user(user_id, first_name):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO users (user_id, first_name)
        VALUES (%s, %s)
        ON CONFLICT (user_id) DO NOTHING
    """, (user_id, first_name))
    conn.commit()
    cur.close()
    conn.close()


def save_task(user_id, task_text, scheduled_datetime):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO tasks (user_id, task_text, scheduled_time)
        VALUES (%s, %s, %s)
    """, (user_id, task_text, scheduled_datetime))
    conn.commit()
    cur.close()
    conn.close()


def get_pending_tasks():
    conn = get_connection()
    cur = conn.cursor()
    now_uz = datetime.now(UZ_TZ)
    cur.execute("""
        SELECT * FROM tasks 
        WHERE scheduled_time <= %s 
        AND is_done = FALSE 
        AND reminded = FALSE
    """, (now_uz,))
    tasks = cur.fetchall()
    cur.close()
    conn.close()
    return tasks


def mark_reminded(task_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE tasks SET reminded = TRUE WHERE id = %s", (task_id,))
    conn.commit()
    cur.close()
    conn.close()


def mark_done(task_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE tasks SET is_done = TRUE WHERE id = %s", (task_id,))
    conn.commit()
    cur.close()
    conn.close()


def mark_task_status(task_id: int, status: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE tasks 
        SET is_done = TRUE, status = %s 
        WHERE id = %s
    """, (status, task_id))
    conn.commit()
    cur.close()
    conn.close()


# === XABARLAR TARIXI ===

def save_message(user_id: int, role: str, content: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO messages (user_id, role, content)
        VALUES (%s, %s, %s)
    """, (user_id, role, content))
    conn.commit()
    cur.close()
    conn.close()


def get_recent_messages(user_id: int, limit: int = 10) -> list:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT role, content FROM messages 
        WHERE user_id = %s 
        ORDER BY created_at DESC 
        LIMIT %s
    """, (user_id, limit))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


def cleanup_old_messages(user_id: int, keep_last: int = 50):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        DELETE FROM messages 
        WHERE user_id = %s 
        AND id NOT IN (
            SELECT id FROM messages 
            WHERE user_id = %s 
            ORDER BY created_at DESC 
            LIMIT %s
        )
    """, (user_id, user_id, keep_last))
    conn.commit()
    cur.close()
    conn.close()


# === NAMOZ VAQTLARI FUNKSIYALARI (YANGI) ===

def save_user_location(user_id: int, latitude: float, longitude: float):
    """Foydalanuvchi lokatsiyasini saqlash"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE users 
        SET latitude = %s, longitude = %s 
        WHERE user_id = %s
    """, (latitude, longitude, user_id))
    conn.commit()
    cur.close()
    conn.close()


def get_user_location(user_id: int):
    """Foydalanuvchi lokatsiyasini olish"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT latitude, longitude FROM users WHERE user_id = %s
    """, (user_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    
    if row and row["latitude"] and row["longitude"]:
        return row["latitude"], row["longitude"]
    return None


def save_prayer_times(user_id: int, date, times: dict):
    """times: {"fajr": "05:30", "dhuhr": "13:00", ...}"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO prayer_times (user_id, date, fajr, dhuhr, asr, maghrib, isha)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (user_id, date) DO UPDATE SET
            fajr = EXCLUDED.fajr,
            dhuhr = EXCLUDED.dhuhr,
            asr = EXCLUDED.asr,
            maghrib = EXCLUDED.maghrib,
            isha = EXCLUDED.isha
    """, (
        user_id, date,
        times["fajr"], times["dhuhr"], times["asr"],
        times["maghrib"], times["isha"]
    ))
    conn.commit()
    cur.close()
    conn.close()


def get_prayer_times(user_id: int, date):
    """Berilgan kun uchun namoz vaqtlarini olish"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT fajr, dhuhr, asr, maghrib, isha
        FROM prayer_times 
        WHERE user_id = %s AND date = %s
    """, (user_id, date))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return dict(row) if row else None


def get_users_with_location():
    """Lokatsiya bergan barcha foydalanuvchilar"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT user_id, latitude, longitude FROM users 
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(r) for r in rows]


def get_upcoming_prayer_reminders():
    """15 daqiqa ichida bo'ladigan namozlarni topish"""
    from datetime import timedelta
    
    conn = get_connection()
    cur = conn.cursor()
    now_uz = datetime.now(UZ_TZ)
    today = now_uz.date()
    current_time = now_uz.time()
    future_time = (now_uz + timedelta(minutes=15)).time()
    
    cur.execute("""
        SELECT id, user_id, date, fajr, dhuhr, asr, maghrib, isha,
               reminded_fajr, reminded_dhuhr, reminded_asr, 
               reminded_maghrib, reminded_isha
        FROM prayer_times
        WHERE date = %s
    """, (today,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    
    reminders = []
    prayers = ["fajr", "dhuhr", "asr", "maghrib", "isha"]
    prayer_names_uz = {
        "fajr": "Bomdod", "dhuhr": "Peshin", "asr": "Asr",
        "maghrib": "Shom", "isha": "Xufton"
    }
    
    for row in rows:
        row = dict(row)
        for prayer in prayers:
            prayer_time = row[prayer]
            already_reminded = row[f"reminded_{prayer}"]
            
            if already_reminded:
                continue
            
            if current_time <= prayer_time <= future_time:
                reminders.append({
                    "id": row["id"],
                    "user_id": row["user_id"],
                    "prayer": prayer,
                    "prayer_name_uz": prayer_names_uz[prayer],
                    "time": prayer_time
                })
    
    return reminders


def mark_prayer_reminded(prayer_times_id: int, prayer: str):
    """Namoz eslatilgan deb belgilash"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"""
        UPDATE prayer_times 
        SET reminded_{prayer} = TRUE 
        WHERE id = %s
    """, (prayer_times_id,))
    conn.commit()
    cur.close()
    conn.close()