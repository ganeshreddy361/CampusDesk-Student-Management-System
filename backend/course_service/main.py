import os
import sqlite3
from contextlib import contextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from jose import JWTError, jwt
from pydantic import BaseModel, Field

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "courses.db")

app = FastAPI(title="Course Management Microservice", version="1.0.0")

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
            CREATE TABLE IF NOT EXISTS courses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                code TEXT NOT NULL UNIQUE,
                department TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT ''
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS enrollments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                course_id INTEGER NOT NULL,
                UNIQUE(student_id, course_id)
            )
        """)


initialize_db()


class CourseCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    code: str = Field(min_length=2, max_length=20)
    department: str = Field(min_length=2, max_length=100)
    description: str = Field(default="", max_length=500)


class CourseUpdate(CourseCreate):
    pass


class EnrollmentCreate(BaseModel):
    student_id: int = Field(gt=0)


def serialize(row):
    return dict(row)


@app.get("/health")
def health():
    return {"service": "course", "status": "healthy"}


@app.post("/courses", status_code=201)
def create_course(course: CourseCreate):
    try:
        with connect_db() as db:
            cursor = db.execute(
                """INSERT INTO courses (name, code, department, description)
                   VALUES (?, ?, ?, ?)""",
                (
                    course.name.strip(),
                    course.code.strip().upper(),
                    course.department.strip(),
                    course.description.strip(),
                ),
            )
            row = db.execute(
                "SELECT * FROM courses WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
            return serialize(row)
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Course code already exists")


@app.get("/courses")
def get_courses():
    with connect_db() as db:
        rows = db.execute("SELECT * FROM courses ORDER BY id DESC").fetchall()
        return [serialize(row) for row in rows]


@app.get("/courses/{course_id}")
def get_course(course_id: int):
    with connect_db() as db:
        row = db.execute(
            "SELECT * FROM courses WHERE id = ?", (course_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Course not found")
        return serialize(row)


@app.put("/courses/{course_id}")
def update_course(course_id: int, course: CourseUpdate):
    try:
        with connect_db() as db:
            existing = db.execute(
                "SELECT id FROM courses WHERE id = ?", (course_id,)
            ).fetchone()
            if not existing:
                raise HTTPException(status_code=404, detail="Course not found")

            db.execute(
                """UPDATE courses
                   SET name = ?, code = ?, department = ?, description = ?
                   WHERE id = ?""",
                (
                    course.name.strip(),
                    course.code.strip().upper(),
                    course.department.strip(),
                    course.description.strip(),
                    course_id,
                ),
            )
            row = db.execute(
                "SELECT * FROM courses WHERE id = ?", (course_id,)
            ).fetchone()
            return serialize(row)
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Course code already exists")


@app.delete("/courses/{course_id}")
def delete_course(course_id: int):
    with connect_db() as db:
        existing = db.execute(
            "SELECT id FROM courses WHERE id = ?", (course_id,)
        ).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Course not found")

        db.execute("DELETE FROM enrollments WHERE course_id = ?", (course_id,))
        db.execute("DELETE FROM courses WHERE id = ?", (course_id,))
        return {"message": "Course deleted successfully", "course_id": course_id}


@app.post("/courses/{course_id}/enrollments", status_code=201)
def enroll_student(course_id: int, enrollment: EnrollmentCreate):
    with connect_db() as db:
        course = db.execute(
            "SELECT id FROM courses WHERE id = ?", (course_id,)
        ).fetchone()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")

        try:
            db.execute(
                "INSERT INTO enrollments (student_id, course_id) VALUES (?, ?)",
                (enrollment.student_id, course_id),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(
                status_code=409, detail="Student is already enrolled in this course"
            )

        return {
            "message": "Enrollment created",
            "student_id": enrollment.student_id,
            "course_id": course_id,
        }


@app.get("/courses/{course_id}/students")
def get_course_students(course_id: int):
    with connect_db() as db:
        course = db.execute(
            "SELECT id FROM courses WHERE id = ?", (course_id,)
        ).fetchone()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")

        rows = db.execute(
            """SELECT student_id, course_id
               FROM enrollments WHERE course_id = ? ORDER BY id""",
            (course_id,),
        ).fetchall()

        return [serialize(row) for row in rows]
