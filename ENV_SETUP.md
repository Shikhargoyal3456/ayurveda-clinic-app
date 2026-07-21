# Environment Setup Guide

## 1. Create Your `.env`

1. Copy `.env.example` to `.env`
2. Replace placeholder values with real credentials
3. Keep `.env` out of git

## 2. Sarvam AI

1. Sign up at Sarvam AI.
2. Open the developer/API section.
3. Generate an API key for speech-to-text access.
4. Set:
   - `SARVAM_API_KEY`
   - `SARVAM_SPEECH_TO_TEXT_URL=https://api.sarvam.ai/speech-to-text`
5. The app uses model `saarika:v2` and defaults to `hi-IN`.

## 3. Gmail App Password

1. Use a Gmail account dedicated to clinic sending.
2. Turn on Google 2-Step Verification.
3. Open Google Account settings.
4. Search for `App Passwords`.
5. Create a new app password for Mail.
6. Copy the generated 16-character password.
7. Set:
   - `GMAIL_USER=your_clinic_gmail@gmail.com`
   - `GMAIL_APP_PASSWORD=your_16_character_app_password`

Screenshot flow to follow:

- Google Account home
- Security tab
- 2-Step Verification enabled
- App Passwords page
- Generated password dialog copied into `.env`

## 4. Vertex AI / Gemini

1. Create a Google Cloud project.
2. Enable billing.
3. Enable Vertex AI APIs.
4. Set the project and region variables:
   - `VERTEX_AI_PROJECT`
   - `GOOGLE_CLOUD_PROJECT`
   - `VERTEX_AI_LOCATION`
5. Ensure the runtime environment has access to the project credentials expected by your deployment target.

## 5. Optional Integrations

- `GROQ_API_KEY`: optional AI fallback
- `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`: payments
- `WHATSAPP_*`: future or sidecar WhatsApp flows
- `TWILIO_*`: messaging/OTP style workflows if used

## 6. Branding and Clinic Settings

Set these for investor demos and clinic rollout:

- `CLINIC_NAME`
- `DOCTOR_NAME`
- `DOCTOR_LANGUAGE`
- `CLINIC_ADDRESS`
- `SUPPORT_EMAIL`
- `SUPPORT_PHONE`

## 7. Security Settings

Review these before production:

- `SECRET_KEY`
- `SESSION_HTTPS_ONLY`
- `HTTPS_REDIRECT_ENABLED`
- `RATE_LIMIT_ENABLED`
- `API_IP_RATE_LIMIT_REQUESTS`
- `API_USER_RATE_LIMIT_REQUESTS`

## 8. Production Database

For real deployments, set:

- `DATABASE_URL=postgresql+psycopg2://...`

SQLite is acceptable for local development but not recommended for production clinic usage.
