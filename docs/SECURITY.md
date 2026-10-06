# Security model

## Accounts and sessions
- Email + password. Passwords are hashed with scrypt (N=16384, r=8, p=1, random 16-byte salt, standard library); they are
  never stored or logged in clear text. Minimum length 10.
- Login returns a signed HS256 JWT access token (default lifetime 12 h) in the response body; clients send it as
  `Authorization: Bearer <token>`. The server signs with `SECRET_KEY`; unsigned (`alg: none`), wrongly signed, expired
  and wrong-type tokens are rejected. There is no refresh token: expiry means sign in again.
- The same message is returned for an unknown email and a wrong password, and an unknown email still pays the hashing
  cost, so neither the response nor its timing reveals which accounts exist.
- Production refuses to start unless `SECRET_KEY` is at least 32 characters and not a placeholder.
- The browser stores the token in `localStorage`. That is simple and works for CLI/API clients too, but any cross-site
  scripting bug would expose it; React escapes output and the app injects no raw HTML. A cookie-based session is the
  alternative if the threat model changes.

## Authorization
- Experiments are private to their owner by default for signed-in users; owners may make them public (read-only to others).
- Experiments created without an account belong to the shared demo sandbox: visible to everyone, runnable by anyone,
  never "public" owned data. Deployments can disable anonymous writes (`ALLOW_ANONYMOUS_WRITES=false`).
- Visibility is enforced in one place (`backend/app/services/access.py`) and applied to every endpoint that exposes data
  derived from an experiment: lists, details, metrics, evidence, analysis, failures, explanations, lineage, dashboard
  counts, fingerprints, comparisons, model experiment counts and clusters. Hidden experiments answer 404 (not 403) so their
  existence is not revealed.
- Clusters are scoped: shared clusters are built only from experiments everyone can see; a signed-in user's own clustering
  is stored as theirs. Un-publishing an experiment removes it from shared clusters immediately.
- Anyone who can see an experiment may clone it; the clone is theirs and private (visibility is never inherited).

## Abuse limits (public demo mode)
Per-IP write limit, per-IP login/register limit (always on), maximum runs per experiment, maximum experiments per user and
in total, maximum accounts, maximum concurrent experiments, per-run timeout. The limiter is in-memory and per process:
correct for one free-tier container, not for several replicas (use Redis then).

## Other
Security headers, CORS allow-list, request validation (Pydantic), no secrets in the frontend or the repository, `.env`
ignored by Git. Database passwords belong in the host's environment settings only.

## Transport and browser hardening
- Content-Security-Policy on the app's pages (`script-src 'self'`, no inline script, `frame-ancestors 'none'`, `object-src 'none'`);
  the API's Swagger page is exempt because it loads a CDN script.
- Strict-Transport-Security in production; `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`.
- Request bodies over 1 MB are refused with 413, whether declared in Content-Length or streamed.
- Log lines are scrubbed of bearer tokens, passwords, API keys and database URL passwords before any handler sees them.
- Production refuses to start with a weak `SECRET_KEY` or a wildcard `CORS_ORIGINS`.
- Search input treats `%` and `_` as literal characters; all queries are parameterised.
- CSV exports neutralise formula cells; reports escape HTML in model output; the Markdown viewer renders React elements only.

## Dependency audit (October 2026)
`pip-audit` on `requirements.txt`: no known vulnerabilities. `npm audit --omit=dev`: 0 after upgrading `react-router-dom` to
the patched 7.x. `npm audit` still lists advisories in development tooling (the Vite dev server, Vitest and related
packages). They affect only a developer running the dev server or tests, and none of that code is in the production image
(the Docker build ships the compiled bundle only). Re-run both audits before each release; CI does.

## Not covered (known gaps)
Email verification, password reset, account deletion, two-factor authentication, audit logging, per-account (rather than
per-IP) rate limits, and token revocation before expiry.
