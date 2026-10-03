# Deployment (₹0 / free tiers)

**Free tiers change often. The facts below were checked in early October 2026; re-check each provider's
pricing page before relying on them, and treat nothing here as permanently free.**

## Architecture
```
Browser --HTTPS--> Render free web service (one Docker container: React build + FastAPI)
                         |
                         +--> Neon free PostgreSQL (external, TLS)
                         +--> inference: MOCK model (public demo). Real models run locally.
```
One service means one URL and no CORS configuration. Components are still separable: the database is just
`DATABASE_URL`, and inference is just `MODEL_PROVIDER`.

## What the public demo is (and is not)
- `MODEL_PROVIDER=mock`: outputs are deterministic placeholders, labelled DEMO / MOCK DATA everywhere. The public
  site demonstrates the platform, not real LLM behavior. Real experiments: run locally with Ollama or a local model.
- `PUBLIC_DEMO_MODE=true`: max 40 runs per experiment, 20 write requests per minute per IP, 300 experiments total.
- Not built yet (Phase 6): user accounts and private experiments. Everyone sees the same public data.

## Steps
1. **GitHub.** Create an empty repository, then from the project folder in PowerShell:
   ```powershell
   git init
   git add .
   git commit -m "LLM Lens"
   git branch -M main
   git remote add origin https://github.com/YOUR_NAME/llm-lens.git
   git push -u origin main
   ```
   Check that `.env` is not in the repository (it is git-ignored).
2. **Database (Neon).** Sign up at neon.com (no card), create a project, copy the connection string
   (`postgresql://...?sslmode=require`). Paste it as-is; the app converts it for the async driver.
3. **Web service (Render).** Sign up at render.com, choose New > Blueprint, connect the GitHub repo. Render reads
   `render.yaml`. When prompted, paste the Neon string as `DATABASE_URL`. `SECRET_KEY` is generated for you.
4. Wait for the build (several minutes). Open the `https://<name>.onrender.com` URL. `/api/health` should show
   `"database": "ok"` and `"mock_mode": true`.

## Known free-tier behavior
- Render free web services sleep after about 15 minutes idle; the first visit afterwards takes roughly a minute.
- Neon suspends compute after 5 idle minutes and wakes in well under a second.
- If a Neon monthly limit is hit, compute suspends until next month.
- Free-tier container RAM is small (512 MB at the time of writing), which is why the public image has no torch.

## Production checklist
- [ ] `SECRET_KEY` set (the app refuses to start in production with the placeholder)
- [ ] `DATABASE_URL` set in the Render dashboard, not in Git
- [ ] `PUBLIC_DEMO_MODE=true`, `MODEL_PROVIDER=mock`
- [ ] `/api/health` reports database ok
- [ ] No `.env` or secrets in the repository
- [ ] Limitations: in-memory rate limiter is per-process; no auth until Phase 6

## Alternatives considered (Oct 2026)
Hugging Face Docker Spaces, Koyeb and Fly.io no longer offer card-free free container hosting; Supabase free
projects pause after a week idle; Render's own free Postgres expires after 30 days. See the research notes in the
project chat for sources.
