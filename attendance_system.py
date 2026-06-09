import json
import pickle
from datetime import datetime
from pathlib import Path

import cv2
import face_recognition

from database import get_student_by_roll, mark_attendance, get_default_subject_for_classroom

BASE_DIR = Path(__file__).resolve().parent
ENCODING_PATH = BASE_DIR / "encodings" / "face_encodings.pkl"
ACTIVE_SESSIONS_PATH = BASE_DIR / "active_sessions.json"


def save_active_sessions(active_sessions):
    """Save active classroom-subject sessions to disk."""
    with open(ACTIVE_SESSIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(active_sessions, f)


def load_active_sessions():
    """Load active classroom-subject sessions from disk."""
    if not ACTIVE_SESSIONS_PATH.exists():
        return {}
    try:
        with open(ACTIVE_SESSIONS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def clear_active_sessions():
    """Remove the active session file after attendance ends."""
    try:
        if ACTIVE_SESSIONS_PATH.exists():
            ACTIVE_SESSIONS_PATH.unlink()
    except Exception:
        pass


def load_encodings():
    """Load face encodings from the pickle file."""
    if not ENCODING_PATH.exists():
        raise FileNotFoundError("Face encoding file not found. Train the model first.")

    with open(ENCODING_PATH, "rb") as file:
        data = pickle.load(file)
    return (
        data.get("encodings", []),
        data.get("names", []),
        data.get("rolls", []),
        data.get("classrooms", []),
    )


def start_attendance_session(classroom=None, subject=None, attendance_enabled=True, stop_event=None):
    """Run real-time face recognition and mark attendance in the database."""
    known_encodings, known_names, known_rolls, known_classrooms = load_encodings()
    # Load active sessions mapping if present (classroom -> subject)
    active_sessions = load_active_sessions()
    has_active_sessions = bool(active_sessions)

    # If active_sessions are defined, restrict known encodings to those classrooms
    if has_active_sessions:
        selected = [i for i, room in enumerate(known_classrooms) if room in active_sessions]
        known_encodings = [known_encodings[i] for i in selected]
        known_names = [known_names[i] for i in selected]
        known_rolls = [known_rolls[i] for i in selected]
    elif classroom:
        selected = [i for i, room in enumerate(known_classrooms) if room == classroom]
        known_encodings = [known_encodings[i] for i in selected]
        known_names = [known_names[i] for i in selected]
        known_rolls = [known_rolls[i] for i in selected]

    if not known_encodings:
        raise RuntimeError("No face encoding data found for the requested classroom. Train the model with classroom data first.")
    camera = cv2.VideoCapture(0)

    if not camera.isOpened():
        raise RuntimeError("Unable to open webcam. Check your camera connection.")

    attendance_date = datetime.now().strftime("%Y-%m-%d")
    print("[INFO] Starting attendance session. Press 'q' or ESC to exit.")
    cv2.namedWindow("Real-Time Attendance", cv2.WINDOW_NORMAL)

    try:
        while True:
            if stop_event is not None and stop_event.is_set():
                break
            ret, frame = camera.read()
            if not ret:
                break

            small_frame = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
            rgb_small = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

            face_locations = face_recognition.face_locations(rgb_small, model="hog")
            face_encodings = face_recognition.face_encodings(rgb_small, face_locations)

            for face_encoding, face_location in zip(face_encodings, face_locations):
                name = "Unknown"
                roll_no = None
                rect_color = (0, 0, 255)
                FACE_MATCH_THRESHOLD = 0.35  # Strict threshold for confident matches

                if known_encodings:
                    face_distances = face_recognition.face_distance(known_encodings, face_encoding)
                    best_match_idx = int(min(range(len(face_distances)), key=lambda i: face_distances[i]))
                    best_distance = float(face_distances[best_match_idx])
                    
                    # Only recognize if distance is below strict threshold
                    if best_distance < FACE_MATCH_THRESHOLD:
                        name = known_names[best_match_idx]
                        roll_no = known_rolls[best_match_idx]

                top, right, bottom, left = [coord * 2 for coord in face_location]
                if name != "Unknown" and roll_no:
                    student = get_student_by_roll(roll_no)
                    if student:
                        student_id = student[0]
                        student_classroom = student[5]
                        attendance_time = datetime.now().strftime("%H:%M:%S")
                        # Decide subject: priority - active_sessions mapping, explicit subject arg, default classroom subject
                        attendance_subject = None
                        if 'active_sessions' in locals() and active_sessions and student_classroom in active_sessions:
                            attendance_subject = active_sessions.get(student_classroom)
                        elif subject is not None:
                            attendance_subject = subject
                        else:
                            attendance_subject = get_default_subject_for_classroom(student_classroom)
                        if attendance_enabled:
                            if mark_attendance(student_id, attendance_date, attendance_time, subject=attendance_subject):
                                print(f"[ATTENDANCE] Marked present: {name} ({roll_no}) [{attendance_subject or 'General'}]")
                            status_text = f"{name} - Present"
                        else:
                            status_text = f"{name} - Attendance Disabled"
                        rect_color = (0, 255, 0)
                    else:
                        status_text = "Unknown Student"
                        rect_color = (0, 0, 255)
                else:
                    status_text = "Unknown"
                    rect_color = (0, 0, 255)

                cv2.rectangle(frame, (left, top), (right, bottom), rect_color, 2)
                cv2.putText(
                    frame,
                    status_text,
                    (left, top - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    rect_color,
                    2,
                )

            cv2.imshow("Real-Time Attendance", frame)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
            if cv2.getWindowProperty("Real-Time Attendance", cv2.WND_PROP_VISIBLE) < 1:
                break
    finally:
        camera.release()
        cv2.destroyAllWindows()
        if has_active_sessions:
            clear_active_sessions()
        print("[INFO] Attendance session ended.")


def start_student_attendance_session(roll_no: str):
    """Run face recognition for a single student to automatically mark attendance."""
    known_encodings, known_names, known_rolls, known_classrooms = load_encodings()
    target_indexes = [i for i, roll in enumerate(known_rolls) if roll == roll_no]
    if not target_indexes:
        raise RuntimeError("No face encodings found for this student. Train the model and register the student first.")

    student_encodings = [known_encodings[i] for i in target_indexes]
    expected_name = known_names[target_indexes[0]]

    camera = cv2.VideoCapture(0)
    if not camera.isOpened():
        raise RuntimeError("Unable to open webcam. Check your camera connection.")

    attendance_date = datetime.now().strftime("%Y-%m-%d")
    print("[INFO] Starting student face scan. Press 'q' or ESC to cancel.")
    cv2.namedWindow("Student Face Scan", cv2.WINDOW_NORMAL)
    active_sessions = load_active_sessions()

    try:
        while True:
            ret, frame = camera.read()
            if not ret:
                break

            small_frame = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
            rgb_small = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

            face_locations = face_recognition.face_locations(rgb_small, model="hog")
            face_encodings = face_recognition.face_encodings(rgb_small, face_locations)

            for face_encoding, face_location in zip(face_encodings, face_locations):
                face_distances = face_recognition.face_distance(student_encodings, face_encoding)
                best_distance = float(min(face_distances))
                rect_color = (0, 0, 255)
                status_text = "Unknown"
                FACE_MATCH_THRESHOLD = 0.35  # Strict threshold

                top, right, bottom, left = [coord * 2 for coord in face_location]
                if best_distance < FACE_MATCH_THRESHOLD:
                    student = get_student_by_roll(roll_no)
                    if student:
                        student_id = student[0]
                        student_classroom = student[5]
                        # If active sessions exist, only mark if this student's classroom is active
                        if active_sessions and student_classroom not in active_sessions:
                            status_text = f"{expected_name} - No active session for {student_classroom}"
                            rect_color = (0, 0, 255)
                        else:
                            attendance_subject = active_sessions.get(student_classroom) if active_sessions else get_default_subject_for_classroom(student_classroom)
                            attendance_time = datetime.now().strftime("%H:%M:%S")
                            if mark_attendance(student_id, attendance_date, attendance_time, subject=attendance_subject):
                                status_text = f"{expected_name} - Present [{attendance_subject or 'General'}]"
                                rect_color = (0, 255, 0)
                                print(f"[ATTENDANCE] Marked present: {expected_name} ({roll_no}) [{attendance_subject or 'General'}]")
                            else:
                                status_text = f"{expected_name} - Already marked"
                                rect_color = (0, 255, 0)
                    else:
                        status_text = "Unknown Student"
                        rect_color = (0, 0, 255)

                cv2.rectangle(frame, (left, top), (right, bottom), rect_color, 2)
                cv2.putText(
                    frame,
                    status_text,
                    (left, top - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    rect_color,
                    2,
                )

                if status_text.startswith(expected_name):
                    cv2.imshow("Student Face Scan", frame)
                    cv2.waitKey(1000)
                    return status_text

            cv2.imshow("Student Face Scan", frame)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
            if cv2.getWindowProperty("Student Face Scan", cv2.WND_PROP_VISIBLE) < 1:
                break

        raise RuntimeError("Face scan ended without recognizing the registered student.")
    finally:
        camera.release()
        cv2.destroyAllWindows()
        print("[INFO] Student face scan session ended.")
