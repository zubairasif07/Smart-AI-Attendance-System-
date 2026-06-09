"""
Flask Web UI for Smart AI Face Recognition Attendance System.
Run:  python app.py
"""

import io
import threading
from datetime import datetime
from pathlib import Path

from flask import (
    Flask,
    Response,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
    session,
)

import database
from attendance_system import (
    clear_active_sessions,
    load_active_sessions,
    save_active_sessions,
    start_attendance_session,
    start_student_attendance_session,
)
import numpy as np
import cv2
import face_recognition
from attendance_system import load_encodings

# Cache loaded encodings to avoid re-reading pickle on every request
KNOWN_ENCODINGS_CACHE = None
from export_report import (
    get_attendance_dataframe,
    plot_attendance_summary,
    save_attendance_csv,
)
from register_student import register_student
from train_model import train_face_encodings

BASE_DIR = Path(__file__).resolve().parent
ENCODING_FILE = BASE_DIR / "encodings" / "face_encodings.pkl"

app = Flask(__name__)
app.url_map.strict_slashes = False
app.secret_key = "attendance-system-secret-2024"

database.initialize_database()

# ─── Background attendance thread tracking ────────────────────────────────────
_attendance_thread: threading.Thread | None = None
_attendance_stop_event: threading.Event | None = None
_attendance_status: dict = {"running": False, "message": "Idle"}
_current_session_id: int | None = None

# ─── Async student registration task tracking ─────────────────────────────────
import uuid
_registration_tasks: dict = {}   # task_id -> {status, message, student_name}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _stats() -> dict:
    """Return quick summary stats for the dashboard."""
    conn = database.connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM students")
    total_students = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM attendance")
    total_records = cursor.fetchone()[0]
    cursor.execute(
        "SELECT COUNT(*) FROM attendance WHERE date = ?",
        (datetime.now().strftime("%Y-%m-%d"),),
    )
    today_records = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM classrooms")
    total_classrooms = cursor.fetchone()[0]
    conn.close()
    return {
        "total_students": total_students,
        "total_records": total_records,
        "today_records": today_records,
        "total_classrooms": total_classrooms,
    }


def login_required(f):
    """Decorator to require teacher login for routes."""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "teacher_id" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Teacher login page."""
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        
        teacher = database.verify_teacher(email, password)
        if teacher:
            session["teacher_id"] = teacher["id"]
            session["teacher_email"] = teacher["email"]
            session["teacher_name"] = teacher["name"]
            flash(f"Welcome, {teacher['name']}!", "success")
            return redirect(url_for("teacher_dashboard"))
        else:
            flash("Invalid email or password.", "error")
    
    return render_template("login.html")


@app.route("/logout")
def logout():
    """Logout teacher."""
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("index"))


# ── Teacher Dashboard ─────────────────────────────────────────────────────────

@app.route("/teacher")
@login_required
def teacher_dashboard():
    stats = _stats()
    return render_template("teacher_dashboard.html", stats=stats)


# ── Student Management ────────────────────────────────────────────────────────

@app.route("/teacher/students")
@login_required
def students():
    students_list = database.get_all_students()
    classrooms = database.get_classrooms()
    return render_template(
        "students.html", students=students_list, classrooms=classrooms
    )


@app.route("/teacher/students/register", methods=["POST"])
@login_required
def register():
    """Synchronous registration (fallback / legacy)."""
    name = request.form.get("name", "").strip()
    roll_no = request.form.get("roll_no", "").strip()
    department = request.form.get("department", "").strip()
    semester = request.form.get("semester", "").strip()
    classroom = request.form.get("classroom", "").strip()

    if not all([name, roll_no, department, semester, classroom]):
        flash("All fields are required.", "error")
        return redirect(url_for("students"))

    try:
        student_id = register_student(name, roll_no, department, semester, classroom)
        # Clear cached encodings so new training data is loaded immediately
        global KNOWN_ENCODINGS_CACHE
        KNOWN_ENCODINGS_CACHE = None
        flash(
            f"Student '{name}' registered successfully (ID: {student_id}). "
            "Face images collected and model trained.",
            "success",
        )
    except Exception as exc:
        flash(f"Registration failed: {exc}", "error")
    return redirect(url_for("students"))



@app.route("/api/register/async", methods=["POST"])
@login_required
def register_async():
    """Start student registration in a background thread; return a task_id for polling."""
    name = request.form.get("name", "").strip()
    roll_no = request.form.get("roll_no", "").strip()
    department = request.form.get("department", "").strip()
    semester = request.form.get("semester", "").strip()
    classroom = request.form.get("classroom", "").strip()

    if not all([name, roll_no, department, semester, classroom]):
        return jsonify({"success": False, "message": "All fields are required."}), 400

    task_id = str(uuid.uuid4())
    _registration_tasks[task_id] = {
        "status": "running",
        "message": "Opening camera to collect face images…",
        "student_name": name,
        "student_id": None,
    }

    def _run():
        try:
            sid = register_student(name, roll_no, department, semester, classroom)
            # Invalidate encoding cache so new student is recognised immediately
            global KNOWN_ENCODINGS_CACHE
            KNOWN_ENCODINGS_CACHE = None
            _registration_tasks[task_id].update({
                "status": "done",
                "message": f"Student '{name}' registered successfully!",
                "student_id": sid,
            })
        except Exception as exc:
            _registration_tasks[task_id].update({
                "status": "error",
                "message": str(exc),
            })

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return jsonify({"success": True, "task_id": task_id})


@app.route("/api/register/status/<task_id>")
@login_required
def register_status(task_id):
    """Poll the status of an async registration task."""
    task = _registration_tasks.get(task_id)
    if not task:
        return jsonify({"status": "not_found", "message": "Task not found."}), 404
    return jsonify(task)


# ── Classrooms ────────────────────────────────────────────────────────────────

@app.route("/teacher/classrooms")
@login_required
def classrooms():
    classrooms_list = database.get_classrooms()
    return render_template("classrooms.html", classrooms=classrooms_list)


@app.route("/teacher/classrooms/add", methods=["POST"])
@login_required
def add_classroom():
    name = request.form.get("classroom_name", "").strip()
    if not name:
        flash("Classroom name is required.", "error")
        return redirect(url_for("classrooms"))
    classroom_id = database.add_classroom(name)
    if classroom_id:
        flash(f"Classroom '{name}' added.", "success")
    else:
        flash(f"Classroom '{name}' already exists.", "warning")
    return redirect(url_for("classrooms"))


# ── Subjects ──────────────────────────────────────────────────────────────────

@app.route("/teacher/subjects")
@login_required
def subjects():
    classrooms_list = database.get_classrooms()
    selected = request.args.get("classroom", classrooms_list[0] if classrooms_list else "")
    subjects_list = database.get_subjects(selected) if selected else []
    return render_template(
        "subjects.html",
        classrooms=classrooms_list,
        selected_classroom=selected,
        subjects=subjects_list,
    )


@app.route("/teacher/subjects/add", methods=["POST"])
@login_required
def add_subject():
    classroom = request.form.get("classroom", "").strip()
    subject_name = request.form.get("subject_name", "").strip()
    if not classroom or not subject_name:
        flash("Classroom and subject name are required.", "error")
        return redirect(url_for("subjects"))
    subject_id = database.add_subject(classroom, subject_name)
    if subject_id:
        flash(f"Subject '{subject_name}' added to {classroom}.", "success")
    else:
        flash("Subject already exists for this classroom.", "warning")
    return redirect(url_for("subjects", classroom=classroom))


@app.route("/api/subjects")
def api_subjects():
    classroom = request.args.get("classroom", "")
    return jsonify(database.get_subjects(classroom))


# ── Training ──────────────────────────────────────────────────────────────────

@app.route("/teacher/train", methods=["POST"])
@login_required
def train_model():
    try:
        train_face_encodings()
        # Clear cached encodings so new training data is loaded on next request
        global KNOWN_ENCODINGS_CACHE
        KNOWN_ENCODINGS_CACHE = None
        flash("Face recognition model trained successfully.", "success")
    except Exception as exc:
        flash(f"Training failed: {exc}", "error")
    return redirect(url_for("teacher_dashboard"))


# ── Attendance Session (live) ─────────────────────────────────────────────────

@app.route("/teacher/attendance")
@login_required
def attendance_page():
    classrooms_list = database.get_classrooms()
    subjects_map = {c: database.get_subjects(c) for c in classrooms_list}
    active = load_active_sessions()
    sessions = database.get_attendance_sessions()[:10]
    return render_template(
        "attendance.html",
        classrooms=classrooms_list,
        subjects_map=subjects_map,
        active_sessions=active,
        sessions=sessions,
        attendance_running=_attendance_status["running"],
    )


@app.route("/teacher/attendance/start", methods=["POST"])
@login_required
def start_attendance():
    global _attendance_thread, _attendance_stop_event, _attendance_status, _current_session_id

    if _attendance_status["running"]:
        flash("Attendance session already running.", "warning")
        return redirect(url_for("attendance_page"))

    # Collect classroom-subject pairs from form
    classrooms_posted = request.form.getlist("classroom[]")
    subjects_posted = request.form.getlist("subject[]")
    pairs = {c: s for c, s in zip(classrooms_posted, subjects_posted) if c and s}

    if not pairs:
        flash("Add at least one classroom-subject pair.", "error")
        return redirect(url_for("attendance_page"))

    save_active_sessions(pairs)
    _current_session_id = database.log_attendance_session(
        "Multiple",
        "Multiple",
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        status="Active",
    )

    _attendance_stop_event = threading.Event()

    def run():
        global _attendance_status
        _attendance_status = {"running": True, "message": "Attendance session is running..."}
        try:
            start_attendance_session(
                attendance_enabled=True,
                stop_event=_attendance_stop_event,
            )
            _attendance_status = {"running": False, "message": "Session completed."}
        except Exception as exc:
            _attendance_status = {"running": False, "message": f"Error: {exc}"}
        finally:
            clear_active_sessions()
            if _current_session_id:
                database.update_attendance_session(
                    _current_session_id,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "Completed",
                )

    _attendance_thread = threading.Thread(target=run, daemon=True)
    _attendance_thread.start()
    flash("Attendance session started. Camera window opened.", "success")
    return redirect(url_for("attendance_page"))


@app.route("/teacher/attendance/stop", methods=["POST"])
@login_required
def stop_attendance():
    global _attendance_stop_event, _attendance_status, _current_session_id
    if _attendance_stop_event:
        _attendance_stop_event.set()
    clear_active_sessions()
    if _current_session_id:
        database.update_attendance_session(
            _current_session_id,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Stopped",
        )
        _current_session_id = None
    _attendance_status = {"running": False, "message": "Session stopped."}
    flash("Attendance session stopped.", "info")
    return redirect(url_for("attendance_page"))


@app.route("/api/attendance/status")
def attendance_status_api():
    return jsonify(_attendance_status)


# ── Session History ───────────────────────────────────────────────────────────

@app.route("/teacher/sessions")
@login_required
def session_history():
    sessions = database.get_attendance_sessions()
    return render_template("sessions.html", sessions=sessions)


# ── Attendance Records ────────────────────────────────────────────────────────

@app.route("/teacher/records")
@login_required
def attendance_records():
    classroom_filter = request.args.get("classroom", "")
    subject_filter = request.args.get("subject", "")
    date_filter = request.args.get("date", "")
    roll_filter = request.args.get("roll_no", "")

    filters = {}
    if classroom_filter:
        filters["classroom"] = classroom_filter
    if subject_filter:
        filters["subject"] = subject_filter
    if date_filter:
        filters["date"] = date_filter
    if roll_filter:
        filters["roll_no"] = roll_filter

    records = database.get_attendance_records(filters or None)
    classrooms_list = database.get_classrooms()
    all_subjects = database.get_subjects()

    return render_template(
        "records.html",
        records=records,
        classrooms=classrooms_list,
        all_subjects=all_subjects,
        filters={
            "classroom": classroom_filter,
            "subject": subject_filter,
            "date": date_filter,
            "roll_no": roll_filter,
        },
    )


# ── Export ────────────────────────────────────────────────────────────────────

@app.route("/teacher/export")
@login_required
def export_page():
    classrooms_list = database.get_classrooms()
    all_subjects = database.get_subjects()
    return render_template(
        "export.html", classrooms=classrooms_list, all_subjects=all_subjects
    )


@app.route("/teacher/export/csv")
@login_required
def export_csv():
    classroom = request.args.get("classroom") or None
    subject = request.args.get("subject") or None
    filters = {}
    if classroom:
        filters["classroom"] = classroom
    if subject:
        filters["subject"] = subject

    try:
        csv_path = save_attendance_csv(
            f"attendance_{classroom or 'all'}_{subject or 'all'}.csv",
            filters=filters or None,
        )
        return send_file(str(csv_path), as_attachment=True)
    except Exception as exc:
        flash(f"Export failed: {exc}", "error")
        return redirect(url_for("export_page"))


@app.route("/teacher/export/graph")
@login_required
def export_graph():
    try:
        graph_path = plot_attendance_summary()
        return send_file(str(graph_path), mimetype="image/png")
    except Exception as exc:
        flash(f"Graph failed: {exc}", "error")
        return redirect(url_for("export_page"))


# ── Student Dashboard ─────────────────────────────────────────────────────────

@app.route("/student")
def student_dashboard():
    return render_template("student_dashboard.html")


@app.route("/student/attendance")
def student_attendance():
    roll_no = request.args.get("roll_no", "").strip()
    student = None
    records = []
    if roll_no:
        student = database.get_student_by_roll(roll_no)
        if student:
            records = database.get_attendance_records({"roll_no": roll_no})
    return render_template(
        "student_attendance.html", student=student, records=records, roll_no=roll_no
    )


@app.route("/student/scan", methods=["POST"])
def student_scan():
    roll_no = request.form.get("roll_no", "").strip()
    if not roll_no:
        flash("Roll number is required.", "error")
        return redirect(url_for("student_dashboard"))

    student = database.get_student_by_roll(roll_no)
    if not student:
        flash("No student registered with this roll number.", "error")
        return redirect(url_for("student_dashboard"))

    try:
        result = start_student_attendance_session(roll_no)
        flash(f"Face scan result: {result}", "success")
    except Exception as exc:
        flash(f"Scan failed: {exc}", "error")
    return redirect(url_for("student_attendance", roll_no=roll_no))


@app.route('/student/api/scan', methods=['POST'])
def student_api_scan():
    """API endpoint to accept a single captured image and mark attendance."""
    roll_no = request.form.get('roll_no', '').strip()
    if not roll_no:
        return jsonify({'success': False, 'message': 'roll_no is required'}), 400

    img_file = request.files.get('image')
    if not img_file:
        return jsonify({'success': False, 'message': 'image file missing'}), 400

    try:
        data = img_file.read()
        arr = np.frombuffer(data, np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError('invalid image')

        # Resize large images for faster processing
        h, w = img.shape[:2]
        max_w = 640
        if w > max_w:
            scale = max_w / float(w)
            img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)

        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        face_locations = face_recognition.face_locations(rgb, model='hog')
        face_encodings = face_recognition.face_encodings(rgb, face_locations)
        if not face_encodings:
            return jsonify({'success': False, 'message': 'No face detected in the image.'}), 200

        # Load known encodings and find target student's encodings (cached)
        global KNOWN_ENCODINGS_CACHE
        if KNOWN_ENCODINGS_CACHE is None:
            KNOWN_ENCODINGS_CACHE = load_encodings()
        known_encodings, known_names, known_rolls, known_classrooms = KNOWN_ENCODINGS_CACHE
        target_indexes = [i for i, r in enumerate(known_rolls) if r == roll_no]
        if not target_indexes:
            return jsonify({'success': False, 'message': 'No encodings found for this roll number.'}), 200

        student_encodings = [known_encodings[i] for i in target_indexes]
        # Compare against the first detected face
        probe = face_encodings[0]
        
        # Use face_distance for stricter matching (lower threshold = stricter)
        face_distances = face_recognition.face_distance(student_encodings, probe)
        best_match_distance = float(min(face_distances))
        
        # Require distance < 0.35 for a positive match (stricter than default 0.6)
        FACE_MATCH_THRESHOLD = 0.35
        if best_match_distance >= FACE_MATCH_THRESHOLD:
            return jsonify({
                'success': False, 
                'message': f'Face does not match the registered student. (Similarity: {100 - int(best_match_distance * 100)}%)'
            }), 200

        # Mark attendance
        student = database.get_student_by_roll(roll_no)
        if not student:
            return jsonify({'success': False, 'message': 'Student record not found.'}), 200

        student_id = student[0]
        student_classroom = student[5]
        active_sessions_map = load_active_sessions()
        attendance_subject = None
        if active_sessions_map and student_classroom in active_sessions_map:
            attendance_subject = active_sessions_map.get(student_classroom)
        else:
            attendance_subject = database.get_default_subject_for_classroom(student_classroom)

        attendance_date = datetime.now().strftime('%Y-%m-%d')
        attendance_time = datetime.now().strftime('%H:%M:%S')
        marked = database.mark_attendance(student_id, attendance_date, attendance_time, subject=attendance_subject)
        if marked:
            return jsonify({'success': True, 'message': f'Attendance marked for {student[1]} ({roll_no}).', 'subject': attendance_subject}), 200
        else:
            return jsonify({'success': True, 'message': f'Attendance already marked for {student[1]} ({roll_no}).', 'subject': attendance_subject}), 200

    except Exception as exc:
        return jsonify({'success': False, 'message': f'Error processing image: {exc}'}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)
