# MyOdyssey.ai PWA Deployment Checklist

This checklist is for production HTTPS releases of the MyOdyssey.ai frontend and FastAPI backend. It assumes the service worker remains restricted to static PWA assets and navigation fallback only.

## Required Environment

Frontend:

- `NEXT_PUBLIC_API_URL`: HTTPS URL for the deployed FastAPI backend, for example `https://api.myodyssey.example`.
- Build: `npm run build`
- Start: `npm run start`

Backend:

- `JWT_SECRET_KEY`: secure production secret. Never reuse the example value.
- `BACKEND_CORS_ORIGINS`: comma-separated HTTPS frontend origins, for example `https://myodyssey.example,https://www.myodyssey.example`.
- `SQLITE_DATABASE_PATH`: optional path to a persistent SQLite database file on the deployment host.
- `DATABASE_URL`: optional full SQLAlchemy database URL. Use this instead of `SQLITE_DATABASE_PATH` when the host provides a database URL. Neon-style `postgresql://...?...sslmode=require` URLs are accepted and normalized internally to the installed `psycopg` driver.
- `GEMINI_API_KEY`: backend-only Gemini key when AI generation is enabled.
- Optional model overrides: `GEMINI_COURSE_PLAN_MODEL`, `GEMINI_LESSON_PRIMARY_MODEL`, `GEMINI_LESSON_FALLBACK_MODEL`.
- Start command depends on host, for example `uvicorn main:app --host 0.0.0.0 --port 8001` from `backend/`.

The frontend must not use a `localhost` API URL in production. The backend must not allow broad wildcard CORS with credentials.

## Staging Deployment Configuration

No provider-specific deployment manifest is required by the application code. If the repository does not include a host-specific file such as `render.yaml`, `fly.toml`, `vercel.json`, a Dockerfile, or a CI/CD workflow, choose an existing staging host for the project and configure it through that provider's dashboard or CLI.

Backend staging service:

- Runtime: Python matching the backend dependency set.
- Install command: `pip install -r requirements.txt` from `backend/`.
- Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT` when the host provides `PORT`, or the provider's equivalent.
- Required variables: `JWT_SECRET_KEY`, `BACKEND_CORS_ORIGINS`, and either a persistent `SQLITE_DATABASE_PATH` or `DATABASE_URL`.
- Optional variables: `GEMINI_API_KEY`, `GEMINI_COURSE_PLAN_MODEL`, `GEMINI_LESSON_PRIMARY_MODEL`, `GEMINI_LESSON_FALLBACK_MODEL`.
- Health check: `GET /health` should return `{"status":"healthy"}`.

Frontend staging service:

- Runtime: Node compatible with Next.js 16.
- Install command: `npm ci` from `frontend/`.
- Build command: `npm run build`.
- Start command: `npm run start -- --port $PORT` when the host provides `PORT`, or the provider's equivalent.
- Required variable: `NEXT_PUBLIC_API_URL`, set to the HTTPS backend staging URL.

The backend CORS origin must be the exact HTTPS frontend staging origin. Do not use wildcard CORS with credentials.

## Database and Schema Updates

On backend startup, `Base.metadata.create_all(bind=engine)` and `apply_sqlite_schema_updates(engine)` run from the app lifespan. Before release, back up the production SQLite database. Run the new backend version once against staging and confirm startup completes without schema errors.

The default local database path remains `backend/literacy_learning.db`. For staging, point `SQLITE_DATABASE_PATH` at a mounted persistent disk or set `DATABASE_URL` to the host-provided persistent database URL. Ephemeral SQLite storage is not production-safe because users, XP, generated lessons, and sync idempotency records can be lost during restarts.

For Neon PostgreSQL, use the pooled or direct connection string supplied by Neon with `sslmode=require`. Run the backend once against an empty staging database and verify `/health`, registration, login, profile retrieval, one lesson/puzzle flow, and one `/sync/offline-actions` idempotency retry before connecting the staging frontend.

Do not run destructive IndexedDB migrations during rollback or release cleanup. Pending offline actions must remain device-local until synchronized or explicitly cleared by the user.

## Service Worker Release Rules

- Current static cache: `myodyssey-pwa-static-v2`.
- Cache prefix for cleanup: `myodyssey-pwa-`.
- Precached files: `/offline.html`, `/manifest.webmanifest`, `/icons/icon-192.png`, `/icons/icon-512.png`, `/apple-icon.png`.
- Fetch strategy: same-origin `GET` navigation requests only, network-first, `/offline.html` fallback.
- Do not cache authenticated API responses, lessons, quizzes, games, mutations, or user pages in the service worker.
- Increment the service-worker static cache version when changing precached static PWA assets.
- Do not change the cache version on every runtime request.

Development builds unregister this app's own `/sw.js` registration and remove caches beginning with `myodyssey-pwa-`. They must not remove unrelated service workers or caches.

## Release Sequence

1. Run frontend offline, PWA, and learning tests.
2. Run backend offline-sync, puzzle, quiz/progress, and XP tests.
3. Run `npm run lint`.
4. Run `npx tsc --noEmit`.
5. Run `npm run build`.
6. Update `frontend/public/sw.js` cache version only when cached static PWA files changed.
7. Deploy backend.
8. Confirm safe database schema updates complete.
9. Deploy frontend with `NEXT_PUBLIC_API_URL` set to the HTTPS backend.
10. Verify `/manifest.webmanifest`, `/sw.js`, and `/offline.html` over HTTPS.
11. Install on Android Chrome and confirm launch starts at `/login`.
12. Test one downloaded lesson and one offline activity.
13. Reconnect and confirm exactly one sync, backend-confirmed XP, and refreshed dashboard progress.
14. Verify the update notice with a second harmless service-worker change.

## Route Smoke Tests

Refresh and direct navigation must work for:

- `/login`
- `/dashboard`
- `/downloads`
- `/lessons/[lessonId]`
- `/generated-lessons/[lessonPlanId]`
- `/puzzles`
- `/read-and-match`
- `/sentence-steps`
- `/sound-builder`
- `/offline.html`

Use the hosting platform's normal Next.js deployment mode. Do not add rewrites that bypass Next.js App Router routing.

Command-line smoke checks after deployment:

```bash
curl -fsS https://<staging-backend>/health
curl -I https://<staging-frontend>/login
curl -I https://<staging-frontend>/manifest.webmanifest
curl -I https://<staging-frontend>/sw.js
curl -I https://<staging-frontend>/offline.html
```

Use valid staging IDs for dynamic routes:

```bash
curl -I https://<staging-frontend>/lessons/<valid-id>
curl -I https://<staging-frontend>/generated-lessons/<valid-id>
```

## Installation QA

Android Chrome or desktop Chrome/Edge:

- Visit the production HTTPS URL.
- Confirm install prompt appears only when eligible.
- Install and launch.
- Confirm app opens at `/login`.
- Confirm install option is hidden when already standalone.
- Confirm update notice appears only after a real service-worker update with an existing controller.

iOS Safari:

- Confirm manual Add to Home Screen guidance is visible.
- Add to Home Screen through the Share menu.
- Launch from the home screen.
- Confirm basic navigation and downloaded content access.

## Offline Learning QA

While online:

- Download a course lesson.
- Download a generated lesson with quiz.
- Download Jumbled Word, Matching, Read and Match, Sentence Steps, and Sound Builder.
- Open `/downloads` and confirm counts, cached dates, remove actions, and storage summary.

Then go offline:

- Open each downloaded item.
- Complete one generated quiz.
- Mark one lesson complete.
- Complete one attempt for each downloaded game.
- Confirm provisional results are labeled pending synchronization.
- Confirm TTS failure does not block gameplay.
- Confirm non-downloaded content shows a friendly missing-download message.

Reconnect:

- Confirm pending actions sync once.
- Confirm backend-confirmed score, XP, progress, and streak values.
- Confirm replay does not duplicate XP where existing rules prohibit it.
- Confirm failed permanent actions remain manageable in `/downloads`.

## Error QA

- Network failure during sync returns actions to pending.
- `401` or `403` during sync preserves actions and asks for sign-in.
- Duplicate sync request does not duplicate attempts.
- Storage quota failure shows a friendly storage warning.
- IndexedDB unavailable does not break online learning.
- Legacy or corrupted cached records are not loaded as playable and can be cleaned up.
- Removing downloaded content does not delete pending attempts.
- Normal logout preserves offline data and warns when unsynced actions exist.
- Clear offline data removes only the current authenticated user's records.

## Security and Privacy

- JWTs and passwords must not be stored in IndexedDB.
- Offline records are scoped by backend `user_id`.
- Sync uses the authenticated backend user as authority, not the local `user_id` in a queued action.
- User B must not see or sync User A's retained downloaded content or actions through normal UI.
- Backend scoring, XP, progress, and streaks remain authoritative.
- IndexedDB is device-local browser storage and is not application-encrypted. Anyone with access to the same unlocked browser profile may inspect it with developer tools.

## Lighthouse

Run Lighthouse against the production HTTPS frontend after deployment:

1. Open Chrome DevTools.
2. Use Lighthouse with Progressive Web App, Performance, Accessibility, Best Practices, and SEO categories.
3. Confirm no installability blockers, invalid manifest fields, missing icons, mixed-content requests, service-worker registration failures, or offline fallback failures.
4. Do not chase a perfect performance score with risky unrelated changes.

If CLI Lighthouse is available, run it against the deployed HTTPS URL. Do not use local HTTP results as proof of installability.

CLI example:

```bash
npx lighthouse https://<staging-frontend>/login --view --preset=desktop
```

For installability, also run a mobile-form-factor audit in Chrome DevTools against the HTTPS staging origin.

## Rollback

- Roll back backend first only if the previous frontend remains compatible with queued event types.
- Unknown offline event types are rejected per event and do not break the entire batch.
- Roll back frontend by deploying the previous build; the service-worker update flow should activate the previous `/sw.js`.
- Do not clear IndexedDB during rollback.
- Pending offline actions should remain until the compatible backend/frontend is restored or the user explicitly clears offline data.
- Watch for repeated update/reload loops after rollback; if observed, clear only this app's service worker and `myodyssey-pwa-` caches during support.

## Known Limitations

- Offline STT, Background Sync, push notifications, browser-storage encryption, and initial-assessment offline mode are not implemented.
- Browser TTS voices vary by device and language.
- iOS does not support the Chromium `beforeinstallprompt` flow.
- Browser storage persistence is best-effort and may be denied by the browser.
