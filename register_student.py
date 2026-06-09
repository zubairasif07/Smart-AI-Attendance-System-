import re
from pathlib import Path

from collect_faces import capture_face_images
from database import add_student, get_student_by_roll
from train_model import train_face_encodings

BASE_DIR = Path(__file__).resolve().parent
DATASET_DIR = BASE_DIR / "dataset"


def sanitize_folder_name(name: str, roll_no: str) -> str:
    """Generate a safe folder name for a student dataset."""
    clean_name = re.sub(r"[^A-Za-z0-9 ]+", "", name).strip().replace(" ", "-")
    return f"{clean_name}_{roll_no}"


def sanitize_classroom(classroom: str) -> str:
    """Generate a safe classroom folder name."""
    return re.sub(r"[^A-Za-z0-9 ]+", "", classroom).strip().replace(" ", "-")


def register_student(name: str, roll_no: str, department: str, semester: str, classroom: str):
    """Register student details and collect a face image dataset."""
    if not (name and roll_no and department and semester and classroom):
        raise ValueError("All student details are required.")

    if get_student_by_roll(roll_no):
        raise ValueError("A student with this roll number already exists.")

    folder_name = sanitize_folder_name(name, roll_no)
    classroom_folder = DATASET_DIR / sanitize_classroom(classroom)
    student_folder = classroom_folder / folder_name
    student_folder.mkdir(parents=True, exist_ok=True)

    student_id = add_student(name, roll_no, department, semester, classroom, str(student_folder.relative_to(DATASET_DIR)))
    if not student_id:
        raise RuntimeError("Failed to save student to the database.")

    capture_face_images(name, roll_no, student_folder)

    try:
        train_face_encodings()
    except Exception as error:
        raise RuntimeError(f"Student registered, but encoding training failed: {error}")

    return student_id
