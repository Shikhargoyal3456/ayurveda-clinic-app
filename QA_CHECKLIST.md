# Kash AI QA Checklist

Use this checklist before every deploy or major demo. Keep the pass small, repeatable, and focused on the flows that can hurt users if they fail.

## Pre-Flight
- Confirm `.env` exists locally and real secrets are not committed.
- Run `verify_environment.py`.
- Run `powershell -ExecutionPolicy Bypass -File scripts\run_tests.ps1`.
- Start the app locally.
- Open `/healthz` and confirm it returns healthy.
- Open `/api/ai/status` and confirm the expected AI mode is active.

## Auth And Dashboard
- Sign in with a known test doctor account.
- Confirm the dashboard loads without console errors.
- Confirm protected pages redirect to login after sign out.

## Direct Medicine Ordering
- Open `/order-medicines`.
- Confirm medicines load from `/patient/medicines`.
- Search for a known medicine and confirm cards filter immediately.
- Search for an unknown medicine and confirm the no-results message appears.
- Add a medicine to cart and confirm the cart count, total, and toast update.
- Increase and decrease quantity and confirm total updates.
- Clear cart and confirm the empty state appears.
- Expand AI Assistant, request suggestions, and confirm loading and fallback states are readable.
- Use "Add All to Cart" and confirm the cart scroll/highlight feedback works.
- Find nearby pharmacies if location is available.
- Select a pharmacy card and confirm the card highlights and button disables.
- Attempt checkout with an incomplete form and confirm validation blocks it.
- Complete the form with a test phone and address and confirm order creation reaches the existing order status link.

## Payment And Order Status
- Open the created order status page.
- Confirm Razorpay/payment messaging is visible.
- Confirm failed or missing payment verification shows a clear error.
- Confirm no duplicate orders were created during one checkout attempt.

## Admin And Reliability
- Open `/api/admin/metrics`.
- Check `logs/security_audit.jsonl` for unexpected security events.
- Check `logs/analytics.jsonl` for order creation events.
- Check `logs/analytics.jsonl` for `search_performed`, `medicine_added_to_cart`, `checkout_started`, and `order_created`.
- Force one safe frontend/API failure and confirm `error_logged` records `error_type`, `route`, and `message`.
- Confirm no new traceback was written during the QA pass.

## Release Decision
- Ship only if order creation, payment status, login, and health checks pass.
- Hold the release if payment, auth, database, or order creation shows any regression.
