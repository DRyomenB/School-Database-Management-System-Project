from datetime import datetime
import sqlite3
import os
from dotenv import load_dotenv
import re
from students import insert_student
load_dotenv()

db_path = os.getenv("DB_PATH")
school_domain = os.getenv("SCHOOL_DOMAIN")

def submit_student_application(first_name, last_name, personal_email, phone, major, status, graduation_date=None, gpa=None):
    # ... existing validation ...
    
    connection = sqlite3.connect(db_path, timeout=10.0)
    cursor = connection.cursor()
    
    # Check personal_email INSTEAD OF email field
    cursor.execute('SELECT * FROM StudentApplication WHERE personal_email = ?', (email,))
    if cursor.fetchone():
        return {"success": False, "message": "An application with this personal email already exists."}
    
    # Insert personal_email + school_email separately
    submission_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        """INSERT INTO StudentApplication (first_name, last_name, email, phone, major, status, graduation_date, gpa, submission_timestamp)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (first_name, last_name, email, phone, major, status, graduation_date, gpa, submission_timestamp)
    )

def normalize_name(name):
    return re.sub(r'[^a-zA-Z0-9]', '', name).lower()



def get_pending_applications(status=None):
    """
    Get applications filtered by status.
    If status is None, returns all applications with status 'submitted' or 'under_review' (pending review).
    If status is provided, returns applications with that specific status.
    """
    connection = None
    try:
        connection = sqlite3.connect(db_path, timeout=10.0)
        cursor = connection.cursor()
        
        if status:
            # Get applications with specific status
            cursor.execute('SELECT * FROM StudentApplication WHERE status = ?', (status,))
        else:
            # Default: get pending applications (submitted or under_review)
            cursor.execute(
                'SELECT * FROM StudentApplication WHERE status IN (?, ?)',
                ('submitted', 'under_review')
            )
        
        applications = cursor.fetchall()
        
        # Convert to list of dictionaries for easier use
        columns = [description[0] for description in cursor.description]
        applications_list = [dict(zip(columns, app)) for app in applications]

        return {"success": True, "applications": applications_list}
    except Exception as e:
        return {"success": False, "message": f"Database error: {e}"}
    finally:
        if connection:
            connection.close()


def generate_school_email(application_id):
    connection = None
    try:
        connection = sqlite3.connect(db_path, timeout=10.0)
        cursor = connection.cursor()

        cursor.execute('SELECT id, first_name, last_name, email, status FROM StudentApplication WHERE id = ?', 
        (application_id,))
        result = cursor.fetchone()
        if not result:
            return {"success": False, "message": "No application found with the given ID."}

        _, first_name, last_name, applicant_email, status = result

        if status != 'approved':
            return {"success": False, "message": "Email generation is only allowed for approved applications."}

        if not first_name or not last_name:
            return {"success": False, "message": "Missing required fields."}

        base = f"{normalize_name(first_name)}.{normalize_name(last_name)}"
        candidate = f"{base}@{school_domain or 'benjamin.edu'}"
        suffix = 1

        while True:
            cursor.execute('SELECT COUNT(*) FROM StudentApplication WHERE email = ?', (candidate,))
            app_count = cursor.fetchone()[0]

            try:
                cursor.execute('SELECT COUNT(*) FROM Student WHERE email = ?', (candidate,))
                student_count = cursor.fetchone()[0]
            except sqlite3.OperationalError:
                student_count = 0

            if app_count == 0 and student_count == 0:
                break

            candidate = f"{base}{suffix}@{school_domain or 'example.edu'}"
            suffix += 1

            if suffix > 10:
                return {"success": False, "message": "Failed to generate a unique email after 10 attempts."}

        return {
            "success": True,
            "email": candidate,
            "message": f"Email generated successfully {candidate}"
        }
    except Exception as e:
        if connection:
            connection.rollback()
        return {"success": False, "message": f"Database error: {e}"}
    finally:
        if connection:
            connection.close()
def update_application_status(application_id, new_status, review=None, note=None):
    connection = None
    try:
        connection = sqlite3.connect(db_path, timeout=10.0)
        cursor = connection.cursor()

        # Only update status since the table does not have review/note columns
        cursor.execute(
            'UPDATE StudentApplication SET status = ? WHERE id = ?',
            (new_status, application_id)
        )
        connection.commit()

        if cursor.rowcount == 0:
            return {"success": False, "message": "No application found with the given ID."}

        return {"success": True, "message": "Application status updated successfully."}
    except Exception as e:
        if connection:
            connection.rollback()
        return {"success": False, "message": f"Database error: {e}"}
    finally:
        if connection:
            connection.close()

def validate_student_login(email, password_hash):

    # Simplified: Student table does not store passwords in this schema.
    if not email or not email.endswith(school_domain or ""):
        return {"success": False, "message": "Invalid email address."}
    
    connection = None
    try:
        connection = sqlite3.connect(db_path, timeout=10.0)
        cursor = connection.cursor()
        cursor.execute('SELECT student_id, first_name, last_name FROM Student WHERE email = ?', (email,))
        student = cursor.fetchone()

        if student:
            return{
                'success': True,
                'student_id': student[0],
                'name': f"{student[1]} {student[2]}"
             }
        else:
            return {"success": False, "message": 'Invalid Email'}

    except Exception as e:
        if connection:
            connection.rollback()
        return {"success": False, "message": f"Database error: {e}"}
    finally:
        if connection:
            connection.close()


def delete_application(application_id):
    connection = None
    try:
        connection = sqlite3.connect(db_path, timeout=10.0)
        cursor = connection.cursor()

        cursor.execute('DELETE FROM StudentApplication WHERE id = ?', (application_id,))
        connection.commit()

        if cursor.rowcount == 0:
            return {"success": False, "message": "No application found with the given ID."}

        return {"success": True, "message": "Application deleted successfully."}
    except Exception as e:
        if connection:
            connection.rollback()
        return {"success": False, "message": f"Database error: {e}"}
    finally:
        if connection:
            connection.close()

def get_application_by_id(application_id):
    connection = None
    try:
        connection = sqlite3.connect(db_path, timeout=10.0)
        cursor = connection.cursor()
        cursor.execute('SELECT * FROM StudentApplication WHERE id = ?', (application_id,))
        row = cursor.fetchone()
        if not row:
            return {"success": False, "message": "No application found with the given ID."}
        columns = [description[0] for description in cursor.description]
        return {"success": True, "application": dict(zip(columns, row))}
    except Exception as e:
        return {"success": False, "message": f"Database error: {e}"}
    finally:
        if connection:
            connection.close()


def accept_application(application_id, review=None, note=None):
    """Approve app + SEND MAILTRAP EMAIL"""
    app_result = get_application_by_id(application_id)
    if not app_result.get("success"):
        return app_result

    application = app_result["application"]
    
    # Update status
    status_result = update_application_status(application_id, "approved", review, note)
    if not status_result.get("success"):
        return status_result

    # Generate school email
    email_result = generate_school_email(application_id)
    if not email_result.get("success"):
        return email_result
    school_email = email_result.get("email")

    # Create student
    insert_student(
        application.get("first_name"),
        application.get("last_name"),
        school_email,
        application.get("phone"),
        application.get("major"),
        "approved",
        application.get("graduation_date"),
        application.get("gpa"),
    )

    # SEND MAILTRAP EMAIL (NEW!)
    from app import mail, send_acceptance_email  # Import your email function
    email_sent = send_acceptance_email(
        application["email"],
        application["first_name"], 
        application["last_name"],
        school_email
    )

    return {
        "success": True,
        "message": f"Approved! School email: {school_email}",
        "school_email": school_email,
        "email_sent": email_sent["success"]
    }


