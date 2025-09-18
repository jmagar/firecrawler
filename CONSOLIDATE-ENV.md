# Environment Consolidation Plan

This document captures the agreed work to converge the Firecrawl stack on a single
source of truth for environment configuration at the project root (`./.env`).

## 1. Current State
- **Root `.env`** – consumed by Docker Compose and the Node services. Provides queue, Redis,
  vector search, and scraper configuration. Actively referenced in `docker-compose.yaml`
  and throughout `apps/api` and `apps/playwright-service-ts`.
- **`apps/firecrawler/.env`** – primarily documentation defaults for the MCP server.
  Only a handful of variables are actually read in code (`FIRECRAWL_API_URL`,
  `FIRECRAWLER_TRANSPORT`, `FIRECRAWLER_HOST`, `FIRECRAWLER_PORT`, retry settings).
- A repo-wide scan surfaced ~180 distinct environment keys; many have no declared defaults.
  Only the keys listed in `./.env` today are guaranteed to be available when running via
  Compose.

## 2. Problems Identified
- **Split authority** – developers must maintain two files that drift independently.
- **Secret leakage risk** – the committed root `.env` currently contains a real
  `OPENAI_API_KEY`.
- **Stale MCP options** – many `FIRECRAWLER_*` entries are documented but unused in code.
- **Trailing whitespace / formatting issues** – e.g., `REDIS_RATE_LIMIT_URL` carries a trailing
  space that can break equality checks.

## 3. Target End State
- Root `.env` is the canonical configuration file. All services (Docker, API, MCP) read from it.
- Sensitive values live in an untracked `.env.local` (or similar), with `./.env.example`
  providing sanitized defaults for onboarding.
- MCP server optionally supports an override file (e.g., `apps/firecrawler/.env.local`) but
  no longer depends on `apps/firecrawler/.env`.
- Documentation reflects the single-file workflow.
- Automation (script or CI) flags future environment keys that lack defaults/examples.

## 4. Migration Tasks
1. **Inventory variables**
   - Freeze the list of keys currently used in code (Python + TypeScript) and classify them by
     owning service. Re-use the extraction script from the initial analysis.

2. **Refine canonical files**
   - Move non-secret defaults from `apps/firecrawler/.env` into root `./.env`, grouped by
     subsystem (API, MCP, vector search, monitoring).
   - Strip real secrets from tracked files. Add/update `./.env.example` with safe placeholders.
   - Normalize formatting (no trailing whitespace, consistent comments, alphabetical blocks).

3. **Update loaders**
   - Adjust `apps/firecrawler/firecrawl_mcp/server.py` and any other Python entry points to
     load the root `.env` (e.g., `load_dotenv(find_dotenv())`). Allow optional local overrides.
   - Ensure Node services continue to load `./.env` via `dotenv` or Compose.

4. **Deprecate duplicate file**
   - Replace `apps/firecrawler/.env` with a short README or remove it entirely once the MCP
     loader change is in place.
   - Keep `apps/firecrawler/.env.example` as a reference, but sync content with the root
     example file to avoid drift.

5. **Documentation sweep**
   - Update onboarding guides (`apps/firecrawler/README.md`,
     `apps/firecrawler/docs/MCP_SERVER.md`, root `README.md`) to reference the unified env.
   - Document override patterns (e.g., `.env.local`) for contributors.

6. **Add guardrails**
   - Introduce a script or CI check that compares variables referenced in code with those
     defined in the canonical env/example files. Fail the check if new keys are missing.

## 5. Rollout Checklist
- [ ] Root `.env` updated, sanitized, and committed alongside `.env.example`.
- [ ] MCP loader reads root `.env` and (optionally) an override file.
- [ ] Redundant `apps/firecrawler/.env` removed or replaced with documentation.
- [ ] Docs refreshed to point to the single source of truth.
- [ ] Verification: run Docker Compose + MCP server using only the root `.env`.
- [ ] Optional automation in place to detect future drift.

## 6. Open Questions
- Should we enforce overrides via `.env.local` or allow service-specific extensions?
- Do we need per-environment (dev/stage/prod) variants, or is a single `.env` + overrides
  sufficient?
- Which CI job (if any) should host the env-drift check?

Decisions on these questions will determine how strict to make the automation in section 6.
