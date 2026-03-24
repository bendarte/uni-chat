# UniChat

UniChat är en svensk sök- och rådgivningsapp för universitetsutbildningar.
Frontend är byggd i Next.js och skickar server-side requests till en FastAPI-backend.
Backendet använder Postgres för programdata, Qdrant för semantisk sökning och Redis för sessioner/rate limiting.
Retrieval drivs av LLM query expansion, med keyword-taxonomy som komplement till vektor- och SQL-sökning.
Systemet är uppdelat för att kunna köras lokalt med Docker Compose och deployas separat till Vercel och Railway.

## Tech stack

- Frontend: Next.js 14, React 18, TypeScript, Tailwind CSS
- Backend: FastAPI, SQLAlchemy, Pydantic
- Data: PostgreSQL, Qdrant, Redis
- Modellintegration: OpenAI embeddings + chat
- Drift: Docker Compose lokalt, Vercel för frontend, Railway för backend

## Lokalt

### 1. Förbered miljövariabler

Skapa `backend/.env` och `frontend/.env.local`.

Backend behöver minst:

```env
APP_ENV=development
BACKEND_API_KEY=change-me
OPENAI_API_KEY=change-me
POSTGRES_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/university_ai
REDIS_URL=redis://localhost:6379
QDRANT_URL=http://localhost:6333
CORS_ALLOWED_ORIGINS=http://localhost:3000
```

Frontend behöver minst:

```env
BACKEND_URL=http://localhost:8000
BACKEND_API_KEY=change-me
```

### 2. Starta backend-stack

```bash
docker compose up -d --build
```

Verifiera:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

### 3. Bootstrapa data och embeddings

```bash
docker compose exec -T backend python scripts/bootstrap_data.py
```

### 4. Starta frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend kör då på `http://localhost:3000`.

## Viktiga endpoints

- `GET /health` — liveness
- `GET /ready` — readiness mot Postgres, Redis och Qdrant
- `POST /chat` — primär chat-endpoint
- `POST /api/chat` — legacy-format för äldre klienter
- `GET /programs/cities` — städer till filterpanelen

## Kvalitetskontroller

```bash
cd frontend && npm run lint
cd frontend && npm run build
cd /Users/osman/ws/ai-tools/uni-chat && backend/.venv/bin/pytest backend/tests
```

Lokala kvalitetskommandon finns också i `.claude/commands/`:

- `/test-retrieval`
- `/test-filters`
- `/diagnose "<fråga>"`
