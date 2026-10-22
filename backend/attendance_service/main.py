import os
import sqlite3
from pathlib import Path
from datetime import date

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from jose import JWTError, jwt
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "attendance.db"
SECRET_PATH = BASE_DIR.parent / "auth_secret.key"

app = FastAPI(title="Attendance Management Service", version="1.0.0")


def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                student_name TEXT NOT NULL,
                attendance_date TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('Present', 'Absent', 'Late')),
                remarks TEXT DEFAULT '',
                UNIQUE(student_id, attendance_date)
            )
        """)


initialize_database()


@app.middleware("http")
async def require_jwt(request: Request, call_next):
    if request.url.path == "/health" or request.method == "OPTIONS":
        return await call_next(request)

    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        return JSONResponse(
            status_code=401,
            content={"detail": "Authentication required"},
        )

    token = authorization.split(" ", 1)[1].strip()

    try:
        secret_key = os.getenv("AUTH_SECRET_KEY")
        if not secret_key:
            secret_key = SECRET_PATH.read_text().strip()

        payload = jwt.decode(token, secret_key, algorithms=["HS256"])
        if not payload.get("sub") or not payload.get("email"):
            raise JWTError("Required token claims are missing")

    except (JWTError, OSError, ValueError):
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid or expired token"},
        )

    return await call_next(request)


class AttendanceCreate(BaseModel):
    student_id: int = Field(gt=0)
    student_name: str = Field(min_length=1, max_length=100)
    attendance_date: date
    status: str
    remarks: str = Field(default="", max_length=500)


class AttendanceUpdate(BaseModel):
    student_id: int = Field(gt=0)
    student_name: str = Field(min_length=1, max_length=100)
    attendance_date: date
    status: str
    remarks: str = Field(default="", max_length=500)


def validate_status(status):
    if status not in ("Present", "Absent", "Late"):
        raise HTTPException(
            status_code=422,
            detail="Status must be Present, Absent, or Late",
        )


@app.get("/health")
def health():
    return {"status": "healthy", "service": "attendance"}


@app.post("/attendance", status_code=201)
def create_attendance(record: AttendanceCreate):
    validate_status(record.status)

    try:
        with get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO attendance
                    (student_id, student_name, attendance_date, status, remarks)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    record.student_id,
                    record.student_name.strip(),
                    record.attendance_date.isoformat(),
                    record.status,
                    record.remarks.strip(),
                ),
            )
            row = connection.execute(
                "SELECT * FROM attendance WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
            return dict(row)
    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=409,
            detail="Attendance for this student and date already exists",
        )


@app.get("/attendance")
def get_attendance(
    student_id: int | None = None,
    attendance_date: date | None = None,
):
    query = "SELECT * FROM attendance WHERE 1=1"
    parameters = []

    if student_id is not None:
        query += " AND student_id = ?"
        parameters.append(student_id)

    if attendance_date is not None:
        query += " AND attendance_date = ?"
        parameters.append(attendance_date.isoformat())

    query += " ORDER BY attendance_date DESC, student_name"

    with get_connection() as connection:
        rows = connection.execute(query, parameters).fetchall()
        return [dict(row) for row in rows]


@app.get("/attendance/{record_id}")
def get_attendance_record(record_id: int):
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM attendance WHERE id = ?", (record_id,)
        ).fetchone()

        if row is None:
            raise HTTPException(status_code=404, detail="Attendance record not found")

        return dict(row)


@app.put("/attendance/{record_id}")
def update_attendance(record_id: int, record: AttendanceUpdate):
    validate_status(record.status)

    try:
        with get_connection() as connection:
            existing = connection.execute(
                "SELECT id FROM attendance WHERE id = ?", (record_id,)
            ).fetchone()

            if existing is None:
                raise HTTPException(
                    status_code=404, detail="Attendance record not found"
                )

            connection.execute(
                """
                UPDATE attendance
                SET student_id = ?, student_name = ?, attendance_date = ?,
                    status = ?, remarks = ?
                WHERE id = ?
                """,
                (
                    record.student_id,
                    record.student_name.strip(),
                    record.attendance_date.isoformat(),
                    record.status,
                    record.remarks.strip(),
                    record_id,
                ),
            )

            row = connection.execute(
                "SELECT * FROM attendance WHERE id = ?", (record_id,)
            ).fetchone()
            return dict(row)
    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=409,
            detail="Attendance for this student and date already exists",
        )


@app.delete("/attendance/{record_id}")
def delete_attendance(record_id: int):
    with get_connection() as connection:
        cursor = connection.execute(
            "DELETE FROM attendance WHERE id = ?", (record_id,)
        )

        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=404, detail="Attendance record not found"
            )

        return {"message": "Attendance record deleted successfully"}
