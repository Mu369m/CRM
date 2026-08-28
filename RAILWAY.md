# Railway deployment

Deploy this repository as two Railway services from the same GitHub repo.

## API service

Set the service root directory to `/backend`. Railway will use `backend/railway.json` and `backend/Dockerfile`.

Required variables:

- `DATABASE_URL`: Railway PostgreSQL connection string converted to `postgresql+asyncpg://...`
- `REDIS_URL`: Railway Redis connection string
- `JWT_SECRET`: long random secret
- `FIELD_ENCRYPTION_KEY`: URL-safe base64 encoding of exactly 32 random bytes
- `WEBHOOK_SIGNING_SECRET`: long random secret
- `CORS_ORIGINS`: JSON array containing the frontend public URL
- `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND`: Redis URLs for worker results

The API runs `alembic upgrade head` before Uvicorn and exposes `/health`.

## Web service

Set the service root directory to `/frontend`. Railway will use `frontend/railway.json` and `frontend/Dockerfile`.

Required variable:

- `NEXT_PUBLIC_API_URL`: public URL of the API service, for example `https://crm-api-production.up.railway.app`

## Worker service

Create a third service with root directory `/backend`, use the same backend Dockerfile, and override the start command:

```text
celery -A app.worker:celery_app worker --loglevel=INFO --concurrency=4
```

Set the same Redis variables as the API service. Do not expose a public domain for the worker.

## Managed services

Add Railway PostgreSQL and Redis plugins to the project. Use their injected connection variables rather than committing credentials. n8n should be deployed separately with persistent storage if automation workflows are required.
