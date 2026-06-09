"""
Initialize teacher account for the attendance system.
Run: python init_teacher.py
"""

import database

def init_teacher():
    """Create initial teacher account."""
    database.initialize_database()
    
    # Check if teacher already exists
    existing = database.get_teacher_by_email("zubair@gmail.com")
    if existing:
        print("✓ Teacher account already exists: zubair@gmail.com")
        return
    
    # Create new teacher
    teacher_id = database.add_teacher(
        email="zubair@gmail.com",
        password="123456",
        name="Zubair Ahmed"
    )
    
    if teacher_id:
        print(f"✓ Teacher account created successfully!")
        print(f"  Email: zubair@gmail.com")
        print(f"  Password: 123456")
        print(f"  Teacher ID: {teacher_id}")
    else:
        print("✗ Failed to create teacher account.")

if __name__ == "__main__":
    init_teacher()
