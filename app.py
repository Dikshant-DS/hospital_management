from datetime import datetime, timedelta
import os
import random
import sqlite3

from flask import Flask, abort, flash, jsonify, redirect, render_template, request, url_for


app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "hospital_secret_key_2024")
DB_PATH = os.path.join(os.path.dirname(__file__), "hospital.db")

PATIENT_STATUSES = {"Active", "Discharged"}
DOCTOR_AVAILABILITY = {"Available", "Busy", "On Leave"}
APPOINTMENT_STATUSES = {"Scheduled", "Completed", "Cancelled"}
BILLING_STATUSES = {"Pending", "Paid"}
BILLING_PARTIES = {"Patient", "Professor"}


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def today():
    return datetime.now().strftime("%Y-%m-%d")


def clean_text(value, default=""):
    return (value or default).strip()


def parse_int(value, default=0, minimum=None, maximum=None):
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    if minimum is not None and number < minimum:
        number = minimum
    if maximum is not None and number > maximum:
        number = maximum
    return number


def parse_float(value, default=0.0, minimum=None):
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default
    if minimum is not None and number < minimum:
        number = minimum
    return round(number, 2)


def valid_date(value):
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return value
    except (TypeError, ValueError):
        return today()


@app.context_processor
def inject_common_values():
    try:
        conn = get_db()
        low_stock = conn.execute(
            "SELECT COUNT(*) FROM medicines WHERE stock <= min_stock"
        ).fetchone()[0]
        conn.close()
    except sqlite3.Error:
        low_stock = 0
    return {"nav_stats": {"low_stock": low_stock}, "today": today()}


def init_db():
    conn = get_db()
    c = conn.cursor()

    c.executescript(
        """
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            age INTEGER,
            gender TEXT,
            blood_group TEXT,
            phone TEXT,
            email TEXT,
            address TEXT,
            admitted_date TEXT,
            status TEXT DEFAULT 'Active',
            ward TEXT,
            doctor_id INTEGER,
            FOREIGN KEY(doctor_id) REFERENCES doctors(id)
        );

        CREATE TABLE IF NOT EXISTS doctors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            specialization TEXT,
            phone TEXT,
            email TEXT,
            experience INTEGER,
            status TEXT DEFAULT 'Active',
            availability TEXT DEFAULT 'Available'
        );

        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER,
            doctor_id INTEGER,
            date TEXT,
            time TEXT,
            reason TEXT,
            status TEXT DEFAULT 'Scheduled',
            notes TEXT,
            FOREIGN KEY(patient_id) REFERENCES patients(id),
            FOREIGN KEY(doctor_id) REFERENCES doctors(id)
        );

        CREATE TABLE IF NOT EXISTS medicines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT,
            stock INTEGER DEFAULT 0,
            price REAL,
            supplier TEXT,
            expiry_date TEXT,
            min_stock INTEGER DEFAULT 10
        );

        CREATE TABLE IF NOT EXISTS billing (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER,
            bill_to TEXT DEFAULT 'Patient',
            professor_name TEXT,
            professor_department TEXT,
            amount REAL,
            description TEXT,
            date TEXT,
            status TEXT DEFAULT 'Pending',
            FOREIGN KEY(patient_id) REFERENCES patients(id)
        );
        """
    )

    billing_columns = {
        row["name"] for row in c.execute("PRAGMA table_info(billing)").fetchall()
    }
    billing_migrations = {
        "bill_to": "ALTER TABLE billing ADD COLUMN bill_to TEXT DEFAULT 'Patient'",
        "professor_name": "ALTER TABLE billing ADD COLUMN professor_name TEXT",
        "professor_department": "ALTER TABLE billing ADD COLUMN professor_department TEXT",
    }
    for column, statement in billing_migrations.items():
        if column not in billing_columns:
            c.execute(statement)

    if c.execute("SELECT COUNT(*) FROM doctors").fetchone()[0] == 0:
        doctors = [
            ("Dr. Sarah Johnson", "Cardiology", "555-0101", "sarah@hospital.com", 12, "Active", "Available"),
            ("Dr. Michael Chen", "Neurology", "555-0102", "michael@hospital.com", 8, "Active", "Available"),
            ("Dr. Emily Davis", "Pediatrics", "555-0103", "emily@hospital.com", 15, "Active", "Busy"),
            ("Dr. Robert Wilson", "Orthopedics", "555-0104", "robert@hospital.com", 20, "Active", "Available"),
            ("Dr. Priya Patel", "Dermatology", "555-0105", "priya@hospital.com", 6, "Active", "Available"),
            ("Dr. James Lee", "General Medicine", "555-0106", "james@hospital.com", 10, "Active", "On Leave"),
        ]
        c.executemany(
            "INSERT INTO doctors (name,specialization,phone,email,experience,status,availability) VALUES (?,?,?,?,?,?,?)",
            doctors,
        )

    if c.execute("SELECT COUNT(*) FROM patients").fetchone()[0] == 0:
        random.seed(42)
        names = [
            "Alice Brown", "Bob Martinez", "Carol White", "David Kim", "Emma Taylor",
            "Frank Moore", "Grace Anderson", "Henry Thomas", "Iris Jackson", "Jack Harris",
            "Karen Clark", "Liam Lewis", "Mia Robinson", "Noah Walker", "Olivia Hall",
        ]
        wards = ["General", "ICU", "Pediatric", "Cardiac", "Orthopedic"]
        blood_groups = ["A+", "A-", "B+", "B-", "O+", "O-", "AB+", "AB-"]
        statuses = ["Active", "Active", "Active", "Discharged", "Active"]
        for i, name in enumerate(names):
            admitted = (datetime.now() - timedelta(days=random.randint(1, 30))).strftime("%Y-%m-%d")
            c.execute(
                """
                INSERT INTO patients
                    (name,age,gender,blood_group,phone,email,address,admitted_date,status,ward,doctor_id)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    name,
                    random.randint(18, 80),
                    random.choice(["Male", "Female"]),
                    random.choice(blood_groups),
                    f"555-{1000 + i}",
                    f"{name.lower().replace(' ', '.')}@email.com",
                    f"{i + 1} Main Street",
                    admitted,
                    random.choice(statuses),
                    random.choice(wards),
                    random.randint(1, 6),
                ),
            )

    if c.execute("SELECT COUNT(*) FROM appointments").fetchone()[0] == 0:
        reasons = ["Routine Checkup", "Follow-up", "Emergency", "Consultation", "Lab Results"]
        statuses = ["Scheduled", "Completed", "Cancelled", "Scheduled", "Completed"]
        times = ["09:00", "10:00", "11:00", "14:00", "15:00", "16:00"]
        for _ in range(20):
            date = (datetime.now() + timedelta(days=random.randint(-5, 10))).strftime("%Y-%m-%d")
            c.execute(
                "INSERT INTO appointments (patient_id,doctor_id,date,time,reason,status) VALUES (?,?,?,?,?,?)",
                (random.randint(1, 15), random.randint(1, 6), date, random.choice(times), random.choice(reasons), random.choice(statuses)),
            )

    if c.execute("SELECT COUNT(*) FROM medicines").fetchone()[0] == 0:
        medicines = [
            ("Paracetamol", "Analgesic", 500, 2.5, "PharmaCorp", "2026-12-01", 50),
            ("Amoxicillin", "Antibiotic", 200, 8.0, "MedSupply", "2026-06-01", 30),
            ("Ibuprofen", "Anti-inflammatory", 350, 3.5, "PharmaCorp", "2026-08-01", 40),
            ("Metformin", "Antidiabetic", 150, 5.0, "HealthMed", "2026-03-01", 20),
            ("Lisinopril", "Antihypertensive", 80, 12.0, "CardioMed", "2026-09-01", 25),
            ("Atorvastatin", "Statin", 120, 15.0, "PharmaCorp", "2027-01-01", 30),
            ("Omeprazole", "Antacid", 400, 4.0, "GastroMed", "2026-11-01", 50),
            ("Cetirizine", "Antihistamine", 600, 3.0, "AllergyMed", "2027-03-01", 60),
        ]
        c.executemany(
            "INSERT INTO medicines (name,category,stock,price,supplier,expiry_date,min_stock) VALUES (?,?,?,?,?,?,?)",
            medicines,
        )

    if c.execute("SELECT COUNT(*) FROM billing").fetchone()[0] == 0:
        descriptions = ["Consultation Fee", "Lab Tests", "X-Ray", "Surgery", "Medicine", "Room Charges"]
        statuses = ["Paid", "Pending", "Paid", "Pending"]
        for _ in range(25):
            date = (datetime.now() - timedelta(days=random.randint(0, 30))).strftime("%Y-%m-%d")
            c.execute(
                "INSERT INTO billing (patient_id,amount,description,date,status) VALUES (?,?,?,?,?)",
                (random.randint(1, 15), round(random.uniform(50, 2000), 2), random.choice(descriptions), date, random.choice(statuses)),
            )

    conn.commit()
    conn.close()


@app.route("/")
def index():
    conn = get_db()
    stats = {
        "total_patients": conn.execute("SELECT COUNT(*) FROM patients").fetchone()[0],
        "active_patients": conn.execute("SELECT COUNT(*) FROM patients WHERE status='Active'").fetchone()[0],
        "total_doctors": conn.execute("SELECT COUNT(*) FROM doctors WHERE status='Active'").fetchone()[0],
        "available_doctors": conn.execute("SELECT COUNT(*) FROM doctors WHERE status='Active' AND availability='Available'").fetchone()[0],
        "today_appointments": conn.execute("SELECT COUNT(*) FROM appointments WHERE date=?", (today(),)).fetchone()[0],
        "pending_bills": conn.execute("SELECT COUNT(*) FROM billing WHERE status='Pending'").fetchone()[0],
        "low_stock": conn.execute("SELECT COUNT(*) FROM medicines WHERE stock <= min_stock").fetchone()[0],
        "total_revenue": conn.execute("SELECT COALESCE(SUM(amount),0) FROM billing WHERE status='Paid'").fetchone()[0],
        "pending_amount": conn.execute("SELECT COALESCE(SUM(amount),0) FROM billing WHERE status='Pending'").fetchone()[0],
    }

    dept_data = conn.execute(
        """
        SELECT d.specialization, COUNT(p.id) as count
        FROM doctors d
        LEFT JOIN patients p ON d.id=p.doctor_id AND p.status='Active'
        WHERE d.status='Active'
        GROUP BY d.specialization
        ORDER BY count DESC, d.specialization
        """
    ).fetchall()
    max_dept_count = max([row["count"] for row in dept_data] or [1])

    recent_patients = conn.execute(
        """
        SELECT p.*, d.name as doctor_name
        FROM patients p
        LEFT JOIN doctors d ON p.doctor_id=d.id
        ORDER BY p.id DESC LIMIT 5
        """
    ).fetchall()

    upcoming_apts = conn.execute(
        """
        SELECT a.*, p.name as patient_name, d.name as doctor_name
        FROM appointments a
        JOIN patients p ON a.patient_id=p.id
        JOIN doctors d ON a.doctor_id=d.id
        WHERE a.date >= ? AND a.status='Scheduled'
        ORDER BY a.date, a.time LIMIT 5
        """,
        (today(),),
    ).fetchall()

    conn.close()
    return render_template(
        "index.html",
        stats=stats,
        dept_data=dept_data,
        max_dept_count=max_dept_count,
        recent_patients=recent_patients,
        upcoming_apts=upcoming_apts,
    )


@app.route("/patients")
def patients():
    conn = get_db()
    search = request.args.get("search", "")
    status_filter = request.args.get("status", "")
    query = """
        SELECT p.*, d.name as doctor_name
        FROM patients p
        LEFT JOIN doctors d ON p.doctor_id=d.id
        WHERE 1=1
    """
    params = []
    if search:
        query += " AND (p.name LIKE ? OR p.phone LIKE ? OR p.blood_group LIKE ?)"
        params += [f"%{search}%", f"%{search}%", f"%{search}%"]
    if status_filter in PATIENT_STATUSES:
        query += " AND p.status=?"
        params.append(status_filter)
    query += " ORDER BY p.id DESC"
    rows = conn.execute(query, params).fetchall()
    doctors = conn.execute("SELECT * FROM doctors WHERE status='Active' ORDER BY name").fetchall()
    conn.close()
    return render_template("patients.html", patients=rows, doctors=doctors, search=search, status_filter=status_filter)


@app.route("/patients/add", methods=["POST"])
def add_patient():
    d = request.form
    name = clean_text(d.get("name"))
    phone = clean_text(d.get("phone"))
    status = d.get("status", "Active")
    if not name or not phone or status not in PATIENT_STATUSES:
        flash("Please enter a valid patient name, phone, and status.", "error")
        return redirect(url_for("patients"))

    conn = get_db()
    conn.execute(
        """
        INSERT INTO patients
            (name,age,gender,blood_group,phone,email,address,admitted_date,status,ward,doctor_id)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            name,
            parse_int(d.get("age"), minimum=0, maximum=150),
            d.get("gender", "Other"),
            d.get("blood_group", "O+"),
            phone,
            clean_text(d.get("email")),
            clean_text(d.get("address")),
            valid_date(d.get("admitted_date")),
            status,
            d.get("ward", "General"),
            d.get("doctor_id") or None,
        ),
    )
    conn.commit()
    conn.close()
    flash("Patient added successfully!", "success")
    return redirect(url_for("patients"))


@app.route("/patients/edit/<int:pid>", methods=["POST"])
def edit_patient(pid):
    d = request.form
    name = clean_text(d.get("name"))
    status = d.get("status", "Active")
    if not name or status not in PATIENT_STATUSES:
        flash("Please enter a valid patient name and status.", "error")
        return redirect(url_for("patients"))

    conn = get_db()
    conn.execute(
        """
        UPDATE patients
        SET name=?, age=?, gender=?, blood_group=?, phone=?, email=?, address=?,
            admitted_date=?, status=?, ward=?, doctor_id=?
        WHERE id=?
        """,
        (
            name,
            parse_int(d.get("age"), minimum=0, maximum=150),
            d.get("gender", "Other"),
            d.get("blood_group", "O+"),
            clean_text(d.get("phone")),
            clean_text(d.get("email")),
            clean_text(d.get("address")),
            valid_date(d.get("admitted_date")),
            status,
            d.get("ward", "General"),
            d.get("doctor_id") or None,
            pid,
        ),
    )
    conn.commit()
    conn.close()
    flash("Patient updated successfully!", "success")
    return redirect(url_for("patients"))


@app.route("/patients/delete/<int:pid>", methods=["POST"])
def delete_patient(pid):
    conn = get_db()
    linked = conn.execute(
        """
        SELECT
            (SELECT COUNT(*) FROM appointments WHERE patient_id=?) +
            (SELECT COUNT(*) FROM billing WHERE patient_id=?)
        """,
        (pid, pid),
    ).fetchone()[0]
    if linked:
        conn.execute("UPDATE patients SET status='Discharged' WHERE id=?", (pid,))
        flash("Patient has history, so the record was marked discharged instead of deleted.", "warning")
    else:
        conn.execute("DELETE FROM patients WHERE id=?", (pid,))
        flash("Patient deleted.", "warning")
    conn.commit()
    conn.close()
    return redirect(url_for("patients"))


@app.route("/patients/discharge/<int:pid>", methods=["POST"])
def discharge_patient(pid):
    conn = get_db()
    conn.execute("UPDATE patients SET status='Discharged' WHERE id=?", (pid,))
    conn.commit()
    conn.close()
    flash("Patient marked as discharged.", "success")
    return redirect(url_for("patients"))


@app.route("/doctors")
def doctors():
    conn = get_db()
    rows = conn.execute(
        """
        SELECT d.*, COUNT(p.id) as patient_count
        FROM doctors d
        LEFT JOIN patients p ON d.id=p.doctor_id AND p.status='Active'
        WHERE d.status='Active'
        GROUP BY d.id
        ORDER BY d.id DESC
        """
    ).fetchall()
    conn.close()
    return render_template("doctors.html", doctors=rows)


@app.route("/doctors/add", methods=["POST"])
def add_doctor():
    d = request.form
    name = clean_text(d.get("name"))
    specialization = clean_text(d.get("specialization"))
    availability = d.get("availability", "Available")
    if not name or not specialization or availability not in DOCTOR_AVAILABILITY:
        flash("Please enter valid doctor details.", "error")
        return redirect(url_for("doctors"))

    conn = get_db()
    conn.execute(
        "INSERT INTO doctors (name,specialization,phone,email,experience,status,availability) VALUES (?,?,?,?,?,?,?)",
        (
            name,
            specialization,
            clean_text(d.get("phone")),
            clean_text(d.get("email")),
            parse_int(d.get("experience"), minimum=0, maximum=60),
            "Active",
            availability,
        ),
    )
    conn.commit()
    conn.close()
    flash("Doctor added successfully!", "success")
    return redirect(url_for("doctors"))


@app.route("/doctors/delete/<int:did>", methods=["POST"])
def delete_doctor(did):
    conn = get_db()
    linked = conn.execute(
        """
        SELECT
            (SELECT COUNT(*) FROM patients WHERE doctor_id=? AND status='Active') +
            (SELECT COUNT(*) FROM appointments WHERE doctor_id=? AND status='Scheduled')
        """,
        (did, did),
    ).fetchone()[0]
    if linked:
        conn.execute("UPDATE doctors SET status='Inactive', availability='On Leave' WHERE id=?", (did,))
        flash("Doctor has active responsibilities, so the profile was deactivated instead of removed.", "warning")
    else:
        conn.execute("DELETE FROM doctors WHERE id=?", (did,))
        flash("Doctor removed.", "warning")
    conn.commit()
    conn.close()
    return redirect(url_for("doctors"))


@app.route("/appointments")
def appointments():
    conn = get_db()
    rows = conn.execute(
        """
        SELECT a.*, p.name as patient_name, d.name as doctor_name
        FROM appointments a
        JOIN patients p ON a.patient_id=p.id
        JOIN doctors d ON a.doctor_id=d.id
        ORDER BY a.date DESC, a.time DESC
        """
    ).fetchall()
    patient_rows = conn.execute("SELECT * FROM patients WHERE status='Active' ORDER BY name").fetchall()
    doctor_rows = conn.execute(
        "SELECT * FROM doctors WHERE status='Active' AND availability!='On Leave' ORDER BY name"
    ).fetchall()
    conn.close()
    return render_template("appointments.html", appointments=rows, patients=patient_rows, doctors=doctor_rows)


@app.route("/appointments/add", methods=["POST"])
def add_appointment():
    d = request.form
    patient_id = parse_int(d.get("patient_id"), minimum=1)
    doctor_id = parse_int(d.get("doctor_id"), minimum=1)
    apt_date = valid_date(d.get("date"))
    apt_time = clean_text(d.get("time"))
    reason = clean_text(d.get("reason"))
    if not patient_id or not doctor_id or not apt_time or not reason:
        flash("Please complete all appointment fields.", "error")
        return redirect(url_for("appointments"))

    conn = get_db()
    patient = conn.execute("SELECT id FROM patients WHERE id=? AND status='Active'", (patient_id,)).fetchone()
    doctor = conn.execute(
        "SELECT id FROM doctors WHERE id=? AND status='Active' AND availability!='On Leave'",
        (doctor_id,),
    ).fetchone()
    conflict = conn.execute(
        """
        SELECT id FROM appointments
        WHERE doctor_id=? AND date=? AND time=? AND status='Scheduled'
        """,
        (doctor_id, apt_date, apt_time),
    ).fetchone()
    if not patient or not doctor:
        flash("Choose an active patient and an available doctor.", "error")
        conn.close()
        return redirect(url_for("appointments"))
    if conflict:
        flash("That doctor already has a scheduled appointment at this time.", "error")
        conn.close()
        return redirect(url_for("appointments"))

    conn.execute(
        "INSERT INTO appointments (patient_id,doctor_id,date,time,reason,status,notes) VALUES (?,?,?,?,?,?,?)",
        (patient_id, doctor_id, apt_date, apt_time, reason, "Scheduled", clean_text(d.get("notes"))),
    )
    conn.commit()
    conn.close()
    flash("Appointment scheduled!", "success")
    return redirect(url_for("appointments"))


@app.route("/appointments/update_status/<int:aid>/<status>", methods=["POST"])
def update_apt_status(aid, status):
    if status not in APPOINTMENT_STATUSES - {"Scheduled"}:
        flash("Invalid appointment status.", "error")
        return redirect(url_for("appointments"))
    conn = get_db()
    conn.execute("UPDATE appointments SET status=? WHERE id=?", (status, aid))
    conn.commit()
    conn.close()
    flash(f"Appointment marked {status.lower()}.", "success")
    return redirect(url_for("appointments"))


@app.route("/medicines")
def medicines():
    conn = get_db()
    rows = conn.execute("SELECT * FROM medicines ORDER BY id DESC").fetchall()
    low_medicines = conn.execute(
        "SELECT * FROM medicines WHERE stock <= min_stock ORDER BY stock ASC, name"
    ).fetchall()
    conn.close()
    return render_template("medicines.html", medicines=rows, low_medicines=low_medicines)


@app.route("/medicines/add", methods=["POST"])
def add_medicine():
    d = request.form
    name = clean_text(d.get("name"))
    category = clean_text(d.get("category"))
    price = parse_float(d.get("price"), minimum=0)
    if not name or not category or price <= 0:
        flash("Please enter a valid medicine name, category, and price.", "error")
        return redirect(url_for("medicines"))

    conn = get_db()
    conn.execute(
        "INSERT INTO medicines (name,category,stock,price,supplier,expiry_date,min_stock) VALUES (?,?,?,?,?,?,?)",
        (
            name,
            category,
            parse_int(d.get("stock"), minimum=0),
            price,
            clean_text(d.get("supplier")),
            d.get("expiry_date") or "",
            parse_int(d.get("min_stock"), default=10, minimum=0),
        ),
    )
    conn.commit()
    conn.close()
    flash("Medicine added!", "success")
    return redirect(url_for("medicines"))


@app.route("/medicines/update_stock/<int:mid>", methods=["POST"])
def update_stock(mid):
    quantity = parse_int(request.form.get("quantity"), minimum=1)
    conn = get_db()
    conn.execute("UPDATE medicines SET stock=stock+? WHERE id=?", (quantity, mid))
    conn.commit()
    conn.close()
    flash("Stock updated!", "success")
    return redirect(url_for("medicines"))


@app.route("/billing")
def billing():
    conn = get_db()
    bills = conn.execute(
        """
        SELECT
            b.*,
            p.name as patient_name,
            CASE
                WHEN COALESCE(b.bill_to, 'Patient') = 'Professor'
                    THEN b.professor_name
                ELSE p.name
            END as billed_name,
            CASE
                WHEN COALESCE(b.bill_to, 'Patient') = 'Professor'
                    THEN COALESCE(NULLIF(b.professor_department, ''), 'Professor Billing')
                ELSE 'Patient Billing'
            END as billed_subtitle
        FROM billing b
        LEFT JOIN patients p ON b.patient_id=p.id
        ORDER BY b.id DESC
        """
    ).fetchall()
    patients = conn.execute("SELECT * FROM patients ORDER BY name").fetchall()
    professors = conn.execute(
        """
        SELECT name, specialization
        FROM doctors
        WHERE status='Active'
        ORDER BY name
        """
    ).fetchall()
    totals_rows = conn.execute("SELECT status, SUM(amount) as total FROM billing GROUP BY status").fetchall()
    totals = {row["status"]: row["total"] for row in totals_rows}
    conn.close()
    return render_template(
        "billing.html",
        bills=bills,
        patients=patients,
        professors=professors,
        totals=totals,
    )


@app.route("/billing/invoice/<int:bid>")
def invoice(bid):
    conn = get_db()
    bill = conn.execute(
        """
        SELECT
            b.*,
            p.name as patient_name,
            p.age as patient_age,
            p.gender as patient_gender,
            p.phone as patient_phone,
            p.email as patient_email,
            p.address as patient_address,
            p.ward as patient_ward,
            d.name as doctor_name,
            CASE
                WHEN COALESCE(b.bill_to, 'Patient') = 'Professor'
                    THEN b.professor_name
                ELSE p.name
            END as billed_name,
            CASE
                WHEN COALESCE(b.bill_to, 'Patient') = 'Professor'
                    THEN COALESCE(NULLIF(b.professor_department, ''), 'Professor Billing')
                ELSE 'Patient Billing'
            END as billed_subtitle
        FROM billing b
        LEFT JOIN patients p ON b.patient_id=p.id
        LEFT JOIN doctors d ON p.doctor_id=d.id
        WHERE b.id=?
        """,
        (bid,),
    ).fetchone()
    conn.close()
    if not bill:
        abort(404)
    return render_template(
        "invoice.html",
        bill=bill,
        generated_on=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )


@app.route("/billing/add", methods=["POST"])
def add_bill():
    d = request.form
    bill_to = d.get("bill_to", "Patient")
    patient_id = parse_int(d.get("patient_id"), minimum=1)
    professor_name = clean_text(d.get("professor_name"))
    professor_department = clean_text(d.get("professor_department"))
    amount = parse_float(d.get("amount"), minimum=0)
    description = clean_text(d.get("description"))
    status = d.get("status", "Pending")
    if (
        bill_to not in BILLING_PARTIES
        or amount <= 0
        or not description
        or status not in BILLING_STATUSES
    ):
        flash("Please enter a valid bill type, amount, description, and status.", "error")
        return redirect(url_for("billing"))

    conn = get_db()
    if bill_to == "Patient":
        patient = conn.execute("SELECT id FROM patients WHERE id=?", (patient_id,)).fetchone()
        if not patient:
            flash("Selected patient does not exist.", "error")
            conn.close()
            return redirect(url_for("billing"))
        professor_name = ""
        professor_department = ""
    else:
        if not professor_name:
            flash("Please enter the professor name.", "error")
            conn.close()
            return redirect(url_for("billing"))
        patient_id = None

    conn.execute(
        """
        INSERT INTO billing
            (patient_id,bill_to,professor_name,professor_department,amount,description,date,status)
        VALUES (?,?,?,?,?,?,?,?)
        """,
        (
            patient_id,
            bill_to,
            professor_name,
            professor_department,
            amount,
            description,
            today(),
            status,
        ),
    )
    conn.commit()
    conn.close()
    flash(f"{bill_to} bill created!", "success")
    return redirect(url_for("billing"))


@app.route("/billing/pay/<int:bid>", methods=["POST"])
def pay_bill(bid):
    conn = get_db()
    conn.execute("UPDATE billing SET status='Paid' WHERE id=?", (bid,))
    conn.commit()
    conn.close()
    flash("Payment recorded!", "success")
    return redirect(url_for("billing"))


@app.route("/api/chart_data")
def chart_data():
    conn = get_db()
    monthly = []
    for i in range(5, -1, -1):
        month_date = datetime.now() - timedelta(days=30 * i)
        month = month_date.strftime("%Y-%m")
        label = month_date.strftime("%b")
        count = conn.execute(
            "SELECT COUNT(*) FROM patients WHERE admitted_date LIKE ?",
            (f"{month}%",),
        ).fetchone()[0]
        monthly.append({"month": label, "count": count})

    dept = conn.execute(
        """
        SELECT d.specialization, COUNT(p.id) as count
        FROM doctors d
        LEFT JOIN patients p ON d.id=p.doctor_id AND p.status='Active'
        WHERE d.status='Active'
        GROUP BY d.specialization
        ORDER BY count DESC, d.specialization
        """
    ).fetchall()

    billing_trend = []
    for i in range(5, -1, -1):
        month_date = datetime.now() - timedelta(days=30 * i)
        month = month_date.strftime("%Y-%m")
        label = month_date.strftime("%b")
        paid = conn.execute(
            "SELECT COALESCE(SUM(amount),0) FROM billing WHERE date LIKE ? AND status='Paid'",
            (f"{month}%",),
        ).fetchone()[0]
        pending = conn.execute(
            "SELECT COALESCE(SUM(amount),0) FROM billing WHERE date LIKE ? AND status='Pending'",
            (f"{month}%",),
        ).fetchone()[0]
        billing_trend.append({"month": label, "paid": round(paid, 2), "pending": round(pending, 2)})

    conn.close()
    return jsonify(
        {
            "monthly_patients": monthly,
            "departments": [{"label": r["specialization"], "value": r["count"]} for r in dept],
            "billing_trend": billing_trend,
        }
    )


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)
