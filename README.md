# Pentagon Backend

This repository contains the backend API for the Pentagon project. The backend is implemented in Python using FastAPI and SQLAlchemy, and it expects a PostgreSQL database.

> Ignore the `frontend/` folder for backend setup.

## Important folders

- `backend/` — backend source code
- `backend/.env` — environment variables for the backend

## Backend setup

1. Open a terminal and go to the backend folder:

```powershell
cd backend
```

2. Activate the virtual environment if it exists:

```powershell
venv\Scripts\activate
```

3. Install backend dependencies:

```powershell
pip install -r requirements.txt
```

## Environment variables

The backend reads configuration from `backend/.env`.

Expected values include:

- `DATABASE_URL` — PostgreSQL connection string
- `SECRET_KEY` — JWT secret key
- `ALGORITHM` — JWT algorithm
- `ACCESS_TOKEN_EXPIRE_MINUTES` — token expiration time

Example from `backend/.env`:

```text
DATABASE_URL=postgresql://pentagon:pentagon123@localhost:5432/pentagondb
SECRET_KEY=supersecretkey123changethislater
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

## Run PostgreSQL in Docker

The backend currently expects PostgreSQL on `localhost:5432` with the database name `pentagondb`.

Use this Docker command to create and run the database container:

```powershell
docker run --name pentagon-db -e POSTGRES_USER=pentagon -e POSTGRES_PASSWORD=pentagon123 -e POSTGRES_DB=pentagondb -p 5432:5432 -d postgres:15
```

If the container already exists, start it with:

```powershell
docker start pentagon-db
```

## Run the backend

From `backend/`:

```powershell
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Then visit:

- `http://localhost:8000/`
- `http://localhost:8000/docs` for the FastAPI Swagger UI

## Notes

- The backend automatically creates database tables via SQLAlchemy models on startup.
- If you want a project-level `requirements.txt`, add it later in `backend/`.
