from concurrent.futures import ThreadPoolExecutor
import unittest

from fastapi import HTTPException

from src.app import activities, signup_for_activity


class SignupCapacityTests(unittest.TestCase):
    def setUp(self):
        self.activity = activities["Chess Club"]
        self.original_participants = self.activity["participants"][:]
        self.original_capacity = self.activity["max_participants"]

    def tearDown(self):
        self.activity["participants"][:] = self.original_participants
        self.activity["max_participants"] = self.original_capacity

    def test_signup_succeeds_when_capacity_is_available(self):
        self.activity["max_participants"] = len(self.activity["participants"]) + 1

        result = signup_for_activity("Chess Club", "new-student@mergington.edu")

        self.assertIn("new-student@mergington.edu", self.activity["participants"])
        self.assertIn("Signed up", result["message"])

    def test_signup_is_rejected_when_activity_is_full(self):
        self.activity["max_participants"] = len(self.activity["participants"])
        participants_before_signup = self.activity["participants"][:]

        with self.assertRaises(HTTPException) as error:
            signup_for_activity("Chess Club", "new-student@mergington.edu")

        self.assertEqual(error.exception.status_code, 400)
        self.assertEqual(error.exception.detail, "Activity is full")
        self.assertEqual(self.activity["participants"], participants_before_signup)

    def test_concurrent_signups_cannot_exceed_capacity(self):
        self.activity["max_participants"] = len(self.activity["participants"]) + 1

        def signup(email):
            try:
                return signup_for_activity("Chess Club", email)
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
            signup_for_activity("Chess Club", existing_student)

        self.assertEqual(error.exception.status_code, 400)
        self.assertEqual(error.exception.detail, "Student is already signed up")

    def test_unknown_activity_is_still_rejected(self):
        with self.assertRaises(HTTPException) as error:
            signup_for_activity("Unknown Activity", "student@mergington.edu")

        self.assertEqual(error.exception.status_code, 404)
        self.assertEqual(error.exception.detail, "Activity not found")


if __name__ == "__main__":
    unittest.main()
