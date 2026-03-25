# UniChat

UniChat is an AI-powered study advisor for Swedish higher education programs. Users can describe a goal, subject, city, or set of constraints in natural language and get ranked programme recommendations with grounded explanations.

Live demo: `https://uni-chat-mu.vercel.app`

## What It Does

- natural-language programme search with multi-turn chat
- live filters for city, level, language, and study pace
- semantic retrieval backed by embeddings and vector search
- deterministic guardrails for hard constraints such as university and exclusions
- grounded recommendation explanations based on retrieved programme metadata

## Architecture

UniChat combines a Next.js frontend with a FastAPI backend.

- `frontend/`
  Next.js 14, React 18, TypeScript, Tailwind CSS
- `backend/`
  FastAPI, SQLAlchemy, Pydantic
- `data layer`
  PostgreSQL for programme records, Redis for session/rate-limiting state, Qdrant for vector search
- `model integration`
  OpenAI embeddings and chat models

The backend uses a retrieval pipeline where programme data is crawled, normalized, stored in PostgreSQL, indexed as embeddings in Qdrant, and then retrieved through a context-enriched query built from both the current user message and prior session state.

## Key Features

- RAG-based programme retrieval for Swedish university search
- multi-turn conversational guidance with persistent session context
- filter sync between sidebar state and extracted chat constraints
- recommendation reranking, deduplication, and constraint handling
- normalized city and university labels across ingestion, retrieval, and UI
- production deployment on Vercel and Railway

## Local Development

### 1. Configure environment variables

Create `backend/.env` and `frontend/.env.local`.

Backend:

```env
APP_ENV=development
BACKEND_API_KEY=change-me
ADMIN_API_KEY=change-me-admin
OPENAI_API_KEY=change-me
POSTGRES_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/university_ai
REDIS_URL=redis://localhost:6379
QDRANT_URL=http://localhost:6333
CORS_ALLOWED_ORIGINS=http://localhost:3000
```

Frontend:

```env
BACKEND_URL=http://localhost:8000
BACKEND_API_KEY=change-me
```

### 2. Start the local stack

```bash
docker compose up -d --build
```

Verify:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

### 3. Bootstrap programme data

```bash
docker compose exec -T backend python scripts/bootstrap_data.py
```

### 4. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

## Useful Endpoints

- `GET /health`
- `GET /ready`
- `POST /chat`
- `GET /api/system/status`
- `GET /programs/cities`

## Quality Checks

```bash
cd frontend && npm run build
cd /Users/osman/ws/ai-tools/uni-chat && backend/.venv/bin/pytest backend/tests
```
