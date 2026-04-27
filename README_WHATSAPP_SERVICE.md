# WhatsApp Prescription Notification Service

This Node.js service sends prescription notifications and medication reminders over WhatsApp using Twilio, answers patient replies with Google Gemini, stores local development data in SQLite, and schedules reminders with Redis/BullMQ.

## Setup

1. Install dependencies:

```bash
npm install
```

2. Add environment variables to `.env`:

```env
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
TWILIO_PRESCRIPTION_CONTENT_SID=
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-flash
REDIS_URL=redis://localhost:6379
SQLITE_DB_PATH=./data/whatsapp_notifications.sqlite
PORT=3000
```

3. Start Redis locally.

4. Start the API:

```bash
npm run dev
```

5. Start the reminder worker in another terminal:

```bash
npm run worker
```

## Endpoints

- `GET /health` checks API, SQLite, and Redis.
- `POST /patients` creates a patient.
- `POST /prescriptions` creates a prescription, sends WhatsApp notification, and schedules reminders.
- `GET /patients/:id/prescriptions` lists prescriptions for a patient.
- `POST /webhook/whatsapp` receives Twilio WhatsApp replies and sends Gemini-powered responses.

## Example Requests

Create patient:

```bash
curl -X POST http://localhost:3000/patients \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"Ravi Kumar\",\"phone\":\"+919999999999\",\"medicalConditions\":\"Diabetes\"}"
```

Create prescription:

```bash
curl -X POST http://localhost:3000/prescriptions \
  -H "Content-Type: application/json" \
  -d "{\"patientId\":1,\"medicineName\":\"Metformin\",\"dosage\":\"500mg\",\"frequency\":\"Twice daily\",\"duration\":\"30 days\",\"doctorName\":\"Sharma\",\"schedule\":[\"morning\",\"night\"]}"
```

## Twilio Webhook

Configure your Twilio WhatsApp sandbox or sender webhook to:

```text
POST https://your-domain.com/webhook/whatsapp
```

## Database Swap Notes

The app isolates database access in `src/models`. To move from SQLite to PostgreSQL later, replace `src/models/database.js` and model query implementations while keeping controllers and services stable.
