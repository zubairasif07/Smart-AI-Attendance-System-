from pathlib import Path
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext
from datetime import datetime

import database
from attendance_system import clear_active_sessions, load_active_sessions, save_active_sessions, start_attendance_session, start_student_attendance_session
from export_report import plot_attendance_summary, save_attendance_csv
from register_student import register_student
from train_model import train_face_encodings

BASE_DIR = Path(__file__).resolve().parent
ENCODING_FILE = BASE_DIR / "encodings" / "face_encodings.pkl"


class AttendanceApp:
    """Main application class for teacher and student dashboards."""

    def __init__(self):
        database.initialize_database()
        self.root = tk.Tk()
        self.root.title("Smart AI Face Recognition Attendance System")
        self.root.geometry("920x640")
        self.root.resizable(False, False)
        self.create_welcome_screen()

    def run(self):
        self.root.mainloop()

    def create_welcome_screen(self):
        """Build the welcome screen for teacher or student mode selection."""
        self.clear_window()
        title = tk.Label(
            self.root,
            text="Smart AI Face Recognition Attendance System",
            font=("Helvetica", 20, "bold"),
            fg="#333333",
        )
        title.pack(pady=20)

        instruction = tk.Label(
            self.root,
            text="Choose a portal to continue:",
            font=("Helvetica", 14),
        )
        instruction.pack(pady=10)

        button_frame = tk.Frame(self.root)
        button_frame.pack(pady=30)

        teacher_btn = tk.Button(
            button_frame,
            text="Teacher Portal",
            width=20,
            height=2,
            bg="#4CAF50",
            fg="white",
            command=self.teacher_dashboard,
        )
        teacher_btn.grid(row=0, column=0, padx=20)

        student_btn = tk.Button(
            button_frame,
            text="Student Portal",
            width=20,
            height=2,
            bg="#2196F3",
            fg="white",
            command=self.student_dashboard,
        )
        student_btn.grid(row=0, column=1, padx=20)

        footer = tk.Label(
            self.root,
            text="Designed for modern attendance automation using Python, OpenCV, face_recognition, SQLite, and Tkinter.",
            font=("Helvetica", 10),
            fg="#555555",
        )
        footer.pack(side="bottom", pady=15)

    def clear_window(self):
        """Remove all current widgets from the root window."""
        for widget in self.root.winfo_children():
            widget.destroy()

    def teacher_dashboard(self):
        """Display teacher dashboard controls."""
        self.clear_window()
        header = tk.Label(
            self.root,
            text="Teacher Dashboard",
            font=("Helvetica", 18, "bold"),
            fg="#222222",
        )
        header.pack(pady=15)

        frame = tk.Frame(self.root)
        frame.pack(pady=20)

        buttons = [
            ("Register Student", self.open_register_window),
            ("Manage Classrooms", self.open_classroom_management_window),
            ("Manage Subjects", self.open_subject_management_window),
            ("Train Model", self.run_training),
            ("Start Attendance", self.open_attendance_window),
            ("Attendance Sessions", self.open_session_history_window),
            ("Export CSV", self.export_csv),
            ("Attendance Graph", self.show_attendance_graph),
            ("View Attendance", self.open_view_attendance),
            ("Back to Home", self.create_welcome_screen),
            ("Exit", self.root.quit),
        ]

        for index, (label, command) in enumerate(buttons):
            btn = tk.Button(
                frame,
                text=label,
                width=20,
                height=2,
                bg="#333333" if index % 2 == 0 else "#555555",
                fg="white",
                command=command,
            )
            btn.grid(row=index // 2, column=index % 2, padx=15, pady=12)

        self.status_label = tk.Label(self.root, text="Ready", font=("Helvetica", 12), fg="#444444")
        self.status_label.pack(pady=20)

    def open_subject_management_window(self):
        """Open a window for teachers to add subjects for each classroom."""
        classrooms = database.get_classrooms()
        if not classrooms:
            messagebox.showwarning("No Classrooms", "No classrooms available. Add classrooms first.")
            return

        subject_win = tk.Toplevel(self.root)
        subject_win.title("Manage Subjects")
        subject_win.geometry("520x340")
        subject_win.resizable(False, False)

        tk.Label(subject_win, text="Classroom:", font=("Helvetica", 12)).place(x=30, y=30)
        classroom_var = tk.StringVar(value=classrooms[0])
        classroom_menu = tk.OptionMenu(subject_win, classroom_var, *classrooms)
        classroom_menu.place(x=180, y=28, width=260)

        tk.Label(subject_win, text="Subject Name:", font=("Helvetica", 12)).place(x=30, y=85)
        subject_entry = tk.Entry(subject_win, width=32, font=("Helvetica", 12))
        subject_entry.place(x=180, y=85)

        existing_area = scrolledtext.ScrolledText(subject_win, width=60, height=10, font=("Courier", 10))
        existing_area.place(x=20, y=150)

        def refresh_subject_list(*args):
            selected = classroom_var.get()
            subjects = database.get_subjects(selected)
            existing_area.config(state=tk.NORMAL)
            existing_area.delete("1.0", tk.END)
            if subjects:
                existing_area.insert(tk.END, f"Subjects for {selected}:\n")
                existing_area.insert(tk.END, "- " + "\n- ".join(subjects) + "\n")
            else:
                existing_area.insert(tk.END, f"No subjects added for {selected} yet.\n")
            existing_area.config(state=tk.DISABLED)

        classroom_var.trace_add("write", refresh_subject_list)
        refresh_subject_list()

        def add_subject_for_class():
            classroom = classroom_var.get().strip()
            subject_name = subject_entry.get().strip()
            if not subject_name:
                messagebox.showwarning("Input Required", "Please enter a subject name.")
                return
            subject_id = database.add_subject(classroom, subject_name)
            if subject_id:
                messagebox.showinfo("Success", f"Subject '{subject_name}' added for {classroom}.")
                subject_entry.delete(0, tk.END)
                refresh_subject_list()
            else:
                messagebox.showwarning("Duplicate", "This subject already exists for the selected classroom.")

        tk.Button(
            subject_win,
            text="Add Subject",
            width=18,
            height=2,
            bg="#4CAF50",
            fg="white",
            command=add_subject_for_class,
        ).place(x=180, y=110)

    def open_classroom_management_window(self):
        """Open a window to add and list classrooms."""
        classroom_win = tk.Toplevel(self.root)
        classroom_win.title("Manage Classrooms")
        classroom_win.geometry("520x320")
        classroom_win.resizable(False, False)

        tk.Label(classroom_win, text="Classroom Name:", font=("Helvetica", 12)).place(x=30, y=30)
        classroom_entry = tk.Entry(classroom_win, width=32, font=("Helvetica", 12))
        classroom_entry.place(x=180, y=30)

        existing_area = scrolledtext.ScrolledText(classroom_win, width=60, height=10, font=("Courier", 10))
        existing_area.place(x=20, y=90)

        def refresh_classroom_list():
            classrooms = database.get_classrooms()
            existing_area.config(state=tk.NORMAL)
            existing_area.delete("1.0", tk.END)
            if classrooms:
                existing_area.insert(tk.END, "Registered Classrooms:\n")
                existing_area.insert(tk.END, "- " + "\n- ".join(classrooms) + "\n")
            else:
                existing_area.insert(tk.END, "No classrooms added yet.\n")
            existing_area.config(state=tk.DISABLED)

        def add_classroom():
            classroom_name = classroom_entry.get().strip()
            if not classroom_name:
                messagebox.showwarning("Input Required", "Please enter a classroom name.")
                return
            classroom_id = database.add_classroom(classroom_name)
            if classroom_id:
                messagebox.showinfo("Success", f"Classroom '{classroom_name}' added.")
                classroom_entry.delete(0, tk.END)
                refresh_classroom_list()
            else:
                messagebox.showwarning("Duplicate", "This classroom already exists.")

        tk.Button(
            classroom_win,
            text="Add Classroom",
            width=18,
            height=2,
            bg="#4CAF50",
            fg="white",
            command=add_classroom,
        ).place(x=180, y=50)

        refresh_classroom_list()

    def scan_student_attendance(self):
        """Handle a student scanning their face to mark attendance."""
        roll_no = self.roll_entry.get().strip()
        if not roll_no:
            messagebox.showwarning("Input Required", "Please enter a roll number before scanning.")
            return

        student = database.get_student_by_roll(roll_no)
        if not student:
            messagebox.showinfo("Not Found", "No student registered with this roll number.")
            return

        try:
            result_text = start_student_attendance_session(roll_no)
            self.result_text.delete("1.0", tk.END)
            self.result_text.insert(tk.END, f"{result_text}\n")
            # Update the student dashboard status label
            try:
                self.student_status_label.config(text="Student attendance scanned successfully.")
            except Exception:
                # Fallback in case label is missing for any reason
                pass
        except Exception as error:
            messagebox.showerror("Scan Error", str(error))
            try:
                self.student_status_label.config(text="Student attendance scan failed.")
            except Exception:
                pass

    def student_dashboard(self):
        """Display student dashboard to view attendance records."""
        self.clear_window()
        header = tk.Label(self.root, text="Student Dashboard", font=("Helvetica", 18, "bold"), fg="#222222")
        header.pack(pady=15)

        roll_frame = tk.Frame(self.root)
        roll_frame.pack(pady=20)

        roll_label = tk.Label(roll_frame, text="Enter Roll Number:", font=("Helvetica", 12))
        roll_label.grid(row=0, column=0, padx=6, pady=6)

        self.roll_entry = tk.Entry(roll_frame, width=28, font=("Helvetica", 12))
        self.roll_entry.grid(row=0, column=1, padx=6, pady=6)

        search_button = tk.Button(
            roll_frame,
            text="View Attendance",
            width=16,
            bg="#2196F3",
            fg="white",
            command=self.search_student_attendance,
        )
        search_button.grid(row=0, column=2, padx=12)

        scan_button = tk.Button(
            roll_frame,
            text="Scan Face & Mark Attendance",
            width=24,
            bg="#4CAF50",
            fg="white",
            command=self.scan_student_attendance,
        )
        scan_button.grid(row=1, column=0, columnspan=3, pady=10)

        self.result_text = scrolledtext.ScrolledText(self.root, width=100, height=18, font=("Courier", 10))
        self.result_text.pack(pady=10)

        self.student_status_label = tk.Label(self.root, text="Ready", font=("Helvetica", 12), fg="#444444")
        self.student_status_label.pack(pady=8)

        back_button = tk.Button(
            self.root,
            text="Back to Home",
            width=18,
            bg="#777777",
            fg="white",
            command=self.create_welcome_screen,
        )
        back_button.pack(pady=8)

    def open_register_window(self):
        """Open a separate registration window within the teacher dashboard."""
        classrooms = database.get_classrooms()
        if not classrooms:
            messagebox.showwarning("No Classrooms", "Add classrooms in Manage Classrooms before registering a student.")
            return

        register_win = tk.Toplevel(self.root)
        register_win.title("Register Student")
        register_win.geometry("520x420")
        register_win.resizable(False, False)

        form_labels = ["Student Name", "Roll Number", "Department", "Semester"]
        self.form_entries = {}

        for index, label in enumerate(form_labels):
            tk.Label(register_win, text=label + ":", font=("Helvetica", 12)).place(x=30, y=30 + 55 * index)
            entry = tk.Entry(register_win, width=30, font=("Helvetica", 12))
            entry.place(x=180, y=30 + 55 * index)
            self.form_entries[label] = entry

        tk.Label(register_win, text="Classroom:", font=("Helvetica", 12)).place(x=30, y=30 + 55 * len(form_labels))
        self.classroom_var = tk.StringVar(value=classrooms[0])
        classroom_menu = tk.OptionMenu(register_win, self.classroom_var, *classrooms)
        classroom_menu.config(width=28)
        classroom_menu.place(x=180, y=30 + 55 * len(form_labels))

        submit_btn = tk.Button(
            register_win,
            text="Register and Collect Faces",
            width=24,
            height=2,
            bg="#4CAF50",
            fg="white",
            command=lambda: self.handle_registration(register_win),
        )
        submit_btn.place(x=160, y=320)

    def handle_registration(self, window):
        """Collect values from the form and register the student."""
        name = self.form_entries["Student Name"].get().strip()
        roll_no = self.form_entries["Roll Number"].get().strip()
        department = self.form_entries["Department"].get().strip()
        semester = self.form_entries["Semester"].get().strip()
        classroom = self.classroom_var.get().strip()

        try:
            student_id = register_student(name, roll_no, department, semester, classroom)
            self.status_label.config(text=f"Student registered successfully with ID {student_id}.")
            messagebox.showinfo("Success", "Registration completed and face images collected.")
            window.destroy()
        except Exception as error:
            messagebox.showerror("Registration Error", str(error))
            self.status_label.config(text="Registration failed.")

    def run_training(self):
        """Train the face recognition model using the dataset folder."""
        try:
            train_face_encodings()
            self.status_label.config(text="Training completed. Face encodings saved.")
            messagebox.showinfo("Training Complete", "Face recognition model trained successfully.")
        except Exception as error:
            messagebox.showerror("Training Error", str(error))
            self.status_label.config(text="Training failed.")

    def open_attendance_window(self):
        """Prompt the teacher to select classroom-subject pairs and start attendance."""
        classrooms = database.get_classrooms()
        if not classrooms:
            messagebox.showwarning("No Classrooms", "No classrooms registered yet. Add students first.")
            return

        attendance_win = tk.Toplevel(self.root)
        attendance_win.title("Build Multi-Classroom Attendance Session")
        attendance_win.geometry("560x520")
        attendance_win.resizable(False, False)

        tk.Label(attendance_win, text="Classroom:", font=("Helvetica", 12)).place(x=20, y=20)
        classroom_var = tk.StringVar(value=classrooms[0])
        classroom_menu = tk.OptionMenu(attendance_win, classroom_var, *classrooms)
        classroom_menu.place(x=150, y=20, width=240)

        tk.Label(attendance_win, text="Subject:", font=("Helvetica", 12)).place(x=20, y=70)
        subject_var = tk.StringVar(value="Select Subject")
        subject_menu = tk.OptionMenu(attendance_win, subject_var, "Select Subject")
        subject_menu.place(x=150, y=70, width=240)

        active_pairs = []
        active_listbox = tk.Listbox(attendance_win, width=45, height=10)
        active_listbox.place(x=20, y=150)

        def refresh_subjects(*args):
            selected = classroom_var.get()
            subjects = database.get_subjects(selected)
            if not subjects:
                subjects = ["General"]
            subject_var.set(subjects[0])
            menu = subject_menu["menu"]
            menu.delete(0, "end")
            for subject in subjects:
                menu.add_command(label=subject, command=lambda value=subject: subject_var.set(value))

        def refresh_active_pairs():
            active_listbox.delete(0, tk.END)
            for classroom_name, subject_name in active_pairs:
                active_listbox.insert(tk.END, f"{classroom_name} - {subject_name}")

        def add_pair():
            classroom_name = classroom_var.get().strip()
            subject_name = subject_var.get().strip()
            if not classroom_name:
                messagebox.showwarning("Input Required", "Please select a classroom.")
                return
            if not subject_name or subject_name == "Select Subject":
                messagebox.showwarning("Input Required", "Please select a subject.")
                return
            if any(existing == classroom_name for existing, _ in active_pairs):
                messagebox.showwarning("Duplicate", f"A session for {classroom_name} already exists.")
                return
            active_pairs.append((classroom_name, subject_name))
            refresh_active_pairs()

        def remove_pair():
            selected_index = active_listbox.curselection()
            if not selected_index:
                messagebox.showwarning("Select Pair", "Select a classroom-subject pair to remove.")
                return
            del active_pairs[selected_index[0]]
            refresh_active_pairs()

        tk.Label(attendance_win, text="Active Attendance Pairs:", font=("Helvetica", 12, "bold")).place(x=20, y=120)

        enabled_var = tk.BooleanVar(value=False)
        status_var = tk.StringVar(value="Attendance is OFF")

        def update_status_label(*args):
            status_var.set("Attendance is ON" if enabled_var.get() else "Attendance is OFF")

        enable_check = tk.Checkbutton(
            attendance_win,
            text="Enable attendance marking",
            font=("Helvetica", 12),
            variable=enabled_var,
            onvalue=True,
            offvalue=False,
            command=update_status_label,
        )
        enable_check.place(x=20, y=360)

        status_label = tk.Label(attendance_win, textvariable=status_var, font=("Helvetica", 12, "bold"), fg="#D32F2F")
        status_label.place(x=260, y=362)

        current_session_id = None
        scan_thread = None
        scan_stop_event = threading.Event()

        def set_control_states(enabled: bool):
            start_button.config(state=tk.NORMAL if enabled else tk.DISABLED)
            stop_button.config(state=tk.DISABLED if enabled else tk.NORMAL)
            launch_button.config(state=tk.DISABLED if enabled else tk.NORMAL)
            add_pair_button.config(state=tk.NORMAL if enabled else tk.DISABLED)
            remove_pair_button.config(state=tk.NORMAL if enabled else tk.DISABLED)
            classroom_menu.config(state=tk.NORMAL if enabled else tk.DISABLED)
            subject_menu.config(state=tk.NORMAL if enabled else tk.DISABLED)
            enable_check.config(state=tk.NORMAL if enabled else tk.DISABLED)

        def start_for_selection():
            nonlocal current_session_id
            if not enabled_var.get():
                messagebox.showwarning("Attendance Disabled", "Enable attendance marking before starting the session.")
                return
            if not active_pairs:
                messagebox.showwarning("No Pairs", "Add at least one classroom-subject pair.")
                return
            active_sessions_map = {classroom_name: subject_name for classroom_name, subject_name in active_pairs}
            save_active_sessions(active_sessions_map)
            current_session_id = database.log_attendance_session(
                "Multiple", "Multiple", datetime.now().strftime("%Y-%m-%d %H:%M:%S"), status="Active"
            )
            launch_button.config(state=tk.NORMAL)
            set_control_states(False)
            status_var.set("Attendance is ON")
            self.status_label.config(text="Attendance session started.")

        def launch_attendance_camera():
            nonlocal scan_thread
            if scan_thread and scan_thread.is_alive():
                messagebox.showinfo("Already Running", "The attendance camera is already running.")
                return
            if not current_session_id:
                messagebox.showwarning("Session Not Started", "Start the attendance session first.")
                return
            scan_stop_event.clear()
            launch_button.config(state=tk.DISABLED)
            self.status_label.config(text="Opening attendance camera...")

            def camera_thread():
                try:
                    start_attendance_session(attendance_enabled=True, stop_event=scan_stop_event)
                    self.status_label.config(text="Attendance camera session ended.")
                except Exception as error:
                    messagebox.showerror("Camera Error", str(error))
                    self.status_label.config(text="Attendance camera error.")
                finally:
                    launch_button.config(state=tk.NORMAL)

            scan_thread = threading.Thread(target=camera_thread, daemon=True)
            scan_thread.start()

        def stop_attendance():
            nonlocal current_session_id
            scan_stop_event.set()
            clear_active_sessions()
            if current_session_id:
                database.update_attendance_session(current_session_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "Stopped")
                current_session_id = None
            status_var.set("Attendance is OFF")
            self.status_label.config(text="Attendance session stopped.")
            set_control_states(True)

        classroom_var.trace_add("write", refresh_subjects)
        refresh_subjects()

        add_pair_button = tk.Button(
            attendance_win,
            text="Add Classroom Subject",
            width=20,
            bg="#2196F3",
            fg="white",
            command=add_pair,
        )
        add_pair_button.place(x=410, y=20)

        remove_pair_button = tk.Button(
            attendance_win,
            text="Remove Selected Pair",
            width=20,
            bg="#F44336",
            fg="white",
            command=remove_pair,
        )
        remove_pair_button.place(x=410, y=70)

        start_button = tk.Button(
            attendance_win,
            text="Start Attendance",
            width=20,
            height=2,
            bg="#4CAF50",
            fg="white",
            command=start_for_selection,
        )
        start_button.place(x=410, y=340)

        launch_button = tk.Button(
            attendance_win,
            text="Open Attendance Camera",
            width=20,
            height=2,
            bg="#2196F3",
            fg="white",
            state=tk.DISABLED,
            command=launch_attendance_camera,
        )
        launch_button.place(x=410, y=400)

        stop_button = tk.Button(
            attendance_win,
            text="Stop Attendance",
            width=20,
            height=2,
            bg="#F44336",
            fg="white",
            state=tk.DISABLED,
            command=stop_attendance,
        )
        stop_button.place(x=410, y=460)

        refresh_active_pairs()

    def run_attendance(self, classroom=None, subject=None, attendance_enabled=True, active_sessions=None, stop_event=None):
        """Start the real-time attendance system for a specific classroom or active sessions."""
        try:
            if not ENCODING_FILE.exists():
                raise FileNotFoundError("Face encodings file not found. Train the model first.")
            start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            session_classroom = "Multiple" if active_sessions else classroom
            session_subject = "Multiple" if active_sessions else subject
            session_id = database.log_attendance_session(session_classroom, session_subject, start_time)
            try:
                if active_sessions:
                    start_attendance_session(attendance_enabled=attendance_enabled, stop_event=stop_event)
                else:
                    start_attendance_session(classroom=classroom, subject=subject, attendance_enabled=attendance_enabled, stop_event=stop_event)
                database.update_attendance_session(session_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "Completed")
                self.status_label.config(text="Attendance session completed.")
            except Exception as inner_error:
                database.update_attendance_session(session_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "Failed")
                raise inner_error
        except Exception as error:
            messagebox.showerror("Attendance Error", str(error))
            self.status_label.config(text="Attendance failed.")

    def export_csv(self):
        """Open a dialog for exporting attendance CSV with classroom and subject filters."""
        classrooms = database.get_classrooms()
        export_win = tk.Toplevel(self.root)
        export_win.title("Export Attendance CSV")
        export_win.geometry("460x240")
        export_win.resizable(False, False)

        tk.Label(export_win, text="Classroom:", font=("Helvetica", 12)).pack(pady=(16, 4))
        classroom_var = tk.StringVar(value="All Classrooms")
        classroom_menu = tk.OptionMenu(export_win, classroom_var, *(["All Classrooms"] + classrooms))
        classroom_menu.pack(pady=6)

        tk.Label(export_win, text="Subject:", font=("Helvetica", 12)).pack(pady=(12, 4))
        subject_var = tk.StringVar(value="All Subjects")
        subject_menu = tk.OptionMenu(export_win, subject_var, "All Subjects")
        subject_menu.pack(pady=6)

        def update_subjects(*args):
            selected = classroom_var.get()
            if selected == "All Classrooms":
                subjects = ["All Subjects"] + database.get_subjects()
            else:
                subjects = ["All Subjects"] + database.get_subjects(selected)
            subject_var.set(subjects[0] if subjects else "All Subjects")
            menu = subject_menu["menu"]
            menu.delete(0, "end")
            for subject in subjects:
                menu.add_command(label=subject, command=lambda value=subject: subject_var.set(value))

        classroom_var.trace_add("write", update_subjects)
        update_subjects()

        def export_selection():
            selected_classroom = None if classroom_var.get() == "All Classrooms" else classroom_var.get()
            selected_subject = None if subject_var.get() == "All Subjects" else subject_var.get()
            filename = f"attendance_{(selected_classroom or 'all_classes').replace(' ', '_')}_{(selected_subject or 'all_subjects').replace(' ', '_')}.csv"
            try:
                csv_path = save_attendance_csv(filename, filters={
                    "classroom": selected_classroom,
                    "subject": selected_subject,
                })
                messagebox.showinfo("CSV Export", f"Attendance exported to {csv_path}")
                self.status_label.config(text="Attendance exported to CSV.")
                export_win.destroy()
            except Exception as error:
                messagebox.showerror("Export Error", str(error))
                self.status_label.config(text="CSV export failed.")

        tk.Button(
            export_win,
            text="Export Filtered CSV",
            width=22,
            height=2,
            bg="#4CAF50",
            fg="white",
            command=export_selection,
        ).pack(pady=16)

    def show_attendance_graph(self):
        """Plot attendance summary and save the graph image."""
        try:
            graph_path = plot_attendance_summary()
            messagebox.showinfo("Graph Generated", f"Attendance graph saved to {graph_path}")
            self.status_label.config(text="Attendance graph created.")
        except Exception as error:
            messagebox.showerror("Graph Error", str(error))
            self.status_label.config(text="Graph generation failed.")

    def open_session_history_window(self):
        """Show logged attendance sessions in a separate window."""
        session_win = tk.Toplevel(self.root)
        session_win.title("Attendance Session History")
        session_win.geometry("860x520")
        session_win.resizable(False, False)

        sessions = database.get_attendance_sessions()
        if not sessions:
            tk.Label(session_win, text="No attendance sessions logged yet.", font=("Helvetica", 12)).pack(pady=20)
            return

        text_area = scrolledtext.ScrolledText(session_win, width=104, height=28, font=("Courier", 10))
        text_area.pack(padx=10, pady=10)
        text_area.insert(tk.END, "ID | Classroom | Subject | Start Time | End Time | Status\n")
        text_area.insert(tk.END, "" + "-" * 130 + "\n")
        for record in sessions:
            text_area.insert(tk.END, " | ".join(str(value or "") for value in record) + "\n")
        text_area.config(state=tk.DISABLED)

    def open_view_attendance(self):
        """Show a window with attendance record listings."""
        view_win = tk.Toplevel(self.root)
        view_win.title("Attendance Records")
        view_win.geometry("900x520")
        view_win.resizable(False, False)

        records = database.get_attendance_records()
        if not records:
            tk.Label(view_win, text="No attendance records found.", font=("Helvetica", 12)).pack(pady=20)
            return

        text_area = scrolledtext.ScrolledText(view_win, width=110, height=28, font=("Courier", 10))
        text_area.pack(padx=10, pady=10)
        text_area.insert(tk.END, "ID | Name | Roll | Department | Semester | Classroom | Subject | Date | Time | Status\n")
        text_area.insert(tk.END, "" + "-" * 170 + "\n")
        for record in records:
            text_area.insert(tk.END, " | ".join(str(value) for value in record) + "\n")
        text_area.config(state=tk.DISABLED)

    def search_student_attendance(self):
        """Display student attendance records in the student dashboard."""
        roll_no = self.roll_entry.get().strip()
        if not roll_no:
            messagebox.showwarning("Input Required", "Please enter a roll number.")
            return

        student = database.get_student_by_roll(roll_no)
        if not student:
            messagebox.showinfo("Not Found", "No student registered with this roll number.")
            return

        records = database.get_attendance_records({"roll_no": roll_no})
        self.result_text.delete("1.0", tk.END)
        if not records:
            self.result_text.insert(tk.END, f"No attendance records found for {roll_no}.\n")
            return

        self.result_text.insert(tk.END, f"Attendance for {student[1]} ({roll_no})\n")
        self.result_text.insert(tk.END, "Subject        | Date       | Time     | Status\n")
        self.result_text.insert(tk.END, "---------------------------------------------------------\n")
        for row in records:
            self.result_text.insert(tk.END, f"{row[6] or 'General':<14} | {row[7]} | {row[8]} | {row[9]}\n")

        total = len(records)
        self.result_text.insert(tk.END, f"\nTotal records: {total}\n")
