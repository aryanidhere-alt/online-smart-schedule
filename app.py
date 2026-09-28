from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from database import get_db_connection
from functools import wraps
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.lib import colors
import os

app = Flask(__name__)

import os

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "online-smart-schedule-development-key"
)

# ==========================================================
# HOME PAGE
# ==========================================================

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/index")
def index():
    return redirect(url_for("home"))

# ==========================================================
# STUDENT REGISTER
# ==========================================================

@app.route("/student/register", methods=["GET", "POST"])
def student_register():

    if request.method == "POST":

        name = request.form["student_name"]
        email = request.form["email"]
        password = request.form["password"]
        department = request.form["department"]
        semester = request.form["semester"]

        connection = get_db_connection()
        cursor = connection.cursor()

        try:

            query = """
            INSERT INTO students
            (student_name, email, password, department, semester)
            VALUES (%s, %s, %s, %s, %s)
            """

            cursor.execute(
                query,
                (name, email, password, department, semester)
            )

            connection.commit()

            flash("Registration successful. Please login.")

            return redirect(url_for("student_login"))

        except Exception as e:

            connection.rollback()

            flash("Email already exists or registration failed.")

        finally:

            cursor.close()
            connection.close()

    return render_template("student_register.html")


# ==========================================================
# STUDENT LOGIN
# ==========================================================

@app.route("/student/login", methods=["GET", "POST"])
def student_login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        query = """
        SELECT *
        FROM students
        WHERE email = %s
        AND password = %s
        """

        cursor.execute(query, (email, password))

        student = cursor.fetchone()

        cursor.close()
        connection.close()

        if student:

            session["student_id"] = student["student_id"]
            session["student_name"] = student["student_name"]
            session["student_department"] = student["department"]
            session["student_semester"] = student["semester"]

            return redirect(url_for("student_dashboard"))

        flash("Invalid email or password.")

    return render_template("student_login.html")


# ==========================================================
# STUDENT DASHBOARD
# ==========================================================

@app.route("/student/dashboard")
def student_dashboard():

    if "student_id" not in session:
        return redirect(url_for("student_login"))

    return render_template(
        "student_dashboard.html",
        name=session["student_name"],
        department=session["student_department"],
        semester=session["student_semester"]
    )


# ==========================================================
# STUDENT TIMETABLE
# ==========================================================

@app.route("/student/timetable")
def student_timetable():

    # Student must be logged in
    if "student_id" not in session:
        return redirect(url_for("student_login"))

    connection = None
    cursor = None

    try:

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        department = session["student_department"]
        semester = session["student_semester"]

        query = """
            SELECT
                t.timetable_id,
                t.department,
                t.semester,
                t.day_name,
                t.time_slot,

                s.subject_name,

                f.faculty_name,

                r.room_no

            FROM timetable t

            JOIN subjects s
                ON t.subject_id = s.subject_id

            JOIN faculty f
                ON t.faculty_id = f.faculty_id

            JOIN classrooms r
                ON t.room_id = r.room_id

            WHERE t.department = %s
            AND t.semester = %s

            ORDER BY
                CASE t.day_name
                    WHEN 'Monday' THEN 1
                    WHEN 'Tuesday' THEN 2
                    WHEN 'Wednesday' THEN 3
                    WHEN 'Thursday' THEN 4
                    WHEN 'Friday' THEN 5
                    WHEN 'Saturday' THEN 6
                    ELSE 7
                END,

                t.time_slot
        """

        cursor.execute(
            query,
            (department, semester)
        )

        timetables = cursor.fetchall()

        return render_template(
            "student_timetable.html",
            timetables=timetables,
            department=department,
            semester=semester
        )

    except Exception as e:

        print("Student Timetable Error:", e)

        return "Error loading student timetable: " + str(e)

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()

# ==========================================================
# FACULTY LOGIN
# ==========================================================

@app.route("/faculty/login", methods=["GET", "POST"])
def faculty_login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        query = """
        SELECT *
        FROM faculty
        WHERE email = %s
        AND password = %s
        """

        cursor.execute(query, (email, password))

        faculty = cursor.fetchone()

        cursor.close()
        connection.close()

        if faculty:

            session["faculty_id"] = faculty["faculty_id"]
            session["faculty_name"] = faculty["faculty_name"]
            session["faculty_department"] = faculty["department"]

            return redirect(url_for("faculty_dashboard"))

        flash("Invalid email or password.")

    return render_template("faculty_login.html")


# ==========================================================
# FACULTY DASHBOARD
# ==========================================================

@app.route("/faculty/dashboard")
def faculty_dashboard():

    if "faculty_id" not in session:
        return redirect(url_for("faculty_login"))

    return render_template(
        "faculty_dashboard.html",
        name=session["faculty_name"],
        department=session["faculty_department"]
    )


# ==========================================================
# ADD TIMETABLE
# ==========================================================

@app.route("/faculty/add-timetable", methods=["GET", "POST"])
def add_timetable():

    if "faculty_id" not in session:
        return redirect(url_for("faculty_login"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Get subjects
    cursor.execute("SELECT * FROM subjects")
    subjects = cursor.fetchall()

    # Get classrooms
    cursor.execute("SELECT * FROM classrooms")
    classrooms = cursor.fetchall()

    # Get ONLY the logged-in faculty
    cursor.execute("""
        SELECT faculty_id, faculty_name, department
        FROM faculty
        WHERE faculty_id = %s
    """, (session["faculty_id"],))
    faculties = cursor.fetchall()

    if request.method == "POST":

        subject_id = request.form["subject_id"]
        faculty_id = session["faculty_id"]
        room_id = request.form["room_id"]

        department = request.form["department"]
        semester = request.form["semester"]

        day_name = request.form["day_name"]
        time_slot = request.form["time_slot"]

        # Make sure the selected subject belongs to the selected semester.
        cursor.execute("""
            SELECT subject_id
            FROM subjects
            WHERE subject_id = %s
            AND semester = %s
        """, (subject_id, semester))

        valid_subject = cursor.fetchone()

        if not valid_subject:
            cursor.close()
            connection.close()
            flash("Please select a subject from the selected semester.")
            return redirect(url_for("add_timetable"))

        # ------------------------------------------
        # FACULTY CLASH
        # ------------------------------------------

        cursor.execute(
            """
            SELECT timetable_id
            FROM timetable
            WHERE faculty_id = %s
            AND day_name = %s
            AND time_slot = %s
            """,
            (faculty_id, day_name, time_slot)
        )

        faculty_clash = cursor.fetchone()

        if faculty_clash:

            cursor.close()
            connection.close()

            flash("Clash detected: Faculty already has a lecture at this time.")

            return redirect(url_for("add_timetable"))

        # ------------------------------------------
        # ROOM CLASH
        # ------------------------------------------

        cursor.execute(
            """
            SELECT timetable_id
            FROM timetable
            WHERE room_id = %s
            AND day_name = %s
            AND time_slot = %s
            """,
            (room_id, day_name, time_slot)
        )

        room_clash = cursor.fetchone()

        if room_clash:

            cursor.close()
            connection.close()

            flash("Clash detected: Classroom is already occupied.")

            return redirect(url_for("add_timetable"))

        # ------------------------------------------
        # DUPLICATE CLASS
        # ------------------------------------------

        cursor.execute(
            """
            SELECT timetable_id
            FROM timetable
            WHERE department = %s
            AND semester = %s
            AND day_name = %s
            AND time_slot = %s
            """,
            (
                department,
                semester,
                day_name,
                time_slot
            )
        )

        class_clash = cursor.fetchone()

        if class_clash:

            cursor.close()
            connection.close()

            flash("This class already has a lecture at this time.")

            return redirect(url_for("add_timetable"))

        # ------------------------------------------
        # INSERT
        # ------------------------------------------

        query = """
        INSERT INTO timetable
        (
            subject_id,
            faculty_id,
            room_id,
            department,
            semester,
            day_name,
            time_slot
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """

        cursor.execute(
            query,
            (
                subject_id,
                faculty_id,
                room_id,
                department,
                semester,
                day_name,
                time_slot
            )
        )

        connection.commit()

        # Notification
            # Create notification for the correct department and semester
        message = f"New timetable lecture added on {day_name} at {time_slot}."

        cursor.execute("""
            INSERT INTO notifications
            (message, department, semester)
            VALUES (%s, %s, %s)
        """, (
            message,
            department,
            semester
        ))

        connection.commit()

        cursor.close()
        connection.close()

        flash("Timetable added successfully.")

        return redirect(url_for("faculty_timetable"))

    # GET request: show the timetable form.
    cursor.close()
    connection.close()

    return render_template(
        "add_timetable.html",
        subjects=subjects,
        classrooms=classrooms,
        faculties=faculties
    )

# ==========================================================
# VIEW TIMETABLE
# ==========================================================

@app.route("/timetable")
def view_timetable():

    department = request.args.get("department", "")
    semester = request.args.get("semester", "")

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    query = """
    SELECT
        timetable.timetable_id,
        timetable.department,
        timetable.semester,
        timetable.day_name,
        timetable.time_slot,

        subjects.subject_name,

        faculty.faculty_name,

        classrooms.room_no

    FROM timetable

    JOIN subjects
    ON timetable.subject_id = subjects.subject_id

    JOIN faculty
    ON timetable.faculty_id = faculty.faculty_id

    JOIN classrooms
    ON timetable.room_id = classrooms.room_id

    WHERE 1=1
    """

    parameters = []

    if department:

        query += " AND timetable.department = %s"

        parameters.append(department)

    if semester:

        query += " AND timetable.semester = %s"

        parameters.append(semester)

    query += """
    ORDER BY
    CASE day_name
        WHEN 'Monday' THEN 1
        WHEN 'Tuesday' THEN 2
        WHEN 'Wednesday' THEN 3
        WHEN 'Thursday' THEN 4
        WHEN 'Friday' THEN 5
        WHEN 'Saturday' THEN 6
    END,
    time_slot
    """

    cursor.execute(query, parameters)

    timetables = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "view_timetable.html",
        timetables=timetables,
        department=department,
        semester=semester
    )


# ==========================================================
# FACULTY TIMETABLE
# ==========================================================

@app.route("/faculty/timetable")
def faculty_timetable():

    if "faculty_id" not in session:
        return redirect(url_for("faculty_login"))

    connection = None
    cursor = None

    try:

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                t.timetable_id,
                t.faculty_id,
                t.department,
                t.semester,
                t.day_name,
                t.time_slot,
                s.subject_name,
                f.faculty_name,
                r.room_no
            FROM timetable t
            JOIN subjects s
                ON t.subject_id = s.subject_id
            JOIN faculty f
                ON t.faculty_id = f.faculty_id
            JOIN classrooms r
                ON t.room_id = r.room_id
            WHERE t.faculty_id = %s
            ORDER BY
                CASE t.day_name
                    WHEN 'Monday' THEN 1
                    WHEN 'Tuesday' THEN 2
                    WHEN 'Wednesday' THEN 3
                    WHEN 'Thursday' THEN 4
                    WHEN 'Friday' THEN 5
                    WHEN 'Saturday' THEN 6
                    ELSE 7
                END,
                t.time_slot
        """, (session["faculty_id"],))

        timetables = cursor.fetchall()

        return render_template(
            "faculty_timetable.html",
            timetables=timetables
        )

    except Exception as e:

        print("Faculty Timetable Error:", e)

        return "Error loading timetable: " + str(e)

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ==========================================================
# DELETE TIMETABLE
# ==========================================================

@app.route("/notifications")
def notifications():

    connection = None
    cursor = None

    try:

        # Automatically remove notifications older than 24 hours
        cleanup_connection = get_db_connection()
        cleanup_cursor = cleanup_connection.cursor()

        cleanup_cursor.execute("""
            DELETE FROM notifications
            WHERE created_at < (NOW() - INTERVAL 24 HOUR)
        """)

        cleanup_connection.commit()
        cleanup_cursor.close()
        cleanup_connection.close()

        # Now connect for loading notifications
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # STUDENT: show only their department + semester notifications
        if "student_id" in session:

            department = session["student_department"]
            semester = session["student_semester"]

            cursor.execute("""
                SELECT notification_id, message, created_at
                FROM notifications
                WHERE department = %s
                AND semester = %s
                ORDER BY created_at DESC
            """, (department, semester))

        # FACULTY: show all notifications
        elif "faculty_id" in session:

            cursor.execute("""
                SELECT
                    notification_id,
                    message,
                    created_at,
                    department,
                    semester
                FROM notifications
                ORDER BY created_at DESC
            """)

        else:
            return redirect(url_for("home"))

        notification_list = cursor.fetchall()

        return render_template(
            "notifications.html",
            notifications=notification_list
        )

    except Exception as e:

        print("Notification Error:", e)

        return "Error loading notifications: " + str(e)

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()

@app.route("/delete-timetable/<int:timetable_id>")
def delete_timetable(timetable_id):

    # Make sure faculty is logged in
    if "faculty_id" not in session:
        return redirect(url_for("faculty_login"))

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Get the timetable AND check which faculty owns it
        cursor.execute("""
            SELECT
                t.timetable_id,
                t.faculty_id,
                t.department,
                t.semester,
                t.day_name,
                t.time_slot,
                s.subject_name,
                f.faculty_name,
                r.room_no
            FROM timetable t
            JOIN subjects s
                ON t.subject_id = s.subject_id
            JOIN faculty f
                ON t.faculty_id = f.faculty_id
            JOIN classrooms r
                ON t.room_id = r.room_id
            WHERE t.timetable_id = %s
        """, (timetable_id,))

        timetable = cursor.fetchone()

        # Timetable does not exist
        if not timetable:
            return "Timetable not found."

        # IMPORTANT:
        # Check whether this timetable belongs to the logged-in faculty
        if timetable["faculty_id"] != session["faculty_id"]:

            return """
            <h2>Access Denied</h2>
            <p>You can only delete your own timetable.</p>
            <a href="/faculty/timetable">Back to Timetable</a>
            """

        # Create notification for the same department and semester
        # as the timetable being deleted.
        message = (
            f"Timetable cancelled: "
            f"{timetable['subject_name']} on "
            f"{timetable['day_name']} at "
            f"{timetable['time_slot']}, "
            f"Room {timetable['room_no']}. "
            f"Faculty: {timetable['faculty_name']}."
        )

        cursor.execute("""
            INSERT INTO notifications
            (message, department, semester)
            VALUES (%s, %s, %s)
        """, (
            message,
            timetable["department"],
            timetable["semester"]
        ))

        # Delete ONLY this faculty's timetable
        cursor.execute("""
            DELETE FROM timetable
            WHERE timetable_id = %s
            AND faculty_id = %s
        """, (
            timetable_id,
            session["faculty_id"]
        ))

        connection.commit()

        return redirect(url_for("faculty_timetable"))

    except Exception as e:

        if connection:
            connection.rollback()

        print("Delete Timetable Error:", e)

        return "Error deleting timetable: " + str(e)

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()

            # ==========================================================
# STUDENT DOWNLOAD TIMETABLE PDF
# ==========================================================

@app.route("/student/download-pdf")
def student_download_pdf():

    # Student must be logged in
    if "student_id" not in session:
        return redirect(url_for("student_login"))

    connection = None
    cursor = None

    try:

        # Get student's department and semester
        department = session["student_department"]
        semester = session["student_semester"]

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Get only this student's timetable
        query = """
            SELECT
                t.day_name,
                t.time_slot,
                s.subject_name,
                f.faculty_name,
                r.room_no

            FROM timetable t

            JOIN subjects s
                ON t.subject_id = s.subject_id

            JOIN faculty f
                ON t.faculty_id = f.faculty_id

            JOIN classrooms r
                ON t.room_id = r.room_id

            WHERE t.department = %s
            AND t.semester = %s

            ORDER BY
                CASE t.day_name
                    WHEN 'Monday' THEN 1
                    WHEN 'Tuesday' THEN 2
                    WHEN 'Wednesday' THEN 3
                    WHEN 'Thursday' THEN 4
                    WHEN 'Friday' THEN 5
                    WHEN 'Saturday' THEN 6
                    ELSE 7
                END,
                t.time_slot
        """

        cursor.execute(
            query,
            (department, semester)
        )

        data = cursor.fetchall()

        # Create PDF folder
        os.makedirs("generated_pdfs", exist_ok=True)

        # Safe filename
        filename = (
            f"generated_pdfs/"
            f"Student_Timetable_{department}_{semester}.pdf"
        )

        # Create PDF
        document = SimpleDocTemplate(
            filename,
            pagesize=A4
        )

        # PDF title information
        table_data = [
            [
                "Day",
                "Time",
                "Subject",
                "Faculty",
                "Room"
            ]
        ]

        # Add timetable rows
        for row in data:

            table_data.append(
                [
                    row["day_name"],
                    row["time_slot"],
                    row["subject_name"],
                    row["faculty_name"],
                    row["room_no"]
                ]
            )

        # If no timetable exists
        if len(table_data) == 1:

            table_data.append(
                [
                    "-",
                    "-",
                    "No timetable available",
                    "-",
                    "-"
                ]
            )

        # Create table
        table = Table(
            table_data,
            repeatRows=1
        )

        # Table styling
        table.setStyle(
            TableStyle(
                [

                    (
                        "BACKGROUND",
                        (0, 0),
                        (-1, 0),
                        colors.HexColor("#4f46e5")
                    ),

                    (
                        "TEXTCOLOR",
                        (0, 0),
                        (-1, 0),
                        colors.white
                    ),

                    (
                        "FONTNAME",
                        (0, 0),
                        (-1, 0),
                        "Helvetica-Bold"
                    ),

                    (
                        "GRID",
                        (0, 0),
                        (-1, -1),
                        0.5,
                        colors.grey
                    ),

                    (
                        "ALIGN",
                        (0, 0),
                        (-1, -1),
                        "CENTER"
                    ),

                    (
                        "VALIGN",
                        (0, 0),
                        (-1, -1),
                        "MIDDLE"
                    ),

                    (
                        "TOPPADDING",
                        (0, 0),
                        (-1, -1),
                        8
                    ),

                    (
                        "BOTTOMPADDING",
                        (0, 0),
                        (-1, -1),
                        8
                    ),

                ]
            )
        )

        # Build PDF
        document.build([table])

        # Send PDF to browser
        return send_file(
            filename,
            as_attachment=True,
            download_name="My_Timetable.pdf"
        )

    except Exception as e:

        print("Student PDF Error:", e)

        return "Error generating PDF: " + str(e)

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ==========================================================
# FACULTY DOWNLOAD TIMETABLE PDF
# ==========================================================

@app.route("/faculty/download-pdf")
def faculty_download_pdf():

    # Faculty must be logged in
    if "faculty_id" not in session:
        return redirect(url_for("faculty_login"))

    connection = None
    cursor = None

    try:

        faculty_id = session["faculty_id"]

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Get ONLY the logged-in faculty's timetable
        cursor.execute("""
            SELECT
                t.day_name,
                t.time_slot,
                s.subject_name,
                f.faculty_name,
                r.room_no,
                t.department,
                t.semester

            FROM timetable t

            JOIN subjects s
                ON t.subject_id = s.subject_id

            JOIN faculty f
                ON t.faculty_id = f.faculty_id

            JOIN classrooms r
                ON t.room_id = r.room_id

            WHERE t.faculty_id = %s

            ORDER BY
                CASE t.day_name
                    WHEN 'Monday' THEN 1
                    WHEN 'Tuesday' THEN 2
                    WHEN 'Wednesday' THEN 3
                    WHEN 'Thursday' THEN 4
                    WHEN 'Friday' THEN 5
                    WHEN 'Saturday' THEN 6
                    ELSE 7
                END,
                t.time_slot
        """, (faculty_id,))

        data = cursor.fetchall()

        # --------------------------------------------------
        # Check if faculty has timetable
        # --------------------------------------------------

        if not data:
            return """
            <h2>No Timetable Available</h2>
            <p>You do not have any timetable entries yet.</p>
            <a href="/faculty/timetable">
                Back to Faculty Timetable
            </a>
            """

        # --------------------------------------------------
        # Get faculty name
        # --------------------------------------------------

        faculty_name = data[0]["faculty_name"]

        # --------------------------------------------------
        # Create PDF folder
        # --------------------------------------------------

        os.makedirs("generated_pdfs", exist_ok=True)

        filename = (
            f"generated_pdfs/"
            f"Faculty_Timetable_{faculty_id}.pdf"
        )

        # --------------------------------------------------
        # Create PDF
        # --------------------------------------------------

        document = SimpleDocTemplate(
            filename,
            pagesize=A4,
            rightMargin=30,
            leftMargin=30,
            topMargin=30,
            bottomMargin=30
        )

        # --------------------------------------------------
        # PDF table
        # --------------------------------------------------

        table_data = [
            [
                "Day",
                "Time",
                "Subject",
                "Faculty",
                "Room"
            ]
        ]

        # Add timetable rows
        for row in data:

            table_data.append(
                [
                    str(row["day_name"]),
                    str(row["time_slot"]),
                    str(row["subject_name"]),
                    str(row["faculty_name"]),
                    str(row["room_no"])
                ]
            )

        # --------------------------------------------------
        # Create table
        # --------------------------------------------------

        table = Table(
            table_data,
            colWidths=[
                75,
                105,
                145,
                110,
                55
            ],
            repeatRows=1
        )

        # --------------------------------------------------
        # Table styling
        # --------------------------------------------------

        table.setStyle(
            TableStyle(
                [

                    # Header
                    (
                        "BACKGROUND",
                        (0, 0),
                        (-1, 0),
                        colors.HexColor("#4f46e5")
                    ),

                    (
                        "TEXTCOLOR",
                        (0, 0),
                        (-1, 0),
                        colors.white
                    ),

                    (
                        "FONTNAME",
                        (0, 0),
                        (-1, 0),
                        "Helvetica-Bold"
                    ),

                    (
                        "FONTSIZE",
                        (0, 0),
                        (-1, 0),
                        10
                    ),

                    # Body
                    (
                        "FONTNAME",
                        (0, 1),
                        (-1, -1),
                        "Helvetica"
                    ),

                    (
                        "FONTSIZE",
                        (0, 1),
                        (-1, -1),
                        9
                    ),

                    # Grid
                    (
                        "GRID",
                        (0, 0),
                        (-1, -1),
                        0.5,
                        colors.grey
                    ),

                    # Alignment
                    (
                        "ALIGN",
                        (0, 0),
                        (-1, -1),
                        "CENTER"
                    ),

                    (
                        "VALIGN",
                        (0, 0),
                        (-1, -1),
                        "MIDDLE"
                    ),

                    # Padding
                    (
                        "TOPPADDING",
                        (0, 0),
                        (-1, -1),
                        8
                    ),

                    (
                        "BOTTOMPADDING",
                        (0, 0),
                        (-1, -1),
                        8
                    ),

                    (
                        "LEFTPADDING",
                        (0, 0),
                        (-1, -1),
                        5
                    ),

                    (
                        "RIGHTPADDING",
                        (0, 0),
                        (-1, -1),
                        5
                    ),

                ]
            )
        )

        # --------------------------------------------------
        # Build PDF
        # --------------------------------------------------

        document.build([table])

        # --------------------------------------------------
        # Download PDF
        # --------------------------------------------------

        return send_file(
            filename,
            as_attachment=True,
            download_name="Faculty_Timetable.pdf"
        )

    except Exception as e:

        print("Faculty PDF Error:", e)

        return "Error generating faculty PDF: " + str(e)

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ==========================================================
# LOGOUT
# ==========================================================

@app.route("/logout")
def logout():

    session.clear()
 
    return redirect(url_for("home"))


# ==========================================================
# FACULTY - VIEW ALL TIMETABLES
# ==========================================================

@app.route("/faculty/all-timetables")
def faculty_all_timetables():

    if "faculty_id" not in session:
        return redirect(url_for("faculty_login"))

    connection = None
    cursor = None

    try:

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                t.timetable_id,
                t.department,
                t.semester,
                t.day_name,
                t.time_slot,

                s.subject_name,

                f.faculty_name,

                r.room_no

            FROM timetable t

            JOIN subjects s
                ON t.subject_id = s.subject_id

            JOIN faculty f
                ON t.faculty_id = f.faculty_id

            JOIN classrooms r
                ON t.room_id = r.room_id

            ORDER BY
                CASE t.day_name
                    WHEN 'Monday' THEN 1
                    WHEN 'Tuesday' THEN 2
                    WHEN 'Wednesday' THEN 3
                    WHEN 'Thursday' THEN 4
                    WHEN 'Friday' THEN 5
                    WHEN 'Saturday' THEN 6
                    ELSE 7
                END,

                t.time_slot
        """)

        timetables = cursor.fetchall()

        return render_template(
            "faculty_all_timetables.html",
            timetables=timetables
        )

    except Exception as e:

        print("Faculty All Timetable Error:", e)

        return "Error loading all timetables: " + str(e)

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()

            # ==========================================================
# FACULTY - DOWNLOAD ALL TIMETABLES PDF
# ==========================================================

@app.route("/faculty/download-all-pdf")
def faculty_download_all_pdf():

    if "faculty_id" not in session:
        return redirect(url_for("faculty_login"))

    connection = None
    cursor = None

    try:

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                t.day_name,
                t.time_slot,
                s.subject_name,
                f.faculty_name,
                r.room_no,
                t.department,
                t.semester

            FROM timetable t

            JOIN subjects s
                ON t.subject_id = s.subject_id

            JOIN faculty f
                ON t.faculty_id = f.faculty_id

            JOIN classrooms r
                ON t.room_id = r.room_id

            ORDER BY
                CASE t.day_name
                    WHEN 'Monday' THEN 1
                    WHEN 'Tuesday' THEN 2
                    WHEN 'Wednesday' THEN 3
                    WHEN 'Thursday' THEN 4
                    WHEN 'Friday' THEN 5
                    WHEN 'Saturday' THEN 6
                    ELSE 7
                END,

                t.time_slot
        """)

        data = cursor.fetchall()

        # --------------------------------------------------
        # PDF IMPORTS
        # --------------------------------------------------

        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.platypus import (
            SimpleDocTemplate,
            Table,
            TableStyle,
            Paragraph,
            Spacer
        )
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet
        import os

        # --------------------------------------------------
        # CREATE PDF FOLDER
        # --------------------------------------------------

        os.makedirs("generated_pdfs", exist_ok=True)

        filename = "generated_pdfs/Faculty_All_Timetables.pdf"

        # Landscape gives more space for columns
        document = SimpleDocTemplate(
            filename,
            pagesize=landscape(A4),
            rightMargin=25,
            leftMargin=25,
            topMargin=25,
            bottomMargin=25
        )

        styles = getSampleStyleSheet()

        elements = []

        # --------------------------------------------------
        # TITLE
        # --------------------------------------------------

        elements.append(
            Paragraph(
                "College All Timetables",
                styles["Title"]
            )
        )

        elements.append(
            Paragraph(
                "Online Smart Schedule",
                styles["Heading2"]
            )
        )

        elements.append(Spacer(1, 15))

        # --------------------------------------------------
        # TABLE HEADER
        # --------------------------------------------------

        table_data = [
            [
                "Department",
                "Semester",
                "Day",
                "Time",
                "Subject",
                "Faculty",
                "Room"
            ]
        ]

        # --------------------------------------------------
        # ADD DATA
        # --------------------------------------------------

        for row in data:

            table_data.append([
                row["department"],
                row["semester"],
                row["day_name"],
                row["time_slot"],
                row["subject_name"],
                row["faculty_name"],
                row["room_no"]
            ])

        # --------------------------------------------------
        # NO DATA
        # --------------------------------------------------

        if len(table_data) == 1:

            table_data.append([
                "-",
                "-",
                "-",
                "-",
                "No timetable available",
                "-",
                "-"
            ])

        # --------------------------------------------------
        # CREATE TABLE
        # --------------------------------------------------

        table = Table(
            table_data,
            repeatRows=1,
            colWidths=[
                75,
                55,
                65,
                90,
                130,
                110,
                55
            ]
        )

        # --------------------------------------------------
        # TABLE STYLE
        # --------------------------------------------------

        table.setStyle(
            TableStyle([

                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor("#4f46e5")
                ),

                (
                    "TEXTCOLOR",
                    (0, 0),
                    (-1, 0),
                    colors.white
                ),

                (
                    "FONTNAME",
                    (0, 0),
                    (-1, 0),
                    "Helvetica-Bold"
                ),

                (
                    "FONTSIZE",
                    (0, 0),
                    (-1, -1),
                    8
                ),

                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.grey
                ),

                (
                    "ALIGN",
                    (0, 0),
                    (-1, -1),
                    "CENTER"
                ),

                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "MIDDLE"
                ),

                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    7
                ),

                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    7
                )

            ])
        )

        # --------------------------------------------------
        # BUILD PDF
        # --------------------------------------------------

        elements.append(table)

        document.build(elements)

        # --------------------------------------------------
        # DOWNLOAD
        # --------------------------------------------------

        return send_file(
            filename,
            as_attachment=True,
            download_name="Faculty_All_Timetables.pdf"
        )

    except Exception as e:

        print("Faculty All PDF Error:", e)

        return "Error generating PDF: " + str(e)

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()
  
# ==========================================================
# RUN APPLICATION
# ==========================================================


if __name__ == "__main__":
    app.run(debug=True)