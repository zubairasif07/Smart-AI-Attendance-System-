# Smart AI Face Recognition Attendance System

## Project Overview
This Python project uses AI and computer vision to detect student faces through a webcam and automatically mark attendance. It includes a professional Tkinter GUI with separate Teacher and Student dashboards, multi-classroom support, SQLite database storage, face dataset collection, training, real-time attendance capture, CSV export, and attendance graphs.

## Folder Structure
```
AI_Attendance_System/
│
├── dataset/
├── encodings/
├── database/
├── reports/
├── screenshots/
│
├── main.py
├── register_student.py
├── collect_faces.py
├── train_model.py
├── attendance_system.py
├── database.py
├── gui.py
├── export_report.py
├── requirements.txt
└── README.md
```

## Installation Guide
1. Install Python 3.8 or newer.
2. Open a terminal in the project folder.
3. Create a virtual environment:
   ```bash
   python -m venv venv
   ```
4. Activate the environment:
   - Windows:
     ```bash
     venv\Scripts\activate
     ```
5. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
6. Run the database initialization script once:
   ```bash
   python database.py
   ```

## Execution Guide
1. Start the application:
   ```bash
   python main.py
   ```
2. Choose `Teacher Dashboard` or `Student Dashboard`.
3. For teacher actions:
   - Register Student: add student details and capture 30 face images.
   - Train Model: compute face encodings from `dataset/`.
   - Start Attendance: recognize faces in live webcam feed and store attendance.
   - View Attendance: review recorded attendance.
   - Export CSV: save attendance logs to `reports/attendance_report.csv`.
   - Attendance Graph: save attendance chart to `reports/attendance_summary.png`.
4. For students:
   - Enter a roll number and view attendance history.

## File Descriptions
- `main.py` - Launches the Tkinter application.
- `gui.py` - Provides teacher and student dashboard interfaces.
- `database.py` - Manages SQLite connection and tables.
- `register_student.py` - Saves student details and starts dataset capture.
- `collect_faces.py` - Uses webcam to gather and save face images.
- `train_model.py` - Reads dataset images and creates face encodings.
- `attendance_system.py` - Recognizes faces in real time and marks attendance.
- `export_report.py` - Exports attendance reports and builds graphs.
- `requirements.txt` - Python dependencies.

## Sample Screenshots Description
1. **Welcome Screen** - Selection page with Teacher and Student dashboard buttons.
2. **Teacher Dashboard** - Buttons for registration, training, attendance, reports, and graphs.
3. **Student Dashboard** - Enter roll number and review attendance records.
4. **Face Capture Window** - Live webcam preview with detected face box and capture count.
5. **Attendance Window** - Live recognition with green box for recognized faces and red box for unknown faces.
6. **Exported Report** - CSV and attendance graph saved in `reports/`.

## Mini Project Report
### Problem Statement
Manual attendance is time-consuming and prone to errors. This system automates attendance using face recognition to reduce fraud and increase accuracy.

### Objective
Build an intelligent system that registers students, captures face data, trains a recognition model, and marks attendance automatically.

### Methodology
- Use Tkinter for GUI dashboards.
- Store student details and attendance in SQLite.
- Collect face images using OpenCV webcam capture.
- Encode faces using the `face_recognition` library.
- Recognize faces in real time and save attendance data.
- Generate reports with Pandas and Matplotlib.

### Tools and Technologies
- Python
- OpenCV
- face_recognition
- NumPy
- Pandas
- Matplotlib
- Tkinter
- SQLite3
- Pillow

### Results
The system supports student registration, face dataset generation, model training, real-time recognition, attendance marking, CSV export, and graphical analytics.

## Viva Questions and Answers
1. **What is face recognition?**
   Face recognition identifies or verifies a person by analyzing facial features in an image.
2. **Why use SQLite for this system?**
   SQLite offers lightweight local storage with no server, ideal for desktop applications.
3. **How are face encodings generated?**
   Encodings are numerical representations of face features produced by the `face_recognition` library.
4. **Why do we need to train the model?**
   Training computes the feature vectors needed to compare live faces to stored student faces.
5. **What does the attendance graph represent?**
   It shows how many times each student was marked present.
6. **How does the system avoid duplicate attendance?**
   The system checks the attendance table for the same student and date before inserting a record.

## Future Improvements
- Add admin authentication for teacher dashboard access.
- Add multiple classroom support with batch selection.
- Add anti-spoofing with liveness detection.
- Integrate email or SMS attendance reports.
- Add monthly and daily summary dashboards with charts.
- Build a web app version using Flask or Django.
- Add face recognition improvement with deep learning models.

## Notes
- Use a well-lit environment for strong face detection.
- Register each student once before training the model.
- Keep the webcam stable and ensure a clear view of faces.
