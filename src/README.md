# Mergington High School Activities API

A super simple FastAPI application that allows students to view and sign up for extracurricular activities.

## Features

- View all available extracurricular activities
- Teachers can sign in to register and unregister students
- Students can view activities and participant lists without signing in

## Getting Started

1. Install the dependencies:

   ```
   pip install fastapi uvicorn
   ```

2. Run the application:

   ```
   python app.py
   ```

3. Open your browser and go to:
   - API documentation: http://localhost:8000/docs
   - Alternative documentation: http://localhost:8000/redoc

## Teacher accounts

Teacher credentials are kept in `src/teachers.json`, which is intentionally
ignored by Git. Start by copying `src/teachers.example.json` to that path. Add
each teacher with a PBKDF2-SHA256 password hash (never store plaintext
passwords). For example, generate a hash in a Python prompt without echoing the
password:

```python
import getpass, hashlib, secrets
password = getpass.getpass("Teacher password: ")
salt = secrets.token_hex(16)
digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 260000).hex()
print(f"pbkdf2_sha256$260000${salt}${digest}")
```

Put the username and resulting hash in the `teachers` array:

```json
{
  "teachers": [
    {
      "username": "teacher",
      "password_hash": "pbkdf2_sha256$260000$<salt>$<hash>"
    }
  ]
}
```

Set `SESSION_SECRET` to a random value of at least 32 characters before
starting the app. Set `COOKIE_SECURE=1` when serving the app over HTTPS. If
the local teacher file or session secret is missing, teacher sign-in is
unavailable; activity viewing remains public.

## API Endpoints

| Method | Endpoint                                                          | Description                                                         |
| ------ | ----------------------------------------------------------------- | ------------------------------------------------------------------- |
| GET    | `/activities`                                                     | Get all activities with their details and current participant count |
| GET    | `/auth/session`                                                    | Check whether the current browser is signed in as a teacher          |
| POST   | `/auth/login`                                                      | Sign in with a configured teacher username and password              |
| POST   | `/auth/logout`                                                     | Sign out the current browser                                         |
| POST   | `/activities/{activity_name}/signup?email=student@mergington.edu` | Teacher-only student signup; checks capacity and duplicate signup    |
| DELETE | `/activities/{activity_name}/unregister?email=student@mergington.edu` | Teacher-only student removal                                         |

## Data Model

The application uses a simple data model with meaningful identifiers:

1. **Activities** - Uses activity name as identifier:

   - Description
   - Schedule
   - Maximum number of participants allowed
   - List of student emails who are signed up

2. **Students** - Uses email as identifier:
   - Name
   - Grade level

All data is stored in memory, which means data will be reset when the server restarts.
