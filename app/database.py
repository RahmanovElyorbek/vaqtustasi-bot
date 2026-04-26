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
    
    # ⚠️ VAQTINCHALIK: eski jadvalni o'chirish
    cur.execute("DROP TABLE IF EXISTS tasks CASCADE")
    
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
    
    # Vazifalar jadvali — yangi format
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
    
    conn.commit()
    cur.close()
    conn.close()
    print("Database initialized!")

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
    """
    scheduled_datetime — datetime obyekti (timezone bilan)
    """
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
    """
    Vaqti yetib kelgan, lekin hali eslatilmagan vazifalarni qaytaradi.
    """
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