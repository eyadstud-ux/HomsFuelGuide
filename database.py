
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).with_name("fuel_reports.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                station_name TEXT NOT NULL,
                area TEXT NOT NULL,
                fuel_type TEXT NOT NULL,
                availability TEXT NOT NULL,
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (
                    datetime('now', 'localtime')
                )
            )
        """)


def add_report(
    station_name,
    area,
    fuel_type,
    availability,
    notes=""
):
    with get_connection() as conn:
        cursor = conn.execute("""
            INSERT INTO reports (
                station_name,
                area,
                fuel_type,
                availability,
                notes
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            station_name,
            area,
            fuel_type,
            availability,
            notes
        ))
        return cursor.lastrowid


def get_reports(limit=10):
    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT *
            FROM reports
            ORDER BY id DESC
            LIMIT ?
        """, (limit,))
        return cursor.fetchall()

def get_recent_reports(hours=6, limit=10):
    """إرجاع البلاغات المسجلة خلال آخر عدد محدد من الساعات."""
    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT *
            FROM reports
            WHERE datetime(created_at) >= datetime('now', 'localtime', ?)
            ORDER BY id DESC
            LIMIT ?
        """, (f"-{hours} hours", limit))
        return cursor.fetchall()

def is_duplicate_report(
    station_name,
    area,
    fuel_type,
    availability,
    minutes=30,
):
    """التحقق من وجود بلاغ مطابق خلال آخر عدد محدد من الدقائق."""
    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT 1
            FROM reports
            WHERE station_name = ?
              AND area = ?
              AND fuel_type = ?
              AND availability = ?
              AND datetime(created_at) >=
                  datetime('now', 'localtime', ?)
            LIMIT 1
        """, (
            station_name.strip(),
            area.strip(),
            fuel_type,
            availability,
            f"-{minutes} minutes",
        ))

        return cursor.fetchone() is not None

def get_area_report_counts(hours=6):
    """إحصاء البلاغات الحديثة حسب المنطقة."""
    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT area, COUNT(*) AS report_count
            FROM reports
            WHERE datetime(created_at) >=
                datetime('now', 'localtime', ?)
            GROUP BY area
            ORDER BY report_count DESC, area ASC
        """, (f"-{hours} hours",))

        return cursor.fetchall()
