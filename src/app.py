"""
High School Management System API

A super simple FastAPI application that allows students to view and sign up
for extracurricular activities at Mergington High School.
"""

import hashlib
import hmac
import json
import logging
import os
import time
from pathlib import Path
from threading import Lock

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="Mergington High School API",
              description="API for viewing and signing up for extracurricular activities")
logger = logging.getLogger(__name__)
signup_lock = Lock()
SESSION_COOKIE = "teacher_session"
SESSION_MAX_AGE = 8 * 60 * 60
PASSWORD_HASH_ITERATIONS = 260_000
TEACHERS_FILE = Path(__file__).with_name("teachers.json")

# Mount the static files directory
current_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=os.path.join(Path(__file__).parent,
          "static")), name="static")

# In-memory activity database
activities = {
    "Chess Club": {
        "description": "Learn strategies and compete in chess tournaments",
        "schedule": "Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 12,
        "participants": ["michael@mergington.edu", "daniel@mergington.edu"]
    },
    "Programming Class": {
        "description": "Learn programming fundamentals and build software projects",
        "schedule": "Tuesdays and Thursdays, 3:30 PM - 4:30 PM",
        "max_participants": 20,
        "participants": ["emma@mergington.edu", "sophia@mergington.edu"]
    },
    "Gym Class": {
        "description": "Physical education and sports activities",
        "schedule": "Mondays, Wednesdays, Fridays, 2:00 PM - 3:00 PM",
        "max_participants": 30,
        "participants": ["john@mergington.edu", "olivia@mergington.edu"]
    },
    "Soccer Team": {
        "description": "Join the school soccer team and compete in matches",
        "schedule": "Tuesdays and Thursdays, 4:00 PM - 5:30 PM",
        "max_participants": 22,
        "participants": ["liam@mergington.edu", "noah@mergington.edu"]
    },
    "Basketball Team": {
        "description": "Practice and play basketball with the school team",
        "schedule": "Wednesdays and Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["ava@mergington.edu", "mia@mergington.edu"]
    },
    "Art Club": {
        "description": "Explore your creativity through painting and drawing",
        "schedule": "Thursdays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["amelia@mergington.edu", "harper@mergington.edu"]
    },
    "Drama Club": {
        "description": "Act, direct, and produce plays and performances",
        "schedule": "Mondays and Wednesdays, 4:00 PM - 5:30 PM",
        "max_participants": 20,
        "participants": ["ella@mergington.edu", "scarlett@mergington.edu"]
    },
    "Math Club": {
        "description": "Solve challenging problems and participate in math competitions",
        "schedule": "Tuesdays, 3:30 PM - 4:30 PM",
        "max_participants": 10,
        "participants": ["james@mergington.edu", "benjamin@mergington.edu"]
    },
    "Debate Team": {
        "description": "Develop public speaking and argumentation skills",
        "schedule": "Fridays, 4:00 PM - 5:30 PM",
        "max_participants": 12,
        "participants": ["charlotte@mergington.edu", "henry@mergington.edu"]
    }
}


class TeacherCredentials(BaseModel):
    username: str
    password: str


def _load_teachers():
    try:
        with TEACHERS_FILE.open(encoding="utf-8") as teacher_file:
            teachers = json.load(teacher_file)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        logger.exception("Unable to load teacher credentials")
        raise HTTPException(
            status_code=503,
            detail="Teacher login is not configured correctly",
        ) from error

    if not isinstance(teachers, dict) or not isinstance(teachers.get("teachers"), list):
        raise HTTPException(
            status_code=503,
            detail="Teacher login is not configured correctly",
        )

    for teacher in teachers["teachers"]:
        if (
            not isinstance(teacher, dict)
            or not isinstance(teacher.get("username"), str)
            or not isinstance(teacher.get("password_hash"), str)
        ):
            raise HTTPException(
                status_code=503,
                detail="Teacher login is not configured correctly",
            )
    return teachers["teachers"]


def _verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations_text, salt, expected_hash = password_hash.split("$")
        iterations = int(iterations_text)
        expected = bytes.fromhex(expected_hash)
        salt_bytes = bytes.fromhex(salt)
    except (ValueError, TypeError):
        return False

    if (
        algorithm != "pbkdf2_sha256"
        or not PASSWORD_HASH_ITERATIONS <= iterations <= 1_000_000
        or len(expected) != hashlib.sha256().digest_size
        or len(salt_bytes) < 16
    ):
        return False

    actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt_bytes, iterations)
    return hmac.compare_digest(actual, expected)


def _session_secret() -> bytes:
    secret = os.environ.get("SESSION_SECRET", "")
    if len(secret) < 32:
        raise HTTPException(
            status_code=503,
            detail="Teacher login is not configured correctly",
        )
    return secret.encode()


def _create_session(username: str, expires_at: int) -> str:
    message = f"{username}:{expires_at}"
    signature = hmac.new(_session_secret(), message.encode(), hashlib.sha256).hexdigest()
    return f"{message}:{signature}"


def _authenticated_teacher(request: Request) -> str:
    token = request.cookies.get(SESSION_COOKIE, "")
    try:
        username, expires_text, signature = token.rsplit(":", 2)
        expires_at = int(expires_text)
    except (ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Teacher login required")

    if expires_at <= int(time.time()):
        raise HTTPException(status_code=401, detail="Teacher login required")

    message = f"{username}:{expires_at}"
    expected_signature = hmac.new(
        _session_secret(), message.encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(signature, expected_signature):
        raise HTTPException(status_code=401, detail="Teacher login required")

    if not any(teacher["username"] == username for teacher in _load_teachers()):
        raise HTTPException(status_code=401, detail="Teacher login required")
    return username


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/activities")
def get_activities():
    return activities


@app.post("/auth/login")
def login(credentials: TeacherCredentials, response: Response):
    teacher = next(
        (teacher for teacher in _load_teachers()
         if teacher["username"] == credentials.username),
        None,
    )
    if teacher is None or not _verify_password(
        credentials.password, teacher["password_hash"]
    ):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    expires_at = int(time.time()) + SESSION_MAX_AGE
    response.set_cookie(
        key=SESSION_COOKIE,
        value=_create_session(credentials.username, expires_at),
        max_age=SESSION_MAX_AGE,
        httponly=True,
        secure=os.environ.get("COOKIE_SECURE", "").lower() in {"1", "true"},
        samesite="strict",
        path="/",
    )
    return {"authenticated": True, "username": credentials.username}


@app.get("/auth/session")
def get_session(request: Request):
    try:
        username = _authenticated_teacher(request)
    except HTTPException as error:
        if error.status_code == 401:
            return {"authenticated": False}
        raise
    return {"authenticated": True, "username": username}


@app.post("/auth/logout")
def logout(response: Response):
    response.delete_cookie(
        key=SESSION_COOKIE,
        httponly=True,
        secure=os.environ.get("COOKIE_SECURE", "").lower() in {"1", "true"},
        samesite="strict",
        path="/",
    )
    return {"authenticated": False}


@app.post("/activities/{activity_name}/signup")
def signup_for_activity(activity_name: str, email: str, request: Request):
    """Sign up a student for an activity"""
    _authenticated_teacher(request)

    # Validate activity exists
    if activity_name not in activities:
        raise HTTPException(status_code=404, detail="Activity not found")

    # Get the specific activity
    activity = activities[activity_name]

    with signup_lock:
        # Validate student is not already signed up
        if email in activity["participants"]:
            raise HTTPException(
                status_code=400,
                detail="Student is already signed up"
            )

        if len(activity["participants"]) >= activity["max_participants"]:
            raise HTTPException(
                status_code=400,
                detail="Activity is full"
            )

        activity["participants"].append(email)

    return {"message": f"Signed up {email} for {activity_name}"}


@app.delete("/activities/{activity_name}/unregister")
def unregister_from_activity(activity_name: str, email: str, request: Request):
    """Unregister a student from an activity"""
    _authenticated_teacher(request)

    # Validate activity exists
    if activity_name not in activities:
        raise HTTPException(status_code=404, detail="Activity not found")

    # Get the specific activity
    activity = activities[activity_name]

    # Validate student is signed up
    if email not in activity["participants"]:
        raise HTTPException(
            status_code=400,
            detail="Student is not signed up for this activity"
        )

    with signup_lock:
        # Validate student is signed up
        if email not in activity["participants"]:
            raise HTTPException(
                status_code=400,
                detail="Student is not signed up for this activity"
            )

        activity["participants"].remove(email)
    return {"message": f"Unregistered {email} from {activity_name}"}
