import os
import sqlite3
from contextlib import contextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr, Field

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "students.db")

app = FastAPI(title="Student Management Microservice", version="1.0.0")

# JWT_AUTH_MIDDLEWARE
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
            secret_path = os.path.join(
                os.path.dirname(BASE_DIR), "auth_secret.key"
            )
            with open(secret_path, "r") as secret_file:
                secret_key = secret_file.read().strip()

        payload = jwt.decode(
            token, secret_key, algorithms=["HS256"]
        )

        if not payload.get("sub") or not payload.get("email"):
            raise JWTError("Required token claims are missing")

    except (JWTError, OSError, ValueError):
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid or expired token"},
        )

    return await call_next(request)


@contextmanager
def connect_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def initialize_db():
    with connect_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                phone TEXT NOT NULL,
                department TEXT NOT NULL,
                course TEXT NOT NULL
            )
        """)


initialize_db()


class StudentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    phone: str = Field(min_length=7, max_length=20)
    department: str = Field(min_length=2, max_length=100)
    course: str = Field(min_length=2, max_length=100)


class StudentUpdate(StudentCreate):
    pass


def serialize(row):
    return dict(row)


@app.get("/health")
def health():
    return {"service": "student", "status": "healthy"}


@app.post("/students", status_code=201)
def create_student(student: StudentCreate):
    try:
        with connect_db() as db:
            cursor = db.execute(
                """INSERT INTO students
                   (name, email, phone, department, course)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    student.name.strip(),
                    str(student.email).lower(),
                    student.phone.strip(),
                    student.department.strip(),
                    student.course.strip(),
                ),
            )
            student_id = cursor.lastrowid
            row = db.execute(
                "SELECT * FROM students WHERE id = ?", (student_id,)
            ).fetchone()
            return serialize(row)
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Student email already exists")


@app.get("/students")
def get_students():
    with connect_db() as db:
        rows = db.execute("SELECT * FROM students ORDER BY id DESC").fetchall()
        return [serialize(row) for row in rows]


@app.get("/students/{student_id}")
def get_student(student_id: int):
    with connect_db() as db:
        row = db.execute(
            "SELECT * FROM students WHERE id = ?", (student_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Student not found")
        return serialize(row)


@app.put("/students/{student_id}")
def update_student(student_id: int, student: StudentUpdate):
    try:
        with connect_db() as db:
            existing = db.execute(
                "SELECT id FROM students WHERE id = ?", (student_id,)
            ).fetchone()
            if not existing:
                raise HTTPException(status_code=404, detail="Student not found")

            db.execute(
                """UPDATE students
                   SET name = ?, email = ?, phone = ?, department = ?, course = ?
                   WHERE id = ?""",
                (
                    student.name.strip(),
                    str(student.email).lower(),
                    student.phone.strip(),
                    student.department.strip(),
                    student.course.strip(),
                    student_id,
                ),
            )
            row = db.execute(
                "SELECT * FROM students WHERE id = ?", (student_id,)
            ).fetchone()
            return serialize(row)
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Student email already exists")


@app.delete("/students/{student_id}")
def delete_student(student_id: int):
    with connect_db() as db:
        cursor = db.execute("DELETE FROM students WHERE id = ?", (student_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Student not found")
        return {"message": "Student deleted successfully", "student_id": student_id}
