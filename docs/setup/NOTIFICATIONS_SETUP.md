# Notifications Setup

Kash AI now supports:

- Gmail SMTP for email delivery
- Fast2SMS or MSG91 for SMS delivery

## Environment Variables

Email:

- `SENDER_EMAIL`
- `SENDER_PASSWORD`
- `SMTP_HOST` (optional, defaults to Gmail)
- `SMTP_PORT` (optional, defaults to `587`)

SMS:

- `SMS_PROVIDER` (`fast2sms` or `msg91`, optional)
- `FAST2SMS_API_KEY`
- `FAST2SMS_SENDER_ID`
- `MSG91_AUTH_KEY`
- `MSG91_SENDER_ID`
- `MSG91_ROUTE`

Support details used in patient messages:

- `SUPPORT_PHONE`
- `SUPPORT_EMAIL`

## Notes

- Gmail should use an App Password, not a normal mailbox password.
- If both Fast2SMS and MSG91 are configured, the app will use the preferred provider in `SMS_PROVIDER` first and fall back to the other one.
- Prescription sharing now uses email plus SMS instead of the older Twilio-specific send path.
