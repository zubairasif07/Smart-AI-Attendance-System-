import os
import pickle
from pathlib import Path

import face_recognition

from database import get_all_students

BASE_DIR = Path(__file__).resolve().parent
DATASET_DIR = BASE_DIR / "dataset"
ENCODING_DIR = BASE_DIR / "encodings"
ENCODING_DIR.mkdir(parents=True, exist_ok=True)
ENCODING_PATH = ENCODING_DIR / "face_encodings.pkl"


def train_face_encodings():
    """Read dataset images, compute face encodings, and save them to a pickle file."""
    known_encodings = []
    known_names = []
    known_rolls = []
    known_classrooms = []

    students = get_all_students()
    if not students:
        raise RuntimeError("No registered students found. Register students first.")

    for student in students:
        _, name, roll_no, _, _, classroom, folder_name = student
        student_folder = DATASET_DIR / folder_name
        if not student_folder.exists() or not student_folder.is_dir():
            print(f"[WARN] Dataset folder missing for {name} ({roll_no}). Skipping.")
            continue

        image_files = list(student_folder.glob("*.jpg")) + list(student_folder.glob("*.png"))
        if not image_files:
            print(f"[WARN] No face images found in {student_folder}. Skipping.")
            continue

        for image_file in image_files:
            image = face_recognition.load_image_file(str(image_file))
            face_locations = face_recognition.face_locations(image, model="hog")
            face_encodings = face_recognition.face_encodings(image, face_locations)

            if face_encodings:
                known_encodings.append(face_encodings[0])
                known_names.append(name)
                known_rolls.append(roll_no)
                known_classrooms.append(classroom)
                print(f"[TRAIN] Processed image {image_file.name} for {name} ({classroom})")
            else:
                print(f"[WARN] No face found in {image_file.name}. Skipping.")

    if not known_encodings:
        raise RuntimeError("Failed to generate any face encodings. Check dataset images.")

    with open(ENCODING_PATH, "wb") as file:
        pickle.dump(
            {
                "encodings": known_encodings,
                "names": known_names,
                "rolls": known_rolls,
                "classrooms": known_classrooms,
            },
            file,
        )

    print(f"[SUCCESS] Training completed. Encodings saved to {ENCODING_PATH}")
    return ENCODING_PATH


if __name__ == "__main__":
    train_face_encodings()
