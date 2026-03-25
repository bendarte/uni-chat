# Deploy

Den här guiden utgår från:

- backend på Railway
- frontend på Vercel
- samma repo för båda

Målet är att få upp en stabil release med tydlig bootstrap och enkel rollback.

## Översikt

Ordningen är:

1. Lägg in miljövariabler
2. Deploya backend till Railway
3. Kör bootstrap för schema + data + embeddings
4. Verifiera backend med `/health` och `/ready`
5. Deploya frontend till Vercel
6. Verifiera hela flödet

## Produktionsvariabler

Sätt dessa i respektive plattform:

### Backend

- `APP_ENV=production`
- `BACKEND_API_KEY=<stark hemlig nyckel>`
- `OPENAI_API_KEY=<din OpenAI-nyckel>`
- `POSTGRES_URL=<Railway Postgres-URL>`
- `REDIS_URL=<Railway Redis-URL>`
- `QDRANT_URL=<publik eller privat Qdrant-URL>`
- `CORS_ALLOWED_ORIGINS=<din Vercel-domän, kommaseparerad om flera>`

### Frontend

- `BACKEND_URL=<din Railway-backend, t.ex. https://uni-chat-backend.up.railway.app>`
- `BACKEND_API_KEY=<samma BACKEND_API_KEY som backend använder>`

## Backend på Railway

### 1. Skapa projektet

1. Logga in på Railway.
2. Skapa ett nytt projekt från GitHub-repot.
3. Sätt **Root Directory** till `backend`.
4. Railway använder då `backend/Procfile`.

### 2. Lägg till tjänster

Lägg till eller koppla:

- PostgreSQL
- Redis
- Qdrant

Om Qdrant inte körs i Railway behöver du sätta `QDRANT_URL` till den externa instansen.

### 3. Lägg in miljövariabler

Sätt alla backend-variabler från listan ovan innan första deploy.

### 4. Deploya

Railway deployar automatiskt efter push eller manuell redeploy.

### 5. Verifiera backend

När deployen är klar:

```bash
curl https://DIN-BACKEND-DOMÄN/health
curl https://DIN-BACKEND-DOMÄN/ready
```

Förväntat:

- `/health` returnerar `{"status":"ok"}`
- `/ready` returnerar `200` och alla dependencies som `ok: true`

## Bootstrap av data och embeddings

Kör bootstrap separat från webprocessen. Webappen bootstrapar inte längre data vid startup.

### Rekommenderad ordning

1. DB up
2. Schema
3. Data ingest
4. Embeddings till Qdrant
5. Backend live

### Kommando

Kör samma miljövariabler som backend använder och kör:

```bash
cd backend
python scripts/bootstrap_data.py
```

I Railway kan det göras via shell/one-off command i backendmiljön.

Verifiera efter bootstrap:

- `GET /ready` ger `200`
- chatten returnerar rekommendationer
- länkar i rekommendationerna är riktiga programlänkar

## Data-backfill och Qdrant-republish

Använd detta när du har lagt till ny normaliseringslogik för fält som redan finns i Postgres, till exempel `university` eller `city`.

### När det behövs

- samma lärosäte visas under flera namn i rekommendationer
- felaktiga city-värden har lagrats historiskt
- Qdrant använder payloads eller embeddings byggda från äldre, sämre metadata

### Säker ordning

1. Kör alltid dry-run först
2. Kontrollera att antalet uppdateringar ser rimligt ut
3. Kör skarp backfill mot Postgres
4. Republish:a Qdrant från den normaliserade databasen
5. Kör samma dry-run igen och verifiera att `updated` är `0`
6. Smoke-testa chatten och `/programs/cities`

### Dry-run

Kör i samma miljö som backend använder:

```bash
cd backend
python scripts/backfill_university_labels.py --field both --dry-run --json
```

Byt `both` mot `university` eller `city` om du bara vill backfilla ett fält.

Förväntat:

- JSON med `checked`
- JSON med `updated`
- lista över vilka rader som skulle ändras

### Skarp körning utan Qdrant

Om du först vill uppdatera bara Postgres:

```bash
cd backend
python scripts/backfill_university_labels.py --field both --json
```

### Skarp körning med Qdrant-republish

När du vill bygga om vektorlagret från den redan normaliserade databasen:

```bash
cd backend
python scripts/backfill_university_labels.py --field both --republish-qdrant --json
```

Detta gör följande:

- uppdaterar historiska rader i Postgres
- bygger en ny Qdrant-collection från den normaliserade datan
- flyttar aliaset `programs_active` till den nya collectionen
- tar bort föregående aktiva collection när publishen lyckats

### Efterkontroller

Kör samma dry-run igen:

```bash
cd backend
python scripts/backfill_university_labels.py --field both --dry-run --json
```

Förväntat efter en lyckad körning:

- `updated: 0`

Kontrollera sedan:

```bash
curl https://DIN-BACKEND-DOMÄN/ready
curl -H "X-API-Key: ..." https://DIN-BACKEND-DOMÄN/programs/cities
```

Och smoke-testa minst:

- ett universitet med tidigare aliasproblem, till exempel Chalmers eller Göteborgs universitet
- en city-fråga där felaktiga landvärden tidigare förekom
- en vanlig chatfråga med 3–5 rekommendationer

### Driftanteckningar

- kör helst detta i en one-off shell eller jobbmiljö, inte i webprocessen
- Qdrant-republish gör OpenAI-embeddings och kan ta några minuter beroende på datamängd
- kör först i staging om du är osäker på antal uppdateringar eller kostnad
- om dry-run visar oväntat många ändringar, stoppa och kontrollera normaliseringsreglerna innan skarp körning

## Frontend på Vercel

### 1. Skapa projektet

1. Logga in på Vercel.
2. Importera samma GitHub-repo.
3. Sätt **Root Directory** till `frontend`.
4. Vercel läser då `frontend/vercel.json`.

### 2. Lägg in miljövariabler

Sätt:

- `BACKEND_URL`
- `BACKEND_API_KEY`

### 3. Deploya

Kör första deploymenten och notera din Vercel-domän.

### 4. Uppdatera CORS i backend

Sätt `CORS_ALLOWED_ORIGINS` i Railway till din Vercel-domän, till exempel:

```env
CORS_ALLOWED_ORIGINS=https://uni-chat.vercel.app
```

Om du använder preview-domäner kan du lägga flera origins kommaseparerat.

## Slutlig verifiering

När båda sidorna är deployade:

1. Öppna frontend i webbläsaren.
2. Skriv en vanlig fråga, till exempel `jag vill bli läkare`.
3. Kontrollera att svar och rekommendationer visas.
4. Testa filter för stad, nivå och språk.
5. Testa ämnesbyte i samma session, till exempel `jag vill bli läkare` följt av `börja om` och sedan `jag vill läsa ekonomi`.
6. Klicka på minst två länkar i rekommendationerna.
7. Kontrollera backend:

```bash
curl https://DIN-BACKEND-DOMÄN/health
curl https://DIN-BACKEND-DOMÄN/ready
```

8. Kör lokala regressionskommandon mot den deployade backenden om du har åtkomst:

```bash
cd backend
BACKEND_BASE_URL=https://DIN-BACKEND-DOMÄN BACKEND_API_KEY=... .venv/bin/python scripts/verify_chat.py
```

## Rollback

Om senaste releasen är trasig:

### Backend

1. Öppna Railway.
2. Gå till tidigare lyckad deployment.
3. Redeploya den versionen.
4. Verifiera `/health` och `/ready`.

### Frontend

1. Öppna Vercel.
2. Välj senaste fungerande deploymenten.
3. Promote eller redeploya den versionen.

### Efter rollback

Kör alltid:

```bash
curl https://DIN-BACKEND-DOMÄN/health
curl https://DIN-BACKEND-DOMÄN/ready
```

Och testa minst ett helt användarflöde i webbläsaren.

## Checklista före release

- Backend deployad på Railway
- Frontend deployad på Vercel
- `BACKEND_API_KEY` satt i båda miljöerna
- `CORS_ALLOWED_ORIGINS` pekar på Vercel-domänen
- `bootstrap_data.py` körd med riktiga produktionsvariabler
- `/health` och `/ready` gröna
- Chat, filter, ämnesbyte och länkar testade i webbläsaren
- Senaste fungerande deployment identifierad för rollback
