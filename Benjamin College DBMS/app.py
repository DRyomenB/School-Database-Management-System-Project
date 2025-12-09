from flask import Flask, render_template, request, redirect, url_for, session, g, flash
import sqlite3
from functools import wraps
import math

DATABASE = "database.db"

app = Flask(__name__)
app.secret_key = "dev-secret-key"  # change for production

# DATABASE HELPERS

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

# SCHEDULE / CONFLICT HELPERS
DAY_ORDER = {"M": 1, "T": 2, "W": 3, "Th": 4, "F": 5}

def get_section_schedule(db, selection_id):
    """
    Returns list of rows: (day_code, start_time, end_time) for a section.
    """
    return db.execute(
        """
        SELECT day_code, start_time, end_time
        FROM CourseSchedule
        WHERE selection_id = ?
        """,
        (selection_id,),
    ).fetchall()

def build_meeting_label(rows):
    """
    Turn CourseSchedule rows into a label like 'MW 10:00-11:30' or 'TTh 13:00-14:30'.
    Assumes same start/end time on each day (true for our sample data).
    """
    if not rows:
        return ""

    # Sort by day order for consistency
    rows_sorted = sorted(rows, key=lambda r: DAY_ORDER.get(r["day_code"], 99))
    days = [r["day_code"] for r in rows_sorted]

    start_time = rows_sorted[0]["start_time"]
    end_time = rows_sorted[0]["end_time"]

    # Collapse days into compact string e.g. ['M','W'] -> 'MW', ['T','Th'] -> 'TTh'
    day_str = "".join(days)

    return f"{day_str} {start_time}-{end_time}"

def attach_meeting_labels(db, rows):
    """
    Takes an iterable of sqlite3.Row objects that contain selection_id
    and returns a list of dicts with an extra 'meeting_label' field.
    """
    out = []
    for row in rows:
        selection_id = row["selection_id"]
        sched = get_section_schedule(db, selection_id)
        label = build_meeting_label(sched)
        d = dict(row)
        d["meeting_label"] = label
        out.append(d)
    return out

def _time_to_minutes(t):
    # t = 'HH:MM'
    h, m = map(int, t.split(":"))
    return h * 60 + m

def sections_conflict(db, selection_new, selection_existing):
    """
    True if CourseSchedule for selection_new conflicts in time
    with CourseSchedule for selection_existing.
    """
    sched_new = get_section_schedule(db, selection_new)
    sched_existing = get_section_schedule(db, selection_existing)

    for r1 in sched_new:
        for r2 in sched_existing:
            if r1["day_code"] != r2["day_code"]:
                continue
            s1 = _time_to_minutes(r1["start_time"])
            e1 = _time_to_minutes(r1["end_time"])
            s2 = _time_to_minutes(r2["start_time"])
            e2 = _time_to_minutes(r2["end_time"])
            if s1 < e2 and s2 < e1:
                return True
    return False

# AUTH HELPER
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

# HOME + LOGIN + LOGOUT
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

# ADMIN
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

# Admin: Students
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

# Admin: Instructors & Payroll
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

@app.route("/admin/payroll")
@login_required(role="admin")
def admin_payroll():
    db = get_db()
    rows = db.execute(
        """
        SELECT p.*, e.first_name || ' ' || e.last_name AS name
        FROM Payroll p
        JOIN Employee e ON p.employee_id = e.employee_id
        ORDER BY p.pay_date DESC
        """
    ).fetchall()
    return render_template("admin_payroll.html", payrolls=rows)

@app.route("/instructor/payroll")
@login_required(role="instructor")
def instructor_payroll():
    db = get_db()
    eid = session["employee_id"]

    rows = db.execute(
        """
        SELECT * FROM Payroll
        WHERE employee_id = ?
        ORDER BY pay_date DESC
        """,
        (eid,),
    ).fetchall()

    return render_template("instructor_payroll.html", payrolls=rows)

@app.route("/admin/payroll/add", methods=["GET", "POST"])
@login_required(role="admin")
def admin_add_payroll():
    db = get_db()
    employees = db.execute(
        """
        SELECT employee_id, first_name || ' ' || last_name AS name, salary
        FROM Employee ORDER BY last_name
        """
    ).fetchall()

    if request.method == "POST":
        employee_id = request.form["employee_id"]
        gross = float(request.form["gross_amount"])
        deductions = float(request.form.get("deductions") or 0)
        net = gross - deductions

        db.execute(
            """
            INSERT INTO Payroll (employee_id, pay_date, gross_amount, deductions, net_amount, notes)
            VALUES (?, DATE('now'), ?, ?, ?, ?)
            """,
            (employee_id, gross, deductions, net, request.form.get("notes")),
        )
        db.commit()
        flash("Payroll entry recorded.")
        return redirect(url_for("admin_payroll"))

    return render_template("admin_add_payroll.html", employees=employees)

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

@app.route("/admin/instructors/<int:employee_id>/reviews")
@login_required(role="admin")
def admin_instructor_reviews(employee_id):
    db = get_db()
    instructor = db.execute(
        "SELECT * FROM Employee WHERE employee_id=?",
        (employee_id,),
    ).fetchone()
    reviews = db.execute(
        """
        SELECT * FROM PerformanceReview
        WHERE employee_id=?
        ORDER BY review_date DESC
        """,
        (employee_id,),
    ).fetchall()
    return render_template(
        "reviews_admin.html",
        instructor=instructor,
        reviews=reviews,
    )

@app.route("/admin/instructors/<int:employee_id>/reviews/add", methods=["GET", "POST"])
@login_required(role="admin")
def admin_add_review(employee_id):
    db = get_db()
    instructor = db.execute(
        "SELECT * FROM Employee WHERE employee_id=?",
        (employee_id,),
    ).fetchone()

    if request.method == "POST":
        db.execute(
            """
            INSERT INTO PerformanceReview (employee_id, review_date, rating, comments)
            VALUES (?, ?, ?, ?)
            """,
            (
                employee_id,
                request.form["review_date"],
                request.form["rating"],
                request.form["comments"],
            ),
        )
        db.commit()
        flash("Review added.")
        return redirect(url_for("admin_instructor_reviews", employee_id=employee_id))

    return render_template("add_review.html", instructor=instructor)

# Admin: Budgets
@app.route("/admin/budgets")
@login_required(role="admin")
def admin_budgets():
    db = get_db()
    rows = db.execute(
        """
        SELECT b.budget_id,
               d.department_name,
               b.fiscal_year,
               b.allocated_amount,
               b.spent_amount
        FROM DepartmentBudget b
        JOIN Department d ON b.department_id = d.department_id
        ORDER BY b.fiscal_year DESC, d.department_name
        """
    ).fetchall()
    return render_template("budgets.html", budgets=rows)

@app.route("/admin/budgets/add", methods=["GET", "POST"])
@login_required(role="admin")
def admin_add_budget():
    db = get_db()
    departments = db.execute(
        "SELECT * FROM Department ORDER BY department_name"
    ).fetchall()

    if request.method == "POST":
        db.execute(
            """
            INSERT INTO DepartmentBudget (department_id, fiscal_year, allocated_amount, spent_amount)
            VALUES (?, ?, ?, ?)
            """,
            (
                request.form["department_id"],
                request.form["fiscal_year"],
                request.form["allocated_amount"],
                request.form.get("spent_amount") or 0,
            ),
        )
        db.commit()
        flash("Budget record added.")
        return redirect(url_for("admin_budgets"))

    return render_template("add_budget.html", departments=departments)

# Admin: Courses & Sections
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

    sections_raw = db.execute(
        """
        SELECT cs.selection_id,
               cs.course_id,
               cs.capacity,
               e.first_name || ' ' || e.last_name AS instructor_name,
               b.building_name,
               r.room_number
        FROM CourseSelection cs
        LEFT JOIN Employee e ON cs.instructor_id = e.employee_id
        LEFT JOIN Room r ON cs.room_id = r.room_id
        LEFT JOIN Building b ON r.building_id = b.building_id
        ORDER BY cs.course_id, cs.selection_id
        """
    ).fetchall()

    sections = attach_meeting_labels(db, sections_raw)

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

@app.route("/admin/courses/<int:course_id>/sections")
@login_required(role="admin")
def admin_course_sections(course_id):
    db = get_db()

    course = db.execute(
        "SELECT * FROM Course WHERE course_id=?", (course_id,)
    ).fetchone()

    sections_raw = db.execute(
        """
        SELECT cs.selection_id,
               cs.course_id,
               cs.capacity,
               (SELECT COUNT(*) FROM Enrollment WHERE selection_id = cs.selection_id) AS enrolled,
               e.first_name || ' ' || e.last_name AS instructor_name,
               b.building_name,
               r.room_number
        FROM CourseSelection cs
        LEFT JOIN Employee e ON cs.instructor_id = e.employee_id
        LEFT JOIN Room r ON cs.room_id = r.room_id
        LEFT JOIN Building b ON r.building_id = b.building_id
        WHERE cs.course_id = ?
        ORDER BY cs.selection_id
        """,
        (course_id,),
    ).fetchall()

    sections = attach_meeting_labels(db, sections_raw)

    return render_template(
        "course_sections.html",
        course=course,
        sections=sections
    )

@app.route("/admin/courses/<int:course_id>/sections/add", methods=["GET", "POST"])
@login_required(role="admin")
def admin_add_section(course_id):
    db = get_db()

    course = db.execute(
        "SELECT * FROM Course WHERE course_id=?", (course_id,)
    ).fetchone()

    instructors = db.execute(
        "SELECT employee_id, first_name || ' ' || last_name AS name FROM Employee ORDER BY last_name"
    ).fetchall()

    rooms = _get_rooms(db)

    if request.method == "POST":
        instructor_id = request.form.get("instructor_id") or None
        room_id = request.form.get("room_id") or None
        start_time = request.form["start_time"]
        end_time = request.form["end_time"]
        capacity = request.form.get("capacity") or 30
        selected_days = request.form.getlist("days")

        cur = db.execute(
            """
            INSERT INTO CourseSelection (course_id, instructor_id, room_id, capacity)
            VALUES (?, ?, ?, ?)
            """,
            (course_id, instructor_id, room_id, capacity),
        )
        selection_id = cur.lastrowid

        for day in selected_days:
            db.execute(
                """
                INSERT INTO CourseSchedule (selection_id, day_code, start_time, end_time)
                VALUES (?, ?, ?, ?)
                """,
                (selection_id, day, start_time, end_time),
            )

        db.commit()
        flash("Section created successfully.")
        return redirect(url_for("admin_course_sections", course_id=course_id))

    return render_template(
        "add_section.html",
        course=course,
        instructors=instructors,
        rooms=rooms,
    )

@app.route("/admin/sections/edit/<int:selection_id>/<int:course_id>", methods=["GET", "POST"])
@login_required(role="admin")
def admin_edit_section(selection_id, course_id):
    db = get_db()

    section = db.execute(
        "SELECT * FROM CourseSelection WHERE selection_id=?",
        (selection_id,),
    ).fetchone()

    instructors = db.execute(
        "SELECT employee_id, first_name || ' ' || last_name AS name FROM Employee ORDER BY last_name"
    ).fetchall()

    rooms = _get_rooms(db)

    # existing schedule rows for this section
    sched_rows = db.execute(
        """
        SELECT day_code, start_time, end_time
        FROM CourseSchedule
        WHERE selection_id=?
        ORDER BY CASE day_code
            WHEN 'M' THEN 1
            WHEN 'T' THEN 2
            WHEN 'W' THEN 3
            WHEN 'Th' THEN 4
            WHEN 'F' THEN 5
            ELSE 99
        END
        """,
        (selection_id,),
    ).fetchall()

    existing_days = [r["day_code"] for r in sched_rows]
    start_time = sched_rows[0]["start_time"] if sched_rows else ""
    end_time = sched_rows[0]["end_time"] if sched_rows else ""

    if request.method == "POST":
        instructor_id = request.form.get("instructor_id") or None
        room_id = request.form.get("room_id") or None
        capacity = request.form.get("capacity") or 30
        new_start = request.form["start_time"]
        new_end = request.form["end_time"]
        new_days = request.form.getlist("days")

        db.execute(
            """
            UPDATE CourseSelection
            SET instructor_id=?, room_id=?, capacity=?
            WHERE selection_id=?
            """,
            (instructor_id, room_id, capacity, selection_id),
        )

        # Replace schedule rows
        db.execute(
            "DELETE FROM CourseSchedule WHERE selection_id=?",
            (selection_id,),
        )
        for day in new_days:
            db.execute(
                """
                INSERT INTO CourseSchedule (selection_id, day_code, start_time, end_time)
                VALUES (?, ?, ?, ?)
                """,
                (selection_id, day, new_start, new_end),
            )

        db.commit()
        flash("Section updated successfully.")
        return redirect(url_for("admin_course_sections", course_id=course_id))

    return render_template(
        "edit_section.html",
        section=section,
        instructors=instructors,
        rooms=rooms,
        course_id=course_id,
        existing_days=existing_days,
        start_time=start_time,
        end_time=end_time,
    )

@app.route("/admin/sections/delete/<int:selection_id>/<int:course_id>")
@login_required(role="admin")
def admin_delete_section(selection_id, course_id):
    db = get_db()
    db.execute("DELETE FROM CourseSchedule WHERE selection_id=?", (selection_id,))
    db.execute("DELETE FROM CourseSelection WHERE selection_id=?", (selection_id,))
    db.commit()
    flash("Section deleted.")
    return redirect(url_for("admin_course_sections", course_id=course_id))

# Admin: SQL Console
@app.route("/admin/sql", methods=["GET", "POST"])
@login_required(role="admin")
def admin_sql_console():
    db = get_db()
    results = None
    headers = None
    query = ""

    if request.method == "POST":
        query = request.form.get("query", "").strip()

        forbidden = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE"]
        q_upper = query.upper()

        if any(bad in q_upper for bad in forbidden):
            flash("Modification queries are not allowed for safety.")
        elif not q_upper.startswith("SELECT"):
            flash("Only SELECT queries are permitted.")
        else:
            try:
                cursor = db.execute(query)
                rows = cursor.fetchall()
                headers = [desc[0] for desc in cursor.description] if rows else []
                results = rows
            except Exception as e:
                flash(f"SQL Error: {e}")

    return render_template(
        "admin_sql.html",
        query=query,
        results=results,
        headers=headers,
    )

# STUDENT
@app.route("/student/dashboard")
@login_required(role="student")
def student_dashboard():
    db = get_db()
    sid = session["student_id"]
    student = db.execute(
        "SELECT * FROM Student WHERE student_id=?", (sid,)
    ).fetchone()

    rows_raw = db.execute(
        """
        SELECT e.enrollment_id,
               cs.selection_id,
               c.course_code,
               c.course_name,
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

    enrollments = attach_meeting_labels(db, rows_raw)

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
    rows_raw = db.execute(
        """
        SELECT e.enrollment_id,
               cs.selection_id,
               c.course_code,
               c.course_name,
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

    courses = attach_meeting_labels(db, rows_raw)
    return render_template("student_courses.html", courses=courses)

@app.route("/student/enroll", methods=["GET", "POST"])
@login_required(role="student")
def student_enroll():
    db = get_db()
    sid = session["student_id"]

    if request.method == "POST":
        selection_id = int(request.form["selection_id"])

        # Capacity check
        cap_row = db.execute(
            """
            SELECT capacity,
                   (SELECT COUNT(*) FROM Enrollment WHERE selection_id = ?) AS enrolled
            FROM CourseSelection
            WHERE selection_id = ?
            """,
            (selection_id, selection_id),
        ).fetchone()

        if cap_row and cap_row["enrolled"] >= cap_row["capacity"]:
            flash("⚠ This section is FULL. Please choose another.")
            return redirect(url_for("student_enroll"))

        # Prerequisite check
        course_row = db.execute(
            "SELECT course_id FROM CourseSelection WHERE selection_id=?",
            (selection_id,),
        ).fetchone()
        course_id = course_row["course_id"]

        prereqs = db.execute(
            "SELECT prereq_course_id FROM CoursePrerequisite WHERE course_id=?",
            (course_id,),
        ).fetchall()

        for p in prereqs:
            needed_id = p["prereq_course_id"]
            passed = db.execute(
                """
                SELECT COUNT(*) AS c
                FROM Enrollment e
                JOIN CourseSelection cs ON e.selection_id = cs.selection_id
                WHERE e.student_id = ?
                  AND cs.course_id = ?
                  AND e.grade IS NOT NULL
                  AND e.grade >= 70
                """,
                (sid, needed_id),
            ).fetchone()["c"]
            if passed == 0:
                flash("⚠ Prerequisite not met for this course.")
                return redirect(url_for("student_enroll"))

        # Time conflict check using CourseSchedule
        existing = db.execute(
            """
            SELECT cs.selection_id
            FROM Enrollment e
            JOIN CourseSelection cs ON e.selection_id = cs.selection_id
            WHERE e.student_id = ?
            """,
            (sid,),
        ).fetchall()

        for row in existing:
            if sections_conflict(db, selection_id, row["selection_id"]):
                flash("⚠ Schedule conflict with an existing class.")
                return redirect(url_for("student_enroll"))

        db.execute(
            """
            INSERT INTO Enrollment (student_id, selection_id, enrollment_date)
            VALUES (?, ?, DATE('now'))
            """,
            (sid, selection_id),
        )
        db.commit()
        flash("Enrolled successfully.")
        return redirect(url_for("student_courses"))

    # GET – available sections
    selections_raw = db.execute(
        """
        SELECT cs.selection_id,
               c.course_code,
               c.course_name,
               b.building_name,
               r.room_number,
               cs.capacity,
               (SELECT COUNT(*) FROM Enrollment e WHERE e.selection_id = cs.selection_id) AS enrolled
        FROM CourseSelection cs
        JOIN Course c ON cs.course_id = c.course_id
        LEFT JOIN Room r ON cs.room_id = r.room_id
        LEFT JOIN Building b ON r.building_id = b.building_id
        WHERE cs.selection_id NOT IN (
            SELECT selection_id FROM Enrollment WHERE student_id = ?
        )
        ORDER BY c.course_code
        """,
        (sid,),
    ).fetchall()

    selections = attach_meeting_labels(db, selections_raw)

    return render_template("student_enroll.html", selections=selections)

@app.route("/student/transcript")
@login_required(role="student")
def student_transcript():
    db = get_db()
    sid = session["student_id"]

    student = db.execute(
        "SELECT * FROM Student WHERE student_id=?",
        (sid,),
    ).fetchone()

    rows = db.execute(
        """
        SELECT c.course_code,
               c.course_name,
               c.credit,
               e.grade
        FROM Enrollment e
        JOIN CourseSelection cs ON e.selection_id = cs.selection_id
        JOIN Course c ON cs.course_id = c.course_id
        WHERE e.student_id = ?
        ORDER BY c.course_code
        """,
        (sid,),
    ).fetchall()

    total_credits = sum(r["credit"] for r in rows if r["credit"] is not None)
    completed_rows = [r for r in rows if r["grade"] is not None]
    if completed_rows:
        gpa = sum((r["grade"] / 25.0) for r in completed_rows) / len(completed_rows)
    else:
        gpa = None

    return render_template(
        "transcript.html",
        student=student,
        rows=rows,
        total_credits=total_credits,
        gpa=gpa,
    )

# INSTRUCTOR
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

    sections_raw = db.execute(
        """
        SELECT cs.selection_id,
               c.course_code,
               c.course_name,
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

    sections = attach_meeting_labels(db, sections_raw)

    return render_template(
        "instructor_dashboard.html",
        instructor=instructor,
        sections=sections,
    )

@app.route("/instructor/reviews")
@login_required(role="instructor")
def instructor_reviews():
    db = get_db()
    eid = session["employee_id"]

    # Instructor info with office + department
    instructor = db.execute(
        """
        SELECT e.*,
               d.department_name,
               r.room_number AS office_room_number,
               b.building_name AS office_building_name
        FROM Employee e
        LEFT JOIN Department d ON e.department_id = d.department_id
        LEFT JOIN Room r ON e.office_id = r.room_id
        LEFT JOIN Building b ON r.building_id = b.building_id
        WHERE e.employee_id = ?
        """,
        (eid,),
    ).fetchone()

    # Reviews list
    reviews = db.execute(
        """
        SELECT review_id, review_date, rating, comments
        FROM PerformanceReview
        WHERE employee_id = ?
        ORDER BY review_date DESC
        """,
        (eid,),
    ).fetchall()

    return render_template(
        "reviews_instructor.html",
        instructor=instructor,
        reviews=reviews,
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

    section_row = db.execute(
        """
        SELECT cs.selection_id,
               cs.course_id,
               cs.capacity,
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

    section_list = attach_meeting_labels(db, [section_row])
    section = section_list[0]

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

    section_row = db.execute(
        """
        SELECT cs.selection_id,
               cs.course_id,
               cs.capacity,
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

    section_list = attach_meeting_labels(db, [section_row])
    section = section_list[0]

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

# RUN
if __name__ == "__main__":
    print(app.url_map)
    app.run(debug=True)