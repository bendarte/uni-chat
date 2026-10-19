# Backlog

Findings that are out of scope for the step they were discovered in. Each entry names where it came from.

## Data and ingestion

- **`bootstrap_data.py` is not idempotent.** On a database that already holds data it live-crawls antagning.se, embeds whatever it finds (387 programmes on 2026-10-19), republishes the Qdrant alias to that smaller collection and leaves Postgres with both the old and the new rows. Postgres and Qdrant end up out of sync by a factor of ten. See `docs/AUDIT.md`, section Stack. *(found in step 01)*
- **No scheduled re-ingest.** Programme data goes stale with no job to refresh it. *(found in step 01)*
- **`Program` has no field for credits, start week, entry requirements, application code or tuition**, although the source CSV carries them. Needed for richer cards in steps 08–09. *(found in step 01)*
- **No database migrations.** The schema is created with `Base.metadata.create_all()` at startup (`backend/app/main.py:104`). The first column change in production will need Alembic. *(found in step 01)*
- **`run_full_test.py` judges source URLs with HEAD only**, so a server answering 405 Method Not Allowed is reported as broken (`https://www.hkr.se/program/LLK1U`). It should fall back to GET. *(found in step 01)*

## Configuration and tooling

- **No ruff configuration in the repo.** The 811 findings from step 01 come from ruff's defaults, so the number is not reproducible in CI. Check in a config and decide `target-version`: 479 UP006 and 146 UP045 findings only apply from Python 3.10 in annotations, and the local venv runs 3.9.6. *(found in step 01)*
- **`ruff` is missing from `requirements-dev.txt`**, which only lists pytest and pytest-mock. *(found in step 01)*
- **Python version mismatch.** Tests run on 3.9.6 locally, the container runs 3.11 (`backend/Dockerfile:1`). *(found in step 01)*
- **`npm run build` silently depends on a live backend.** Without one, static generation throws two `TypeError: fetch failed` and still exits 0, producing empty pages. *(found in step 01)*
- **Empty `.env` in the repo root.** Zero bytes, unused by `docker-compose.yml` (which reads `backend/.env`). Remove it or document it. *(found in step 01)*
- **API keys are only validated when `APP_ENV=production`** (`backend/app/config.py:43-46`), and `APP_ENV` defaults to `development`. A deploy that forgets the variable starts without keys, silently. *(found in step 01)*
- **httpx deprecation in 7 tests.** `tests/test_program_router.py` uses the deprecated `app=` shortcut; move to `transport=WSGITransport(app=...)`. *(found in step 01)*

## API and frontend

- **The chat proxy forwards raw Pydantic 422 payloads to the browser.** An empty message returns `{"detail":[{"type":"string_too_short",...}]}` with a link to errors.pydantic.dev. Needs a Swedish user-facing message. *(found in step 01)*
- **`/api/system/status` reports `programs` and `vector_chunks` without flagging a mismatch**, so a ten-fold divergence looks healthy. *(found in step 01)*
- **`questions` is almost always empty.** Across seven successful smoke queries the backend returned follow-up questions only for nonsense input. Rendering them in the frontend is pointless until generation improves. *(found in step 01)*

## README

- **Hardcoded local path** in `README.md:142`: `cd /Users/osman/ws/ai-tools/uni-chat && ...`. *(found in step 01)*
- **The README claims deterministic guardrails for exclusions**, which step 01 disproved ("sjuksköterska men inte i Stockholm" returns a Stockholm programme). Fix the behaviour or the claim. *(found in step 01)*
