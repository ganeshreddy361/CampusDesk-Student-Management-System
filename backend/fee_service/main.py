import os
import sqlite3
from contextlib import contextmanager
from datetime import date

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from jose import JWTError, jwt
from pydantic import BaseModel, Field, ConfigDict

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "fees.db")

app = FastAPI(title="Fee Payment Microservice", version="1.0.0")


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

        payload = jwt.decode(token, secret_key, algorithms=["HS256"])
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
            CREATE TABLE IF NOT EXISTS fees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                student_name TEXT NOT NULL,
                academic_year TEXT NOT NULL,
                total_fee REAL NOT NULL CHECK(total_fee >= 0),
                amount_paid REAL NOT NULL CHECK(amount_paid >= 0),
                due_date TEXT NOT NULL,
                payment_method TEXT NOT NULL DEFAULT 'Not specified',
                remarks TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CHECK(amount_paid <= total_fee)
            )
        """)


initialize_db()


class FeeCreate(BaseModel):
    student_id: int = Field(gt=0)
    student_name: str = Field(min_length=2, max_length=100)
    academic_year: str = Field(min_length=4, max_length=20)
    total_fee: float = Field(ge=0)
    amount_paid: float = Field(ge=0)
    due_date: date
    payment_method: str = Field(default="Not specified", max_length=50)
    remarks: str = Field(default="", max_length=500)

    model_config = ConfigDict(str_strip_whitespace=True)


class FeeUpdate(FeeCreate):
    pass


def serialize(row):
    record = dict(row)
    record["balance_due"] = round(
        record["total_fee"] - record["amount_paid"], 2
    )

    if record["amount_paid"] >= record["total_fee"]:
        record["payment_status"] = "Paid"
    elif record["amount_paid"] > 0:
        record["payment_status"] = "Partial"
    else:
        record["payment_status"] = "Pending"

    return record


def validate_fee(fee):
    if fee.amount_paid > fee.total_fee:
        raise HTTPException(
            status_code=422,
            detail="Amount paid cannot exceed total fee",
        )


def find_fee(db, fee_id):
    row = db.execute(
        "SELECT * FROM fees WHERE id = ?", (fee_id,)
    ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Fee record not found")

    return row


@app.get("/health")
def health():
    return {"service": "fee", "status": "healthy"}


@app.post("/fees", status_code=201)
def create_fee(fee: FeeCreate):
    validate_fee(fee)

    with connect_db() as db:
        cursor = db.execute(
            """INSERT INTO fees
               (student_id, student_name, academic_year, total_fee,
                amount_paid, due_date, payment_method, remarks)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                fee.student_id,
                fee.student_name.strip(),
                fee.academic_year.strip(),
                fee.total_fee,
                fee.amount_paid,
                fee.due_date.isoformat(),
                fee.payment_method.strip() or "Not specified",
                fee.remarks.strip(),
            ),
        )
        row = find_fee(db, cursor.lastrowid)
        return serialize(row)


@app.get("/fees")
def get_fees(student_id: int | None = None):
    with connect_db() as db:
        if student_id is not None:
            rows = db.execute(
                "SELECT * FROM fees WHERE student_id = ? ORDER BY id DESC",
                (student_id,),
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM fees ORDER BY id DESC"
            ).fetchall()

        return [serialize(row) for row in rows]


@app.get("/fees/{fee_id}")
def get_fee(fee_id: int):
    with connect_db() as db:
        return serialize(find_fee(db, fee_id))


@app.put("/fees/{fee_id}")
def update_fee(fee_id: int, fee: FeeUpdate):
    validate_fee(fee)

    with connect_db() as db:
        find_fee(db, fee_id)
        db.execute(
            """UPDATE fees SET
               student_id = ?, student_name = ?, academic_year = ?,
               total_fee = ?, amount_paid = ?, due_date = ?,
               payment_method = ?, remarks = ?
               WHERE id = ?""",
            (
                fee.student_id,
                fee.student_name.strip(),
                fee.academic_year.strip(),
                fee.total_fee,
                fee.amount_paid,
                fee.due_date.isoformat(),
                fee.payment_method.strip() or "Not specified",
                fee.remarks.strip(),
                fee_id,
            ),
        )
        return serialize(find_fee(db, fee_id))


@app.delete("/fees/{fee_id}")
def delete_fee(fee_id: int):
    with connect_db() as db:
        find_fee(db, fee_id)
        db.execute("DELETE FROM fees WHERE id = ?", (fee_id,))
        return {
            "message": "Fee record deleted successfully",
            "fee_id": fee_id,
        }
