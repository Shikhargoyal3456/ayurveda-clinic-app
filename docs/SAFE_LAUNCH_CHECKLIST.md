# Safe Launch Checklist

This checklist is focused on reducing launch risk without changing core business logic.

## Before Launch

- Confirm the home page loads fast on a phone.
- Confirm medicine search works as a guest.
- Confirm prescription upload works as a guest.
- Confirm order placement shows a clear success message.
- Confirm tracking shows the latest order after redirect.
- Confirm help is visible on every patient screen.
- Confirm buttons are easy to tap on a small screen.
- Confirm text is readable without zooming.
- Confirm common errors use plain language.

## Manual Flows To Test

1. Home -> Search -> Add to cart -> Place Order
2. Home -> Upload Prescription -> Add all to cart -> Place Order
3. Home -> Track Orders
4. Home -> Refill Last Order
5. My Health -> Set Reminder
6. My Health -> Consult Doctor -> Start Consultation

## Failure Cases To Test

- No internet during medicine search
- No internet during prescription upload
- No internet during order placement
- Empty cart checkout attempt
- Bad phone number entry
- Missing address entry
- Missing order in tracking

## Accessibility Checks

- Keyboard can reach main actions
- Help sheet opens and closes with keyboard
- Important status text is announced clearly
- Inputs have labels
- Color is not the only status signal

## Launch Safety Rules

- Do not remove duplicate routes until tests are runnable
- Do not rewrite payment flow without test coverage
- Do not rewrite delivery tracking without test coverage
- Prefer redirects and documentation over deletions
- Ship patient-flow improvements in small batches
