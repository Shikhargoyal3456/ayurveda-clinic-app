# Semgrep Security Checkpoint

## Verification

- `semgrep` was not available on PATH, so scanner re-run could not be performed locally.
- `python -m compileall app routers services scripts alembic apps verify_environment.py` passed.
- `node --check src/app.js` passed.
- `node --check src/utils/ayurvedic_vocabulary.js` passed.
- Focused pytest for profiles/subscriptions/WhatsApp: 1 failed, 3 passed. The remaining failure is a redirect expectation mismatch: login returns `/patient/dashboard`, while the test expects `/patient` or `/profiles/add`.
- Full pytest: 63 failed, 53 passed, 1 skipped, 41 errors.

## Pass 1 Status

Mechanical fixes have been applied for SQL injection, path traversal, pickle-to-JSON metadata, SRI, CSRF templates/Express middleware, Docker hardening, dynamic regex escaping, NaN guard, non-literal import allowlist, nginx header consolidation, and inline template-string interpolation.

Additional verification/fixes from the follow-up prompts:

- The global CSRF middleware now validates `X-CSRF-Token` against the session token without reading form bodies in middleware.
- Password hashing now defaults to the already-configured `pbkdf2_sha256` scheme to avoid the installed `passlib 1.7.4` and `bcrypt 5.0.0` incompatibility.
- Existing bcrypt and pbkdf2 hashes are still accepted by `verify_password`.

## docs.pkl to JSON

- The new metadata file is `docs.json`.
- The loader serializes document content and metadata as JSON primitives.
- Existing `docs.pkl` files are not deserialized for safety. The current migration behavior is fail-safe rebuild: if `docs.json` is absent and `docs.pkl` exists, the app logs that the legacy pickle cannot be loaded safely and rebuilds from source documents.
- If a deployed environment needs preservation of pickle-only metadata, perform an offline one-time conversion in a controlled trusted environment, then deploy only `docs.json`.

## Pass 2 Inputs Still Required

Do not guess these values before fixing.

- Redirect allowlists: confirm valid internal redirect paths/domains for any Semgrep `tainted-redirect-fastapi` findings, including room URLs and WhatsApp/external redirects if flagged.
- SSRF allowlists: provide legitimate outbound domains for image URL fetching, delivery provider APIs, supplier APIs, webhook/monitoring URLs, geocoding, medicine APIs, WhatsApp/SMS/Telegram providers, Ollama/RAG endpoints, and AI fallback endpoints if those were flagged.
- Express CORS: provide the trusted browser origins allowed to call `src/app.js`.
- Direct HTML responses: confirm which raw `HTMLResponse` call sites intentionally render HTML and which should be converted to Jinja2 templates.
- ReDoS review: approve rewritten fixed/escaped regex patterns for any remaining stdlib regex findings.
- Credential logging: approve what should remain logged versus redacted for secret rotation and OAuth/token-adjacent exception logs.
- ReplaceAll sanitization: approve adding DOMPurify/sanitize-html or switching to DOM text APIs at the flagged client-side sanitizer.
- JSF autoescape disabled: no local `escape=false` or `autoescape=False` call site was found in the current tree.
- Mutable GitHub action tags: fixed by pinning official action tag SHAs.

Pinned action SHAs:

- `actions/checkout@v4` -> `11d5960a326750d5838078e36cf38b85af677262`
- `actions/setup-python@v5` -> `a26af69be951a213d495a4c3e4e4022e16d87065`

## Pass 3 Authorization Plan

Existing auth mechanisms observed:

- Legacy doctor session: session cookies store doctor identity and session metadata; `get_current_doctor` validates session state.
- Portal session: `create_portal_session`, `get_portal_user`, and role checks gate patient, pharmacy, lab, delivery, doctor, and admin portals.
- CSRF: `ensure_csrf_token`, `verify_csrf`, and global API CSRF middleware protect state-changing cookie-authenticated requests.

Recommended authorization groups:

- Patients/cases/prescriptions: require current doctor or portal patient, then filter by doctor ownership or linked patient profile/user. Owner field is unclear for some guest/order-token flows.
- Orders/pharmacy: require pharmacy owner/admin or patient portal user; filter orders through store ownership or patient account/profile. Confirm owner field for phone-only orders.
- Lab: require lab owner/admin; filter lab stores by owner and reports by linked lab/order. Confirm report ownership fields.
- Telemedicine: require doctor or patient portal user; filter sessions by doctor id or linked patient user/profile. Confirm public preview/session-token model.
- Subscriptions: doctor subscriptions should filter by doctor/user id; patient medicine subscriptions should require portal patient ownership unless explicitly public/admin.
- Admin: require admin role for admin routers and keep CSRF on unsafe routes.
- Webhooks: fail closed with unconditional signature verification when secrets/signatures are missing.

Allowed Pass 3 exceptions already applied:

- Added existing CSRF protection to profile state-changing endpoints and matching templates.
- Made OpenWA and Razorpay webhook verification fail closed when required secrets/signatures are missing.
