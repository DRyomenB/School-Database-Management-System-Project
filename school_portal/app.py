from flask import Flask, render_template, request, redirect, url_for, session, g, flash
import sqlite3
from functools import wraps
import math
import re
from datetime import datetime

DAY_MAP = {
    "M": "Mon",
    "T": "Tue",
    "W": "Wed",
    "Th": "Thu",
    "F": "Fri"
}

# Extract days (M,T,W,Th,F) and times
def parse_meeting_time(mt):
    # Normalize formatting
    mt = mt.strip().replace(" ", "").upper()

    # Handle "TH" before single-letter days like T or H
    normalized = mt.replace("TH", "H")  # Temporary replace for parsing
    
    # Extract days and times
    pattern = r'([MTWHF]+).*?(\d{1,2}:\d{2}).*?(\d{1,2}:\d{2})'
    match = re.search(pattern, normalized)
    if not match:
        return None, None, None
    
    days, start, end = match.groups()
    
    # Convert temporary H back into Th
    days = days.replace("H", "Th")

    start = datetime.strptime(start, "%H:%M")
    end = datetime.strptime(end, "%H:%M")

    return days, start, end

def times_overlap(mt1, mt2):
    days1, start1, end1 = parse_meeting_time(mt1)
    days2, start2, end2 = parse_meeting_time(mt2)
    
    if not days1 or not days2:
        return False
    
    # Check if any same day
    if not any(d in days2 for d in days1):
        return False
    
    return start1 < end2 and start2 < end1

DATABASE = "database.db"

app = Flask(__name__)
app.secret_key = "dev-secret-key"  # change for production


# ---------------- Database Helpers ---------------- #

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(error):
    db = g.pop("db", None)
    if db:
        db.close()


# ---------------- Auth Helper ---------------- #

def login_required(role=None):
    def decorator(view):
        @wraps(view)
        def wrapped_view(**kwargs):
            if "user_id" not in session:
                return redirect(url_for("login"))
            if role and session.get("role") != role:
                flash("Unauthorized access.")
                return redirect(url_for("home"))
            return view(**kwargs)
        return wrapped_view
    return decorator


# ---------------- Home + Login + Logout ---------------- #

@app.route("/")
def home():
    if "role" not in session:
        return redirect(url_for("login"))

    role = session["role"]
    if role == "admin":
        return redirect(url_for("admin_dashboard"))
    if role == "student":
        return redirect(url_for("student_dashboard"))
    if role == "instructor":
        return redirect(url_for("instructor_dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()

        db = get_db()
        user = db.execute(
            "SELECT * FROM UserAccount WHERE username=? AND password=?",
            (username, password),
        ).fetchone()

        if user:
            session["user_id"] = user["user_id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            session["student_id"] = user["student_id"]
            session["employee_id"] = user["employee_id"]
            return redirect(url_for("home"))

        flash("Incorrect username or password.")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# -------------------------------------------------------- #
#                        ADMIN
# -------------------------------------------------------- #

@app.route("/admin/dashboard")
@login_required(role="admin")
def admin_dashboard():
    db = get_db()
    student_count = db.execute("SELECT COUNT(*) AS c FROM Student").fetchone()["c"]
    course_count = db.execute("SELECT COUNT(*) AS c FROM Course").fetchone()["c"]
    instructor_count = db.execute("SELECT COUNT(*) AS c FROM Employee").fetchone()["c"]
    enrollment_count = db.execute("SELECT COUNT(*) AS c FROM Enrollment").fetchone()["c"]

    dept_stats = db.execute(
        """
        SELECT d.department_name,
               COUNT(s.student_id) AS student_count
        FROM Department d
        LEFT JOIN Student s ON s.major = d.department_name
        GROUP BY d.department_id
        ORDER BY d.department_name
        """
    ).fetchall()
    max_students = max([row["student_count"] for row in dept_stats] or [1])

    return render_template(
        "admin_dashboard.html",
        student_count=student_count,
        course_count=course_count,
        instructor_count=instructor_count,
        enrollment_count=enrollment_count,
        dept_stats=dept_stats,
        max_students=max_students,
    )


# ---- Admin: Students (with search & pagination) ---- #

@app.route("/admin/students")
@login_required(role="admin")
def admin_students():
    db = get_db()
    q = request.args.get("q", "").strip()
    page = int(request.args.get("page", 1))
    per_page = 10

    base_sql = "FROM Student WHERE 1=1"
    params = []

    if q:
        base_sql += " AND (first_name LIKE ? OR last_name LIKE ? OR email LIKE ?)"
        like = f"%{q}%"
        params.extend([like, like, like])

    total = db.execute(f"SELECT COUNT(*) AS c {base_sql}", params).fetchone()["c"]
    total_pages = max(1, math.ceil(total / per_page))
    page = max(1, min(page, total_pages))
    offset = (page - 1) * per_page

    students = db.execute(
        f"SELECT * {base_sql} ORDER BY last_name, first_name LIMIT ? OFFSET ?",
        params + [per_page, offset],
    ).fetchall()

    return render_template(
        "students.html",
        students=students,
        q=q,
        page=page,
        total_pages=total_pages,
    )


@app.route("/admin/students/add", methods=["GET", "POST"])
@login_required(role="admin")
def admin_add_student():
    db = get_db()
    if request.method == "POST":
        db.execute(
            """
            INSERT INTO Student (first_name, last_name, email, major, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                request.form["first_name"],
                request.form["last_name"],
                request.form["email"],
                request.form["major"],
                request.form["status"],
            ),
        )
        db.commit()
        flash("Student added.")
        return redirect(url_for("admin_students"))
    return render_template("add_student.html")


@app.route("/admin/students/edit/<int:student_id>", methods=["GET", "POST"])
@login_required(role="admin")
def admin_edit_student(student_id):
    db = get_db()
    student = db.execute(
        "SELECT * FROM Student WHERE student_id=?", (student_id,)
    ).fetchone()
    if request.method == "POST":
        db.execute(
            """
            UPDATE Student
            SET first_name=?, last_name=?, email=?, major=?, status=?
            WHERE student_id=?
            """,
            (
                request.form["first_name"],
                request.form["last_name"],
                request.form["email"],
                request.form["major"],
                request.form["status"],
                student_id,
            ),
        )
        db.commit()
        flash("Student updated.")
        return redirect(url_for("admin_students"))
    return render_template("edit_student.html", student=student)


@app.route("/admin/students/delete/<int:student_id>")
@login_required(role="admin")
def admin_delete_student(student_id):
    db = get_db()
    db.execute("DELETE FROM Student WHERE student_id=?", (student_id,))
    db.commit()
    flash("Student deleted.")
    return redirect(url_for("admin_students"))


# ---- Admin: Instructors (with office room) ---- #

@app.route("/admin/instructors")
@login_required(role="admin")
def admin_instructors():
    db = get_db()
    instructors = db.execute(
        """
        SELECT e.*,
               d.department_name,
               r.room_number AS office_room_number,
               b.building_name AS office_building_name
        FROM Employee e
        LEFT JOIN Department d ON e.department_id = d.department_id
        LEFT JOIN Room r ON e.office_id = r.room_id
        LEFT JOIN Building b ON r.building_id = b.building_id
        ORDER BY e.last_name, e.first_name
        """
    ).fetchall()
    return render_template("instructors.html", instructors=instructors)


def _get_rooms(db):
    return db.execute(
        """
        SELECT r.room_id, r.room_number, b.building_name
        FROM Room r
        JOIN Building b ON r.building_id = b.building_id
        ORDER BY b.building_name, r.room_number
        """
    ).fetchall()


@app.route("/admin/instructors/add", methods=["GET", "POST"])
@login_required(role="admin")
def admin_add_instructor():
    db = get_db()
    departments = db.execute(
        "SELECT * FROM Department ORDER BY department_name"
    ).fetchall()
    rooms = _get_rooms(db)

    if request.method == "POST":
        office_id = request.form.get("office_id") or None
        db.execute(
            """
            INSERT INTO Employee (first_name, last_name, email, position_title,
                                  department_id, salary, office_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request.form["first_name"],
                request.form["last_name"],
                request.form["email"],
                request.form["position_title"],
                request.form.get("department_id") or None,
                request.form.get("salary") or None,
                office_id,
            ),
        )
        db.commit()
        flash("Instructor added.")
        return redirect(url_for("admin_instructors"))

    return render_template(
        "add_instructor.html",
        departments=departments,
        rooms=rooms,
    )


@app.route("/admin/instructors/edit/<int:employee_id>", methods=["GET", "POST"])
@login_required(role="admin")
def admin_edit_instructor(employee_id):
    db = get_db()
    instructor = db.execute(
        "SELECT * FROM Employee WHERE employee_id=?", (employee_id,)
    ).fetchone()
    departments = db.execute(
        "SELECT * FROM Department ORDER BY department_name"
    ).fetchall()
    rooms = _get_rooms(db)

    if request.method == "POST":
        office_id = request.form.get("office_id") or None
        db.execute(
            """
            UPDATE Employee
            SET first_name=?, last_name=?, email=?, position_title=?,
                department_id=?, salary=?, office_id=?
            WHERE employee_id=?
            """,
            (
                request.form["first_name"],
                request.form["last_name"],
                request.form["email"],
                request.form["position_title"],
                request.form.get("department_id") or None,
                request.form.get("salary") or None,
                office_id,
                employee_id,
            ),
        )
        db.commit()
        flash("Instructor updated.")
        return redirect(url_for("admin_instructors"))

    return render_template(
        "edit_instructor.html",
        instructor=instructor,
        departments=departments,
        rooms=rooms,
    )


@app.route("/admin/instructors/delete/<int:employee_id>")
@login_required(role="admin")
def admin_delete_instructor(employee_id):
    db = get_db()
    db.execute("DELETE FROM Employee WHERE employee_id=?", (employee_id,))
    db.commit()
    flash("Instructor deleted.")
    return redirect(url_for("admin_instructors"))


# ---- Admin: Courses ---- #

@app.route("/admin/courses")
@login_required(role="admin")
def admin_courses():
    db = get_db()
    courses = db.execute(
        """
        SELECT c.*, d.department_name
        FROM Course c
        JOIN Department d ON c.department_id = d.department_id
        ORDER BY c.course_code
        """
    ).fetchall()

    # Fetch sections grouped by course
    sections = db.execute(
        """
        SELECT cs.selection_id, cs.course_id, cs.meeting_time,
               e.first_name || ' ' || e.last_name AS instructor_name,
               b.building_name, r.room_number
        FROM CourseSelection cs
        LEFT JOIN Employee e ON cs.instructor_id = e.employee_id
        LEFT JOIN Room r ON cs.room_id = r.room_id
        LEFT JOIN Building b ON r.building_id = b.building_id
        ORDER BY cs.course_id, cs.meeting_time
        """
    ).fetchall()

    # Group by course ID
    section_map = {}
    for s in sections:
        section_map.setdefault(s["course_id"], []).append(s)

    return render_template(
        "courses.html",
        courses=courses,
        section_map=section_map
    )


@app.route("/admin/courses/add", methods=["GET", "POST"])
@login_required(role="admin")
def admin_add_course():
    db = get_db()
    departments = db.execute(
        "SELECT * FROM Department ORDER BY department_name"
    ).fetchall()
    if request.method == "POST":
        db.execute(
            """
            INSERT INTO Course (course_code, course_name, credit, department_id)
            VALUES (?, ?, ?, ?)
            """,
            (
                request.form["course_code"],
                request.form["course_name"],
                request.form.get("credit") or None,
                request.form["department_id"],
            ),
        )
        db.commit()
        flash("Course added.")
        return redirect(url_for("admin_courses"))
    return render_template("add_course.html", departments=departments)


@app.route("/admin/courses/edit/<int:course_id>", methods=["GET", "POST"])
@login_required(role="admin")
def admin_edit_course(course_id):
    db = get_db()
    course = db.execute(
        "SELECT * FROM Course WHERE course_id=?", (course_id,)
    ).fetchone()
    departments = db.execute(
        "SELECT * FROM Department ORDER BY department_name"
    ).fetchall()
    if request.method == "POST":
        db.execute(
            """
            UPDATE Course
            SET course_code=?, course_name=?, credit=?, department_id=?
            WHERE course_id=?
            """,
            (
                request.form["course_code"],
                request.form["course_name"],
                request.form.get("credit") or None,
                request.form["department_id"],
                course_id,
            ),
        )
        db.commit()
        flash("Course updated.")
        return redirect(url_for("admin_courses"))
    return render_template("edit_course.html", course=course, departments=departments)


@app.route("/admin/courses/delete/<int:course_id>")
@login_required(role="admin")
def admin_delete_course(course_id):
    db = get_db()
    db.execute("DELETE FROM Course WHERE course_id=?", (course_id,))
    db.commit()
    flash("Course deleted.")
    return redirect(url_for("admin_courses"))

# ---- Admin: Course Sections ---- #

@app.route("/admin/courses/<int:course_id>/sections")
@login_required(role="admin")
def admin_course_sections(course_id):
    db = get_db()

    course = db.execute(
        "SELECT * FROM Course WHERE course_id=?", (course_id,)
    ).fetchone()

    sections = db.execute(
        """
        SELECT cs.*, 
            (SELECT COUNT(*) FROM Enrollment WHERE selection_id = cs.selection_id) AS enrolled,
            e.first_name || ' ' || e.last_name AS instructor_name,
            b.building_name,
            r.room_number
        FROM CourseSelection cs
        LEFT JOIN Employee e ON cs.instructor_id = e.employee_id
        LEFT JOIN Room r ON cs.room_id = r.room_id
        LEFT JOIN Building b ON r.building_id = b.building_id
        WHERE cs.course_id = ?
        ORDER BY cs.meeting_time
        """,
        (course_id,)
    ).fetchall()

    return render_template("course_sections.html",
                           course=course,
                           sections=sections)

@app.route("/admin/courses/<int:course_id>/sections/add", methods=["GET", "POST"])
@login_required(role="admin")
def admin_add_section(course_id):
    db = get_db()

    instructors = db.execute(
        "SELECT employee_id, first_name || ' ' || last_name AS name "
        "FROM Employee ORDER BY last_name"
    ).fetchall()

    rooms = db.execute(
        """
        SELECT r.room_id, r.room_number, b.building_name
        FROM Room r
        JOIN Building b ON r.building_id = b.building_id
        ORDER BY b.building_name, r.room_number
        """
    ).fetchall()

    if request.method == "POST":
        db.execute(
            """
            INSERT INTO CourseSelection (course_id, instructor_id, room_id, meeting_time)
            VALUES (?, ?, ?, ?)
            """,
            (
                course_id,
                request.form.get("instructor_id") or None,
                request.form.get("room_id") or None,
                request.form["meeting_time"]
            ),
        )
        db.commit()
        flash("Class section created.")
        return redirect(url_for("admin_course_sections", course_id=course_id))

    return render_template("add_section.html",
                           course_id=course_id,
                           instructors=instructors,
                           rooms=rooms)


@app.route("/admin/sections/delete/<int:selection_id>/<int:course_id>")
@login_required(role="admin")
def admin_delete_section(selection_id, course_id):
    db = get_db()
    db.execute(
        "DELETE FROM CourseSelection WHERE selection_id = ?",
        (selection_id,)
    )
    db.commit()
    flash("Section deleted.")
    return redirect(url_for("admin_course_sections", course_id=course_id))

# -------------------------------------------------------- #
#                        STUDENT
# -------------------------------------------------------- #

@app.route("/student/dashboard")
@login_required(role="student")
def student_dashboard():
    db = get_db()
    sid = session["student_id"]
    student = db.execute(
        "SELECT * FROM Student WHERE student_id=?", (sid,)
    ).fetchone()

    enrollments = db.execute(
        """
        SELECT c.course_code,
               c.course_name,
               cs.meeting_time,
               b.building_name,
               r.room_number,
               e.grade
        FROM Enrollment e
        JOIN CourseSelection cs ON e.selection_id = cs.selection_id
        JOIN Course c ON cs.course_id = c.course_id
        LEFT JOIN Room r ON cs.room_id = r.room_id
        LEFT JOIN Building b ON r.building_id = b.building_id
        WHERE e.student_id = ?
        ORDER BY c.course_code
        """,
        (sid,),
    ).fetchall()

    return render_template(
        "student_dashboard.html",
        student=student,
        enrollments=enrollments,
    )


@app.route("/student/courses")
@login_required(role="student")
def student_courses():
    db = get_db()
    sid = session["student_id"]
    courses = db.execute(
        """
        SELECT c.course_code,
               c.course_name,
               cs.meeting_time,
               b.building_name,
               r.room_number,
               e.grade
        FROM Enrollment e
        JOIN CourseSelection cs ON e.selection_id = cs.selection_id
        JOIN Course c ON cs.course_id = c.course_id
        LEFT JOIN Room r ON cs.room_id = r.room_id
        LEFT JOIN Building b ON r.building_id = b.building_id
        WHERE e.student_id = ?
        ORDER BY c.course_code
        """,
        (sid,),
    ).fetchall()
    return render_template("student_courses.html", courses=courses)


@app.route("/student/enroll", methods=["GET", "POST"])
@login_required(role="student")
def student_enroll():
    db = get_db()
    student_id = session["student_id"]

    # Student submits enrollment form
    if request.method == "POST":
        selection_id = request.form["selection_id"]

        # Capacity Check
        cap = db.execute(
            """
            SELECT capacity,
                   (SELECT COUNT(*) FROM Enrollment WHERE selection_id = ?) AS enrolled
            FROM CourseSelection
            WHERE selection_id = ?
            """,
            (selection_id, selection_id)
        ).fetchone()

        if cap and cap["enrolled"] >= cap["capacity"]:
            flash("⚠ Cannot enroll: This section is FULL.")
            return redirect(url_for("student_enroll"))

        # Time conflict check
        new_days, new_start, new_end = parse_meeting_time(
            db.execute(
                "SELECT meeting_time FROM CourseSelection WHERE selection_id = ?",
                (selection_id,)
            ).fetchone()["meeting_time"]
        )

        # Existing enrollments
        existing = db.execute(
            """
            SELECT cs.meeting_time
            FROM Enrollment e
            JOIN CourseSelection cs ON e.selection_id = cs.selection_id
            WHERE e.student_id = ?
            """,
            (student_id,)
        ).fetchall()

        for e in existing:
            e_days, e_start, e_end = parse_meeting_time(e["meeting_time"])
            if times_overlap(new_days, new_start, new_end, e_days, e_start, e_end):
                flash("⚠ Cannot enroll: Time conflict detected.")
                return redirect(url_for("student_enroll"))

        # If OK → Insert Enrollment
        db.execute(
            """
            INSERT INTO Enrollment (student_id, selection_id, enrollment_date)
            VALUES (?, ?, DATE('now'))
            """,
            (student_id, selection_id)
        )
        db.commit()

        flash("✔ Successfully enrolled!")
        return redirect(url_for("student_dashboard"))

    # GET — Show available sections
    sections = db.execute(
        """
        SELECT cs.selection_id,
               c.course_code,
               c.course_name,
               cs.meeting_time,
               cs.capacity,
               (SELECT COUNT(*) FROM Enrollment e WHERE e.selection_id = cs.selection_id) AS enrolled,
               b.building_name,
               r.room_number
        FROM CourseSelection cs
        JOIN Course c ON cs.course_id = c.course_id
        LEFT JOIN Room r ON cs.room_id = r.room_id
        LEFT JOIN Building b ON r.building_id = b.building_id
        WHERE cs.selection_id NOT IN (
            SELECT selection_id FROM Enrollment WHERE student_id = ?
        )
        ORDER BY c.course_code
        """,
        (student_id,)
    ).fetchall()

    return render_template("student_enroll.html", sections=sections)

@app.route("/student/transcript")
@login_required(role="student")
def student_transcript():
    db = get_db()
    sid = session["student_id"]
    student = db.execute(
        "SELECT * FROM Student WHERE student_id=?", (sid,)
    ).fetchone()

    transcript_rows = db.execute(
        """
        SELECT c.course_code, c.course_name, e.grade
        FROM Enrollment e
        JOIN CourseSelection cs ON e.selection_id = cs.selection_id
        JOIN Course c ON cs.course_id = c.course_id
        WHERE e.student_id = ?
        ORDER BY c.course_code
        """,
        (sid,),
    ).fetchall()

    return render_template(
        "transcript.html",
        student=student,
        transcript_rows=transcript_rows,
    )


# -------------------------------------------------------- #
#                       INSTRUCTOR
# -------------------------------------------------------- #

@app.route("/instructor/dashboard")
@login_required(role="instructor")
def instructor_dashboard():
    db = get_db()
    eid = session["employee_id"]

    instructor = db.execute(
        """
        SELECT e.*,
               r.room_number AS office_room_number,
               b.building_name AS office_building_name
        FROM Employee e
        LEFT JOIN Room r ON e.office_id = r.room_id
        LEFT JOIN Building b ON r.building_id = b.building_id
        WHERE e.employee_id = ?
        """,
        (eid,),
    ).fetchone()

    sections = db.execute(
        """
        SELECT cs.selection_id,
               c.course_code,
               c.course_name,
               cs.meeting_time,
               b.building_name,
               r.room_number
        FROM CourseSelection cs
        JOIN Course c ON cs.course_id = c.course_id
        LEFT JOIN Room r ON cs.room_id = r.room_id
        LEFT JOIN Building b ON r.building_id = b.building_id
        WHERE cs.instructor_id = ?
        ORDER BY c.course_code
        """,
        (eid,),
    ).fetchall()

    return render_template(
        "instructor_dashboard.html",
        instructor=instructor,
        sections=sections,
    )


@app.route("/instructor/section/<int:selection_id>", methods=["GET", "POST"])
@login_required(role="instructor")
def instructor_section(selection_id):
    db = get_db()

    if request.method == "POST":
        for key, value in request.form.items():
            if key.startswith("grade_") and value.strip():
                enrollment_id = key.split("_")[1]
                db.execute(
                    "UPDATE Enrollment SET grade=? WHERE enrollment_id=?",
                    (float(value), enrollment_id),
                )

        # recalc GPA for students in this section
        sids = db.execute(
            "SELECT DISTINCT student_id FROM Enrollment WHERE selection_id=?",
            (selection_id,),
        ).fetchall()
        for row in sids:
            sid = row["student_id"]
            gpa_row = db.execute(
                """
                SELECT AVG(grade)/25.0 AS gpa
                FROM Enrollment
                WHERE student_id=? AND grade IS NOT NULL
                """,
                (sid,),
            ).fetchone()
            if gpa_row["gpa"] is not None:
                db.execute(
                    "UPDATE Student SET gpa=? WHERE student_id=?",
                    (gpa_row["gpa"], sid),
                )
        db.commit()
        flash("Grades updated and GPA recalculated.")

    section = db.execute(
        """
        SELECT cs.*,
               c.course_code,
               c.course_name,
               b.building_name,
               r.room_number
        FROM CourseSelection cs
        JOIN Course c ON cs.course_id = c.course_id
        LEFT JOIN Room r ON cs.room_id = r.room_id
        LEFT JOIN Building b ON r.building_id = b.building_id
        WHERE cs.selection_id = ?
        """,
        (selection_id,),
    ).fetchone()

    students = db.execute(
        """
        SELECT e.enrollment_id,
               s.student_id,
               s.first_name,
               s.last_name,
               e.grade
        FROM Enrollment e
        JOIN Student s ON e.student_id = s.student_id
        WHERE e.selection_id = ?
        ORDER BY s.last_name, s.first_name
        """,
        (selection_id,),
    ).fetchall()

    report = db.execute(
        """
        SELECT AVG(grade) AS avg_grade,
               MIN(grade) AS min_grade,
               MAX(grade) AS max_grade
        FROM Enrollment
        WHERE selection_id = ? AND grade IS NOT NULL
        """,
        (selection_id,),
    ).fetchone()

    return render_template(
        "instructor_section.html",
        section=section,
        students=students,
        report=report,
    )


@app.route("/instructor/section/<int:selection_id>/attendance", methods=["GET", "POST"])
@login_required(role="instructor")
def instructor_attendance(selection_id):
    db = get_db()
    today = db.execute("SELECT DATE('now') AS d").fetchone()["d"]

    if request.method == "POST":
        db.execute(
            "DELETE FROM Attendance WHERE selection_id=? AND date=?",
            (selection_id, today),
        )
        for key, value in request.form.items():
            if key.startswith("status_"):
                sid = key.split("_")[1]
                db.execute(
                    """
                    INSERT INTO Attendance (student_id, selection_id, date, status)
                    VALUES (?, ?, ?, ?)
                    """,
                    (sid, selection_id, today, value),
                )
        db.commit()
        flash("Attendance saved.")

    section = db.execute(
        """
        SELECT cs.*,
               c.course_code,
               c.course_name,
               b.building_name,
               r.room_number
        FROM CourseSelection cs
        JOIN Course c ON cs.course_id = c.course_id
        LEFT JOIN Room r ON cs.room_id = r.room_id
        LEFT JOIN Building b ON r.building_id = b.building_id
        WHERE cs.selection_id = ?
        """,
        (selection_id,),
    ).fetchone()

    students = db.execute(
        """
        SELECT s.student_id,
               s.first_name,
               s.last_name
        FROM Enrollment e
        JOIN Student s ON e.student_id = s.student_id
        WHERE e.selection_id = ?
        ORDER BY s.last_name, s.first_name
        """,
        (selection_id,),
    ).fetchall()

    records = db.execute(
        """
        SELECT student_id, status
        FROM Attendance
        WHERE selection_id=? AND date=?
        """,
        (selection_id, today),
    ).fetchall()
    status_map = {row["student_id"]: row["status"] for row in records}

    stats = db.execute(
        """
        SELECT
            SUM(status='Present') AS present_count,
            SUM(status='Absent')  AS absent_count,
            SUM(status='Late')    AS late_count
        FROM Attendance
        WHERE selection_id=?
        """,
        (selection_id,),
    ).fetchone()

    return render_template(
        "attendance.html",
        section=section,
        students=students,
        today=today,
        status_map=status_map,
        stats=stats,
    )

# ---------------- Run ---------------- #

if __name__ == "__main__":
    print(app.url_map)
    app.run(debug=True)