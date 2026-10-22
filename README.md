# CampusDesk - Student Management System

A student management application built with React, FastAPI, SQLite, JWT authentication, and a microservices architecture.

## Services

- Frontend: React and Vite (port 5173)
- API Gateway: port 8000
- Authentication Service: port 8001
- Student Service: port 8002
- Course Service: port 8003
- Branch Service: port 8004
- Attendance Service: port 8005
- Fee Service: port 8006

## Project Structure

- `frontend/` - React application
- `backend/api_gateway/` - API Gateway
- `backend/auth_service/` - Authentication
- `backend/student_service/` - Student management
- `backend/course_service/` - Course management
- `backend/branch_service/` - Branch management
- `backend/attendance_service/` - Attendance management
- `backend/fee_service/` - Fee management
- `backend/requirements.txt` - Python dependencies
- `postman/collection.json` - Postman API collection
- `screenshots/` - Project screenshots

## Setup

Activate the Python environment with `source backend/venv/bin/activate` and install dependencies using `python -m pip install -r backend/requirements.txt`.

Install frontend dependencies using `cd frontend && npm install`.

## Run

Start each backend service in its own terminal using its configured Uvicorn command. Do not start another instance if that port is already occupied. Start the frontend from `frontend/` using `npm run dev`.

## Verify

Check gateway health at `http://127.0.0.1:8000/health`. Open the Swagger documentation for a running service at its `/docs` URL.

## API Testing

Import `postman/collection.json` into Postman and test the requests using valid credentials and IDs.

## Security

Configure the same private JWT secret for services that validate tokens. Never commit secrets, passwords, or access tokens to GitHub.
