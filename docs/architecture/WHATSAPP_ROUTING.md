# WhatsApp Routing

This project uses two separate WhatsApp delivery stacks:

## Twilio WhatsApp (Node service)

Used for:
- Outbound prescription notifications
- Outbound reminder messages
- Inbound Twilio WhatsApp webhook handling
- Prescription image replies and AI-driven WhatsApp responses

Primary files:
- `src/config.js`
- `src/services/twilioService.js`
- `src/controllers/prescriptionController.js`
- `src/controllers/webhookController.js`
- `src/routes/webhookRoutes.js`
- `src/queues/reminderWorker.js`

Environment variables required by the Node/Twilio stack:
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_WHATSAPP_NUMBER`
- `TWILIO_PRESCRIPTION_CONTENT_SID`
- `NODE_ENV`
- `PORT`

## Meta WhatsApp Cloud API (Python app)

Used for:
- Python-side patient and pharmacy WhatsApp sends
- App-level WhatsApp health reporting
- Fallback to `wa.me` links when Meta delivery is disabled or unavailable

Primary files:
- `app/config.py`
- `services/whatsapp.py`
- `services/communication.py`

Environment variables required by the Python/Meta stack:
- `WHATSAPP_ACCESS_TOKEN`
- `WHATSAPP_PHONE_NUMBER_ID`
- `WHATSAPP_API_VERSION`
- `WHATSAPP_TEMPLATE_NAME`
- `WHATSAPP_TEMPLATE_LANGUAGE_CODE`
- `ENABLE_WHATSAPP_API`

## Python to Node bridge

The Python app can hand prescription sends to the Node/Twilio service through:
- `NODE_WHATSAPP_SERVICE_URL`

Bridge file:
- `services/node_whatsapp.py`

That bridge posts prescription payloads to the Node service `/prescriptions` endpoint so the Twilio WhatsApp workflow remains centralized in the Node stack.
