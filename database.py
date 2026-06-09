import csv
import sqlite3
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_DIR = BASE_DIR / "database"
DB_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DB_DIR / "attendance.db"


def connect_db():
    """Create a connection to the SQLite database."""
    return sqlite3.connect(DB_PATH)


def initialize_database():
    """Initialize the students and attendance tables and migrate schema if needed."""
    conn = connect_db()
    cursor = conn.cursor()
    
    # Teachers table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS teachers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            name TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            roll_no TEXT NOT NULL UNIQUE,
            department TEXT,
            semester TEXT,
            classroom TEXT,
            folder_name TEXT
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            date TEXT,
            time TEXT,
            status TEXT,
            subject TEXT,
            FOREIGN KEY(student_id) REFERENCES students(id)
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS classrooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            classroom_name TEXT NOT NULL UNIQUE
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            classroom TEXT NOT NULL,
            subject_name TEXT NOT NULL,
            UNIQUE(classroom, subject_name)
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS attendance_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            classroom TEXT,
            subject TEXT,
            start_time TEXT,
            end_time TEXT,
            status TEXT
        )
        """
    )
    cursor.execute("PRAGMA table_info(students)")
    columns = [row[1] for row in cursor.fetchall()]
    if "classroom" not in columns:
        cursor.execute("ALTER TABLE students ADD COLUMN classroom TEXT")
    cursor.execute("PRAGMA table_info(attendance)")
    attendance_columns = [row[1] for row in cursor.fetchall()]
    if "subject" not in attendance_columns:
        cursor.execute("ALTER TABLE attendance ADD COLUMN subject TEXT")
    conn.commit()
    conn.close()


def add_student(name, roll_no, department, semester, classroom, folder_name):
    """Insert a new student record into the students table."""
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO students (name, roll_no, department, semester, classroom, folder_name) VALUES (?, ?, ?, ?, ?, ?)",
            (name, roll_no, department, semester, classroom, folder_name),
        )
        conn.commit()
        student_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        student_id = None
    conn.close()
    return student_id


def get_all_students():
    """Return all registered students."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, name, roll_no, department, semester, classroom, folder_name FROM students ORDER BY name"
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_student_by_roll(roll_no):
    """Find a student by roll number."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, name, roll_no, department, semester, classroom, folder_name FROM students WHERE roll_no = ?",
        (roll_no,),
    )
    row = cursor.fetchone()
    conn.close()
    return row


def get_student_by_id(student_id):
    """Find a student by database id."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, name, roll_no, department, semester, classroom, folder_name FROM students WHERE id = ?",
        (student_id,),
    )
    row = cursor.fetchone()
    conn.close()
    return row


def attendance_exists(student_id, date, subject=None):
    """Return True if attendance is already marked for the student on the given date and subject."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM attendance WHERE student_id = ? AND date = ? AND COALESCE(subject, '') = ?",
        (student_id, date, subject or ""),
    )
    row = cursor.fetchone()
    conn.close()
    return row is not None


def mark_attendance(student_id, date, time, status="Present", subject=None):
    """Mark attendance for a student if not already recorded for the date and subject."""
    if attendance_exists(student_id, date, subject):
        return False
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO attendance (student_id, date, time, status, subject) VALUES (?, ?, ?, ?, ?)",
        (student_id, date, time, status, subject or ""),
    )
    conn.commit()
    conn.close()
    return True


def get_attendance_records(filters=None):
    """Return attendance records with optional filtering."""
    conn = connect_db()
    cursor = conn.cursor()
    query = (
        "SELECT attendance.id, students.name, students.roll_no, students.department, students.semester, students.classroom, attendance.subject, attendance.date, attendance.time, attendance.status "
        "FROM attendance "
        "INNER JOIN students ON attendance.student_id = students.id "
    ""
    )
    params = []
    if filters:
        conditions = []
        if filters.get("roll_no"):
            conditions.append("students.roll_no = ?")
            params.append(filters["roll_no"])
        if filters.get("date"):
            conditions.append("attendance.date = ?")
            params.append(filters["date"])
        if filters.get("classroom"):
            conditions.append("students.classroom = ?")
            params.append(filters["classroom"])
        if filters.get("subject"):
            conditions.append("COALESCE(attendance.subject, '') = ?")
            params.append(filters["subject"])
        if conditions:
            query += "WHERE " + " AND ".join(conditions) + " "
    query += "ORDER BY attendance.date DESC, attendance.time DESC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_attendance_summary():
    """Return summary of attendance percentage per student."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT students.name, students.roll_no, COUNT(attendance.id) as present_count "
        "FROM students LEFT JOIN attendance ON students.id = attendance.student_id "
        "GROUP BY students.id "
        "ORDER BY students.name"
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def export_attendance_to_csv(csv_path):
    """Export all attendance records to a CSV file."""
    records = get_attendance_records()
    headers = ["Record ID", "Name", "Roll Number", "Department", "Semester", "Classroom", "Subject", "Date", "Time", "Status"]
    with open(csv_path, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(headers)
        writer.writerows(records)
    return csv_path

def add_classroom(classroom_name):
    """Add a new classroom name into the classrooms table."""
    if not classroom_name:
        return None
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO classrooms (classroom_name) VALUES (?)",
            (classroom_name.strip(),),
        )
        conn.commit()
        classroom_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        classroom_id = None
    conn.close()
    return classroom_id


def add_subject(classroom, subject_name):
    """Add a new subject for a classroom."""
    if not classroom or not subject_name:
        return None
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO subjects (classroom, subject_name) VALUES (?, ?)",
            (classroom, subject_name.strip()),
        )
        conn.commit()
        subject_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        subject_id = None
    conn.close()
    return subject_id


def get_subjects(classroom=None):
    """Return a list of subjects filtered by classroom or all subjects."""
    conn = connect_db()
    cursor = conn.cursor()
    if classroom:
        cursor.execute(
            "SELECT subject_name FROM subjects WHERE classroom = ? ORDER BY subject_name",
            (classroom,),
        )
    else:
        cursor.execute("SELECT DISTINCT subject_name FROM subjects ORDER BY subject_name")
    rows = [row[0] for row in cursor.fetchall()]
    conn.close()
    return rows


def get_default_subject_for_classroom(classroom):
    """Return the first registered subject for a classroom, or None if no subjects exist."""
    if not classroom:
        return None
    subjects = get_subjects(classroom)
    return subjects[0] if subjects else None


def log_attendance_session(classroom, subject, start_time, end_time=None, status="Active"):
    """Log a teacher attendance session in the database."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO attendance_sessions (classroom, subject, start_time, end_time, status) VALUES (?, ?, ?, ?, ?)",
        (classroom or "", subject or "", start_time, end_time or "", status),
    )
    conn.commit()
    session_id = cursor.lastrowid
    conn.close()
    return session_id


def update_attendance_session(session_id, end_time, status):
    """Update an existing attendance session record."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE attendance_sessions SET end_time = ?, status = ? WHERE id = ?",
        (end_time, status, session_id),
    )
    conn.commit()
    conn.close()


def get_attendance_sessions():
    """Return all logged attendance sessions."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, classroom, subject, start_time, end_time, status FROM attendance_sessions ORDER BY id DESC"
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_classrooms():
    """Return a list of registered classroom names, falling back on student classrooms if needed."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT classroom_name FROM classrooms ORDER BY classroom_name")
    rows = [row[0] for row in cursor.fetchall()]
    if not rows:
        cursor.execute("SELECT DISTINCT classroom FROM students WHERE classroom IS NOT NULL AND classroom != '' ORDER BY classroom")
        rows = [row[0] for row in cursor.fetchall()]
    conn.close()
    return rows


def get_classroom_by_name(name):
    """Return a classroom record by its name."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, classroom_name FROM classrooms WHERE classroom_name = ?", (name,))
    row = cursor.fetchone()
    conn.close()
    return row


# ─── Teacher Authentication ────────────────────────────────────────────────────

def add_teacher(email, password, name="Teacher"):
    """Add a new teacher to the database."""
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO teachers (email, password, name) VALUES (?, ?, ?)",
            (email.lower(), password, name),
        )
        conn.commit()
        teacher_id = cursor.lastrowid
        conn.close()
        return teacher_id
    except sqlite3.IntegrityError:
        conn.close()
        return None


def get_teacher_by_email(email):
    """Get teacher by email address."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, email, password, name FROM teachers WHERE email = ?", (email.lower(),))
    row = cursor.fetchone()
    conn.close()
    return row


def verify_teacher(email, password):
    """Verify teacher email and password. Returns teacher info if valid, None otherwise."""
    teacher = get_teacher_by_email(email)
    if teacher and teacher[2] == password:  # teacher[2] is password
        return {"id": teacher[0], "email": teacher[1], "name": teacher[3]}
    return None


if __name__ == "__main__":
    initialize_database()
    print(f"Database initialized at {DB_PATH}")
