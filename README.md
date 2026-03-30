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
- `AWS_ACCESS_KEY_ID` — AWS access key for Bedrock (Claude integration)
- `AWS_SECRET_ACCESS_KEY` — AWS secret access key for Bedrock
- `AWS_REGION` — AWS region (e.g., `us-east-1`)

Example from `backend/.env`:

```text
DATABASE_URL=postgresql://pentagon:pentagon123@localhost:5432/pentagondb
SECRET_KEY=supersecretkey123changethislater
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
AWS_ACCESS_KEY_ID=your_access_key_here
AWS_SECRET_ACCESS_KEY=your_secret_access_key_here
AWS_REGION=us-east-1
```

### AWS Bedrock Setup

The backend uses AWS Bedrock to call Claude for intelligent hyperparameter suggestions. To enable this:

1. Create AWS credentials with permissions for `bedrock:InvokeModel`
2. Fill in the AWS credentials in `backend/.env`:
   - `AWS_ACCESS_KEY_ID` — your AWS access key
   - `AWS_SECRET_ACCESS_KEY` — your AWS secret access key
   - `AWS_REGION` — your preferred AWS region

If AWS credentials are not configured, the backend will fall back to default hyperparameter values.

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
- **Important:** `bcrypt` is pinned to version 4.0.1 for passlib compatibility. Do not upgrade without testing.
- AWS Bedrock integration requires valid AWS credentials to enable Claude-based hyperparameter suggestions.
