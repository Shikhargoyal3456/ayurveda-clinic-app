import sqlite3


conn = sqlite3.connect("ayurveda.db")
cursor = conn.cursor()

TABLES = {"consultation_metrics", "ai_feedback", "doctor_activity_log"}

for table in sorted(TABLES):
    cursor.execute("SELECT * FROM pragma_table_info(?)", (table,))
    columns = [col[1] for col in cursor.fetchall()]
    print(f"{table}: {len(columns)} columns - {columns}")

conn.close()
