# Route Consolidation Plan

This plan is intentionally non-destructive.

The current app has overlapping patient-facing routes that work today, but should be consolidated only after the Python test environment is usable again.

## Keep As Primary

- `/`
- `/order-medicines`
- `/orders`
- `/my-health`
- `/telemedicine/book`
- `/patient/order/{order_id}/status`
- `/api/prescription/analyze-upload`
- `/api/prescription/history`
- `/api/medicines/search`

## Redirects Already In Place

- `/medicines` redirects to `/order-medicines`

## Duplicate Or Overlapping Areas

- Order tracking:
  `/orders`
  `/orders/tracking/{order_id}`
  `/order-status/{order_id}`
  `/api/orders/{order_id}/track`
  `/api/orders/check/{order_id}`

- Prescription upload:
  `/api/prescription/analyze`
  `/api/prescription/analyze-upload`
  `/api/prescription/upload`
  `/scan-prescription/`

- Patient medicine browsing:
  `/order-medicines`
  `/patient/medicines`
  `/api/medicines/search`

- Portal and dashboard language:
  `/portal/patient`
  `/dashboard`
  several admin and EMR dashboards

## Safe Cleanup Order

1. Add tests for the primary patient flow routes.
2. Move all patient entry links to the primary routes only.
3. Add redirects from old HTML routes where needed.
4. Mark duplicate JSON endpoints as deprecated in code comments.
5. Remove dead routes only after tests pass and usage is checked.

## Do Not Remove Yet

- `/orders/tracking/{order_id}`
  It is still referenced by admin and pharmacy flows.

- `/order-status/{order_id}`
  It is still used as a public fulfillment-style status endpoint.

- `/api/prescription/upload`
  It may still support older superapp code.

- `/patient/medicines`
  It may still feed other patient tools.
