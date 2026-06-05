# Gestionar de Sarcini

A full-stack task management web application built with **FastAPI** and vanilla JavaScript.

## Features

- User registration and login with JWT authentication
- Create, edit, complete, and delete tasks
- Filter to show only incomplete tasks
- Persistent storage with SQLite
- Deployed on [Render.com](https://render.com) with one-click config via `render.yaml`

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python, FastAPI, SQLite |
| Auth | JWT (PyJWT), bcrypt (passlib) |
| Frontend | Bootstrap 5, Vanilla JS |
| Config | python-dotenv |
| Deploy | Render.com |

## Getting Started

**Prerequisites:** Python 3.11+

```bash
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and set your own `SECRET_KEY`:

```env
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
EXPIRARE_TOKEN_MINUTE=30
DATABASE_PATH=sarcini.db
```

Run the server:

```bash
uvicorn main:app --reload
```

The app is served at `http://localhost:8000`. The frontend is bundled — no separate build step needed.

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/inregistrare` | Register a new user |
| `POST` | `/autentificare` | Login, returns JWT |
| `GET` | `/sarcini` | List tasks (optional `?doar_nefinalizate=true`) |
| `POST` | `/sarcini` | Create a task |
| `PUT` | `/sarcini/{id}` | Update a task |
| `PATCH` | `/sarcini/{id}/finalizeaza` | Mark task as complete |
| `DELETE` | `/sarcini/{id}` | Delete a task |
| `GET` | `/healthz` | Health check |

## Deployment

The repo includes a `render.yaml` for zero-config deployment on Render. `SECRET_KEY` is auto-generated; all other variables have sensible defaults.

## About Me

The **About me** tab in the app loads [victorbalan.com](https://victorbalan.com/) — my personal portfolio and CV. The source code for that site lives in the [PersonalProfile](https://github.com/victorbalan/PersonalProfile) repository.
