import sqlite3


conn = sqlite3.connect("ayurveda.db")
cursor = conn.cursor()

for table in ["consultation_metrics", "ai_feedback", "doctor_activity_log"]:
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [col[1] for col in cursor.fetchall()]
    print(f"{table}: {len(columns)} columns - {columns}")

conn.close()
