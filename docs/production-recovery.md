# UniChat production recovery (Vercel + Railway)

This is an operational checklist. It does **not** claim the live service is healthy; check the deployment logs before changing any configuration. Never paste secrets into tickets, PRs, logs or screenshots.

## 1. Identify the failing layer

- Open the Vercel deployment for `uni-chat-mu.vercel.app` and inspect **Function Logs** for `/api/system/status` and `/api/chat`. Make sure the latest deployment is **Ready**.
- Check the Railway **backend** service status, its latest deployment and application logs.
- On Railway, visit `https://<your-backend-domain>/health` and `https://<your-backend-domain>/ready` (replace with the real configured domain). The latter must return HTTP 200 and `ready:true`.
- A 200 from `/health` but 503 from `/ready` points to a dependency issue (PostgreSQL, Redis or Qdrant). A failed `/health` points to the app not starting, or its routing being unavailable.
- Check the Vercel frontend route `/api/system/status`: HTTP 200 + `ready:true` indicates that the proxy can reach backend and all required dependencies. HTTP 503 means the end-to-end check failed; check logs for which hop.

## 2. Confirm configuration without sharing secret values

Vercel frontend, **server-side** environment variables:

- `BACKEND_URL`: actual public Railway backend HTTPS URL; never localhost
- `BACKEND_API_KEY`: must match Railway's value exactly

Railway backend environment variables:

- `APP_ENV=production`
- `BACKEND_API_KEY`: non-empty (matching Vercel)
- `ADMIN_API_KEY`: non-empty (never expose publicly)
- `POSTGRES_URL`, `REDIS_URL`, `QDRANT_URL`: real reachable service connection strings
- `OPENAI_API_KEY` for embeddings / LLM requests
- `CORS_ALLOWED_ORIGINS` should match the expected frontend origin (though Vercel proxies most calls server-side)

The backend's Dockerfile and Procfile expect `backend/` as their working project root and run `uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}`.

Do not paste or commit credentials. If any credentials were exposed, rotate them.

## 3. Interpret common errors

| Symptom | Likely check |
| --- | --- |
| Vercel frontend loads but shows backend unavailable | Inspect `BACKEND_URL`, Railway service deployment, `/ready` |
| Railway deployment crashes before healthcheck | Check logs for database connection errors, missing env or import errors |
| `/health` = 200, `/ready` = 503 | Check PostgreSQL, Redis, Qdrant; inspect `/ready` response only via trusted channel |
| `/ready` = 200, frontend still 503 | Compare `BACKEND_URL`, `BACKEND_API_KEY` and latest Vercel deployment; redeploy after env changes |
| Frontend status 200, chat 401/503 | Backend API key mismatch or backend error. Check corresponding logs |
| Chat works but returns no recommendations | Verify `/api/system/status` index/program counts and data ingestion health |

## 4. Recover safely

1. Restore or restart an unhealthy Railway backend service and its dependencies from the provider dashboard.
2. Validate health **before** backfilling any data. Do not delete or recreate production PostgreSQL/Qdrant collections without a verified backup.
3. Correct mismatched Vercel env values, then redeploy Vercel after changes.
4. Smoke-test home page, readiness endpoint, a normal Swedish programme request, and source-link results.
5. Confirm logs contain no secrets and the status endpoint no longer serves cached successful answers.

## 5. Follow-up code quality work

- Refactor `backend/app/services/chat_service.py` (2k+ lines) into smaller intent/state/recommendation modules, with tests before each extraction.
- Add retrieval evals with answer relevance, constraint compliance, and source-link validity.
- Add full backend integration tests against ephemeral PostgreSQL, Redis and Qdrant in CI; current PR first adds frontend build/lint + Python syntax checks.

