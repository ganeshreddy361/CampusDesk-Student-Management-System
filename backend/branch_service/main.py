import os
import sqlite3
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from jose import JWTError, jwt
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "branches.db"
SECRET_PATH = BASE_DIR.parent / "auth_secret.key"

app = FastAPI(title="Branch Management Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS branches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                code TEXT NOT NULL UNIQUE,
                location TEXT NOT NULL,
                description TEXT DEFAULT ''
            )
        """)


initialize_database()


# Protect branch endpoints with the same JWT secret as the other services.
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


class BranchCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    code: str = Field(min_length=1, max_length=20)
    location: str = Field(min_length=1, max_length=150)
    description: str = Field(default="", max_length=500)


class BranchUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    code: str = Field(min_length=1, max_length=20)
    location: str = Field(min_length=1, max_length=150)
    description: str = Field(default="", max_length=500)


@app.get("/health")
def health():
    return {"status": "healthy", "service": "branch"}


@app.post("/branches", status_code=201)
def create_branch(branch: BranchCreate):
    try:
        with get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO branches (name, code, location, description)
                VALUES (?, ?, ?, ?)
                """,
                (
                    branch.name.strip(),
                    branch.code.strip().upper(),
                    branch.location.strip(),
                    branch.description.strip(),
                ),
            )
            branch_id = cursor.lastrowid
            row = connection.execute(
                "SELECT * FROM branches WHERE id = ?", (branch_id,)
            ).fetchone()
            return dict(row)
    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=409,
            detail="A branch with this code already exists",
        )


@app.get("/branches")
def get_branches():
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM branches ORDER BY id"
        ).fetchall()
        return [dict(row) for row in rows]


@app.get("/branches/{branch_id}")
def get_branch(branch_id: int):
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM branches WHERE id = ?", (branch_id,)
        ).fetchone()

        if row is None:
            raise HTTPException(status_code=404, detail="Branch not found")

        return dict(row)


@app.put("/branches/{branch_id}")
def update_branch(branch_id: int, branch: BranchUpdate):
    try:
        with get_connection() as connection:
            existing = connection.execute(
                "SELECT id FROM branches WHERE id = ?", (branch_id,)
            ).fetchone()

            if existing is None:
                raise HTTPException(
                    status_code=404, detail="Branch not found"
                )

            connection.execute(
                """
                UPDATE branches
                SET name = ?, code = ?, location = ?, description = ?
                WHERE id = ?
                """,
                (
                    branch.name.strip(),
                    branch.code.strip().upper(),
                    branch.location.strip(),
                    branch.description.strip(),
                    branch_id,
                ),
            )

            row = connection.execute(
                "SELECT * FROM branches WHERE id = ?", (branch_id,)
            ).fetchone()
            return dict(row)
    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=409,
            detail="A branch with this code already exists",
        )


@app.delete("/branches/{branch_id}")
def delete_branch(branch_id: int):
    with get_connection() as connection:
        cursor = connection.execute(
            "DELETE FROM branches WHERE id = ?", (branch_id,)
        )

        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Branch not found")

        return {"message": "Branch deleted successfully"}
