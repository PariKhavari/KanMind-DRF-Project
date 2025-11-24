# KanMind – Django REST Backend

KanMind is a Kanban-style task management backend built with **Django** and **Django REST Framework (DRF)**.

This repository contains **only the backend** implementation.

---

## Features

- User registration and login via REST API
- Token-based authentication
- E-mail check endpoint for user lookup
- Board management (create/update/delete boards)
- Task management with:
  - status workflow (to-do, in-progress, review, done)
  - priorities (low, medium, high, critical)
  - assignee & reviewer
  - due dates
- Comments on tasks
- Dashboard statistics and “assigned to me” / “reviewing” task lists
- Permissions and role-based access:
  - Board owner, board members
  - Task creator
  - Assignee / reviewer

---

## Tech Stack

- Python 3.11+ (recommended)
- Django 5.x
- Django REST Framework
- SQLite (default for development)
- `djangorestframework-authtoken` for token authentication

All Python dependencies are listed in `requirements.txt`.

---

## Project Structure

The project follows the required structure:

```text
core/                   # main Django project (settings, urls, wsgi)
auth_app/
    api/
        serializers.py
        views.py
        urls.py
boards_app/
    api/
        serializers.py
        views.py
        urls.py
        permissions.py
    models.py
    admin.py
manage.py
requirements.txt
README.md
```

- The main project is called **`core`**.
- Backend apps are named with `_app` suffix:
  - `auth_app` – authentication and user-related endpoints
  - `boards_app` – boards, tasks, comments, dashboard

---

## Setup & Installation

### 1. Clone the repository

```bash
git clone <YOUR_REPOSITORY_URL>.git
cd <YOUR_REPOSITORY_FOLDER>
```

### 2. Create and activate a virtual environment

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Apply migrations

```bash
python manage.py migrate
```

### 5. Create a superuser (for Django Admin)

```bash
python manage.py createsuperuser
```

Follow the prompts and set username, email and password.

### 6. Run the development server

```bash
python manage.py runserver
```

The API will be available at:

- `http://127.0.0.1:8000/`

---

## Authentication

The API uses **Token Authentication** for most endpoints.

### 1. Registration

Endpoint:

```http
POST /api/registration/
```

Example request:

```json
{
  "fullname": "Example Username",
  "email": "example@mail.de",
  "password": "examplePassword",
  "repeated_password": "examplePassword"
}
```

Example response:

```json
{
  "token": "your-token-here",
  "fullname": "Example Username",
  "email": "example@mail.de",
  "user_id": 1
}
```

### 2. Login

Endpoint:

```http
POST /api/login/
```

Example request:

```json
{
  "email": "example@mail.de",
  "password": "examplePassword"
}
```

Example response:

```json
{
  "token": "your-token-here",
  "fullname": "Example Username",
  "email": "example@mail.de",
  "user_id": 1
}
```

### 3. Using the token

For all protected endpoints, send:

```http
Authorization: Token <your-token-here>
```

in the HTTP headers.

---

## Main API Endpoints (Overview)

Only an overview is given here – the detailed specification is taken from the provided API documentation.

### Authentication (`auth_app`)

- `POST /api/registration/` Register
- `POST /api/login/`
- `GET /api/email-check/?email=<email>`

### Boards & Tasks (`boards_app`)

#### Boards

`GET /api/boards/` all boards
`POST /api/boards/` Create a new board
`GET /api/boards/{id}/` a single board
`PATCH /api/boards/{id}/` Update
`DELETE /api/boards/{id}/`Only the board **owner**

#### Tasks

- `GET /api/tasks/` List tasks
- `POST /api/tasks/` Create a new task.  
  **The user must be a member of the board** to create a task.

  Expected fields (simplified):

  ```json
  {
    "board": 2,
    "title": "Code review",
    "description": "Review pull request #123",
    "status": "review", // "to-do" | "in-progress" | "review" | "done"
    "priority": "medium", // "low" | "medium" | "high" | "critical"
    "assignee_id": 3,
    "reviewer_id": 1,
    "due_date": "2025-02-27"
  }
  ```

- `GET /api/tasks/{id}/` a single task

  ```json
  {
    "id": 1,
    "board": 2,
    "title": "...",
    "description": "...",
    "status": "review",
    "priority": "medium",
    "assignee": { "id": ..., "email": "...", "fullname": "..." },
    "reviewer": { ... } | null,
    "due_date": "YYYY-MM-DD",
    "comments_count": 0
  }
  ```

- `PATCH /api/tasks/{id}/` Update
- `DELETE /api/tasks/{id}/` Only the creator or owner of the boerd

---

### Special Task Endpoints

- `GET /api/tasks/assigned-to-me/`  
  All tasks where the current user is the **assignee**.

- `GET /api/tasks/reviewing/`  
  All tasks where the current user is the **reviewer**.

---

### Dashboard

- `GET /api/dashboard/stats/`  
  Returns aggregated statistics for the current user, e.g.:

  ```json
  {
    "boards_member_of": 3,
    "tasks_assigned_to_me": 7,
    "urgent_tasks_count": 2,
    "done_last_14_days": 5
  }
  ```

---

## Django Admin

The Django admin is enabled and can be accessed at:

```text
http://127.0.0.1:8000/admin/
```

Log in with the superuser created via `createsuperuser`.

- Boards, tasks, columns and activities are registered in the admin
  to allow manual inspection and debugging.

---

## Coding Conventions & Quality

The codebase follows these conventions:

- PEP8-compliant Python code
- One function/method has at most one clear responsibility
- Views are implemented using:
  - `ModelViewSet` for CRUD resources
  - `APIView` / `GenericAPIView` for special endpoints
- Serializers:
  - use `ModelSerializer` for CRUD
  - use `validate_<field>` or `validate()` for extra validation where needed
- Permissions:
  - handled in dedicated `permissions.py` in `boards_app/api`
  - combine `IsAuthenticated` with project-specific permissions such as
    `IsBoardMember` and deletion rules for tasks
