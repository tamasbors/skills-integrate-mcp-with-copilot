from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
import unittest

from fastapi import HTTPException
from fastapi import Response
from starlette.requests import Request

from src import app as app_module
from src.app import activities, signup_for_activity, unregister_from_activity


class SignupCapacityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_password = "test-teacher-password"
        salt = bytes(range(16))
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            cls.test_password.encode(),
            salt,
            app_module.PASSWORD_HASH_ITERATIONS,
        ).hex()
        cls.test_password_hash = (
            f"pbkdf2_sha256${app_module.PASSWORD_HASH_ITERATIONS}"
            f"${salt.hex()}${digest}"
        )

    def setUp(self):
        self.original_teacher_file = app_module.TEACHERS_FILE
        self.original_session_secret = os.environ.get("SESSION_SECRET")
        self.temp_dir = tempfile.TemporaryDirectory()
        app_module.TEACHERS_FILE = Path(self.temp_dir.name) / "teachers.json"
        app_module.TEACHERS_FILE.write_text(
            json.dumps(
                {
                    "teachers": [
                        {
                            "username": "teacher",
                            "password_hash": self.test_password_hash,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        os.environ["SESSION_SECRET"] = "test-session-secret-with-32-characters"
        self.activity = activities["Chess Club"]
        self.original_participants = self.activity["participants"][:]
        self.original_capacity = self.activity["max_participants"]

    def tearDown(self):
        self.activity["participants"][:] = self.original_participants
        self.activity["max_participants"] = self.original_capacity
        app_module.TEACHERS_FILE = self.original_teacher_file
        if self.original_session_secret is None:
            os.environ.pop("SESSION_SECRET", None)
        else:
            os.environ["SESSION_SECRET"] = self.original_session_secret
        self.temp_dir.cleanup()

    @staticmethod
    def teacher_request():
        expires_at = int(time.time()) + app_module.SESSION_MAX_AGE
        token = app_module._create_session("teacher", expires_at)
        return Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/",
                "headers": [(b"cookie", f"{app_module.SESSION_COOKIE}={token}".encode())],
            }
        )

    @staticmethod
    def anonymous_request():
        return Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/",
                "headers": [],
            }
        )

    def test_signup_succeeds_when_capacity_is_available(self):
        self.activity["max_participants"] = len(self.activity["participants"]) + 1

        result = signup_for_activity(
            "Chess Club", "new-student@mergington.edu", self.teacher_request()
        )

        self.assertIn("new-student@mergington.edu", self.activity["participants"])
        self.assertIn("Signed up", result["message"])

    def test_signup_is_rejected_when_activity_is_full(self):
        self.activity["max_participants"] = len(self.activity["participants"])
        participants_before_signup = self.activity["participants"][:]

        with self.assertRaises(HTTPException) as error:
            signup_for_activity(
                "Chess Club", "new-student@mergington.edu", self.teacher_request()
            )

        self.assertEqual(error.exception.status_code, 400)
        self.assertEqual(error.exception.detail, "Activity is full")
        self.assertEqual(self.activity["participants"], participants_before_signup)

    def test_concurrent_signups_cannot_exceed_capacity(self):
        self.activity["max_participants"] = len(self.activity["participants"]) + 1

        def signup(email):
            try:
                return signup_for_activity("Chess Club", email, self.teacher_request())
            except HTTPException as error:
                return error

        emails = ["first@mergington.edu", "second@mergington.edu"]
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(signup, emails))

        self.assertEqual(sum(isinstance(result, dict) for result in results), 1)
        self.assertEqual(sum(email in self.activity["participants"] for email in emails), 1)

    def test_duplicate_signup_is_still_rejected(self):
        existing_student = self.activity["participants"][0]

        with self.assertRaises(HTTPException) as error:
            signup_for_activity("Chess Club", existing_student, self.teacher_request())

        self.assertEqual(error.exception.status_code, 400)
        self.assertEqual(error.exception.detail, "Student is already signed up")

    def test_unknown_activity_is_still_rejected(self):
        with self.assertRaises(HTTPException) as error:
            signup_for_activity(
                "Unknown Activity",
                "student@mergington.edu",
                self.teacher_request(),
            )

        self.assertEqual(error.exception.status_code, 404)
        self.assertEqual(error.exception.detail, "Activity not found")

    def test_signup_is_rejected_without_teacher_session(self):
        participants_before_signup = self.activity["participants"][:]

        with self.assertRaises(HTTPException) as error:
            signup_for_activity(
                "Chess Club", "new-student@mergington.edu", self.anonymous_request()
            )

        self.assertEqual(error.exception.status_code, 401)
        self.assertEqual(self.activity["participants"], participants_before_signup)

    def test_unregister_is_rejected_without_teacher_session(self):
        existing_student = self.activity["participants"][0]

        with self.assertRaises(HTTPException) as error:
            unregister_from_activity(
                "Chess Club", existing_student, self.anonymous_request()
            )

        self.assertEqual(error.exception.status_code, 401)
        self.assertIn(existing_student, self.activity["participants"])

    def test_teacher_can_unregister_a_student(self):
        existing_student = self.activity["participants"][0]

        result = unregister_from_activity(
            "Chess Club", existing_student, self.teacher_request()
        )

        self.assertNotIn(existing_student, self.activity["participants"])
        self.assertIn("Unregistered", result["message"])

    def test_teacher_can_sign_in_and_receive_an_http_only_session_cookie(self):
        response = Response()

        result = app_module.login(
            app_module.TeacherCredentials(
                username="teacher", password=self.test_password
            ),
            response,
        )

        self.assertEqual(result, {"authenticated": True, "username": "teacher"})
        cookie = response.headers["set-cookie"]
        self.assertIn("httponly", cookie.lower())
        self.assertIn("samesite=strict", cookie.lower())
        request = Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/",
                "headers": [(b"cookie", cookie.split(";", 1)[0].encode())],
            }
        )
        self.assertEqual(app_module._authenticated_teacher(request), "teacher")

    def test_invalid_teacher_password_is_rejected(self):
        with self.assertRaises(HTTPException) as error:
            app_module.login(
                app_module.TeacherCredentials(
                    username="teacher", password="incorrect-password"
                ),
                Response(),
            )

        self.assertEqual(error.exception.status_code, 401)


if __name__ == "__main__":
    unittest.main()
