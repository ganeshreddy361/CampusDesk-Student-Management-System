from datetime import datetime, timedelta, timezone
import os
import secrets
import sqlite3

from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, EmailStr, Field
from jose import jwt, JWTError
from passlib.context import CryptContext

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "auth.db")
SECRET_KEY = os.getenv("AUTH_SECRET_KEY", secrets.token_urlsafe(32))
ALGORITHM = "HS256"
TOKEN_MINUTES = 30

app = FastAPI(title="Authentication Microservice", version="1.0.0")
password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def connect_db():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_db():
    with connect_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL
            )
        """)


initialize_db()


class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)


def find_user(email: str):
    with connect_db() as db:
        return db.execute(
            "SELECT * FROM users WHERE email = ?", (email.lower(),)
        ).fetchone()


def create_token(user_id: int, email: str):
    expires = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_MINUTES)
    return jwt.encode(
        {"sub": str(user_id), "email": email, "exp": expires},
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


def current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload["sub"])
        email = payload["email"]
    except (JWTError, ValueError, KeyError, TypeError):
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = find_user(email)
    if not user or user["id"] != user_id:
        raise HTTPException(status_code=401, detail="User not found")

    return {"id": user["id"], "name": user["name"], "email": user["email"]}


@app.get("/health")
def health():
    return {"service": "authentication", "status": "healthy"}


@app.post("/auth/register", status_code=201)
def register(data: RegisterRequest):
    email = str(data.email).lower()

    if find_user(email):
        raise HTTPException(status_code=409, detail="Email is already registered")

    password_hash = password_context.hash(data.password)

    try:
        with connect_db() as db:
            cursor = db.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                (data.name.strip(), email, password_hash),
            )
            user_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Email is already registered")

    return {"message": "Registration successful", "user_id": user_id}


@app.post("/auth/login")
def login(data: LoginRequest):
    user = find_user(str(data.email).lower())

    if not user or not password_context.verify(data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    return {
        "access_token": create_token(user["id"], user["email"]),
        "token_type": "bearer",
        "expires_in": TOKEN_MINUTES * 60,
    }


@app.get("/auth/me")
def me(user=Depends(current_user)):
    return user


@app.post("/auth/logout")
def logout(user=Depends(current_user)):
    # JWT logout is completed on the frontend by deleting the stored token.
    return {"message": "Logout successful. Remove the access token on the client."}
