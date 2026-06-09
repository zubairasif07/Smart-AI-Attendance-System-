import os
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from database import export_attendance_to_csv, get_attendance_records, get_attendance_summary

BASE_DIR = Path(__file__).resolve().parent
REPORTS_DIR = BASE_DIR / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def save_attendance_csv(filename: str = "attendance_report.csv", filters=None):
    """Export attendance records to a CSV file using optional filters."""
    csv_path = REPORTS_DIR / filename
    df = get_attendance_dataframe(filters)
    if df.empty:
        raise RuntimeError("No attendance records found for the selected filters.")
    df.to_csv(csv_path, index=False)
    return csv_path


def get_attendance_dataframe(filters=None):
    """Return attendance records as a pandas dataframe."""
    records = get_attendance_records(filters)
    columns = ["Record ID", "Name", "Roll Number", "Department", "Semester", "Classroom", "Subject", "Date", "Time", "Status"]
    return pd.DataFrame(records, columns=columns)


def plot_attendance_summary():
    """Generate a bar chart for attendance counts using Matplotlib."""
    summary = get_attendance_summary()
    if not summary:
        raise RuntimeError("No attendance data available to plot.")

    students = [row[0] for row in summary]
    attend_count = [row[2] for row in summary]

    plt.figure(figsize=(10, 6))
    plt.bar(students, attend_count, color="#4CAF50")
    plt.xticks(rotation=45, ha="right")
    plt.title("Student Attendance Count")
    plt.xlabel("Student")
    plt.ylabel("Present Count")
    plt.tight_layout()

    graph_path = REPORTS_DIR / "attendance_summary.png"
    plt.savefig(graph_path)
    plt.close()
    return graph_path


def create_student_report(roll_no: str):
    """Export a student-specific attendance report to CSV."""
    csv_path = REPORTS_DIR / f"attendance_{roll_no}.csv"
    df = get_attendance_dataframe({"roll_no": roll_no})
    df.to_csv(csv_path, index=False)
    return csv_path
