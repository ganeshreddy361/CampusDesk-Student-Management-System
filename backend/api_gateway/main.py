import os

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

AUTH_URL = os.getenv("AUTH_SERVICE_URL", "http://127.0.0.1:8001")
STUDENT_URL = os.getenv("STUDENT_SERVICE_URL", "http://127.0.0.1:8002")
COURSE_URL = os.getenv("COURSE_SERVICE_URL", "http://127.0.0.1:8003")
BRANCH_URL = os.getenv("BRANCH_SERVICE_URL", "http://127.0.0.1:8004")
ATTENDANCE_URL = os.getenv("ATTENDANCE_SERVICE_URL", "http://127.0.0.1:8005")
FEE_URL = os.getenv("FEE_SERVICE_URL", "http://127.0.0.1:8006")

app = FastAPI(title="Student Management API Gateway", version="1.1.0")

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

ROUTES = [
    ("/auth", AUTH_URL),
    ("/students", STUDENT_URL),
    ("/courses", COURSE_URL),
    ("/branches", BRANCH_URL),
    ("/attendance", ATTENDANCE_URL),
    ("/fees", FEE_URL),
]


@app.get("/health")
async def health():
    services = {}
    async with httpx.AsyncClient(timeout=3.0) as client:
        for name, url in [
            ("authentication", AUTH_URL),
            ("students", STUDENT_URL),
            ("courses", COURSE_URL),
            ("branches", BRANCH_URL),
            ("attendance", ATTENDANCE_URL),
            ("fees", FEE_URL),
        ]:
            try:
                response = await client.get(f"{url}/health")
                services[name] = (
                    "healthy" if response.is_success else "unavailable"
                )
            except httpx.RequestError:
                services[name] = "unavailable"

    status = (
        "healthy"
        if all(value == "healthy" for value in services.values())
        else "degraded"
    )
    return {"gateway": status, "services": services}


@app.api_route(
    "/{full_path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
)
async def gateway(full_path: str, request: Request):
    path = "/" + full_path
    target = None

    for prefix, base_url in ROUTES:
        if path == prefix or path.startswith(prefix + "/"):
            target = base_url
            break

    if target is None:
        return JSONResponse(
            status_code=404,
            content={"detail": "Gateway route not found"},
        )

    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in {
            "host", "content-length", "connection", "transfer-encoding"
        }
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            upstream = await client.request(
                method=request.method,
                url=f"{target}{path}",
                params=request.query_params,
                content=await request.body(),
                headers=headers,
            )
    except httpx.RequestError:
        return JSONResponse(
            status_code=502,
            content={"detail": "Requested microservice is unavailable"},
        )

    excluded = {
        "content-encoding", "content-length",
        "transfer-encoding", "connection",
    }
    response_headers = {
        key: value
        for key, value in upstream.headers.items()
        if key.lower() not in excluded
    }

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=response_headers,
        media_type=upstream.headers.get("content-type"),
    )
