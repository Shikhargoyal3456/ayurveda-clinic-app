import sqlite3
import datetime

conn = sqlite3.connect('ayurveda.db')
cursor = conn.cursor()

# First, check if there's a doctor
cursor.execute("SELECT id FROM doctors LIMIT 1")
doctor = cursor.fetchone()

if doctor:
    doctor_id = doctor[0]
    print(f"✅ Found doctor with ID: {doctor_id}")
else:
    # Create a doctor if none exists
    cursor.execute("""
        INSERT INTO doctors (name, email, phone, created_at)
        VALUES (?, ?, ?, ?)
    """, ("Dr. Test", "doctor@test.com", "8888888888", datetime.datetime.now()))
    doctor_id = cursor.lastrowid
    print(f"✅ Created new doctor with ID: {doctor_id}")

# Add test patient with doctor_id
cursor.execute("""
    INSERT INTO patients (name, age, phone, email, doctor_id, created_at)
    VALUES (?, ?, ?, ?, ?, ?)
""", ("Test Patient", 30, "9999999999", "test@patient.com", doctor_id, datetime.datetime.now()))

conn.commit()
print("✅ Patient added successfully")

# Verify
cursor.execute("SELECT id, name, age, phone, email, doctor_id FROM patients ORDER BY id DESC LIMIT 1")
print(cursor.fetchall())

conn.close()