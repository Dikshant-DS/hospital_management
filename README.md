# MediCore HMS - Hospital Management Dashboard

Final year project built with Python Flask, SQLite, Jinja templates, vanilla JavaScript, and Chart.js.

## Overview

MediCore HMS is a compact hospital management system for tracking patients, doctors, appointments, pharmacy stock, and billing. The database is initialized automatically with sample data on first run.

## Features

| Module | Features |
| --- | --- |
| Dashboard | KPI cards, patient admission trends, revenue chart, department distribution |
| Patients | Add, edit, search, filter, discharge, and guarded delete |
| Doctors | Doctor profiles, availability, patient counts, guarded remove |
| Appointments | Scheduling, completion/cancellation, active-patient checks, doctor time-conflict prevention |
| Medicines | Inventory tracking, low-stock alerts based on each medicine's threshold, restocking |
| Billing | Invoice creation, pending/paid totals, payment recording |

## Run Locally

```bash
cd hospital_dashboard
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open `http://localhost:5000` in your browser.

## Project Structure

```text
hospital_dashboard/
|-- app.py
|-- hospital.db
|-- requirements.txt
|-- README.md
`-- templates/
    |-- base.html
    |-- index.html
    |-- patients.html
    |-- doctors.html
    |-- appointments.html
    |-- medicines.html
    `-- billing.html
```

## Notes

- SQLite foreign keys are enabled for each database connection.
- State-changing actions use POST routes.
- Doctors cannot be double-booked for active scheduled appointments at the same date and time.
- Patients and doctors with linked operational history are preserved by status changes instead of unsafe hard deletion.
