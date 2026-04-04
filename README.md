# Pentagon Backend

This repository contains the backend API for the Pentagon (FusionAI) project — an AI-powered web platform for training image semantic segmentation models using a Teacher-Student knowledge distillation approach. The backend is implemented in Python using FastAPI and SQLAlchemy, with PostgreSQL as the database.

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

| Variable | Description | Required |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string | Yes |
| `SECRET_KEY` | JWT secret key (used for local auth) | Yes |
| `ALGORITHM` | JWT algorithm (default: `HS256`) | Yes |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token expiration time in minutes | Yes |
| `AWS_REGION` | AWS region (e.g., `ap-south-1`) | Yes |
| `AWS_LAMBDA_URL` | Lambda URL for Claude hyperparameter suggestions | Optional |
| `COGNITO_USER_POOL_ID` | Cognito User Pool ID | Optional |
| `COGNITO_APP_CLIENT_ID` | Cognito App Client ID | Optional |
| `COGNITO_APP_CLIENT_SECRET` | Cognito App Client Secret | Optional |

Example `backend/.env`:

```text
DATABASE_URL=postgresql://pentagon:pentagon123@localhost:5432/pentagondb
SECRET_KEY=supersecretkey123changethislater
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
AWS_REGION=ap-south-1
AWS_LAMBDA_URL=https://your-lambda-url.lambda-url.region.on.aws/
COGNITO_USER_POOL_ID=your_user_pool_id_here
COGNITO_APP_CLIENT_ID=your_app_client_id_here
COGNITO_APP_CLIENT_SECRET=your_app_client_secret_here
```

## Authentication

The backend supports two auth modes, determined automatically at startup:

### Local Auth (default)
When `COGNITO_USER_POOL_ID` and `COGNITO_APP_CLIENT_ID` are set to placeholder values or not set, the backend uses its own JWT-based auth with bcrypt password hashing. No external services needed.

### AWS Cognito Auth
When valid Cognito credentials are provided, the backend delegates authentication to AWS Cognito:

- **Register** — Calls Cognito `sign_up`. A verification code is sent to the user's email.
- **Verify Email** — Calls Cognito `confirm_sign_up` with the 6-digit code the user received.
- **Resend Code** — Calls Cognito `resend_confirmation_code` if the code expired.
- **Login** — Calls Cognito `initiate_auth` with `USER_PASSWORD_AUTH`, returns the Cognito ID token. If the user hasn't verified their email, returns a 403 error.
- **Token verification** — Validates Cognito JWTs using the User Pool's JWKS endpoint (RS256). Keys are cached after first fetch.
- **User linking** — On first Cognito login, a local user record is auto-created and linked via `cognito_sub`.
- **SECRET_HASH** — Automatically computed and sent with all Cognito API calls when `COGNITO_APP_CLIENT_SECRET` is configured.

To enable Cognito:

1. Create a Cognito User Pool with email as the sign-in identifier
2. Create an App Client with `ALLOW_USER_PASSWORD_AUTH` enabled
3. Replace the placeholder values in `.env` with your real credentials
4. Run the database migration (see below)
5. Restart the backend

### Claude Hyperparameter Suggestions

The backend uses an AWS Lambda function to call Claude for intelligent hyperparameter suggestions. Set `AWS_LAMBDA_URL` in `.env` to enable this. If not configured, the backend falls back to default hyperparameter values.

## Run PostgreSQL in Docker

The backend expects PostgreSQL on `localhost:5432` with the database name `pentagondb`.

Create and run the database container:

```powershell
docker run --name pentagon-db -e POSTGRES_USER=pentagon -e POSTGRES_PASSWORD=pentagon123 -e POSTGRES_DB=pentagondb -p 5432:5432 -d postgres:15
```

If the container already exists, start it with:

```powershell
docker start pentagon-db
```

## Database migrations

The backend auto-creates tables on startup via `Base.metadata.create_all`. However, when new columns are added to existing tables, you need to run manual migrations.

### Add Cognito support columns:

```powershell
docker exec -it pentagon-db psql -U pentagon -d pentagondb -c "ALTER TABLE users ADD COLUMN IF NOT EXISTS cognito_sub VARCHAR UNIQUE; ALTER TABLE users ALTER COLUMN hashed_password DROP NOT NULL;"
```

### Add classes column to sessions:

```powershell
docker exec -it pentagon-db psql -U pentagon -d pentagondb -c "ALTER TABLE sessions ADD COLUMN IF NOT EXISTS classes VARCHAR;"
```

## Run the backend

From `backend/`:

```powershell
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Then visit:

- `http://localhost:8000/` — health check
- `http://localhost:8000/docs` — FastAPI Swagger UI

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/auth/register` | Register a new user (sends verification code via Cognito) |
| `POST` | `/auth/confirm` | Verify email with 6-digit code |
| `POST` | `/auth/resend-code` | Resend verification code |
| `POST` | `/auth/login` | Login and get access token |
| `GET` | `/sessions` | List all sessions for current user |
| `POST` | `/sessions` | Create a new session (deduplicates by name + task) |
| `GET` | `/sessions/{id}` | Get session details |
| `DELETE` | `/sessions/{id}` | Delete a session |
| `PATCH` | `/sessions/{id}/status` | Update session status |
| `POST` | `/sessions/{id}/apikey` | Generate API key for a session |
| `POST` | `/sessions/{id}/upload` | Register dataset info |
| `GET` | `/sessions/{id}/model/download` | Download trained model |
| `POST` | `/sessions/suggest-hyperparameters` | Get Claude-suggested hyperparameters |

## Notes

- **bcrypt** is pinned to version 4.0.1 for passlib compatibility. Do not upgrade without testing.
- **boto3** is required for Cognito integration.
- CORS is configured to allow both port 5173 (Vite dev) and port 3000.
- The frontend communicates via REST API and WebSocket for real-time training metrics.
- Cognito free tier covers 50,000 MAUs — more than enough for development and hackathon use.
