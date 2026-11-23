# UniChat on Oracle Cloud Always Free

This is a **deployment template**, not a live deployment. No OCI account, domain, DNS record, secret or running instance has been provisioned by this PR.

## Architecture

- Vercel: existing Next.js frontend
- Oracle Linux/Ubuntu ARM VM: Docker Compose for FastAPI, PostgreSQL, Redis, Qdrant
- Caddy: automatic TLS on a dedicated API subdomain
- **Only TCP 80/443 publicly accessible; never expose database, Redis, Qdrant or FastAPI ports.**
- Vercel server-side `BACKEND_URL` points to `https://<your-api-domain>` and `BACKEND_API_KEY` matches the VM value.

## Create the VM

1. Create an OCI Ampere A1 (VM.Standard.A1.Flex) instance in your home region, using **Always Free eligible** Ubuntu ARM64, at most 2 OCPU / 12 GB RAM total for the tenancy.
2. Assign a reserved public IPv4 (only within current free limits). Add DNS A record for a subdomain you own.
3. OCI VCN ingress: allow TCP 80 and 443 from the internet; allow SSH TCP 22 **only from your own IP**. Do not allow 5432, 6379, 6333 or 8000 publicly.
4. Install Docker Engine + Docker Compose plugin on Ubuntu and keep security updates enabled.
5. `git clone https://github.com/bendarte/uni-chat.git` (or check out this PR branch until merged).
6. `cd uni-chat/deploy/oci && cp .env.example .env`; edit `.env` securely, using separate strong secrets.
7. Confirm `POSTGRES_PASSWORD` and the password embedded in `POSTGRES_URL` are **identical**, then run:
   `docker compose --env-file .env config --quiet`
   `docker compose --env-file .env up -d --build`
8. Verify `https://<your-api-domain>/health` responds 200 and `/ready` responds 200 with `ready:true`. Start or re-run ingestion if the database is empty; a healthy empty database **does not imply working search**.
9. Update Vercel's server-side `BACKEND_URL` and `BACKEND_API_KEY`, redeploy, test `/api/system/status` and a full chat with recommendations and source links.

## Data migration is required

The old Railway storage does **not** move automatically. Back up and restore PostgreSQL, and restore or rebuild Qdrant indexes. Preserve the **same embedding provider and vector dimension** when restoring old indexes. If changing provider/model, create a new index and re-embed the original records, then publish the new alias; do not silently mix embeddings.

The bundled backend requires `OPENAI_API_KEY` to generate OpenAI embeddings in the current code. Docker/Oracle Always Free **does not** make paid external AI APIs free. Treat switching to local embeddings as a separate, tested migration.

## Operations

- `docker compose ps`
- `docker compose logs --tail=100 backend`
- `docker compose logs --tail=100 qdrant postgres redis caddy`
- `docker compose exec -T postgres pg_dump -U unichat -d university_ai > unichat-backup.sql` (store backups **encrypted, off the VM**)
- Back up Qdrant with Qdrant snapshots; retain copies outside the VM.
- Keep Docker images patched, record the version used, verify ARM64 support.
- Monitor disk/memory usage; Oracle may reclaim idle Always Free instances, and availability is not guaranteed.
- Do not share `.env`, logs containing secrets or private datasets.

## Configuration safety

Caddy requests TLS certificates only after DNS and ports 80/443 are set correctly. If the server needs to restart before Qdrant is ready, the backend uses `restart: unless-stopped` and should recover when dependencies become available. Inspect its logs rather than blindly re-running ingestion.

**CI passing is not proof that the public service is up.**
