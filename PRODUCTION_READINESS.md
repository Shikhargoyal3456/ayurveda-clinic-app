# Kash AI — Production Readiness Report

**Date:** 2026-08-22  ·  **Scope:** Full integrity audit, professional polish, run/deploy readiness, and key-journey tracing for the Kash AI FastAPI + Jinja platform.

---

## Executive summary

The application is in strong shape and behaves like a maturely-engineered product: every Python module compiles, every template parses, all statically-referenced templates and assets resolve, and the four core user journeys are wired end to end. This pass verified those properties across the whole codebase, fixed a small number of real issues (a broken startup command in the README, an off-brand error page and favicon, and missing social/SEO metadata on the public surface), and added the one piece of documentation that was missing (a concise quick-start).

One hard constraint shaped the method: the app cannot be executed in this environment (FastAPI, SQLAlchemy, and Pydantic aren't installed and package installs are blocked), so all verification here is **static** — bytecode compilation, Jinja parsing, reference resolution, and route/template wiring. Running the app locally and clicking through the portals remains the recommended final gate before launch, and is quick to do with the new `RUN.md`.

| Area | Result |
|---|---|
| Python compilation (325 files) | ✅ All compile clean |
| Template syntax (187 templates) | ✅ All parse clean |
| Referenced templates exist | ✅ All reachable ones resolve |
| Static assets resolve | ✅ All 36+ references + base CSS/JS present |
| Core user journeys wired | ✅ Login, consult, AI doctor, orders |
| Branded 404/500 pages | ✅ Re-themed to the botanical brand |
| Favicon / OG / social meta | ✅ Added across public + portal surfaces |
| Run & deploy docs | ✅ Verified; `RUN.md` added; README fixed |
| Live runtime smoke test | ⚠️ Not possible in this sandbox — do locally |

---

## Integrity audit

**Python.** All 325 Python files across the application packages (`app`, `routers`, `routes`, `services`, `models`, `shared`, `apps`, `core`, `middleware`, `utils`), the top-level scripts, the test suite, and the `scripts/` directory compile to bytecode without syntax errors. A full import/startup test wasn't possible because the web-framework dependencies aren't installed here; that check is covered by the local run in `RUN.md`.

**Templates.** All 187 Jinja templates — across `templates/`, `templates_v2/`, `shared/templates/`, and the five `apps/*/templates/` directories — parse cleanly with the i18n, `do`, and loop-control extensions enabled. Of the 127 distinct template names referenced from Python, every runtime-reachable one resolves. The four `portals/*/dashboard.html` references resolve through the multi-directory loader in `shared/template_engine.py`, which spans all the app template folders.

**Static assets.** Every `url_for('static', …)` reference resolves to a real file, and all CSS and JavaScript loaded by the base templates (which load on every page) are present. Three static mounts are configured: `/static`, `/shared-static`, and `/public`.

**User journeys.** All four primary flows are wired route → template → write-endpoint: login/signup (`/auth/login`, `/auth/signup` render `auth/login.html` and `auth/signup.html`), booking a consultation (`/telemedicine/book` renders `telemedicine/guest_book.html`, backed by `/api/telemedicine/create-session`), the AI doctor (`/new/ai-doctor` renders `new_ai_doctor.html`, backed by the AI analysis endpoints), and ordering medicines (`/order-medicines` renders `order_medicines.html`, backed by a full order lifecycle: checkout, create, verify, confirm, dispatch, deliver).

---

## Fixes and additions in this pass

The 404/500 **error page** was already wired into the exception handlers but was styled in an orange scheme that clashed with the brand and pulled a video from an external CDN that the Content-Security-Policy blocks. It has been rebuilt in the botanical palette with the Fraunces display face and a CSS-only dosha orb, so it renders beautifully and is fully self-contained (only Google Fonts, which the app already loads). Its navigation links were verified against real routes.

The **favicon** still used the old cold-teal colours; it has been re-themed to the botanical identity — an ink field with a verdant leaf and a turmeric pulse-line and node.

The public **`/new` surface had no social or SEO metadata** at all, which matters because it's the page people share. It now carries a description, theme-colour, favicon link, Open Graph tags, and a Twitter summary-large-image card. The portal base template's existing Open Graph tags were rounded out with `og:type`, a Twitter card, and a theme colour. Both point at a newly generated **1200×630 branded social card** (`static/images/kash-ai-og.png`) rendered in the brand palette with the dosha orb, wordmark, and Nadi pulse motif.

The **README's production start command was wrong** — it read `uvicorn main:app`, but there is no top-level `main` module; the ASGI entrypoint is `app.main:app`. Left as-is it would fail with `ModuleNotFoundError` on deploy. It's corrected to the Gunicorn production command, and the vague "run migrations, if any" step now names the actual command (`alembic upgrade head`). A concise **`RUN.md`** quick-start was added covering local development, production, Docker, configuration, health endpoints, and tests — complementing the existing detailed `DEPLOYMENT.md` and `OPERATIONS_RUNBOOK.md` rather than duplicating them.

---

## Notes and recommended final checks

Before launch, run the app locally with the steps in `RUN.md` and click through the portals — this is the one check the sandbox can't perform and it will confirm the runtime import graph and template rendering end to end.

A couple of low-priority housekeeping items are worth a look. `routers/v2.py` defines an admin "accuracy dashboard" route that references a template which doesn't exist in `templates_v2/`, but the router is never imported or mounted anywhere, so it's dead code — either wire it up with its template or remove the file. Separately, `diagnostic_report.txt` at the repo root is a stale March diagnostic dump that embeds a local machine path and probably shouldn't ship in the repo; `err.tmp` (empty) is likewise leftover scratch. These are safe to delete manually whenever convenient.

The design system carries one deliberate, easily-reversible choice: headings across the portals use Fraunces via `--font-heading`. If the small headings in dense dashboards ever feel too heavy, it's a one-line change in `shared/static/css/variables.css`.
