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

## Not covered (known gaps)
Email verification, password reset, account deletion, two-factor authentication, audit logging, per-account (rather than
per-IP) rate limits, and token revocation before expiry.
