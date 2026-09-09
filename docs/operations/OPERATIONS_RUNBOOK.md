# Kash AI Operations Runbook

This runbook keeps day-to-day operation systematic. It is intentionally practical: protect the order flow, keep secrets safe, and make failures easy to diagnose.

## Operating Principles
- Do not mix risky backend route changes with UI-only polish in the same release.
- Keep order, payment, auth, and database changes small and separately tested.
- Treat `.env` as private. Update `.env.example` when configuration requirements change.
- Prefer improving frontend UX around stable APIs before changing backend contracts.
- Log and investigate failed order, AI, pharmacy lookup, and payment events.

## Standard Release Flow
1. Pull the latest code and review `git status`.
2. Make the smallest scoped change that solves the current user problem.
3. Run the QA checklist in `QA_CHECKLIST.md`.
4. Review the diff and confirm no secrets or unrelated files were changed.
5. Commit with a clear message.
6. Deploy.
7. Smoke test production:
   - `/healthz`
   - `/order-medicines`
   - `/api/ai/status`
   - `/api/admin/metrics`
   - one test order flow if safe for the environment

## Priority Levels
- Critical: app startup, auth, database connection, order creation, payment verification.
- Important: AI suggestions, pharmacy lookup, dashboard, admin metrics, patient notifications.
- Nice-to-have: copy polish, animations, non-blocking visual refinements.

## Incident Triage
1. Check whether the app starts and `/healthz` works.
2. Check logs for traceback or security events.
3. Reproduce the broken route locally with the same environment flags.
4. If order or payment is affected, pause deployments and avoid unrelated changes.
5. Fix the smallest failing path first.
6. Re-run the relevant QA checklist section before reopening the flow.

## Direct Medicine Ordering Watchpoints
- `/patient/medicines` must return available catalog items.
- `/order-medicines/ai-suggest` must fail gracefully when AI is unavailable.
- `/patient/nearby-pharmacies` must show a user-facing error if Google Maps or location fails.
- `/patient/order/create` must receive `patient_name`, `patient_phone`, `patient_address`, `medicines_json`, `pharmacy_id`, and CSRF token.
- The frontend must not invent new checkout routes unless the backend is intentionally changed.

## Observability Events
These events are written to `logs/analytics.jsonl` with `timestamp`, `event`, and `details`.

- `search_performed`
- `ai_used`
- `ai_add_all_clicked`
- `medicine_added_to_cart`
- `cart_opened`
- `checkout_started`
- `payment_attempted`
- `payment_success`
- `payment_failed`
- `order_created`
- `error_logged`

## Funnel
Watch the basic direct-order funnel in admin analytics:

- Search: `search_performed`
- Cart: `medicine_added_to_cart`
- Checkout: `checkout_started`
- Payment: `payment_success`

Use the drop-off:

- Search without cart usually means discovery or catalog relevance is weak.
- Cart without checkout usually means price, trust, or form friction is weak.
- Checkout without payment usually means payment trust or payment reliability needs attention.

## Structured Errors
Use `error_logged` for operational failures. Include:

- `error_type`
- `route`
- `message`
- optional order, payment, or total metadata

Required failure types:

- `ai_failure`
- `pharmacy_lookup_failure`
- `order_creation_failure`
- `payment_verification_failure`

## Weekly Maintenance
- Review failed order/payment logs.
- Review admin metrics for traffic and errors.
- Confirm backups are running.
- Confirm `.env.example` matches required configuration.
- Run the test suite and record failures before changing code.
