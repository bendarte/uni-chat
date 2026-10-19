# Backlog

Findings that are out of scope for the step they were discovered in. Each entry names where it came from.

## Data and ingestion

- **`bootstrap_data.py` is not idempotent.** On a database that already holds data it live-crawls antagning.se, embeds whatever it finds (387 programmes on 2026-10-19), republishes the Qdrant alias to that smaller collection and leaves Postgres with both the old and the new rows. Postgres and Qdrant end up out of sync by a factor of ten. See `docs/AUDIT.md`, section Stack. *(found in step 01)*
- **No scheduled re-ingest.** Programme data goes stale with no job to refresh it. *(found in step 01)*
- **`Program` has no field for credits, start week, entry requirements, application code or tuition**, although the source CSV carries them. Needed for richer cards in steps 08–09. *(found in step 01)*
- **No database migrations.** The schema is created with `Base.metadata.create_all()` at startup (`backend/app/main.py:104`). The first column change in production will need Alembic. *(found in step 01)*
- **`import_antagning.py` never removes programmes that disappeared from antagning.se.** It inserts new rows and embeds everything in Postgres, so the catalogue only ever grows. `load_dataset.py` has `delete_stale_programs()` with a safety ratio; the real importer has no equivalent. *(found in step 01b)*
- **`normalize_city()` does not map English city names.** `Gothenburg`, `Malmo`, `Jonkoping` and `Gavle` pass through unchanged, so rows written by the crawl path show up as separate cities next to `Göteborg`, `Malmö`, `Jönköping` and `Gävle` in the filter list. *(found in step 01b)*
- **`QDRANT_PUBLISH_MIN_RATIO` in `load_dataset.py` compares embedded rows against fetched rows**, which is self-referential: a capped crawl always passes it. The real protection now lives in `publish_program_collection()`; decide whether the old check still earns its place. *(found in step 01b)*
- **`run_full_test.py` judges source URLs with HEAD only**, so a server answering 405 Method Not Allowed is reported as broken (`https://www.hkr.se/program/LLK1U`). It should fall back to GET. *(found in step 01)*

## Configuration and tooling

- **Widen the ruff rule set.** `backend/ruff.toml` now pins `target-version = "py39"`, 130 columns and ruff's default rules plus import sorting, which the backend passes cleanly. Adding bugbear, simplify and RUF would surface roughly 35 more findings, 12 of them `RUF012` mutable class defaults that are worth fixing. The pyupgrade rules (315 `UP006`, 110 `UP045` in `app/` alone) depend on a decision first: raise the local virtualenv from 3.9.6 to the 3.11 the container runs, or leave the annotations as they are. Note that `B008` must stay ignored — FastAPI's `Depends()` in argument defaults is the framework's idiom. *(found in step 01, narrowed in step 01b)*
- **`ruff` is missing from `requirements-dev.txt`**, which only lists pytest and pytest-mock. *(found in step 01)*
- **Python version mismatch.** Tests run on 3.9.6 locally, the container runs 3.11 (`backend/Dockerfile:1`). *(found in step 01)*
- **`npm run build` silently depends on a live backend.** Without one, static generation throws two `TypeError: fetch failed` and still exits 0, producing empty pages. *(found in step 01)*
- **Empty `.env` in the repo root.** Zero bytes, unused by `docker-compose.yml` (which reads `backend/.env`). Remove it or document it. *(found in step 01)*
- **API keys are only validated when `APP_ENV=production`** (`backend/app/config.py:43-46`), and `APP_ENV` defaults to `development`. A deploy that forgets the variable starts without keys, silently. *(found in step 01)*
- **httpx deprecation in 7 tests.** `tests/test_program_router.py` uses the deprecated `app=` shortcut; move to `transport=WSGITransport(app=...)`. *(found in step 01)*

- **Next.js 14 is end of life.** 14.2.35 is the last release in the line (it is what the `next-14` dist-tag points at), and `npm audit --omit=dev` still reports 1 critical and 1 high against it, including a bundled `postcss` 8.4.31. Neither can be fixed inside 14.x; the only remedy is 15.x, where the current release is 15.5.28. Plan the major upgrade in step 06, with CI in place to catch regressions. *(found in step 01b)*

## API and frontend

- **The chat proxy forwards raw Pydantic 422 payloads to the browser.** An empty message returns `{"detail":[{"type":"string_too_short",...}]}` with a link to errors.pydantic.dev. Needs a Swedish user-facing message. *(found in step 01)*
- **`/api/system/status` reports `programs` and `vector_chunks` without flagging a mismatch**, so a ten-fold divergence looks healthy. *(found in step 01)*
- **`questions` is almost always empty.** Across seven successful smoke queries the backend returned follow-up questions only for nonsense input. Rendering them in the frontend is pointless until generation improves. *(found in step 01)*

## README

- **Hardcoded local path** in `README.md:142`: `cd /Users/osman/ws/ai-tools/uni-chat && ...`. *(found in step 01)*
- **Exclusions are read as positive filters.** `POST /chat {"message": "sjuksköterska men inte i Stockholm"}` returns `active_filters.city = "Stockholm"` and a single recommendation at Karolinska Institutet in Stockholm, which is not a nursing programme either. The README claim about exclusion handling has been corrected to say so; step 02 fixes the behaviour. *(found in step 01)*
