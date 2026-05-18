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
    
    # DIQQAT: DROP TABLE OLIB TASHLANDI — vazifalar saqlanib qoladi
    
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
    
    # YANGI: xabarlar tarixi (AI kontekst uchun)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            role VARCHAR(20) NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    
    # Index'lar (tezlik uchun)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_tasks_pending 
        ON tasks(scheduled_time) 
        WHERE is_done = FALSE AND reminded = FALSE
    """)
    
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_messages_user 
        ON messages(user_id, created_at DESC)
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


# YANGI FUNKSIYALAR — xabarlar tarixi uchun

def save_message(user_id: int, role: str, content: str):
    """
    role: 'user' yoki 'assistant'
    content: xabar matni
    """
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
    """
    Foydalanuvchining oxirgi N ta xabarini xronologik tartibda qaytaradi.
    AI uchun kontekst sifatida ishlatiladi.
    """
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
    
    # Eskidan yangiga qarab qaytarish
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


def cleanup_old_messages(user_id: int, keep_last: int = 50):
    """
    Eski xabarlarni o'chiradi — baza katta bo'lib ketmasligi uchun.
    Foydalanuvchi uchun faqat oxirgi N ta xabarni saqlaydi.
    """
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

def mark_task_status(task_id: int, status: str):
    """
    status: 'done' yoki 'skipped'
    """
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
